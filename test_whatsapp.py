import os
import json

from dotenv import load_dotenv
from twilio.rest import Client


load_dotenv()

ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

if not ACCOUNT_SID:
    raise RuntimeError("TWILIO_ACCOUNT_SID is missing")

if not AUTH_TOKEN:
    raise RuntimeError("TWILIO_AUTH_TOKEN is missing")

if not WHATSAPP_FROM:
    raise RuntimeError("TWILIO_WHATSAPP_FROM is missing")


recipient = input("Your WhatsApp number (+countrycode...): ").strip()

if not recipient.startswith("+"):
    raise ValueError("Use international format, e.g. +91XXXXXXXXXX")


client = Client(
    ACCOUNT_SID,
    AUTH_TOKEN,
)

message = client.messages.create(
    from_=WHATSAPP_FROM,
    to=f"whatsapp:{recipient}",
    content_sid="HXb5b62575e6e4ff6129ad7c8efe1f983e",
    content_variables=json.dumps({
        "1": "jev-MORPH",
        "2": "WhatsApp test",
    }),
)

print()
print("WhatsApp message sent.")
print("Message SID:", message.sid)
print("Status:", message.status)