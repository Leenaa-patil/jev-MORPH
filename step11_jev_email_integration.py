import os
import re
import base64
from email.mime.text import MIMEText
from pathlib import Path

import httpx
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

APP_NAME = "jev-MORPH"

API_KEY = os.getenv("OPENROUTER_API_KEY")

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"

CONFIDENCE_THRESHOLD = 0.60

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]

CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.json")


# ============================================================
# GMAIL CONNECTION
# ============================================================

def get_gmail_service():

    credentials = None

    if TOKEN_FILE.exists():

        credentials = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            GMAIL_SCOPES,
        )

    if credentials and credentials.expired and credentials.refresh_token:

        credentials.refresh(Request())

    if not credentials or not credentials.valid:

        if not CREDENTIALS_FILE.exists():

            print("\nERROR: credentials.json not found.")
            return None

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            GMAIL_SCOPES,
        )

        credentials = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    return build(
        "gmail",
        "v1",
        credentials=credentials,
    )


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(recipient, subject, body):

    try:

        gmail = get_gmail_service()

        if gmail is None:
            return False

        message = MIMEText(body)

        message["to"] = recipient
        message["subject"] = subject

        encoded_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        result = gmail.users().messages().send(
            userId="me",
            body={
                "raw": encoded_message
            },
        ).execute()

        return bool(result.get("id"))

    except Exception as e:

        print("\nEMAIL SEND ERROR")
        print(e)

        return False


# ============================================================
# ASK JEV-MORPH
# ============================================================

def ask_morph(task):

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
            DECISIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

    except Exception as e:

        print("\nJEV-MORPH CONNECTION ERROR")
        print(e)

        return {
            "choice": "done",
            "confidence": 0,
        }

    if response.status_code != 200:

        print("\nJEV-MORPH API ERROR")
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

        print("\nJEV-MORPH RESPONSE ERROR")
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
# PREVIEWS
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
        "\nSend this? [y/N]: "
    ).strip().lower()

    return answer in {"y", "yes"}


# ============================================================
# EMAIL
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

    if not confirm():

        print("\nCancelled.")
        return

    print("\nSending email...")

    success = send_email(
        recipient,
        subject,
        body,
    )

    if success:

        print("✅ Email sent successfully.")

    else:

        print("❌ Email was not sent.")


# ============================================================
# WHATSAPP
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

    if not confirm():

        print("\nCancelled.")
        return

    print("\nWhatsApp sending is not connected yet.")
    print("Nothing was sent.")


# ============================================================
# RUN TASK
# ============================================================

def run_task(task):

    decision = ask_morph(task)

    action = decision.get(
        "choice",
        "done",
    )

    confidence = decision.get(
        "confidence",
        0,
    )

    if confidence < CONFIDENCE_THRESHOLD:

        print("\nJev-MORPH confidence is too low.")
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

        print(
            "ERROR: OPENROUTER_API_KEY not found in .env"
        )

        return

    print("=" * 60)
    print(f"{APP_NAME} COMMUNICATION AGENT")
    print("=" * 60)
    print("Type a task, or 'exit' to quit.")

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