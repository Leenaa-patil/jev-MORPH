import os
import re
import httpx
from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"

CONFIDENCE_THRESHOLD = 0.60


# ============================================================
# ASK JEV
# ============================================================

def ask_jev(task):

    payload = {
        "model": MODEL,
        "state": task,
        "questions": {
            "communication_action": {
                "type": "choice",
                "instructions": (
                    "Determine what communication action the user wants. "
                    "Choose send_email if the user wants to send, draft, "
                    "compose, or prepare an email. "
                    "Choose send_message if the user wants to send, draft, "
                    "compose, or prepare a message. "
                    "Choose done if this is not a communication request."
                ),
                "criteria": {
                    "send_email":
                        "The user wants to send, draft, compose, or prepare an email.",

                    "send_message":
                        "The user wants to send, draft, compose, or prepare a message.",

                    "done":
                        "This is not a communication request.",
                },
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            JEV_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

    except Exception as e:
        print("\nJEV CONNECTION ERROR")
        print(e)

        return {
            "choice": "done",
            "confidence": 0,
        }

    if response.status_code != 200:
        print("\nJEV API ERROR")
        print("Status:", response.status_code)
        print("Response:", response.text)

        return {
            "choice": "done",
            "confidence": 0,
        }

    try:
        data = response.json()
        return data["answers"]["communication_action"]

    except Exception as e:
        print("\nJEV RESPONSE ERROR")
        print("Error:", e)
        print("Raw response:", response.text)

        return {
            "choice": "done",
            "confidence": 0,
        }


# ============================================================
# EMAIL RECIPIENT
# ============================================================

def extract_email_recipient(task):

    match = re.search(
        r'\b(?:email|mail)\s+(?:to\s+)?([^\s,]+@[^\s,]+)',
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


# ============================================================
# MESSAGE RECIPIENT
# ============================================================

def extract_message_recipient(task):

    patterns = [
        r'\bsend\s+(?:a\s+)?message\s+to\s+([A-Za-z][A-Za-z0-9_-]*)',
        r'\bmessage\s+([A-Za-z][A-Za-z0-9_-]*)',
        r'\btext\s+([A-Za-z][A-Za-z0-9_-]*)',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            task,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    return None


# ============================================================
# MESSAGE / EMAIL BODY
# ============================================================

def extract_message(task):

    # Quoted message
    quoted_patterns = [
        r'\bsaying\s+["\'](.+?)["\']',
        r'\bsays\s+["\'](.+?)["\']',
        r'\bmessage\s*[:\-]\s*["\'](.+?)["\']',
        r'\bbody\s*[:\-]\s*["\'](.+?)["\']',
    ]

    for pattern in quoted_patterns:

        match = re.search(
            pattern,
            task,
            re.IGNORECASE,
        )

        if match:
            return match.group(1).strip()

    # Natural language
    # Example:
    # "draft an email to Sarah and ask her to meet at 6pm"

    match = re.search(
        r'\band\s+(?:ask|tell|let)\s+'
        r'(?:her|him|them)\s+(.+)$',
        task,
        re.IGNORECASE,
    )

    if match:

        text = match.group(1).strip()

        text = re.sub(
            r'^to\s+',
            '',
            text,
            flags=re.IGNORECASE,
        )

        if text:
            text = text[0].upper() + text[1:]

        if not text.endswith((".", "!", "?")):
            text += "."

        return text

    # Colon format
    # Example:
    # "email bob@example.com: See you tomorrow"

    match = re.search(
        r'(?:email|message|text)\s+'
        r'[^:]+:\s*(.+)$',
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return None


# ============================================================
# SUBJECT
# ============================================================

def extract_subject(task):

    match = re.search(
        r'\bsubject\s*[:\-]\s*(.+?)(?:\s+\bbody\b|\s*$)',
        task,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    body = extract_message(task)

    if body:

        if "meeting" in body.lower():
            return "Meeting Update"

        if "meet" in body.lower():
            return "Meeting"

        if "late" in body.lower():
            return "Running Late"

    return "Message from Jev"


# ============================================================
# EMAIL PREVIEW
# ============================================================

def show_email_preview(recipient, subject, body):

    print("\n")
    print("=" * 60)
    print("EMAIL PREVIEW")
    print("=" * 60)

    print(f"To:      {recipient}")
    print(f"Subject: {subject}")

    print("-" * 60)

    print(body)

    print("=" * 60)


# ============================================================
# MESSAGE PREVIEW
# ============================================================

def show_message_preview(recipient, body):

    print("\n")
    print("=" * 60)
    print("MESSAGE PREVIEW")
    print("=" * 60)

    print(f"To: {recipient}")

    print("-" * 60)

    print(body)

    print("=" * 60)


# ============================================================
# CONFIRMATION
# ============================================================

def confirm():

    answer = input(
        "\nPrepare this? [y/N]: "
    ).strip().lower()

    return answer in {"y", "yes"}


# ============================================================
# PREPARE EMAIL
# ============================================================

def prepare_email(task):

    recipient = extract_email_recipient(task)
    body = extract_message(task)
    subject = extract_subject(task)

    if not recipient:
        print("\nI couldn't determine the email recipient.")
        return

    if not body:
        print("\nI couldn't determine what you want to say.")
        return

    show_email_preview(
        recipient,
        subject,
        body,
    )

    if confirm():

        print("\nConfirmed.")
        print("Email draft approved.")
        print("Nothing has been sent yet.")

    else:

        print("\nCancelled.")
        print("Nothing has been prepared.")


# ============================================================
# PREPARE MESSAGE
# ============================================================

def prepare_message(task):

    recipient = extract_message_recipient(task)
    body = extract_message(task)

    if not recipient:
        print("\nI couldn't determine the message recipient.")
        return

    if not body:
        print("\nI couldn't determine what you want to say.")
        return

    show_message_preview(
        recipient,
        body,
    )

    if confirm():

        print("\nConfirmed.")
        print("Message draft approved.")
        print("Nothing has been sent yet.")

    else:

        print("\nCancelled.")
        print("Nothing has been prepared.")


# ============================================================
# RUN TASK
# ============================================================

def run_task(task):

    decision = ask_jev(task)

    action = decision.get(
        "choice",
        "done",
    )

    confidence = decision.get(
        "confidence",
        0,
    )

    if confidence < CONFIDENCE_THRESHOLD:

        print("\nJev confidence is too low.")
        print("No communication action was performed.")
        return

    if action == "send_email":

        prepare_email(task)

    elif action == "send_message":

        prepare_message(task)

    else:

        print("\nNo communication action required.")


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not found in .env")
        return

    print("=" * 60)
    print("JEV COMMUNICATION PLANNER")
    print("=" * 60)
    print("Type a communication task, or 'exit' to quit.")

    while True:

        try:
            task = input("\nYou > ").strip()

        except KeyboardInterrupt:
            print("\nExiting.")
            break

        if not task:
            continue

        if task.lower() in {"exit", "quit", "bye"}:
            print("Goodbye.")
            break

        run_task(task)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()