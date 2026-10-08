"""Version 3: offer access sync.

Reads every offer from a Scaleo affiliate network and writes one row per
affiliate that has access to it into a Google Sheet:

    A: affiliate ID | B: offer title | C: offer ID | D: advertiser

Affiliates named "demo" are skipped. API requests run concurrently
(asyncio + aiohttp) and the sheet is updated with a single write at the end.

Usage:
    python actualization.py
"""
import asyncio
import json
import os
import sys

import aiohttp
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SCALEO_API_BASE = os.getenv("SCALEO_API_BASE", "").rstrip("/")
SCALEO_API_KEY = os.getenv("SCALEO_API_KEY", "")

SHEET_ID = os.getenv("SHEET_ID", "")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

FIRST_OFFER_ID = int(os.getenv("FIRST_OFFER_ID", "1"))
LAST_OFFER_ID = int(os.getenv("LAST_OFFER_ID", "1000"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "15"))

RETRIES = 3   # how many times a failed request is tried


# Google Sheets

def open_worksheet():
    """Connect to the Google Sheet."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)


def write_rows(sheet, rows):
    """Replace the table in A2:D with `rows` using a single write request."""
    sheet.batch_clear(["A2:D"])   # remove old rows so none are left over from the last run
    if rows:
        sheet.update(rows, f"A2:D{1 + len(rows)}")


# Scaleo API

async def get_json(session, url):
    """GET a URL and return the JSON answer, or None if it keeps failing."""
    for attempt in range(1, RETRIES + 1):
        try:
            async with session.get(url, params={"api-key": SCALEO_API_KEY}) as response:
                if response.status == 429 or response.status >= 500:   # busy or broken server
                    raise aiohttp.ClientError(f"HTTP {response.status}")
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
            if attempt == RETRIES:
                return None
            await asyncio.sleep(attempt)   # wait 1 second, then 2, then try again


async def fetch_offer(session, semaphore, offer_id):
    """Return the sheet rows for one offer ([] if there is nothing to add).
    Return None if a request failed."""
    async with semaphore:   # at most MAX_CONCURRENT_REQUESTS offers are processed at once
        # who has access to the offer?
        access = await get_json(session, f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}/affiliate-access")
        if access is None:
            return None

        affiliates = (((access.get("info") or {}).get("affiliate-access")) or {}).get("allowed_affiliates") or []
        affiliates = [a for a in affiliates if (a.get("title") or "").lower() != "demo"]
        if not affiliates:
            return []

        # offer title and advertiser
        details = await get_json(session, f"{SCALEO_API_BASE}/api/v2/network/offers/{offer_id}")
        if details is None:
            return None

        offer = ((details.get("info") or {}).get("offer")) or {}
        title = offer.get("title", "")

        company_name = ""
        try:
            # the advertiser comes as a JSON text inside the JSON answer
            company_name = json.loads(offer.get("advertiser") or "{}").get("company_name", "")
        except json.JSONDecodeError:
            pass

        # one row per affiliate
        return [[aff["id"], title, offer_id, company_name] for aff in affiliates]


# Main

async def collect_rows():
    """Load all offers concurrently. Returns (rows, number_of_failed_offers)."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    ) as session:
        tasks = [fetch_offer(session, semaphore, offer_id)
                 for offer_id in range(FIRST_OFFER_ID, LAST_OFFER_ID + 1)]
        results = await asyncio.gather(*tasks)   # run all tasks, keep the order of offer IDs

    failed = results.count(None)
    rows = [row for result in results if result for row in result]
    return rows, failed


def main():
    sheet = open_worksheet()
    rows, failed = asyncio.run(collect_rows())

    if failed:
        # Don't overwrite the sheet with incomplete data.
        sys.exit(f"{failed} offers could not be loaded, the sheet was NOT changed. Run the script again.")

    write_rows(sheet, rows)
    print(f"Done: {len(rows)} rows written.")


if __name__ == "__main__":
    main()
