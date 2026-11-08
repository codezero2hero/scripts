"""01_download_company_facts.py

Step 1: Get SEC EDGAR company facts once and store them locally.

This script downloads structured company facts from the SEC EDGAR API using the
helper function in edgar_utils.py.

The goal is to cache the raw data locally before running the analysis scripts.
That way, later scripts can read from local files instead of requesting the same
data from the SEC again and again.

Why this matters:
    - It is faster after the first download.
    - It is more polite to SEC servers.
    - It gives me a stable raw-data file to inspect if something looks wrong.
    - It separates "download the data" from "analyze the data."

Output:
    Raw company facts are cached by download_company_facts(), normally into the
    edgar_cache/ folder depending on how edgar_utils.py is configured.

Important:
    This is not analysis yet. This step only collects the raw material.
"""

from edgar_utils import download_company_facts


# Three comparison pairs from the article.
# Edit this list freely if you want to compare different companies.
TICKERS = [
    "V", "MA",       # Payments: the clean comparison
    "KO", "PEP",     # Beverages/snacks: similar label, different mix
    "AAPL", "MSFT",  # Mega-cap tech: same label, different economics
]


def main():
    """Download and cache SEC company facts for each ticker in TICKERS.

    For every ticker, this function:

        1. Downloads or loads cached SEC company facts.
        2. Counts how many us-gaap concepts are available.
        3. Prints a short confirmation message.

    Notes
    -----
    The helper function download_company_facts() controls the caching behavior.

    If that helper supports a refresh option, you can force a fresh download by
    calling:

        download_company_facts(t, refresh=True)
    """
    for t in TICKERS:
        # Let the reader know which ticker is being processed.
        print(f"Downloading {t} ...")

        # Download company facts or load them from the local cache.
        facts = download_company_facts(t)

        # If you need to force a fresh SEC request and your helper supports it,
        # use this version instead:
        #
        # facts = download_company_facts(t, refresh=True)

        # Count available us-gaap concepts.
        # This is a quick sanity check that the SEC response contains data.
        n = len(facts.get("facts", {}).get("us-gaap", {}))

        # Print a simple cache confirmation.
        print(f"  cached {t}: {n} us-gaap concepts")


if __name__ == "__main__":
    main()
