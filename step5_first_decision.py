import os
import subprocess

import httpx
from dotenv import load_dotenv
from pywinauto import Desktop


load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise RuntimeError("OPENROUTER_API_KEY is missing.")


# --------------------------------------------------
# 1. OBSERVE
# --------------------------------------------------

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


# --------------------------------------------------
# 2. ASK JEV
# --------------------------------------------------

payload = {
    "model": "typesafe/jev-1.13",

    "state": {
        "task": "Make sure Notepad is open.",
        "screen": screen_state,
    },

    "questions": {
        "next_action": {
            "type": "choice",

            "instructions": (
                "What should the computer do next "
                "to make sure Notepad is open?"
            ),

            "criteria": {
                "open_notepad": (
                    "Open the Windows Notepad application "
                    "because it is not currently open."
                ),

                "done": (
                    "Do nothing because Notepad is already open."
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
    "https://openrouter.ai/api/alpha/decisions",
    headers=headers,
    json=payload,
    timeout=30,
)

response.raise_for_status()

data = response.json()


# --------------------------------------------------
# 3. READ DECISION
# --------------------------------------------------

answer = data["answers"]["next_action"]

action = answer["choice"]
confidence = answer["confidence"]


print("\n=== JEV DECISION ===")
print("Action:", action)
print("Confidence:", confidence)
print("Probabilities:", answer["probabilities"])


# --------------------------------------------------
# 4. EXECUTE DECISION
# --------------------------------------------------

if action == "open_notepad":

    print("\nExecuting: open_notepad")

    subprocess.Popen(["notepad.exe"])

elif action == "done":

    print("\nExecuting: nothing")

else:

    print("\nUnknown action:", action)