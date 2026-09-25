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
    "model": "typesafe/jev-1.13",

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
        },

        "task_started": {
            "type": "noul",
            "instructions": "Has the user asked the computer to open an application?",
        },

        "readiness": {
            "type": "score",
            "instructions": "How ready is the current computer state for taking the next action?",
            "criteria": [
                "The state is not ready for action.",
                "The state is slightly ready for action.",
                "The state is moderately ready for action.",
                "The state is very ready for action.",
                "The state is completely ready for action.",
            ],
        },
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

answers = data["answers"]

choice = answers["next_action"]
started = answers["task_started"]
readiness = answers["readiness"]


print("\n=== JEV DECISION ===")

print("\nCHOICE")
print("Action:", choice["choice"])
print("Confidence:", choice["confidence"])
print("Probabilities:", choice["probabilities"])

print("\nNOUL")
print("Task started probability:", started["noul"])

print("\nSCORE")
print("Readiness score:", readiness["score"])
print("Confidence:", readiness["confidence"])
print("Probabilities:", readiness["probabilities"])
print("Legend:", readiness["legend"])

print("\nUsage")
print("Input tokens:", data["usage"]["input_tokens"])
print("Output tokens:", data["usage"]["output_tokens"])
print("Cost:", data["usage"]["cost"])