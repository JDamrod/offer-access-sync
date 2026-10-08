"""Version 2: collect all rows first, then write them to the sheet in ONE request.

Still sequential (one API request at a time), but no longer limited by Google Sheets quotas.
"""
import json
import os

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"), scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(os.getenv("SHEET_ID", "")).worksheet(os.getenv("WORKSHEET_NAME", ""))

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY = os.getenv("SCALEO_API_KEY", "")
FIRST_OFFER_ID = int(os.getenv("FIRST_OFFER_ID", "1"))
LAST_OFFER_ID = int(os.getenv("LAST_OFFER_ID", "10"))

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "Content-Type": "application/json"
})

rows = []
i = LAST_OFFER_ID
while i >= FIRST_OFFER_ID:

    # affiliate access
    url1 = f"{SCALEO_API_BASE}/api/v2/network/offers/{i}/affiliate-access"
    r1 = session.get(url1, params={"api-key": SCALEO_API_KEY}, timeout=10)
    data1 = r1.json()

    affiliates = data1["info"]["affiliate-access"]["allowed_affiliates"]

    if not affiliates:
        i -= 1
        continue

    non_demo = [aff for aff in affiliates if aff["title"].lower() != "demo"]

    if not non_demo:
        i -= 1
        continue

    # offer info
    url2 = f"{SCALEO_API_BASE}/api/v2/network/offers/{i}"
    r2 = session.get(url2, params={"api-key": SCALEO_API_KEY}, timeout=10)
    data2 = r2.json()

    advertiser_raw = data2["info"]["offer"]["advertiser"]
    advertiser = json.loads(advertiser_raw)
    company_name = advertiser["company_name"]

    title = data2["info"]["offer"]["title"]

    # add the rows
    for aff in non_demo:
        rows.append([
            aff["id"],      # A: affiliate ID
            title,          # B: offer title
            i,              # C: offer ID
            company_name    # D: advertiser
        ])

    i -= 1


# write everything in one request
start_row = 2
end_row = start_row + len(rows) - 1

sheet.update(rows, f"A{start_row}:D{end_row}")
