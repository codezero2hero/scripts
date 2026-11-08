"""
edgar_utils.py

Shared utility functions for the SEC EDGAR Python toolkit.

Philosophy:
    DOWNLOAD ONCE, ANALYZE MANY TIMES.

Script 1 downloads and caches raw SEC company-facts data. Scripts 2-8 reuse
those cached files to extract financial series, calculate derived metrics,
save CSV files, and create comparison charts.

Main responsibilities:
    - Convert stock tickers into SEC CIK identifiers.
    - Download and cache SEC company-facts JSON.
    - Extract annual and quarterly flow metrics.
    - Extract point-in-time balance-sheet metrics.
    - Calculate margins and year-over-year growth.
    - Save results as CSV files.
    - Create simple comparison charts.

Requirements:
    pip install requests matplotlib

Important:
    Replace USER_AGENT below with your real project name and contact email.
    The SEC expects automated requests to identify the requester.

Notes:
    SEC XBRL data is not perfectly standardized across every company and year.
    Important values should still be checked against the original 10-K or 10-Q.
"""

import csv
import json
import os
import time
from datetime import date

import matplotlib

# Use a non-interactive backend.
#
# This allows charts to be generated on servers, in scripts, and in other
# environments where a graphical desktop window is not available.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import requests


# ---------------------------------------------------------------------------
# SEC request configuration
# ---------------------------------------------------------------------------

# Replace this with a real project name and contact email before using the SEC
# endpoints regularly.
USER_AGENT = "CodeZero2Hero research your-email@example.com"

# These headers are included with every SEC request.
HEADERS = {
    "User-Agent": USER_AGENT,
}


# ---------------------------------------------------------------------------
# Local folders
# ---------------------------------------------------------------------------

# Raw SEC JSON responses are stored here.
CACHE_DIR = "edgar_cache"

# Generated CSV files and charts are stored here.
OUT_DIR = "edgar_output"

# Create the folders if they do not already exist.
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Common XBRL tags
# ---------------------------------------------------------------------------

# Revenue has appeared under several US-GAAP concepts over time.
#
# The toolkit tries these tags in order. When more than one tag contains data,
# flow_series() keeps the first value found for each reporting date.
REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]


# ---------------------------------------------------------------------------
# Shared matplotlib appearance
# ---------------------------------------------------------------------------

# Apply the same basic visual style to every chart produced by the toolkit.
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.size": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})


# ---------------------------------------------------------------------------
# Ticker -> CIK resolution
# ---------------------------------------------------------------------------

# In-memory ticker map.
#
# It begins as None and is downloaded only the first time cik_for() is called.
# Later calls reuse the same dictionary during the current Python process.
_TICKER_MAP = None


def cik_for(ticker):
    """Resolve a stock ticker to the SEC's zero-padded 10-digit CIK.

    Parameters
    ----------
    ticker:
        Stock ticker symbol, such as "V", "MA", "KO", or "AAPL".

    Returns
    -------
    str
        The corresponding SEC Central Index Key as a 10-character string.

        Example:
            "AAPL" -> "0000320193"

    Raises
    ------
    ValueError
        If the ticker is not found in the SEC ticker list.

    Notes
    -----
    The SEC identifies companies internally by CIK rather than by ticker.

    The ticker-to-CIK map is downloaded once per Python process and then kept
    in the module-level _TICKER_MAP dictionary.
    """
    global _TICKER_MAP

    # Download the SEC ticker map only when it has not already been loaded.
    if _TICKER_MAP is None:
        url = "https://www.sec.gov/files/company_tickers.json"

        # Request the official SEC ticker list.
        rows = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        ).json()

        # Convert the SEC response into:
        #
        #     {
        #         "AAPL": "0000320193",
        #         "MSFT": "0000789019",
        #         ...
        #     }
        #
        # zfill(10) ensures every CIK contains exactly ten digits.
        _TICKER_MAP = {
            row["ticker"].upper(): str(row["cik_str"]).zfill(10)
            for row in rows.values()
        }

        # Pause briefly to avoid making SEC requests too aggressively.
        time.sleep(0.3)

    # Normalize the ticker so callers may use lowercase or uppercase.
    normalized_ticker = ticker.upper()

    if normalized_ticker not in _TICKER_MAP:
        raise ValueError(
            f"Ticker {ticker!r} not found in SEC's ticker list."
        )

    return _TICKER_MAP[normalized_ticker]


# ---------------------------------------------------------------------------
# Download and cache
#
# These are the only functions in this module that need network access.
# ---------------------------------------------------------------------------

def _cache_path(ticker):
    """Return the local JSON cache path for one company.

    Parameters
    ----------
    ticker:
        Stock ticker symbol.

    Returns
    -------
    str
        File path containing both the normalized ticker and CIK.

        Example:
            edgar_cache/AAPL_0000320193.json
    """
    return os.path.join(
        CACHE_DIR,
        f"{ticker.upper()}_{cik_for(ticker)}.json",
    )


def download_company_facts(ticker, refresh=False):
    """Download SEC company-facts data and cache it locally.

    Parameters
    ----------
    ticker:
        Stock ticker symbol.

    refresh:
        When False, return the existing cached file when available.

        When True, ignore the cache and request a fresh copy from the SEC.

    Returns
    -------
    dict
        The decoded SEC company-facts JSON response.

    Notes
    -----
    The SEC company-facts endpoint contains structured XBRL facts collected
    from a company's filings.

    Caching avoids downloading the same large JSON file every time an analysis
    script runs.
    """
    path = _cache_path(ticker)

    # Reuse the local file unless a fresh download was explicitly requested.
    if os.path.exists(path) and not refresh:
        with open(path) as file:
            return json.load(file)

    cik = cik_for(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    # Request the latest structured company-facts JSON.
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60,
    )

    # Raise an exception for HTTP errors such as 403, 404, or 500.
    response.raise_for_status()

    data = response.json()

    # Save the raw response so later scripts can work offline.
    with open(path, "w") as file:
        json.dump(data, file)

    # Pause briefly before another possible SEC request.
    time.sleep(0.3)

    return data


def load_facts(ticker):
    """Load cached company facts, downloading them on first use.

    Parameters
    ----------
    ticker:
        Stock ticker symbol.

    Returns
    -------
    dict
        The decoded SEC company-facts JSON.

    Notes
    -----
    This is the normal entry point for analysis scripts.

    If the cache file exists, no SEC request is made. If it does not exist,
    download_company_facts() creates it automatically.
    """
    path = _cache_path(ticker)

    if not os.path.exists(path):
        return download_company_facts(ticker)

    with open(path) as file:
        return json.load(file)


# ---------------------------------------------------------------------------
# Raw SEC facts -> clean time series
# ---------------------------------------------------------------------------

def _usd_facts(facts, tag):
    """Return USD observations for one US-GAAP XBRL tag.

    Parameters
    ----------
    facts:
        Full SEC company-facts dictionary.

    tag:
        US-GAAP concept name, such as:

            "Revenues"
            "OperatingIncomeLoss"
            "NetIncomeLoss"

    Returns
    -------
    list
        SEC fact observations reported in USD.

        An empty list is returned when the tag or USD unit is unavailable.

    Notes
    -----
    This helper intentionally handles missing tags quietly because different
    companies may use different XBRL concepts for similar financial metrics.
    """
    try:
        return facts["facts"]["us-gaap"][tag]["units"]["USD"]
    except KeyError:
        return []


def _days(fact):
    """Return the duration of a flow fact in days.

    Parameters
    ----------
    fact:
        One SEC fact containing ISO-formatted "start" and "end" dates.

    Returns
    -------
    int
        Number of days between the start and end dates.

    Notes
    -----
    Duration is used to classify an observation as approximately:

        - one quarter
        - nine months year-to-date
        - one full fiscal year
    """
    start = date.fromisoformat(fact["start"])
    end = date.fromisoformat(fact["end"])

    return (end - start).days


def _flow_one_tag(facts, tag):
    """Extract annual and quarterly series for one flow XBRL tag.

    Parameters
    ----------
    facts:
        Full SEC company-facts dictionary.

    tag:
        One flow-based US-GAAP tag, such as revenue, operating income, net
        income, or operating cash flow.

    Returns
    -------
    tuple
        Two dictionaries:

        annual_by_end:
            {fiscal_year_end_date: value}

        quarterly:
            {quarter_end_date: value}

    Notes
    -----
    Flow metrics cover a period of time, unlike balance-sheet values that
    represent one point in time.

    Approximate duration ranges are used:

        80-100 days:
            Standalone three-month quarter.

        250-295 days:
            Nine-month year-to-date period.

        350-380 days:
            Full fiscal year.

    Many annual filings do not separately report a three-month Q4 fact in the
    company-facts data. When possible, Q4 is derived as:

        Q4 = full fiscal year - first nine months
    """
    # Annual facts indexed by fiscal-year end date.
    annual_by_end = {}

    # Annual facts indexed by fiscal-year start date.
    #
    # This is needed to match the full-year value with the corresponding
    # nine-month year-to-date value when deriving Q4.
    annual_by_start = {}

    # Nine-month year-to-date facts indexed by fiscal-year start date.
    nine_month = {}

    # Standalone quarterly facts indexed by quarter-end date.
    quarterly = {}

    for fact in _usd_facts(facts, tag):
        # Flow facts should contain both a start and end date.
        #
        # Facts without a start date are normally instant balance-sheet values,
        # so they are ignored here.
        if "start" not in fact:
            continue

        duration = _days(fact)
        end = date.fromisoformat(fact["end"])
        start = fact["start"]

        if 80 <= duration <= 100:
            # Approximate three-month quarter.
            quarterly[end] = fact["val"]

        elif 250 <= duration <= 295:
            # Approximate nine-month year-to-date value.
            nine_month[start] = (
                end,
                fact["val"],
            )

        elif 350 <= duration <= 380:
            # Approximate full fiscal-year value.
            annual_by_end[end] = fact["val"]

            annual_by_start[start] = (
                end,
                fact["val"],
            )

    # Derive Q4 where the SEC facts contain:
    #
    #     full fiscal-year value
    #     first nine months year-to-date value
    #
    # and do not already contain a standalone quarter ending on the fiscal
    # year-end date.
    for start, (fiscal_year_end, fiscal_year_value) in annual_by_start.items():
        if fiscal_year_end in quarterly:
            continue

        if start in nine_month:
            _, nine_month_value = nine_month[start]

            quarterly[fiscal_year_end] = (
                fiscal_year_value - nine_month_value
            )

    return annual_by_end, quarterly


def flow_series(facts, tag_or_tags):
    """Build clean annual and quarterly series for one or more flow tags.

    Parameters
    ----------
    facts:
        Full SEC company-facts dictionary.

    tag_or_tags:
        Either one XBRL tag string or a list of candidate tag strings.

        Examples:
            "OperatingIncomeLoss"

            [
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            ]

    Returns
    -------
    tuple
        Two sorted dictionaries:

        annual:
            {period_end_date: value}

        quarterly:
            {period_end_date: value}

    Notes
    -----
    When multiple candidate tags are supplied, they are processed in order.

    setdefault() preserves the first value found for a reporting date. This
    allows preferred tags to take priority while older or alternative tags
    fill missing periods.
    """
    # Normalize one tag and a list of tags into the same list structure.
    tags = (
        [tag_or_tags]
        if isinstance(tag_or_tags, str)
        else list(tag_or_tags)
    )

    annual = {}
    quarterly = {}

    for tag in tags:
        tag_annual, tag_quarterly = _flow_one_tag(facts, tag)

        # Keep the first value already found for a date.
        for period_end, value in tag_annual.items():
            annual.setdefault(period_end, value)

        for period_end, value in tag_quarterly.items():
            quarterly.setdefault(period_end, value)

    # Sorting makes CSV output, charts, and later calculations deterministic.
    return (
        dict(sorted(annual.items())),
        dict(sorted(quarterly.items())),
    )


def instant_series(facts, tag_or_tags):
    """Build a point-in-time series for one or more XBRL tags.

    Parameters
    ----------
    facts:
        Full SEC company-facts dictionary.

    tag_or_tags:
        One XBRL tag or a list of candidate tags.

    Returns
    -------
    dict
        Sorted mapping of:

            {reporting_date: value}

    Notes
    -----
    Instant values describe the financial position at one date.

    Common examples include:

        - cash
        - debt
        - assets
        - liabilities
        - shares outstanding

    Facts that span a real period are ignored because those belong to flow
    metrics rather than point-in-time metrics.
    """
    tags = (
        [tag_or_tags]
        if isinstance(tag_or_tags, str)
        else list(tag_or_tags)
    )

    output = {}

    for tag in tags:
        for fact in _usd_facts(facts, tag):
            # Ignore values that represent a period rather than one instant.
            #
            # Some instant observations may include matching start and end
            # dates, so only unequal dates are rejected here.
            if "start" in fact and fact["start"] != fact["end"]:
                continue

            reporting_date = date.fromisoformat(fact["end"])

            # Preserve the first candidate-tag value found for the date.
            output.setdefault(
                reporting_date,
                fact["val"],
            )

    return dict(sorted(output.items()))


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def margin(numerator, denominator):
    """Calculate percentage margin for matching dates.

    Parameters
    ----------
    numerator:
        Mapping of dates to values, such as gross profit, operating income, or
        net income.

    denominator:
        Mapping of dates to values, normally revenue.

    Returns
    -------
    dict
        Mapping of dates to percentage margins.

        Example:
            42.5 means 42.5%, not 0.425.

    Formula
    -------
        margin = numerator / denominator * 100

    Notes
    -----
    A result is produced only when:

        - both series contain the same date
        - the denominator is not zero
    """
    return {
        period_end: numerator[period_end] / denominator[period_end] * 100
        for period_end in denominator
        if period_end in numerator and denominator[period_end]
    }


def yoy_growth(series):
    """Calculate year-over-year percentage growth.

    Parameters
    ----------
    series:
        Mapping of dates to financial values.

        The function works with both annual and quarterly series.

    Returns
    -------
    dict
        Mapping of current-period dates to YoY growth percentages.

    Formula
    -------
        YoY growth =
            (current value - prior-year value)
            / prior-year value
            * 100

    Notes
    -----
    A prior observation is treated as the comparable previous-year period when
    it falls approximately 350-380 days before the current observation.

    This tolerance supports fiscal calendars that do not contain exactly 365
    days between comparable reporting dates.

    The first available year normally has no growth result because no previous
    year exists for comparison.
    """
    dates = sorted(series)
    output = {}

    for current_date in dates:
        # Find observations approximately one year before the current date.
        prior_dates = [
            previous_date
            for previous_date in dates
            if 350 <= (current_date - previous_date).days <= 380
        ]

        # A growth rate cannot be calculated without a valid non-zero base.
        if prior_dates and series[prior_dates[-1]]:
            prior_date = prior_dates[-1]

            output[current_date] = (
                (series[current_date] - series[prior_date])
                / series[prior_date]
                * 100
            )

    return output


# ---------------------------------------------------------------------------
# CSV and chart output
# ---------------------------------------------------------------------------

def save_csv(fname, header, rows):
    """Save tabular output as a CSV file.

    Parameters
    ----------
    fname:
        Output filename, such as:

            "KO_annual_revenue_yoy.csv"

    header:
        Sequence containing the CSV column names.

    rows:
        Iterable containing the CSV data rows.

    Notes
    -----
    Files are written inside OUT_DIR.

    newline="" avoids extra blank rows on platforms where the csv module
    otherwise applies newline translation.
    """
    path = os.path.join(OUT_DIR, fname)

    with open(path, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(header)
        writer.writerows(rows)

    print(f"  wrote {path} ({len(rows)} rows)")


def plot_compare(
    data,
    title,
    ylabel,
    fname,
    kind="line",
    pct=False,
    billions=False,
):
    """Create and save a comparison chart.

    Parameters
    ----------
    data:
        Mapping of series labels to dated values.

        Expected structure:

            {
                "V": {
                    date(2023, 9, 30): 32653000000,
                    date(2024, 9, 30): 35926000000,
                },
                "MA": {
                    date(2023, 12, 31): 25098000000,
                    date(2024, 12, 31): 28167000000,
                },
            }

    title:
        Main chart title.

    ylabel:
        Y-axis label.

    fname:
        Output PNG filename.

    kind:
        Chart type.

        Supported behavior:
            "line":
                Draw line charts.

            "bar":
                Draw a bar chart only when data contains one series.

        When multiple series are supplied, lines are used for readability.

    pct:
        When True, format the y-axis as percentages.

    billions:
        When True, divide values by one billion before plotting.

    Returns
    -------
    None

    Notes
    -----
    The chart is saved into OUT_DIR.

    All unique reporting dates from all companies are placed onto one shared
    positional x-axis. This allows companies with different fiscal year-end
    dates to appear in the same chart.

    The function prints a message and exits cleanly when there is no data.
    """
    fig, ax = plt.subplots(figsize=(11, 5.6))

    # Reserve enough room for the title, labels, and legend.
    fig.subplots_adjust(
        left=0.09,
        right=0.97,
        top=0.86,
        bottom=0.12,
    )

    # Build one sorted set containing every reporting date used by any series.
    all_dates = sorted({
        reporting_date
        for series in data.values()
        for reporting_date in series
    })

    # Avoid creating an empty chart when none of the supplied series contain
    # usable data.
    if not all_dates:
        print(f"  (no data to plot for {fname})")
        plt.close(fig)
        return

    # Convert each date into a shared integer x-axis position.
    #
    # Example:
    #     2022-12-31 -> 0
    #     2023-09-30 -> 1
    #     2023-12-31 -> 2
    #
    # This allows companies with different fiscal calendars to share one chart.
    index_by_date = {
        reporting_date: index
        for index, reporting_date in enumerate(all_dates)
    }

    # Reusable chart palette.
    colors = [
        "#2563eb",
        "#dc2626",
        "#059669",
        "#d97706",
    ]

    for series_index, (label, series) in enumerate(data.items()):
        series_dates = sorted(series)

        # Translate reporting dates into shared x-axis positions.
        x_values = [
            index_by_date[reporting_date]
            for reporting_date in series_dates
        ]

        # Optionally convert large dollar values into billions.
        divisor = 1e9 if billions else 1

        y_values = [
            series[reporting_date] / divisor
            for reporting_date in series_dates
        ]

        color = colors[series_index % len(colors)]

        # Bar charts are used only for a single series. Multiple bar series can
        # become difficult to align when companies report on different dates.
        if kind == "bar" and len(data) == 1:
            ax.bar(
                x_values,
                y_values,
                color=color,
                width=0.85,
            )
        else:
            ax.plot(
                x_values,
                y_values,
                "-o",
                linewidth=2.2,
                markersize=4,
                color=color,
                label=label,
            )

    # Limit the number of visible date labels so long series remain readable.
    step = max(
        1,
        len(all_dates) // 8,
    )

    tick_positions = range(
        0,
        len(all_dates),
        step,
    )

    ax.set_xticks(tick_positions)

    # Show years rather than complete dates to keep the axis compact.
    ax.set_xticklabels([
        all_dates[index].year
        for index in tick_positions
    ])

    ax.set_ylabel(ylabel)

    if pct:
        # Values passed into the chart are already percentage points.
        # Example: 12.5 is displayed as 12%.
        ax.yaxis.set_major_formatter(
            lambda value, _: f"{value:.0f}%"
        )

    if len(data) > 1:
        ax.legend(frameon=False)

    # Use a figure-level title so it aligns consistently across charts.
    fig.suptitle(
        title,
        x=0.015,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )

    path = os.path.join(
        OUT_DIR,
        fname,
    )

    fig.savefig(
        path,
        facecolor="white",
    )

    # Closing the figure prevents memory buildup when several charts are made
    # in the same Python process.
    plt.close(fig)

    print(f"  wrote {path}")
