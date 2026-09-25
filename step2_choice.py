import os

import httpx
from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENROUTER_API_KEY is missing. Put it in your .env file."
    )


state = {
    "task": "Open Chrome",
    "screen": "Windows desktop is visible. Chrome is not open.",
}


payload = {
    "model": "~typesafe/jev-latest",
    "state": state,
    "questions": {
        "next_action": {
            "type": "choice",
            "instructions": "What should the computer do next?",
            "criteria": {
                "open_chrome": "Open the Google Chrome application.",
                "open_calculator": "Open the Windows Calculator application.",
                "done": "The task is already complete.",
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

print("RAW RESPONSE:")
print(data)