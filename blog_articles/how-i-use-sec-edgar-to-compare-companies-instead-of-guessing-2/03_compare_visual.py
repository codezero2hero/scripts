"""03_compare_visual.py

Step 3: Put two companies on the same chart.

This script compares two companies visually using SEC EDGAR company facts.

For Visa and Mastercard, operating margin is more useful than gross margin
because these payment-network businesses do not expose a clean GrossProfit
tag in the SEC structured data used by this toolkit.

It loads annual and quarterly revenue and operating income data, calculates
operating margin, and then creates comparison charts for:

    - Annual revenue
    - Annual operating margin
    - Quarterly operating margin

The goal is not to make an investment decision from the chart alone.
The goal is to make differences easier to see so I know what to investigate
in the filings.

Output:
    The generated PNG charts are saved by plot_compare(), normally into the
    edgar_output/ folder depending on how edgar_utils.py is configured.
"""

from edgar_utils import load_facts, flow_series, REVENUE_TAGS, margin, plot_compare


# Companies to compare.
# V = Visa
# MA = Mastercard
A, B = "V", "MA"


def rev_and_operating_margin(t):
    """Return revenue and operating margin series for one ticker.

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
        - annual operating margin series
        - quarterly operating margin series

    Notes
    -----
    Revenue is pulled using REVENUE_TAGS because different companies may use
    different XBRL tags for revenue.

    Operating margin is calculated as:

        operating margin = operating income / revenue

    For Visa and Mastercard, this is usually more practical than gross margin
    because GrossProfit may not be available as a clean structured SEC tag.
    """
    # Load cached SEC company facts for the selected ticker.
    f = load_facts(t)

    # Extract annual and quarterly revenue.
    rev_a, rev_q = flow_series(f, REVENUE_TAGS)

    # Extract annual and quarterly operating income.
    op_a, op_q = flow_series(f, "OperatingIncomeLoss")

    # Return revenue plus calculated operating margins.
    return rev_a, rev_q, margin(op_a, rev_a), margin(op_q, rev_q)


if __name__ == "__main__":
    # Dictionaries keyed by ticker.
    # Example:
    #   ra["V"] = annual revenue series for Visa
    #   oma["MA"] = annual operating margin series for Mastercard
    ra, rq, oma, omq = {}, {}, {}, {}

    # Build revenue and operating margin series for both companies.
    for t in (A, B):
        ra[t], rq[t], oma[t], omq[t] = rev_and_operating_margin(t)

    # Compare annual revenue.
    # billions=True tells plot_compare to display large revenue numbers in $B.
    plot_compare(ra, f"{A} vs {B}: annual revenue", "Revenue ($B)",
                 f"{A}_{B}_annual_revenue.png", billions=True)

    # Compare annual operating margin.
    # pct=True tells plot_compare to format values as percentages.
    plot_compare(oma, f"{A} vs {B}: annual operating margin", "Operating margin",
                 f"{A}_{B}_annual_operatingmargin.png", pct=True)

    # Compare quarterly operating margin.
    # This can reveal whether operating profitability is stable or changing recently.
    plot_compare(omq, f"{A} vs {B}: quarterly operating margin", "Operating margin",
                 f"{A}_{B}_quarterly_operatingmargin.png", pct=True)
