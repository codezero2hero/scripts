"""
Step 4: Extract operating income and calculate operating margin.

This script loads cached SEC EDGAR company facts, extracts revenue and
operating income, calculates operating margin, saves annual results to CSV,
and compares two companies on one annual operating-margin chart.

Metrics produced:
    - Annual operating income
    - Annual operating margin
    - Quarterly operating margin

Formula:
    operating margin = operating income / revenue * 100

Output:
    Annual CSV files are saved by save_csv(), normally into edgar_output/.

    The comparison chart is saved by plot_compare(), normally as:

        edgar_output/operating_margin_annual.png

Why this matters:
    Operating margin helps show how profitable the core business is before
    interest, taxes, and certain non-operating items.

Important:
    Operating income can still be affected by restructuring charges,
    impairments, business mix, accounting classifications, and unusual costs.
    If a value looks unexpected, check the original 10-K or 10-Q.
"""

from edgar_utils import (
    load_facts,
    flow_series,
    REVENUE_TAGS,
    margin,
    save_csv,
    plot_compare,
)


def build(t):
    """Build annual and quarterly operating-margin series for one ticker.

    Parameters
    ----------
    t:
        Stock ticker symbol, such as "AAPL" or "MSFT".

    Returns
    -------
    tuple
        A tuple containing:

        - annual operating-margin series
        - quarterly operating-margin series

    Notes
    -----
    Revenue is extracted using REVENUE_TAGS because companies may use
    different XBRL concepts for revenue across companies or reporting periods.

    Operating income is extracted using the US-GAAP tag:

        OperatingIncomeLoss

    Operating margin is calculated only for dates where both revenue and
    operating income are available.
    """
    # Load the cached SEC company-facts JSON for the selected ticker.
    # If no cached file exists yet, load_facts() may download it first.
    f = load_facts(t)

    # Extract annual and quarterly revenue series.
    rev_a, rev_q = flow_series(f, REVENUE_TAGS)

    # Extract annual and quarterly operating-income series.
    oi_a, oi_q = flow_series(f, "OperatingIncomeLoss")

    # Calculate annual and quarterly operating margins.
    #
    # The margin() helper returns percentage values, so 31.5 means 31.5%.
    om_a, om_q = margin(oi_a, rev_a), margin(oi_q, rev_q)

    # Save annual operating income and operating margin to CSV.
    #
    # If an operating-margin value is unavailable for a date, NaN is written.
    save_csv(
        f"{t}_annual_operating.csv",
        [
            "fiscal_year_end",
            "operating_income_usd",
            "operating_margin_pct",
        ],
        [
            [
                d,
                oi_a[d],
                round(om_a.get(d, float("nan")), 2),
            ]
            for d in sorted(oi_a)
        ],
    )

    # Return both margin series so they can be reused for charts or further
    # analysis without recalculating them.
    return om_a, om_q


if __name__ == "__main__":
    # Companies selected for the comparison.
    pair = ["AAPL", "MSFT"]

    # Build annual operating-margin data for each company.
    #
    # build(t) returns:
    #     (annual operating margin, quarterly operating margin)
    #
    # [0] selects the annual series used in this chart.
    data = {t: build(t)[0] for t in pair}

    # Plot both companies' annual operating margins on the same chart.
    #
    # pct=True tells plot_compare() to format the y-axis as percentages.
    plot_compare(
        data,
        f"{pair[0]} vs {pair[1]}: operating margin (annual)",
        "Operating margin",
        "operating_margin_annual.png",
        pct=True,
    )
