"""Version 1: the first, simplest version (sequential, one Google Sheets call per cell).

Kept for reference, see the README. It is slow and hits the Google Sheets rate limits.
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

i = LAST_OFFER_ID
b = 2
c = 2
while i >= FIRST_OFFER_ID:
    url = f"{SCALEO_API_BASE}/api/v2/network/offers/{i}/affiliate-access"
    params = {
        "api-key": SCALEO_API_KEY,
        "lang": "en",
        "sortField": "added_timestamp",
        "sortDirection": "desc",
        "perPage": 1000,
        "fieldsType": "object",
    }

    r = requests.get(
        url,
        params=params,
        headers={"Accept": "application/json",
                 "Content-Type": "application/json"},
        timeout=10,
    )

    data = r.json()

    i = i - 1

    affiliates = data["info"]["affiliate-access"]["allowed_affiliates"]

    if not affiliates:
        continue

    non_demo = [aff for aff in affiliates if aff["title"].lower() != "demo"]

    if not non_demo:
        continue

    for aff in non_demo:
        sheet.update([[aff['id']]], f"A{b}")
        sheet.update([[i + 1]], f"C{b}")
        b += 1

    c = b - 1

i = 2
while i <= c:

    value = sheet.acell(f"C{i}").value

    URL = f"{SCALEO_API_BASE}/api/v2/network/offers/{value}"

    r = session.get(URL, params={"api-key": SCALEO_API_KEY}, timeout=10)
    data = r.json()

    advertiser_raw = data["info"]["offer"]["advertiser"]
    advertiser = json.loads(advertiser_raw)
    company_name = advertiser["company_name"]

    title = data["info"]["offer"]["title"]

    sheet.update([[company_name]], f"D{i}")
    sheet.update([[title]], f"B{i}")

    i += 1
