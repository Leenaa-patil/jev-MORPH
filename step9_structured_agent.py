import os
import re
import shutil
import subprocess
import time

import httpx
from dotenv import load_dotenv
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# ============================================================
# SETUP
# ============================================================

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise RuntimeError("OPENROUTER_API_KEY is missing.")

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"


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
        "visible_windows": windows
    }


# ============================================================
# ASK JEV
# ============================================================

def ask_jev(task, screen_state, completed_actions):

    payload = {
        "model": MODEL,

        "state": {
            "task": task,
            "screen": screen_state,
            "completed_actions": completed_actions,
        },

        "questions": {

            # ------------------------------------------------
            # NEXT ACTION
            # ------------------------------------------------

            "next_action": {

                "type": "choice",

                "instructions": (
                    "Choose the next action required to complete "
                    "the user's task. "
                    "Use the screen state and completed actions. "
                    "Do not repeat an action that has already "
                    "successfully completed its purpose. "
                    "Choose done when the task is complete."
                ),

                "criteria": {

                    "open_app": (
                        "Open an application required by the task."
                    ),

                    "search": (
                        "Search for something using an open browser."
                    ),

                    "type_text": (
                        "Type text into the currently focused application."
                    ),

                    "calculate": (
                        "Enter a mathematical expression into a calculator."
                    ),

                    "click": (
                        "Click a required UI element."
                    ),

                    "press_key": (
                        "Press a keyboard key required by the task."
                    ),

                    "wait": (
                        "Wait for an application or UI to become ready."
                    ),

                    "done": (
                        "The user's task is completely finished."
                    ),
                },
            },

            # ------------------------------------------------
            # ACTION PARAMETER READINESS
            # ------------------------------------------------

            "action_parameter": {

                "type": "score",

                "instructions": (
                    "How clearly does the user's task specify "
                    "the parameter required for the chosen action?"
                ),

                "criteria": [

                    "No parameter is specified.",

                    "Parameter is barely specified.",

                    "Parameter is partially specified.",

                    "Parameter is mostly clear.",

                    "Parameter is completely clear.",
                ],
            },
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

    return data["answers"]


# ============================================================
# FIND APPLICATION
# ============================================================

def find_app_command(app_name):

    app_name = app_name.lower().strip()

    app_commands = {

        "notepad": [
            "notepad.exe",
        ],

        "calculator": [
            "calc.exe",
        ],

        "calc": [
            "calc.exe",
        ],

        "chrome": [
            "chrome.exe",
        ],

        "brave": [
            "brave.exe",

            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",

            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    }

    candidates = app_commands.get(
        app_name,
        []
    )

    for command in candidates:

        # Full path exists
        if os.path.isfile(command):
            return command

        # Executable exists in PATH
        if shutil.which(command):
            return command

    return None


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
# EXTRACT ACTION PARAMETER
# ============================================================

def extract_parameter(action, task):

    # ========================================================
    # OPEN APP
    # ========================================================

    if action == "open_app":

        patterns = [

            r"open\s+(.+?)(?:\s+and\s+|\s+then\s+|$)",

            r"launch\s+(.+?)(?:\s+and\s+|\s+then\s+|$)",

            r"start\s+(.+?)(?:\s+and\s+|\s+then\s+|$)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                task,
                re.IGNORECASE,
            )

            if match:

                return {
                    "app": match.group(1).strip()
                }

        return {}


    # ========================================================
    # SEARCH
    # ========================================================

    if action == "search":

        match = re.search(
            r"search\s+(?:for\s+)?(.+)$",
            task,
            re.IGNORECASE,
        )

        if match:

            query = match.group(1).strip()

            # Remove later chained instructions
            query = re.split(
                r"\s+and\s+then\s+",
                query,
                flags=re.IGNORECASE,
            )[0]

            return {
                "query": query.strip()
            }

        return {}


    # ========================================================
    # TYPE TEXT
    # ========================================================

    if action == "type_text":

        match = re.search(
            r"type\s+(.+)$",
            task,
            re.IGNORECASE,
        )

        if match:

            return {
                "text": match.group(1).strip()
            }

        return {}


    # ========================================================
    # CALCULATE
    # ========================================================

    if action == "calculate":

        return extract_calculation(task)


    # ========================================================
    # PRESS KEY
    # ========================================================

    if action == "press_key":

        match = re.search(
            r"(?:press|hit)\s+(.+)$",
            task,
            re.IGNORECASE,
        )

        if match:

            return {
                "key": match.group(1).strip()
            }

        return {}


    return {}


# ============================================================
# EXTRACT CALCULATION
# ============================================================

def extract_calculation(task):

    match = re.search(
        r"(?:calculate|compute|solve)\s+(.+)$",
        task,
        re.IGNORECASE,
    )

    if match:

        expression = match.group(1).strip()

        # Remove chained instructions
        expression = re.split(
            r"\s+and\s+then\s+",
            expression,
            flags=re.IGNORECASE,
        )[0]

        return {
            "expression": expression.strip()
        }

    return {}


# ============================================================
# EXECUTE ACTION
# ============================================================

def execute(action, parameters):

    # ========================================================
    # OPEN APP
    # ========================================================

    if action == "open_app":

        app_name = parameters.get("app")

        if not app_name:

            raise RuntimeError(
                "No application was specified."
            )

        print("\nEXECUTING: open_app")
        print("Application:", app_name)

        command = find_app_command(app_name)

        if command is None:

            raise RuntimeError(
                f"Could not find '{app_name}' on this computer."
            )

        print("Launching:", command)

        subprocess.Popen([command])

        print("Application opened.")

        time.sleep(2)

        return True


    # ========================================================
    # SEARCH
    # ========================================================

    if action == "search":

        query = parameters.get("query")

        if not query:

            raise RuntimeError(
                "No search query was specified."
            )

        print("\nEXECUTING: search")
        print("Query:", query)

        brave = find_window("Brave")

        if brave is None:

            raise RuntimeError(
                "Brave browser was not found."
            )

        brave.set_focus()

        time.sleep(0.5)

        # Focus address bar
        send_keys("^l")

        time.sleep(0.2)

        # Type search query
        send_keys(query)

        time.sleep(0.2)

        # Execute search
        send_keys("{ENTER}")

        print("Search executed.")

        time.sleep(2)

        return True


    # ========================================================
    # TYPE TEXT
    # ========================================================

    if action == "type_text":

        text = parameters.get("text")

        if not text:

            raise RuntimeError(
                "No text was specified."
            )

        print("\nEXECUTING: type_text")
        print("Text:", text)

        send_keys(text)

        print("Text typed successfully.")

        return True


    # ========================================================
    # CALCULATE
    # ========================================================

    if action == "calculate":

        expression = parameters.get("expression")

        if not expression:

            raise RuntimeError(
                "No mathematical expression was specified."
            )

        print("\nEXECUTING: calculate")
        print("Expression:", expression)

        calculator = find_window("Calculator")

        if calculator is None:

            raise RuntimeError(
                "Calculator was not found."
            )

        calculator.set_focus()

        time.sleep(0.5)

        # Type expression
        send_keys(expression)

        time.sleep(0.2)

        # Press Enter
        send_keys("{ENTER}")

        print("Calculation executed.")

        time.sleep(1)

        return True


    # ========================================================
    # PRESS KEY
    # ========================================================

    if action == "press_key":

        key = parameters.get("key")

        if not key:

            raise RuntimeError(
                "No key was specified."
            )

        print("\nEXECUTING: press_key")
        print("Key:", key)

        send_keys(
            "{" + key.upper() + "}"
        )

        return True


    # ========================================================
    # WAIT
    # ========================================================

    if action == "wait":

        print("\nEXECUTING: wait")

        time.sleep(2)

        return True


    # ========================================================
    # CLICK
    # ========================================================

    if action == "click":

        raise RuntimeError(
            "Click execution is not implemented yet."
        )


    # ========================================================
    # DONE
    # ========================================================

    if action == "done":

        print("\nTASK COMPLETE.")

        return True


    raise RuntimeError(
        f"Unknown action: {action}"
    )


# ============================================================
# RUN ONE TASK
# ============================================================

def run_task(task):

    completed_actions = []

    print("\n================================")
    print("          NEW TASK")
    print("================================")

    print("\nTask:", task)

    for step in range(10):

        print(
            f"\n========== STEP {step + 1} =========="
        )

        # ----------------------------------------------------
        # OBSERVE
        # ----------------------------------------------------

        screen_state = observe()

        print("\nOBSERVED WINDOWS:")

        for window in screen_state["visible_windows"]:

            print("-", window)

        print("\nCOMPLETED ACTIONS:")

        if completed_actions:

            for item in completed_actions:

                print("-", item)

        else:

            print("- None")


        # ----------------------------------------------------
        # DECIDE
        # ----------------------------------------------------

        answers = ask_jev(
            task,
            screen_state,
            completed_actions,
        )

        action_answer = answers["next_action"]

        action = action_answer["choice"]

        confidence = action_answer["confidence"]

        print("\nJEV DECISION:")

        print(
            "Action:",
            action
        )

        print(
            "Confidence:",
            confidence
        )

        print(
            "Probabilities:",
            action_answer["probabilities"]
        )


        # ----------------------------------------------------
        # DONE
        # ----------------------------------------------------

        if action == "done":

            print("\n✅ TASK COMPLETE.")

            return


        # ----------------------------------------------------
        # GET PARAMETERS
        # ----------------------------------------------------

        parameters = extract_parameter(
            action,
            task,
        )

        print(
            "\nPARAMETERS:",
            parameters
        )


        # ----------------------------------------------------
        # EXECUTE
        # ----------------------------------------------------

        success = execute(
            action,
            parameters,
        )

        if success:

            completed_actions.append(
                action
            )

            print(
                "\nACTION COMPLETED:",
                action
            )

        time.sleep(1)


    print(
        "\n⚠️ Maximum steps reached."
    )


# ============================================================
# MAIN USER COMMAND LOOP
# ============================================================

print("\n========================================")
print("        JEV DESKTOP AGENT")
print("========================================")

print("\nType a task.")
print("Type 'exit' to quit.")

while True:

    print()

    task = input("You > ").strip()

    if not task:

        continue

    if task.lower() in [
        "exit",
        "quit",
    ]:

        print("\nGoodbye 👋")

        break

    try:

        run_task(task)

    except Exception as error:

        print("\n❌ ERROR:")
        print(error)

        print(
            "\nThe agent is still running. "
            "You can give it another task."
        )