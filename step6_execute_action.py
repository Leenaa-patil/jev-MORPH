import os
import subprocess
import time

import httpx
from dotenv import load_dotenv
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


# =========================
# SETUP
# =========================

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise RuntimeError("OPENROUTER_API_KEY is missing.")


# =========================
# 1. OBSERVE
# =========================

desktop = Desktop(backend="uia")

windows = []

for window in desktop.windows(visible_only=True):
    try:
        title = window.window_text().strip()

        if title:
            windows.append(title)

    except Exception:
        pass


screen_state = {
    "visible_windows": windows
}

print("\n=== OBSERVED STATE ===")

for window in windows:
    print("-", window)


# =========================
# 2. ASK JEV
# =========================

payload = {
    "model": "typesafe/jev-1.13",

    "state": {
        "task": "Make sure Notepad contains the text: Hello from Jev Agent.",
        "screen": screen_state,
    },

    "questions": {
        "next_action": {
            "type": "choice",

            "instructions": (
                "What should the computer do next "
                "to complete the task?"
            ),

            "criteria": {
                "open_notepad": (
                    "Open Notepad because it is not currently open."
                ),

                "type_message": (
                    "Type 'Hello from Jev Agent.' into Notepad "
                    "because Notepad is already open."
                ),

                "done": (
                    "Do nothing because the task is already complete."
                ),
            },
        }
    },
}


# =========================
# 3. ASK JEV API
# =========================

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

response = httpx.post(
    "https://openrouter.ai/api/alpha/decisions",
    headers=headers,
    json=payload,
    timeout=30,
)

response.raise_for_status()

data = response.json()


# =========================
# 4. READ JEV DECISION
# =========================

answer = data["answers"]["next_action"]

action = answer["choice"]
confidence = answer["confidence"]

print("\n=== JEV DECISION ===")
print("Action:", action)
print("Confidence:", confidence)
print("Probabilities:", answer["probabilities"])


# =========================
# 5. EXECUTE ACTION
# =========================

if action == "open_notepad":

    print("\nExecuting: open_notepad")

    subprocess.Popen(["notepad.exe"])

    print("Notepad opened.")


elif action == "type_message":

    print("\nExecuting: type_message")

    # Find Notepad
    notepad = None

    for window in desktop.windows(visible_only=True):

        try:
            title = window.window_text()

            if "Notepad" in title:
                notepad = window
                break

        except Exception:
            pass

    if notepad is None:
        raise RuntimeError("Could not find Notepad window.")

    print("Found:", notepad.window_text())

    # Bring Notepad to the front
    notepad.set_focus()

    time.sleep(0.5)

    # Select everything currently in Notepad
    send_keys("^a")

    time.sleep(0.2)

    # Type the message
    send_keys("Hello from Jev Agent.")

    print("Typed message successfully.")


elif action == "done":

    print("\nTask already complete.")


else:

    print("\nUnknown action:", action)