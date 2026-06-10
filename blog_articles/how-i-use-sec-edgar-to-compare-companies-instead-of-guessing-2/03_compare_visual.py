"""03_compare_visual.py

Step 3: Put two companies on the same chart.

This script compares two companies visually using SEC EDGAR company facts.

It loads annual and quarterly revenue and gross profit data, calculates gross
margin, and then creates comparison charts for:

    - Annual revenue
    - Annual gross margin
    - Quarterly gross margin

The goal is not to make an investment decision from the chart alone.
The goal is to make differences easier to see so I know what to investigate
in the filings.
"""

from edgar_utils import load_facts, flow_series, REVENUE_TAGS, margin, plot_compare


# Companies to compare.
# V = Visa
# MA = Mastercard
A, B = "V", "MA"


def rev_and_margin(t):
    """Return revenue and gross margin series for one ticker.

    Parameters
    ----------
    t:
        Stock ticker symbol, for example "V" or "MA".

    Returns
    -------
    tuple
        A tuple containing:

        - annual revenue series
        - quarterly revenue series
        - annual gross margin series
        - quarterly gross margin series

    Notes
    -----
    Revenue is pulled using REVENUE_TAGS because different companies may use
    different XBRL tags for revenue.

    Gross margin is calculated as:

        gross margin = gross profit / revenue
    """
    # Load cached SEC company facts for the selected ticker.
    f = load_facts(t)

    # Extract annual and quarterly revenue.
    rev_a, rev_q = flow_series(f, REVENUE_TAGS)

    # Extract annual and quarterly gross profit.
    gp_a, gp_q = flow_series(f, "GrossProfit")

    # Return revenue plus calculated gross margins.
    return rev_a, rev_q, margin(gp_a, rev_a), margin(gp_q, rev_q)


if __name__ == "__main__":
    # Dictionaries keyed by ticker.
    # Example:
    #   ra["V"] = annual revenue series for Visa
    #   ma["MA"] = annual gross margin series for Mastercard
    ra, rq, ma, mq = {}, {}, {}, {}

    # Build revenue and margin series for both companies.
    for t in (A, B):
        ra[t], rq[t], ma[t], mq[t] = rev_and_margin(t)

    # Compare annual revenue.
    # billions=True tells plot_compare to display large revenue numbers in $B.
    plot_compare(ra, f"{A} vs {B}: annual revenue", "Revenue ($B)",
                 f"{A}_{B}_annual_revenue.png", billions=True)

    # Compare annual gross margin.
    # pct=True tells plot_compare to format values as percentages.
    plot_compare(ma, f"{A} vs {B}: annual gross margin", "Gross margin",
                 f"{A}_{B}_annual_grossmargin.png", pct=True)

    # Compare quarterly gross margin.
    # This can reveal whether margin differences are stable or changing recently.
    plot_compare(mq, f"{A} vs {B}: quarterly gross margin", "Gross margin",
                 f"{A}_{B}_quarterly_grossmargin.png", pct=True)
