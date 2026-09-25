from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main():

    credentials_file = Path("credentials.json")

    if not credentials_file.exists():
        print("ERROR: credentials.json not found.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        SCOPES,
    )

    credentials = flow.run_local_server(port=0)

    gmail = build(
        "gmail",
        "v1",
        credentials=credentials,
    )

    profile = gmail.users().getProfile(
        userId="me"
    ).execute()

    print("\nGmail authentication successful!")
    print("Connected account:", profile["emailAddress"])


if __name__ == "__main__":
    main()