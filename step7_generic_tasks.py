import os
import re
import subprocess
import time

import httpx
from dotenv import load_dotenv
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# ============================================================
# SETUP
# ============================================================

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise RuntimeError("OPENROUTER_API_KEY is missing.")

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"


# ============================================================
# USER TASK
# ============================================================

task = input("\nWhat should I do?\n> ").strip()

if not task:
    raise RuntimeError("No task provided.")

print("\nUSER TASK:")
print(task)


# ============================================================
# ACTION HISTORY
# ============================================================

completed_actions = []


# ============================================================
# OBSERVE
# ============================================================

def observe():

    desktop = Desktop(backend="uia")

    windows = []

    for window in desktop.windows(visible_only=True):

        try:
            title = window.window_text().strip()

            if title:
                windows.append(title)

        except Exception:
            pass

    return {
        "visible_windows": windows,
        "completed_actions": completed_actions,
    }


# ============================================================
# ASK JEV
# ============================================================

def ask_jev(screen_state):

    payload = {
        "model": MODEL,

        "state": {
            "task": task,
            "screen": screen_state,
            "completed_actions": completed_actions,
        },

        "questions": {

            "next_action": {

                "type": "choice",

                "instructions": (
                    "Decide the next action needed to complete "
                    "the user's task. "
                    "Pay attention to completed_actions. "
                    "Do not repeat an action that has already "
                    "successfully completed its required step. "
                    "Choose done when the user's requested task "
                    "has been completed."
                ),

                "criteria": {

                    "open_app": (
                        "An application required by the task "
                        "still needs to be opened."
                    ),

                    "type_text": (
                        "Text required by the task still needs "
                        "to be typed."
                    ),

                    "done": (
                        "All required actions for the user's "
                        "task have already been completed."
                    ),
                },
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = httpx.post(
        JEV_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data["answers"]["next_action"]


# ============================================================
# FIND WINDOW
# ============================================================

def find_window(name):

    desktop = Desktop(backend="uia")

    for window in desktop.windows(visible_only=True):

        try:
            title = window.window_text()

            if name.lower() in title.lower():
                return window

        except Exception:
            pass

    return None


# ============================================================
# EXTRACT APP NAME
# ============================================================

def extract_app_name(user_task):

    patterns = [
        r"open\s+(.+?)(?:\s+and\s+|\s+then\s+|$)",
        r"launch\s+(.+?)(?:\s+and\s+|\s+then\s+|$)",
        r"start\s+(.+?)(?:\s+and\s+|\s+then\s+|$)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            user_task,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    return None


# ============================================================
# EXECUTE
# ============================================================

def execute(action):

    # --------------------------------------------------------
    # OPEN APP
    # --------------------------------------------------------

    if action == "open_app":

        app_name = extract_app_name(task)

        if not app_name:
            raise RuntimeError(
                "Could not determine which application to open."
            )

        print("\nEXECUTING: open_app")
        print("Application:", app_name)

        app_commands = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "chrome.exe",
            "brave": "brave.exe",
        }

        command = app_commands.get(
            app_name.lower()
        )

        if command is None:
            raise RuntimeError(
                f"I don't know how to launch '{app_name}' yet."
            )

        subprocess.Popen([command])

        print("Application opened.")

        return True


    # --------------------------------------------------------
    # TYPE TEXT
    # --------------------------------------------------------

    if action == "type_text":

        print("\nEXECUTING: type_text")

        match = re.search(
            r"type\s+(.+)$",
            task,
            re.IGNORECASE,
        )

        if not match:
            raise RuntimeError(
                "Could not determine what text to type."
            )

        text = match.group(1).strip()

        print("Text:", text)

        if "notepad" in task.lower():
            window = find_window("Notepad")
        else:
            window = None

        if window is None:
            raise RuntimeError(
                "Could not find the target application."
            )

        window.set_focus()

        time.sleep(0.5)

        send_keys("^a")

        time.sleep(0.2)

        send_keys(text)

        print("Text typed successfully.")

        return True


    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    if action == "done":

        print("\nTASK COMPLETE.")

        return True


    raise RuntimeError(
        f"Unknown action: {action}"
    )


# ============================================================
# AGENT LOOP
# ============================================================

print("\n================================")
print("       JEV DESKTOP AGENT")
print("================================")


for step in range(10):

    print(f"\n========== STEP {step + 1} ==========")

    # --------------------------------------------------------
    # OBSERVE
    # --------------------------------------------------------

    screen_state = observe()

    print("\nOBSERVED WINDOWS:")

    for window in screen_state["visible_windows"]:
        print("-", window)

    print("\nCOMPLETED ACTIONS:")

    for action in completed_actions:
        print("-", action)


    # --------------------------------------------------------
    # DECIDE
    # --------------------------------------------------------

    answer = ask_jev(screen_state)

    action = answer["choice"]
    confidence = answer["confidence"]

    print("\nJEV DECISION:")
    print("Action:", action)
    print("Confidence:", confidence)
    print("Probabilities:", answer["probabilities"])


    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    if action == "done":

        print("\n✅ JEV says the task is complete.")

        break


    # --------------------------------------------------------
    # ACT
    # --------------------------------------------------------

    success = execute(action)

    if success:

        completed_actions.append(action)

        print("\nACTION COMPLETED:", action)

    time.sleep(1)


else:

    print("\n⚠️ Maximum steps reached.")


print("\n================================")
print("          AGENT STOPPED")
print("================================")