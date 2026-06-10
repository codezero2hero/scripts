"""01_download_company_facts.py --- Step 0: get the data once, store it locally."""
from edgar_utils import download_company_facts

# Three comparison pairs from the article (edit freely):
TICKERS = ["V", "MA",  # payments  -- the clean comparison
           "KO", "PEP",  # beverages -- similar label, different mix
           "AAPL", "MSFT"]  # mega-cap tech -- same label, different economics


def main():
    for t in TICKERS:
        print(f"Downloading {t} ...")
        facts = download_company_facts(t)  # refresh=True to force re-pull
        n = len(facts.get("facts", {}).get("us-gaap", {}))
        print(f"  cached {t}: {n} us-gaap concepts")


if __name__ == "__main__":
    main()
