import os
import re
import shutil
import subprocess
import time
import urllib.parse

import httpx
from dotenv import load_dotenv
from pywinauto.keyboard import send_keys


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"

# Safety: Jev must be reasonably confident before executing.
CONFIDENCE_THRESHOLD = 0.65


# ============================================================
# SAFE LOCAL STATE
# ============================================================

state = {
    "active_app": None,
    "last_action": None,
    "last_result": None,
    "completed_actions": [],
}


# ============================================================
# APP LOCATOR
# ============================================================

def find_app_command(app_name):
    app_name = app_name.lower().strip()

    commands = {
        "notepad": [
            "notepad.exe"
        ],

        "calculator": [
            "calc.exe"
        ],

        "calc": [
            "calc.exe"
        ],

        "brave": [
            "brave.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    }

    candidates = commands.get(app_name, [])

    for candidate in candidates:

        # Direct executable path
        if os.path.isfile(candidate):
            return candidate

        # Executable available through PATH
        found = shutil.which(candidate)

        if found:
            return found

    return None


# ============================================================
# PARAMETER EXTRACTION
# ============================================================

def extract_open_app(task):
    match = re.search(
        r"\b(?:open|launch|start)\s+"
        r"(notepad|calculator|calc|brave)\b",
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).lower()

    return None


def extract_search_query(task):
    patterns = [
        r"\bsearch(?:\s+(?:for|on))?\s+(.+)$",
        r"\bgoogle\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, task, re.IGNORECASE)

        if match:
            query = match.group(1).strip()

            # Remove common trailing task language
            query = re.sub(
                r"\s+(?:on|using)\s+(?:brave|chrome)$",
                "",
                query,
                flags=re.IGNORECASE,
            )

            return query

    return None


def extract_type_text(task):
    match = re.search(
        r"\btype\s+(.+?)(?:\s+in\s+(?:notepad|the app))?$",
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def extract_calculation(task):
    match = re.search(
        r"\bcalculate\s+(.+)$",
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


def extract_key(task):
    match = re.search(
        r"\bpress\s+(enter|escape|esc|tab|backspace|space)\b",
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).lower()

    return None


# ============================================================
# SAFE OBSERVATION
# ============================================================

def observe():
    """
    IMPORTANT:
    We intentionally DO NOT inspect the desktop.

    Jev only receives state produced by our own actions.
    """

    return {
        "active_app": state["active_app"],
        "last_action": state["last_action"],
        "last_result": state["last_result"],
        "completed_actions": state["completed_actions"][-5:],
    }


# ============================================================
# ASK JEV
# ============================================================

def ask_jev(task):

    observation = observe()

    prompt = f"""
You are Jev, a safe desktop action planner.

User task:
{task}

Safe state:
{observation}

Choose the NEXT action.

Available actions:

open_app
- Open an explicitly requested supported application.

search_web
- Search the web for an explicitly requested query.

type_text
- Type text when the user explicitly asks for typing.

calculate
- Perform a calculation the user explicitly requested.

press_key
- Press a keyboard key the user explicitly requested.

wait
- Wait briefly.

done
- Use this when the requested task is complete.

IMPORTANT SAFETY RULES:

- Do NOT inspect or scrape the desktop.
- Do NOT inspect arbitrary windows.
- Do NOT read account names.
- Do NOT read repository names.
- Do NOT read messages, emails, files, or webpage contents.
- Do NOT invent user intent.
- Only choose actions supported by the user's task.
- If the task is complete, choose done.
"""

    criteria = {
        "open_app": "Open an explicitly requested application.",
        "search_web": "Search for an explicitly requested web query.",
        "type_text": "Type text explicitly requested by the user.",
        "calculate": "Perform an explicitly requested calculation.",
        "press_key": "Press an explicitly requested keyboard key.",
        "wait": "Wait briefly before continuing.",
        "done": "The user's requested task is complete.",
    }

    payload = {
        "model": MODEL,
        "input": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "questions": {
            "next_action": {
                "type": "choice",
                "criteria": criteria,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    response = httpx.post(
        JEV_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    answer = data["answers"]["next_action"]

    return {
        "action": answer["choice"],
        "confidence": answer.get("confidence", 0),
        "probabilities": answer.get("probabilities", {}),
        "usage": data.get("usage", {}),
    }


# ============================================================
# EXECUTION
# ============================================================

def execute_action(action, task):

    print(f"\nExecuting: {action}")

    # --------------------------------------------------------
    # OPEN APP
    # --------------------------------------------------------

    if action == "open_app":

        app = extract_open_app(task)

        if not app:
            return False, "Could not determine which app to open."

        command = find_app_command(app)

        if not command:
            return False, f"Could not find application: {app}"

        try:
            subprocess.Popen([command])

            time.sleep(1)

            state["active_app"] = app
            state["last_action"] = "open_app"
            state["last_result"] = "success"

            state["completed_actions"].append(
                {
                    "action": "open_app",
                    "app": app,
                    "result": "success",
                }
            )

            return True, f"Opened {app}."

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------------
    # SEARCH WEB
    # --------------------------------------------------------

    if action == "search_web":

        query = extract_search_query(task)

        if not query:
            return False, "Could not determine search query."

        encoded_query = urllib.parse.quote_plus(query)

        url = f"https://www.google.com/search?q={encoded_query}"

        # If Brave exists, launch the URL directly.
        brave = find_app_command("brave")

        try:

            if brave:
                subprocess.Popen(
                    [brave, url]
                )

                state["active_app"] = "brave"

            else:
                # Fall back to the user's default browser.
                import webbrowser
                webbrowser.open(url)

            state["last_action"] = "search_web"
            state["last_result"] = "success"

            state["completed_actions"].append(
                {
                    "action": "search_web",
                    "query": query,
                    "result": "success",
                }
            )

            return True, f"Searched for: {query}"

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------------
    # TYPE TEXT
    # --------------------------------------------------------

    if action == "type_text":

        text = extract_type_text(task)

        if not text:
            return False, "Could not determine what text to type."

        try:

            send_keys(text, with_spaces=True)

            state["last_action"] = "type_text"
            state["last_result"] = "success"

            state["completed_actions"].append(
                {
                    "action": "type_text",
                    "result": "success",
                }
            )

            return True, "Text typed."

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------------
    # CALCULATE
    # --------------------------------------------------------

    if action == "calculate":

        expression = extract_calculation(task)

        if not expression:
            return False, "Could not determine calculation."

        try:

            calculator = find_app_command("calculator")

            if not calculator:
                return False, "Calculator was not found."

            subprocess.Popen([calculator])

            time.sleep(1)

            send_keys(expression, with_spaces=True)
            send_keys("{ENTER}")

            state["active_app"] = "calculator"
            state["last_action"] = "calculate"
            state["last_result"] = "success"

            state["completed_actions"].append(
                {
                    "action": "calculate",
                    "result": "success",
                }
            )

            return True, f"Calculated: {expression}"

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------------
    # PRESS KEY
    # --------------------------------------------------------

    if action == "press_key":

        key = extract_key(task)

        if not key:
            return False, "Could not determine key."

        key_map = {
            "enter": "{ENTER}",
            "escape": "{ESC}",
            "esc": "{ESC}",
            "tab": "{TAB}",
            "backspace": "{BACKSPACE}",
            "space": " ",
        }

        try:

            send_keys(key_map[key])

            state["last_action"] = "press_key"
            state["last_result"] = "success"

            state["completed_actions"].append(
                {
                    "action": "press_key",
                    "result": "success",
                }
            )

            return True, f"Pressed {key}."

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------------
    # WAIT
    # --------------------------------------------------------

    if action == "wait":

        time.sleep(1)

        state["last_action"] = "wait"
        state["last_result"] = "success"

        return True, "Waited."

    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    if action == "done":

        state["last_action"] = "done"
        state["last_result"] = "success"

        return True, "Task complete."

    return False, f"Unknown action: {action}"


# ============================================================
# RUN ONE TASK
# ============================================================

def run_task(task):

    print("\n" + "=" * 60)
    print(f"TASK: {task}")
    print("=" * 60)

    max_steps = 8

    for step in range(1, max_steps + 1):

        print(f"\n--- Step {step} ---")

        decision = ask_jev(task)

        action = decision["action"]
        confidence = decision["confidence"]

        print(f"Jev chose: {action}")
        print(f"Confidence: {confidence}")
        print(f"Probabilities: {decision['probabilities']}")

        # Safety gate
        if confidence < CONFIDENCE_THRESHOLD:

            print(
                f"\nJev confidence ({confidence:.2f}) is below "
                f"the safety threshold ({CONFIDENCE_THRESHOLD:.2f})."
            )

            print("Action skipped.")

            return

        if action == "done":

            print("\nJev: DONE")
            return

        success, message = execute_action(
            action,
            task,
        )

        print(f"Result: {message}")

        if not success:

            state["last_action"] = action
            state["last_result"] = "failed"

            print("\nAction failed.")
            return

    print("\nReached maximum agent steps.")


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not found in .env")
        return

    print("=" * 60)
    print("JEV SAFE DESKTOP AGENT")
    print("=" * 60)

    print("\nSupported examples:")
    print("  open notepad")
    print("  open brave")
    print("  open calculator")
    print("  open brave and search github")
    print("  search github")
    print("  open notepad and type hello")
    print("  open calculator and calculate 9+1")
    print("  press enter")
    print("\nType 'exit' to quit.")

    while True:

        try:
            task = input("\nYou > ").strip()

        except KeyboardInterrupt:
            print("\nExiting.")
            break

        if not task:
            continue

        if task.lower() in {
            "exit",
            "quit",
            "bye",
        }:
            print("Goodbye.")
            break

        run_task(task)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()