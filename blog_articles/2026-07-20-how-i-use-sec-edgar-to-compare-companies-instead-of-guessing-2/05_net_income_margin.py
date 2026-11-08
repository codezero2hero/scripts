"""
Extract annual and quarterly net income and calculate net margin.

This script loads cached SEC EDGAR company facts, extracts revenue and net
income, calculates net margin, and saves annual results to a CSV file.

It also compares the annual net margins of Apple and Microsoft on one chart.

Metrics produced:
    - Annual net income
    - Annual net margin
    - Quarterly net margin

Formula:
    net margin = net income / revenue * 100

Output:
    Annual CSV files are saved by save_csv(), normally into edgar_output/.

    The comparison chart is saved by plot_compare(), normally as:

        edgar_output/net_margin_annual.png

Important:
    Net income can be affected by taxes, impairments, investment gains,
    restructuring charges, and other one-time items. If a value looks unusual,
    check the original 10-K or 10-Q.
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
    """Build annual and quarterly net-margin series for one ticker.

    Parameters
    ----------
    t:
        Stock ticker symbol, such as "AAPL" or "MSFT".

    Returns
    -------
    tuple
        A tuple containing:

        - annual net-margin series
        - quarterly net-margin series

    Notes
    -----
    Revenue is extracted using REVENUE_TAGS because companies may use different
    XBRL concepts for revenue across companies or reporting periods.

    Net income is extracted using the US-GAAP tag:

        NetIncomeLoss

    Net margin is calculated only for dates where both revenue and net income
    are available.
    """
    # Load the cached SEC company-facts JSON for the selected ticker.
    # If it has not been cached yet, load_facts() may download it first.
    f = load_facts(t)

    # Extract annual and quarterly revenue series.
    rev_a, rev_q = flow_series(f, REVENUE_TAGS)

    # Extract annual and quarterly net-income series.
    ni_a, ni_q = flow_series(f, "NetIncomeLoss")

    # Calculate annual and quarterly net margins.
    #
    # The margin() helper returns percentage values, so 25.5 means 25.5%.
    nm_a, nm_q = margin(ni_a, rev_a), margin(ni_q, rev_q)

    # Save annual net income and net margin to a CSV file.
    #
    # If a net-margin value is unavailable for a date, NaN is written instead.
    save_csv(
        f"{t}_annual_net.csv",
        [
            "fiscal_year_end",
            "net_income_usd",
            "net_margin_pct",
        ],
        [
            [
                d,
                ni_a[d],
                round(nm_a.get(d, float("nan")), 2),
            ]
            for d in sorted(ni_a)
        ],
    )

    # Return both margin series so they can be reused for charts or additional
    # analysis without recalculating them.
    return nm_a, nm_q


if __name__ == "__main__":
    # Companies selected for the comparison.
    pair = ["AAPL", "MSFT"]

    # Build annual net-margin data for each company.
    #
    # build(t) returns:
    #     (annual net margin, quarterly net margin)
    #
    # [0] selects the annual series for this chart.
    data = {t: build(t)[0] for t in pair}

    # Plot both companies' annual net margins on the same chart.
    #
    # pct=True tells plot_compare() to format the y-axis as percentages.
    plot_compare(
        data,
        f"{pair[0]} vs {pair[1]}: net margin (annual)",
        "Net margin",
        "net_margin_annual.png",
        pct=True,
    )
