"""
SCOPE:
This script automates the retrieval of SEC filings to bypass 'opinionated'
financial news. The goal: To calculate actual GAAP Gross Margin and Revenue growth,
ensuring I'm looking at business performance, not stock price hype:
  1. Pulls quarterly Revenue and Gross Profit for NVIDIA and Arista.
  2. Derives each Q4 (companies don't file a standalone Q4: Q4 = full year
     from the 10-K minus the 9-month figure from the Q3 10-Q).
  3. Computes quarterly gross margin = Gross Profit / Revenue.
  4. Saves a CSV per company (so you can eyeball the numbers against filings)
     and renders the charts.

REQUIREMENTS:  pip install matplotlib

OUTPUT FILES: For each company, this script creates:
    - <company>_quarterly.csv
    - <company>_revenue_10y.png
    - <company>_grossmargin_10y.png

IMPORTANT: Replace USER_AGENT below with your real name and email address. The SEC asks
        automated requests to identify the requester and may reject requests that do
        not provide an appropriate User-Agent header.
"""

import csv
import json
import time
import urllib.request
import urllib.error
from datetime import date

import matplotlib.pyplot as plt

# --- EDIT THIS: SEC requires a descriptive User-Agent with contact info ------
# e.g. CodeZero2Hero research <email address> xxx@xxx.xx
USER_AGENT = "CodeZero2Hero research codezero2hero@gmail.com"

# Number of calendar years shown in the exported CSV files and charts.
# This is a visual research window, not a valuation assumption.
YEARS_BACK = 10
CUTOFF_YEAR = date.today().year - YEARS_BACK

# Companies studied in this article.
# The colours are used only for chart presentation and do not imply any rating.
COMPANIES = {
    "NVIDIA": {"cik": "0001045810", "color": "#76b900"},
    "Arista": {"cik": "0001596532", "color": "#2e8b57"},
}

# Public companies may report revenue using different US-GAAP XBRL concepts
# across filings or over time. Try these concepts in priority order and keep
# the first available value for each quarter-end date.
REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]

# Gross Profit is used with Revenue to calculate reported GAAP gross margin.
GROSS_PROFIT_TAG = "GrossProfit"

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def get_concept(cik, tag):
    """
    Retrieve reported USD facts for one US-GAAP XBRL concept from SEC EDGAR.

    Parameters
    ----------
    cik : str
        SEC Central Index Key for the company, including leading zeros.
    tag : str
        US-GAAP XBRL concept name, such as ``GrossProfit`` or ``Revenues``.

    Returns
    -------
    list
        Reported USD fact records returned by the SEC Company Concept API.
        Returns an empty list when the concept is not available or the request
        cannot be completed.

    Notes
    -----
    A missing concept does not necessarily mean that the company failed to report
    the item. The company may have used a different XBRL tag in that period.
    """


    url = (f"https://data.sec.gov/api/xbrl/companyconcept/"
           f"CIK{cik}/us-gaap/{tag}.json")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code != 404: # A 404 usually means this company has no facts for this tag.
            print(f"  (warning for {tag}: {e})")
        return []
    except Exception as e:
        print(f"  (no data for {tag}: {e})")
        return []

    time.sleep(0.3)  # add some lag so we dont kill SEC servers (be mild)

    return data.get("units", {}).get("USD", [])


# ---------------------------------------------------------------------------
# Turning raw facts into a clean quarterly series (the fiddly part)
# ---------------------------------------------------------------------------
def _days(fact):
    """
    Return the number of days covered by one duration-based XBRL fact.

    Revenue and gross profit are flow measures reported over a period, such as
    three months, nine months or a full fiscal year. The duration is used to
    classify each reported fact into the appropriate reporting period.
    """
    return (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days


def quarterly_flow(facts):
    """
    Convert reported flow facts into a quarterly series and derive missing Q4 data.

    Parameters
    ----------
    facts : list
        SEC XBRL fact records for a duration-based financial metric, such as
        revenue or gross profit.

    Returns
    -------
    dict
        Dictionary mapping quarter-end dates to three-month values.

    Method
    ------
    Reported three-month facts are treated as quarterly observations. When the
    company reports a full fiscal-year value and a matching nine-month
    year-to-date value, a missing fourth quarter is derived as:

        Q4 = full fiscal year - first nine months

    Limitations
    -----------
    This is a practical extraction method for article research, not a complete
    XBRL-normalisation engine. Important outputs should be checked against the
    original filings before publication or investment use.
    """

    quarterly = {}  # Quarter-end date -> reported or derived three-month value.
    annual = {}  # Fiscal-year start date -> (year-end date, full-year value).
    nine_month = {}  # Fiscal-year start date -> (nine-month end date, YTD value).

    for f in facts:
        d = _days(f)
        end = date.fromisoformat(f["end"])
        start = f["start"]
        if 80 <= d <= 100:                 # a 3-month quarter
            quarterly[end] = f["val"]
        elif 250 <= d <= 295:              # a 9-month year-to-date figure
            nine_month[start] = (end, f["val"])
        elif 350 <= d <= 380:              # a full fiscal year
            annual[start] = (end, f["val"])

    # Derive Q4 = full year - 9-month, matched by shared fiscal-year start.
    for start, (fy_end, fy_val) in annual.items():
        if fy_end in quarterly:            # already have an explicit Q4? keep it
            continue
        if start in nine_month:
            _, ytd9 = nine_month[start]
            quarterly[fy_end] = fy_val - ytd9

    return dict(sorted(quarterly.items()))


def revenue_series(cik):
    """
    Build a quarterly revenue series across alternative US-GAAP revenue tags.

    Companies may change the XBRL concept used for revenue over time. This
    function attempts the preferred revenue tags in order and fills missing
    quarter-end values without overwriting values already obtained from a
    higher-priority tag.

    Parameters
    ----------
    cik : str
        SEC Central Index Key for the company.

    Returns
    -------
    dict
        Dictionary mapping quarter-end dates to quarterly revenue in raw USD.
    """

    merged = {}
    for tag in REVENUE_TAGS:
        series = quarterly_flow(get_concept(cik, tag))
        for d, v in series.items():
            merged.setdefault(d, v)        # don't overwrite an earlier tag's value
    return dict(sorted(merged.items()))


def build(cik):
    """
    Build recent quarterly revenue and GAAP gross-margin series for one company.

    Parameters
    ----------
    cik : str
        SEC Central Index Key for the company.

    Returns
    -------
    tuple[dict, dict]
        Two date-keyed quarterly series:

        - revenue: quarterly revenue in raw USD.
        - margin: quarterly GAAP gross margin in percent.

        Gross margin is calculated only for periods where both Revenue and Gross
        Profit are available and reported revenue is non-zero.

    Notes
    -----
    The results are trimmed to the research window defined by ``YEARS_BACK``.
    Before publishing any observation based on a chart, review the corresponding
    CSV values against the company's original filing.
    """

    rev = revenue_series(cik)
    gp = quarterly_flow(get_concept(cik, GROSS_PROFIT_TAG))
    margin = {d: gp[d] / rev[d] * 100 for d in rev if d in gp and rev[d]}
    keep = lambda s: {d: v for d, v in s.items() if d.year >= CUTOFF_YEAR}
    return keep(rev), keep(margin)


# ---------------------------------------------------------------------------
# Output: CSV (for verification) + charts
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.family": "DejaVu Sans",
    "font.size": 12, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25,
})
MUTED = "#6b7280"


def save_csv(name, rev, margin):
    """
    Save extracted quarterly revenue and gross-margin values for manual review.

    The CSV acts as an audit step between the SEC extraction and the published
    chart. It allows the reader or author to compare individual quarter values
    with the original company filings before drawing conclusions.

    Parameters
    ----------
    name : str
        Display name of the company and prefix used in the output filename.
    rev : dict
        Quarterly revenue values keyed by quarter-end date.
    margin : dict
        Quarterly GAAP gross-margin percentages keyed by quarter-end date.

    Returns
    -------
    None
    """
    fn = f"{name.lower()}_quarterly.csv"
    with open(fn, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quarter_end", "revenue_usd", "gross_margin_pct"])
        for d in sorted(rev):
            w.writerow([d, rev[d], round(margin.get(d, float("nan")), 2)])
    print(f"  wrote {fn} ({len(rev)} quarters)")


def chart_revenue(name, rev, color):
    """
    Create a long-term quarterly revenue chart for one company.

    Purpose in the article
    ----------------------
    This chart helps distinguish a long-term business trend from recent market
    excitement. In the NVIDIA and Arista examples, it lets the reader see how much
    of the reported revenue expansion occurred recently rather than assuming the
    current narrative existed throughout the entire period.

    Parameters
    ----------
    name : str
        Company display name and output filename prefix.
    rev : dict
        Quarterly revenue values keyed by quarter-end date, in raw USD.
    color : str
        Colour used for the company's plotted series.

    Output
    ------
    Saves ``<company>_revenue_10y.png`` in the current working directory.

    Returns
    -------
    None
    """
    dates = sorted(rev)
    vals = [rev[d] / 1e9 for d in dates]            # to $B
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.80, bottom=0.12)
    ax.bar(range(len(dates)), vals, color=color, width=0.85)
    step = max(1, len(dates) // 8)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels([f"{dates[i].year}" for i in range(0, len(dates), step)])
    ax.set_ylabel("Quarterly revenue ($B)")
    fig.text(0.015, 0.95, f"{name}: quarterly revenue, last ~{YEARS_BACK} years",
             fontsize=15, fontweight="bold", ha="left", va="top")
    fig.text(0.015, 0.875,
             "The long view: notice how much of the story is recent.",
             fontsize=10.5, color=MUTED, ha="left", va="top")
    fig.text(0.015, 0.015, "Source: SEC EDGAR XBRL (us-gaap), quarterly; "
             "Q4 derived from 10-K minus 9-month 10-Q.",
             fontsize=8.5, color=MUTED, ha="left")
    fig.savefig(f"{name.lower()}_revenue_10y.png", facecolor="white")
    plt.close(fig)
    print(f"  wrote {name.lower()}_revenue_10y.png")


def chart_margin(name, margin, color):
    """
    Create a long-term quarterly GAAP gross-margin chart for one company.

    Purpose in the article
    ----------------------
    Revenue growth can make an exciting company look automatically attractive.
    Gross margin adds a second question: is the company keeping a similar share of
    each sales dollar after the direct cost of delivering its product? This chart
    helps the reader investigate changes in business economics rather than relying
    only on the growth story.

    Parameters
    ----------
    name : str
        Company display name and output filename prefix.
    margin : dict
        Quarterly GAAP gross-margin percentages keyed by quarter-end date.
    color : str
        Colour used for the company's plotted series.

    Output
    ------
    Saves ``<company>_grossmargin_10y.png`` in the current working directory.

    Returns
    -------
    None
    """
    dates = sorted(margin)
    vals = [margin[d] for d in dates]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.80, bottom=0.12)
    ax.plot(range(len(dates)), vals, "-o", lw=2.2, color=color, markersize=4)
    step = max(1, len(dates) // 8)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels([f"{dates[i].year}" for i in range(0, len(dates), step)])
    ax.set_ylabel("GAAP gross margin")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    fig.text(0.015, 0.95, f"{name}: quarterly gross margin, last ~{YEARS_BACK} years",
             fontsize=15, fontweight="bold", ha="left", va="top")
    fig.text(0.015, 0.875,
             "A scary one-quarter dip looks tiny against the long trend.",
             fontsize=10.5, color=MUTED, ha="left", va="top")
    fig.text(0.015, 0.015, "Source: SEC EDGAR XBRL (us-gaap), quarterly.",
             fontsize=8.5, color=MUTED, ha="left")
    fig.savefig(f"{name.lower()}_grossmargin_10y.png", facecolor="white")
    plt.close(fig)
    print(f"  wrote {name.lower()}_grossmargin_10y.png")


def main():
    """
    Retrieve SEC XBRL data, calculate quarterly series and create all outputs.

    For each company listed in ``COMPANIES``, this function:

    1. Retrieves revenue and gross-profit facts from SEC EDGAR.
    2. Builds quarterly revenue and GAAP gross-margin series.
    3. Writes a CSV file for manual verification.
    4. Produces one revenue chart and one gross-margin chart.

    If no revenue data is returned for a company, the script prints a warning and
    continues with the next company.

    Returns
    -------
    None
    """
    for name, cfg in COMPANIES.items():
        print(f"{name}:")
        rev, margin = build(cfg["cik"])
        if not rev:
            print("  no data returned -- check USER_AGENT and network.")
            continue
        save_csv(name, rev, margin)
        chart_revenue(name, rev, cfg["color"])
        chart_margin(name, margin, cfg["color"])


if __name__ == "__main__":
    main()
