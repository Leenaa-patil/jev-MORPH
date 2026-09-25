import os
import re
import sys
import json
import time
import base64
import subprocess
from pathlib import Path
from email.mime.text import MIMEText

import httpx
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ============================================================
# PLATFORM GUARD
# ============================================================
# This project drives the Windows UI (pywinauto / win32gui).


if sys.platform != "win32":
    print(
        "ERROR: jev-MORPH controls the Windows desktop UI and "
        "only runs on Windows (pywinauto / win32gui are "
        "required)."
    )
    sys.exit(1)

from pywinauto import Desktop
from pywinauto.keyboard import send_keys
import win32gui


# ============================================================
# CONFIG
# ============================================================

APP_NAME = "jev-MORPH"

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

JEV_MODEL = "typesafe/jev-1.13"
PARAM_MODEL = "openai/gpt-4o-mini"

MAX_STEPS = 15
MAX_EMAIL_SENDS = 1

BASE_DIR = Path(__file__).resolve().parent

ENV_FILE = BASE_DIR / ".env"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

load_dotenv(ENV_FILE)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[A-Za-z]{2,}$")


# ============================================================
# AVAILABLE ACTIONS
# ============================================================

ACTIONS = [
    "open_app",
    "type_text",
    "search",
    "calculate",
    "wait",
    "send_email",
    "send_message",
    "done",
]

# Which parameters are required for an action to be considered
# valid before we try to execute it.
REQUIRED_PARAMS = {
    "open_app": ["app"],
    "type_text": ["text"],
    "search": ["query"],
    "calculate": ["expression"],
    "wait": [],
    "send_email": ["recipient", "body"],
    "send_message": ["recipient", "message"],
    "done": [],
}

# Apps we actually know how to open + focus. Keeping this an
# explicit whitelist (instead of shelling out to whatever
# string the model produces) is the main safety fix here.
APP_COMMANDS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "brave": [
        "brave.exe",
        r"C:\Program Files\BraveSoftware"
        r"\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware"
        r"\Brave-Browser\Application\brave.exe",
    ],
}

# Window-title regex to focus after opening / before typing
# into a given app.
APP_WINDOW_PATTERNS = {
    "notepad": r".*Notepad.*",
    "calculator": r".*Calculator.*",
    "calc": r".*Calculator.*",
    "brave": r".*Brave.*",
}


# ============================================================
# GMAIL
# ============================================================

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def print_header(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def clean_json_text(text):
    """
    Removes markdown code fences if the model returns:

    ```json
    {...}
    ```
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text)
        text = text.strip()

    return text


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# pywinauto's send_keys() treats these characters as special
# (modifiers like Shift/Ctrl/Alt, or grouping) rather than
# literal text. Escaping them with {X} makes send_keys type
# them as-is. Without this, e.g. "10 + 1" silently drops the
# "+" and becomes "101".
_SEND_KEYS_SPECIAL = "+^%~(){}"


def escape_send_keys(text):
    return "".join(
        f"{{{ch}}}" if ch in _SEND_KEYS_SPECIAL else ch
        for ch in text
    )


# ============================================================
# OBSERVATION
# ============================================================

def observe():
    """
    Minimal observation: just the foreground window title.
    We intentionally do NOT enumerate the entire UI tree.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()

        if not hwnd:
            return {"active_window": ""}

        title = win32gui.GetWindowText(hwnd).strip()

        return {"active_window": title}

    except Exception as error:
        return {
            "active_window": "",
            "observation_error": str(error),
        }


# ============================================================
# WINDOW / FOCUS HELPERS
# ============================================================

def focus_window(title_re, timeout=3):
    """
    Find a window by title regex and bring it to the
    foreground. Returns True only if the foreground window
    actually matches afterwards.

    Uses desktop.windows() (plural) rather than desktop.window()
    because Brave/Chrome-style apps commonly have more than one
    top-level element matching a loose title regex (e.g. a
    hidden helper window, or a leftover window from a previous
    run). desktop.window() raises ElementAmbiguousError in that
    case; desktop.windows() just returns a list we can filter.
    """
    try:
        desktop = Desktop(backend="uia")
        deadline = time.time() + timeout
        window = None

        while time.time() < deadline:
            matches = desktop.windows(
                title_re=title_re,
                visible_only=True,
                enabled_only=True,
            )

            if matches:
                # Prefer the topmost (most recently active) match.
                window = matches[0]
                break

            time.sleep(0.2)

        if window is None:
            print(f"\nWindow not found: {title_re}")
            return False

        window.set_focus()
        time.sleep(0.5)

        state = observe()
        active_title = state.get("active_window", "")

        matched = bool(re.match(title_re, active_title))

        print(
            f"Focused window: {active_title}"
            f" ({'confirmed' if matched else 'NOT confirmed'})"
        )

        return matched

    except Exception as error:
        print("\nFOCUS ERROR")
        print(error)
        return False


def focus_app_window(app):
    """Focus the window for a known app key, if we have a
    pattern for it."""
    pattern = APP_WINDOW_PATTERNS.get(app)

    if not pattern:
        # Unknown app - nothing specific to focus on, so just
        # trust whatever launched most recently.
        return True

    return focus_window(pattern)


def focus_current_window():
    """
    Re-assert focus on whatever the current foreground window
    is. No UI-tree inspection.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()

        if not hwnd:
            return False

        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)

        return True

    except Exception as error:
        print("\nFOCUS ERROR")
        print(error)
        return False


# ============================================================
# JEV DECISION
# ============================================================

def ask_morph(task, action_history, state):
    """
    Jev chooses ONLY the next action. Parameters are extracted
    separately (see extract_parameters).
    """
    if not OPENROUTER_API_KEY:
        print("\nERROR: OPENROUTER_API_KEY missing.")
        return None

    state_payload = {
        "task": task,
        "action_history": action_history,
        "current_state": state,
        "available_actions": ACTIONS,
    }

    payload = {
        "model": JEV_MODEL,
        "state": state_payload,
        "questions": {
            "next_action": {
                "type": "choice",
                "instructions": (
                    "Choose the single best next action "
                    "for the user's task. "
                    "Use the action history and current state. "
                    "Choose done only when the user's task "
                    "is actually complete."
                ),
                "criteria": {
                    "open_app": "Open a desktop application.",
                    "type_text": (
                        "Type text into the currently "
                        "focused application."
                    ),
                    "search": "Perform a web search in a browser.",
                    "calculate": (
                        "Perform a calculation using "
                        "Windows Calculator."
                    ),
                    "wait": (
                        "Wait briefly for an application "
                        "or operation."
                    ),
                    "send_email": (
                        "Send an email using the "
                        "configured Gmail account."
                    ),
                    "send_message": "Send a WhatsApp message.",
                    "done": "The user's requested task is complete.",
                },
            }
        },
    }

    try:
        response = httpx.post(
            DECISIONS_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        answer = data.get("answers", {}).get("next_action", {})

        action = answer.get("choice")
        confidence = safe_float(answer.get("confidence", 0))
        probabilities = answer.get("probabilities", {}) or {}

        if action not in ACTIONS:
            print("\nINVALID ACTION FROM JEV")
            print(action)
            return None

        print(f"\nAction: {action}")
        print(f"Confidence: {confidence:.2f}")

        if probabilities:
            print(f"Probabilities: {probabilities}")

        return {
            "action": action,
            "confidence": confidence,
            "probabilities": probabilities,
        }

    except httpx.HTTPError as error:
        print("\nJEV NETWORK ERROR")
        print(error)
        return None

    except Exception as error:
        print("\nJEV ERROR")
        print(error)
        return None


# ============================================================
# PARAMETER EXTRACTION
# ============================================================

def extract_parameters(task, action, action_history, state):
    """
    Extract parameters using a normal generative model.
    No regex-based parameter extraction.
    """
    if not OPENROUTER_API_KEY:
        print("\nERROR: OPENROUTER_API_KEY missing.")
        return {}

    parameter_schema = {
        "open_app": {"app": "string"},
        "type_text": {"text": "string"},
        "search": {"query": "string"},
        "calculate": {"expression": "string"},
        "wait": {"seconds": "number"},
        "send_email": {
            "recipient": "string",
            "subject": "string",
            "body": "string",
        },
        "send_message": {
            "recipient": "string",
            "message": "string",
        },
        "done": {},
    }

    schema = parameter_schema.get(action, {})

    prompt = f"""
You are the parameter extractor for a Windows desktop agent.

The planner has already selected this action:

ACTION:
{action}

USER TASK:
{task}

ACTION HISTORY:
{json.dumps(action_history, indent=2)}

CURRENT STATE:
{json.dumps(state, indent=2)}

Return ONLY valid JSON.

The JSON must contain exactly the parameters needed
for this action.

Required parameter shape:

{json.dumps(schema, indent=2)}

Rules:

- Extract information from the complete user task.
- Use action history to understand what already happened.
- Do not invent missing information.
- For open_app, use a simple application name such as
  "notepad", "calculator", or "brave".
- For type_text, return the exact text that should be typed.
- For search, return only the search query.
- For calculate, return only the mathematical expression.
- For wait, use a reasonable number of seconds.
- For send_email, preserve the intended recipient,
  subject, and body.
- For send_message, preserve the intended recipient
  and message.
- For done, return an empty object.

JSON ONLY.
"""

    payload = {
        "model": PARAM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    try:
        response = httpx.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        content = clean_json_text(content)
        parameters = json.loads(content)

        if not isinstance(parameters, dict):
            print("\nPARAMETER ERROR: expected JSON object.")
            return {}

        return parameters

    except json.JSONDecodeError as error:
        print("\nPARAMETER JSON ERROR")
        print(error)
        return {}

    except httpx.HTTPError as error:
        print("\nPARAMETER NETWORK ERROR")
        print(error)
        return {}

    except Exception as error:
        print("\nPARAMETER EXTRACTION ERROR")
        print(error)
        return {}


def validate_parameters(action, parameters):
    """
    Confirm every required field for this action is present
    and non-empty. Returns (is_valid, error_message).
    """
    required = REQUIRED_PARAMS.get(action, [])

    for field in required:
        value = parameters.get(field)

        if value is None:
            return False, f"Missing required field: {field}"

        if isinstance(value, str) and not value.strip():
            return False, f"Empty required field: {field}"

    if action == "send_email":
        recipient = str(parameters.get("recipient", "")).strip()

        if not EMAIL_RE.match(recipient):
            return False, f"Not a valid email address: {recipient!r}"

    if action == "open_app":
        app = str(parameters.get("app", "")).strip().lower()

        if app not in APP_COMMANDS:
            return False, f"Unsupported application: {app!r}"

    return True, ""


# ============================================================
# DUPLICATE STEP PROTECTION
# ============================================================

def is_duplicate_step(action_history, action, parameters):
    """
    Prevent only an immediate exact repeat of a successful step.
    Same action + same parameters immediately again = blocked.
    Different parameters = allowed.
    """
    if not action_history:
        return False

    last = action_history[-1]

    return (
        last.get("action") == action
        and last.get("parameters") == parameters
        and last.get("status") == "success"
    )


# ============================================================
# OPEN APP
# ============================================================

def execute_open_app(parameters):
    app = str(parameters.get("app", "")).strip().lower()

    if not app:
        return {"status": "failed", "result": "Application name missing."}

    command = APP_COMMANDS.get(app)

    if not command:
        return {
            "status": "failed",
            "result": f"Unsupported application: {app}",
        }

    try:
        launched = False

        for executable in command:
            try:
                subprocess.Popen([executable])
                launched = True
                break
            except (FileNotFoundError, OSError):
                continue

        if not launched:
            return {"status": "failed", "result": f"Could not find {app}."}

        # Give Windows time to create the window.
        time.sleep(1)

        if not focus_app_window(app):
            return {
                "status": "failed",
                "result": f"{app} launched but its window could not be "
                "confirmed as focused.",
            }

        state = observe()

        return {
            "status": "success",
            "result": f"{app} opened and focused.",
            "state": state,
        }

    except Exception as error:
        return {"status": "failed", "result": str(error)}


# ============================================================
# TYPE TEXT
# ============================================================

def execute_type_text(parameters):
    text = parameters.get("text")

    if text is None:
        return {"status": "failed", "result": "Text missing."}

    try:
        state = observe()
        print(f"Typing into: {state.get('active_window', '')}")

        if not focus_current_window():
            return {
                "status": "failed",
                "result": "Could not focus active window.",
            }

        send_keys(escape_send_keys(str(text)), with_spaces=True)
        time.sleep(0.3)

        return {"status": "success", "result": f"Typed text: {text}"}

    except Exception as error:
        return {"status": "failed", "result": str(error)}


# ============================================================
# SEARCH
# ============================================================

def execute_search(parameters):
    query = str(parameters.get("query", "")).strip()

    if not query:
        return {"status": "failed", "result": "Search query missing."}

    # A search needs an actual browser window. If Brave isn't
    # already the foreground window, open/focus it first
    # instead of blindly typing into whatever has focus.
    state = observe()
    active = state.get("active_window", "")

    if not re.match(APP_WINDOW_PATTERNS["brave"], active):
        open_result = execute_open_app({"app": "brave"})

        if open_result.get("status") != "success":
            return {
                "status": "failed",
                "result": f"Could not open browser for search: "
                f"{open_result.get('result')}",
            }

    if not focus_window(APP_WINDOW_PATTERNS["brave"]):
        return {"status": "failed", "result": "Could not focus browser."}

    try:
        send_keys("^l")
        time.sleep(0.2)
        send_keys(escape_send_keys(query), with_spaces=True)
        send_keys("{ENTER}")
        time.sleep(1)

        return {"status": "success", "result": f"Searched for: {query}"}

    except Exception as error:
        return {"status": "failed", "result": str(error)}


# ============================================================
# CALCULATOR
# ============================================================

def execute_calculate(parameters):
    expression = str(parameters.get("expression", "")).strip()

    if not expression:
        return {
            "status": "failed",
            "result": "Calculation expression missing.",
        }

    print(f"\nCALCULATOR INPUT: {expression}")

    # Make sure Calculator is actually open before trying to
    # focus it (fixes the case where the model asks to
    # calculate without an open_app step first).
    state = observe()
    active = state.get("active_window", "")

    if not re.match(APP_WINDOW_PATTERNS["calculator"], active):
        open_result = execute_open_app({"app": "calculator"})

        if open_result.get("status") != "success":
            return {
                "status": "failed",
                "result": f"Could not open Calculator: "
                f"{open_result.get('result')}",
            }

    if not focus_window(APP_WINDOW_PATTERNS["calculator"]):
        return {
            "status": "failed",
            "result": "Could not focus Windows Calculator.",
        }

    try:
        send_keys("^a")
        time.sleep(0.2)

        send_keys(escape_send_keys(expression), with_spaces=True)
        time.sleep(0.3)

        send_keys("{ENTER}")
        time.sleep(0.8)

        state = observe()
        print(f"Calculator window: {state.get('active_window', '')}")

        return {
            "status": "success",
            "result": f"Calculator evaluated: {expression}",
        }

    except Exception as error:
        return {"status": "failed", "result": str(error)}


# ============================================================
# WAIT
# ============================================================

def execute_wait(parameters):
    try:
        seconds = safe_float(parameters.get("seconds", 1), default=1.0)
        seconds = max(0.1, min(seconds, 10))

        time.sleep(seconds)

        return {"status": "success", "result": f"Waited {seconds:.1f} seconds."}

    except Exception as error:
        return {"status": "failed", "result": str(error)}


# ============================================================
# GMAIL AUTH
# ============================================================

def get_gmail_service():
    credentials = None

    try:
        if TOKEN_FILE.exists():
            credentials = Credentials.from_authorized_user_file(
                TOKEN_FILE, GMAIL_SCOPES
            )

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            if not CREDENTIALS_FILE.exists():
                print("\nERROR: credentials.json not found.")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), GMAIL_SCOPES
            )

            credentials = flow.run_local_server(port=0)

            TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

            try:
                os.chmod(TOKEN_FILE, 0o600)
            except OSError:
                pass

        return build("gmail", "v1", credentials=credentials)

    except Exception as error:
        print("\nGMAIL AUTH ERROR")
        print(error)
        return None


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(recipient, subject, body):
    try:
        if not recipient:
            print("\nERROR: Email recipient missing.")
            return False

        if not body:
            print("\nERROR: Email body missing.")
            return False

        print_header("EMAIL PREVIEW")
        print(f"To:      {recipient}")
        print(f"Subject: {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60)

        answer = input("\nSend this? [y/N]: ").strip().lower()

        if answer not in {"y", "yes"}:
            print("\nCancelled.")
            return False

        gmail = get_gmail_service()

        if gmail is None:
            return False

        message = MIMEText(body)
        message["to"] = recipient
        message["subject"] = subject

        encoded_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        result = (
            gmail.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )

        if result.get("id"):
            print("\nEmail sent successfully.")
            return True

        print("\nEmail send failed.")
        return False

    except Exception as error:
        print("\nEMAIL SEND ERROR")
        print(error)
        return False


# ============================================================
# EMAIL EXECUTOR
# ============================================================

def execute_send_email(parameters, email_send_count):
    if email_send_count >= MAX_EMAIL_SENDS:
        return (
            {"status": "failed", "result": "Email safety limit reached."},
            email_send_count,
        )

    recipient = str(parameters.get("recipient", "")).strip()
    subject = str(parameters.get("subject", "")).strip() or "Message from Jev"
    body = str(parameters.get("body", "")).strip()

    if not recipient:
        return (
            {"status": "failed", "result": "Email recipient missing."},
            email_send_count,
        )

    success = send_email(recipient, subject, body)

    if success:
        email_send_count += 1
        return (
            {"status": "success", "result": f"Email sent to {recipient}."},
            email_send_count,
        )

    return (
        {"status": "cancelled", "result": "Email was not sent."},
        email_send_count,
    )


# ============================================================
# WHATSAPP (not implemented)
# ============================================================

def execute_send_message(parameters):
    print("\nWhatsApp sending is not connected yet.")
    print("Nothing was sent.")

    return {
        "status": "failed",
        "result": "WhatsApp integration is not connected yet.",
    }


# ============================================================
# EXECUTOR ROUTER
# ============================================================

def execute_action(action, parameters, email_send_count):
    if action == "open_app":
        return execute_open_app(parameters), email_send_count

    if action == "type_text":
        return execute_type_text(parameters), email_send_count

    if action == "search":
        return execute_search(parameters), email_send_count

    if action == "calculate":
        return execute_calculate(parameters), email_send_count

    if action == "wait":
        return execute_wait(parameters), email_send_count

    if action == "send_email":
        return execute_send_email(parameters, email_send_count)

    if action == "send_message":
        return execute_send_message(parameters), email_send_count

    if action == "done":
        return (
            {"status": "success", "result": "Task complete."},
            email_send_count,
        )

    return (
        {"status": "failed", "result": f"Unknown action: {action}"},
        email_send_count,
    )


# ============================================================
# MAIN AGENT LOOP
# ============================================================

def run_task(task):
    print_header(f"{APP_NAME} — NEW TASK")
    print(f"Task: {task}")

    action_history = []
    email_send_count = 0

    for step in range(1, MAX_STEPS + 1):
        print_header(f"STEP {step}")

        state = observe()
        print(f"Active window: {state.get('active_window', '')}")

        # 1. JEV DECIDES
        decision = ask_morph(task, action_history, state)

        if not decision:
            print("\nStopping safely.")
            return

        action = decision["action"]
        confidence = decision["confidence"]

        # 2. CONFIDENCE GUARD
        if confidence < 0.40:
            print("\nJev confidence too low.")
            print("Stopping safely.")
            return

        # 3. DONE
        if action == "done":
            print("\nJEV-MORPH: TASK COMPLETE.")
            return

        # 4. EXTRACT PARAMETERS
        parameters = extract_parameters(task, action, action_history, state)
        print(f"\nParameters: {parameters}")

        # 5. VALIDATE PARAMETERS
        is_valid, error_message = validate_parameters(action, parameters)

        if not is_valid:
            print(f"\nInvalid parameters: {error_message}")
            print("Stopping safely.")
            return

        # 6. DUPLICATE STEP PROTECTION
        if is_duplicate_step(action_history, action, parameters):
            print("\nDuplicate successful step detected.")
            print("Stopping safely.")
            return

        # 7. EXECUTE
        result, email_send_count = execute_action(
            action, parameters, email_send_count
        )

        status = result.get("status", "failed")
        result_text = result.get("result", "")

        print(f"\nACTION STATUS: {status}")
        print(f"RESULT: {result_text}")

        # 8. SAVE STRUCTURED HISTORY
        history_entry = {
            "step": step,
            "action": action,
            "parameters": parameters,
            "status": status,
            "result": result_text,
        }

        action_history.append(history_entry)

        # 9. FAILURE GUARD
        if status in {"failed", "cancelled"}:
            print("\nAction did not complete successfully.")
            print("Stopping safely.")
            return

        time.sleep(0.3)

    print("\nMaximum step limit reached.")
    print("Stopping safely.")


# ============================================================
# INTERACTIVE LOOP
# ============================================================

def main():
    print_header(f"{APP_NAME} STARTED")
    print("Type a task, or type 'exit' to quit.")

    while True:
        try:
            task = input("\nYou > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting.")
            break

        if not task:
            continue

        if task.lower() in {"exit", "quit"}:
            print(f"\n{APP_NAME} shutting down.")
            break

        run_task(task)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()