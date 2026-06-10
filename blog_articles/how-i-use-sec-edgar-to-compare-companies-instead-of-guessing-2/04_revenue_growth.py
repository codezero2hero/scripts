"""04_revenue_growth.py

Step 2: Calculate year-over-year revenue growth, annual and quarterly.

This script compares revenue growth between two companies using SEC EDGAR
company facts.

It loads annual and quarterly revenue data, calculates year-over-year growth,
saves annual growth results to CSV, and creates comparison charts for:

    - Annual revenue growth
    - Quarterly revenue growth

Why this matters:
    Revenue tells me the size of the business.
    Revenue growth tells me whether the business is expanding, slowing down,
    or becoming more volatile.

Output:
    CSV files are saved with save_csv().
    PNG charts are saved by plot_compare(), normally into the edgar_output/
    folder depending on how edgar_utils.py is configured.
"""

from edgar_utils import load_facts, flow_series, REVENUE_TAGS, yoy_growth, save_csv, plot_compare


# Companies to compare.
# KO = Coca-Cola
# PEP = PepsiCo
A, B = "KO", "PEP"


def growth(t):
    """Return annual and quarterly year-over-year revenue growth for one ticker.

    Parameters
    ----------
    t:
        Stock ticker symbol, for example "KO" or "PEP".

    Returns
    -------
    tuple
        A tuple containing:

        - annual YoY revenue growth series
        - quarterly YoY revenue growth series

    Notes
    -----
    Revenue is pulled using REVENUE_TAGS because different companies may use
    different XBRL tags for revenue.

    Year-over-year growth compares a period with the same period one year
    earlier. This is often more useful than quarter-over-quarter comparison,
    especially for seasonal businesses.
    """
    # Load SEC company facts and extract annual/quarterly revenue.
    rev_a, rev_q = flow_series(load_facts(t), REVENUE_TAGS)

    # Calculate YoY growth for both annual and quarterly revenue series.
    return yoy_growth(rev_a), yoy_growth(rev_q)


if __name__ == "__main__":
    # Dictionaries keyed by ticker.
    # Example:
    #   ga["KO"] = annual YoY revenue growth for Coca-Cola
    #   gq["PEP"] = quarterly YoY revenue growth for PepsiCo
    ga, gq = {}, {}

    # Build YoY revenue growth series for both companies.
    for t in (A, B):
        ga[t], gq[t] = growth(t)

        # Save annual YoY revenue growth to CSV.
        # The quarterly series is charted below but not saved here.
        save_csv(f"{t}_annual_revenue_yoy.csv", ["fiscal_year_end", "yoy_growth_pct"],
                 [[d, round(ga[t][d], 2)] for d in sorted(ga[t])])

    # Compare annual YoY revenue growth.
    # pct=True tells plot_compare to format values as percentages.
    plot_compare(ga, f"{A} vs {B}: annual revenue growth (YoY)", "YoY growth",
                 f"{A}_{B}_annual_revenue_growth.png", pct=True)

    # Compare quarterly YoY revenue growth.
    # This can show whether recent growth is improving, weakening, or volatile.
    plot_compare(gq, f"{A} vs {B}: quarterly revenue growth (YoY)", "YoY growth",
                 f"{A}_{B}_quarterly_revenue_growth.png", pct=True)
