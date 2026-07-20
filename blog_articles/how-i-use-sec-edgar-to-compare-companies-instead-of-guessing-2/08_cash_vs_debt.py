"""08_cash_vs_debt.py

Step 6: Compare cash and estimated debt using balance-sheet snapshots.

This script loads cached SEC EDGAR company facts, extracts point-in-time cash,
long-term debt, and current debt values, combines the debt components into a
best-effort total-debt estimate, saves the results to CSV, and creates a
cash-versus-debt chart for each company.

Metrics produced:
    - Cash and cash equivalents
    - Estimated long-term debt
    - Estimated current debt
    - Estimated total debt

Formula:
    estimated total debt = long-term debt + current debt

Output:
    CSV files are saved by save_csv(), normally into edgar_output/.

    One chart is created per company, normally as:

        edgar_output/AAPL_cash_vs_debt.png
        edgar_output/MSFT_cash_vs_debt.png

Warning:
    Debt tagging in XBRL is inconsistent across companies.

    The total_debt_est value produced here is a best-effort estimate, not a
    guaranteed accounting total. Always confirm important debt values against
    the balance sheet and debt footnotes in the original 10-K or 10-Q.
"""

from edgar_utils import load_facts, instant_series, save_csv, plot_compare


# Candidate tag for cash and cash equivalents.
#
# Some companies may also report restricted cash or broader cash-related
# concepts under different tags, so this is intentionally a simple starting
# point rather than a complete liquidity calculation.
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
]

# Candidate tags for noncurrent or long-term debt.
#
# The tags are tried in order, and instant_series() keeps the first value found
# for each reporting date.
LONG_TERM_DEBT_TAGS = [
    "LongTermDebtNoncurrent",
    "LongTermDebt",
]

# Candidate tags for debt due within one year.
CURRENT_DEBT_TAGS = [
    "LongTermDebtCurrent",
    "DebtCurrent",
]


def build(t):
    """Build cash and estimated total-debt series for one ticker.

    Parameters
    ----------
    t:
        Stock ticker symbol, such as "AAPL" or "MSFT".

    Returns
    -------
    tuple
        A tuple containing:

        - cash series
        - estimated total-debt series

    Notes
    -----
    Cash and debt are balance-sheet values, so they are extracted with
    instant_series() rather than flow_series().

    The debt estimate is calculated as:

        long-term debt + current debt

    A missing component is treated as zero for the calculation. This keeps the
    series usable, but missing structured data does not necessarily mean that
    the company had no debt in that category.
    """
    # Load the cached SEC company-facts JSON for the selected ticker.
    # If the cache does not exist yet, load_facts() may download it first.
    f = load_facts(t)

    # Extract cash and cash-equivalent balances by reporting date.
    cash = instant_series(f, CASH_TAGS)

    # Extract noncurrent or long-term debt balances.
    lt = instant_series(f, LONG_TERM_DEBT_TAGS)

    # Extract current debt balances.
    cur = instant_series(f, CURRENT_DEBT_TAGS)

    # Combine every date present in either debt series.
    #
    # Missing debt components are treated as zero. For example, when a date has
    # long-term debt but no current-debt tag, the estimate uses only long-term
    # debt for that date.
    debt = {
        d: lt.get(d, 0) + cur.get(d, 0)
        for d in (set(lt) | set(cur))
    }

    # Sort the debt series chronologically for predictable CSV and chart output.
    debt = dict(sorted(debt.items()))

    # Save one row for every date present in either the cash or debt series.
    #
    # Blank cells reveal dates where one side of the comparison is unavailable.
    save_csv(
        f"{t}_cash_vs_debt.csv",
        [
            "period_end",
            "cash_usd",
            "total_debt_est_usd",
        ],
        [
            [
                d,
                cash.get(d, ""),
                debt.get(d, ""),
            ]
            for d in sorted(set(cash) | set(debt))
        ],
    )

    # Return both series so they can be charted or reused elsewhere.
    return cash, debt


if __name__ == "__main__":
    # Generate separate cash-versus-debt outputs for Apple and Microsoft.
    for t in ["AAPL", "MSFT"]:
        # Build the point-in-time cash and estimated debt series.
        cash, debt = build(t)

        # Plot cash and estimated debt on the same chart.
        #
        # billions=True converts the raw USD values into billions for display.
        plot_compare(
            {
                f"{t} cash": cash,
                f"{t} debt (est.)": debt,
            },
            f"{t}: cash vs estimated total debt",
            "$B",
            f"{t}_cash_vs_debt.png",
            billions=True,
        )
