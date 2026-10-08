# Offer Access Sync

A script that copies "who has access to which offer" from a [Scaleo](https://www.scaleo.io/) affiliate network into a Google Sheet. I use it at work to keep a monthly table of offers and the affiliates connected to them up to date, instead of collecting it by hand.

Each row in the sheet looks like this (made-up data):

| Affiliate ID | Offer | Offer ID | Advertiser |
|---|---|---|---|
| 1042 | Example Casino / test \| UK | 1001 | Example Media Ltd |
| 1057 | Example Casino / test \| UK | 1001 | Example Media Ltd |
| 1042 | Demo Betting \| DE | 1002 | Sample Partners |

Affiliates named "demo" are skipped.

## How it evolved

I wrote the first version myself and then rewrote it twice to make it faster. All three versions are in this repository so you can compare them.

| Version | File | What it does | Google Sheets calls |
|---|---|---|---|
| 1 | `legacy/v1_sequential.py` | Loops over offers one by one and writes every cell separately | about 5 per row |
| 2 | `legacy/v2_batched.py` | Collects all rows in memory, then writes them in a single request | 1 in total |
| 3 | `actualization.py` | Same single write, but the Scaleo requests run concurrently (up to 15 at a time) | 1 in total |

- **V1 → V2:** writing cell by cell is slow and, with more rows, runs into the Google Sheets rate limits. Collecting the data first and writing it once solves both problems.
- **V2 → V3:** most of the time is spent waiting for the API to answer. With `asyncio` and `aiohttp` many requests wait at the same time, and a semaphore limits how many are in flight so the API isn't overloaded.

The current version (`actualization.py`) also:

- retries failed requests (server errors, rate limiting) with a growing pause,
- leaves the sheet untouched if some offers could not be loaded, so it never gets half-updated data,
- clears the old rows before writing, so leftovers from the previous run don't stay in the table.

## Benchmark

Measured on offers with IDs 1000-1100 (101 offers, 12 rows written to the sheet), 3 runs each, October 2026.

| Version | Run 1 | Run 2 | Run 3 | Average |
|---|---|---|---|---|
| 1 (sequential, cell by cell) | 68.3 s | 67.3 s | 67.9 s | 67.9 s |
| 2 (batched write) | 33.6 s | 35.2 s | 36.5 s | 35.1 s |
| 3 (async) | 7.0 s | 6.2 s | 5.6 s | 6.3 s |

Version 3 is about 11 times faster than version 1 and about 5.6 times faster than version 2. Most of the gain from version 2 to version 3 comes from running the API requests concurrently.

Only 12 rows were written in this test, so version 1 stayed under the Google Sheets limits. It sends several requests per row, so with a bigger table it would hit them. Times also depend on the API speed and my internet connection, so treat them as a rough comparison.

## Setup

1. Create a Google Cloud service account with access to the Google Sheets API, download its key as `credentials.json`, and share the target sheet with the service account's email.
2. Install and configure:

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in your values
```

3. Run:

```bash
python actualization.py
```

Settings are in `.env`: Scaleo URL and key, the sheet ID and worksheet name, the range of offer IDs to read, and the number of concurrent requests. `credentials.json` and `.env` are in `.gitignore` and must never be committed.

## Notes

- Version 1 is my own first attempt. Versions 2 and 3 were developed with AI help: I understand the batching idea well, and I'm still learning `asyncio`.
- I tested the script against a local mock of the API (successful responses, 404, server errors that succeed on retry, invalid JSON), but the real Scaleo and Google Sheets calls only run in my own setup.
- Not affiliated with Scaleo.

## License

MIT, see [LICENSE](LICENSE).
