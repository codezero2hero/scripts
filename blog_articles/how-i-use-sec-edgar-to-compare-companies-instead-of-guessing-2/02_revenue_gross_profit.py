"""02_revenue_gross_profit.py

Steps 2 & 3: Extract revenue, gross profit, and gross margin from SEC EDGAR data.

This script reads cached SEC company facts for each ticker, extracts both annual
and quarterly revenue/gross profit series, calculates gross margin, and saves the
results into CSV files.

Outputs per ticker:
    - <TICKER>_annual_revenue_grossmargin.csv
    - <TICKER>_quarterly_revenue_grossmargin.csv

Important:
    The numbers come from SEC XBRL tags. Different companies may use different
    tags, especially for revenue. Always validate important numbers against the
    original 10-K or 10-Q filing.
"""

from typing import Dict, Tuple

from edgar_utils import (
    REVENUE_TAGS,
    flow_series,
    load_facts,
    margin,
    save_csv,
)


# Type alias for readability.
# Example:
#   {"2024-09-28": 391035000000}
FinancialSeries = Dict[str, float]


def build(ticker: str) -> Tuple[FinancialSeries, FinancialSeries, FinancialSeries, FinancialSeries]:
    """Build annual and quarterly revenue/gross margin CSVs for one ticker.

    Parameters
    ----------
    ticker:
        Stock ticker symbol, for example "V" for Visa or "MA" for Mastercard.

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
    Gross margin is calculated as:

        gross margin = gross profit / revenue

    The `margin()` helper is expected to return the margin as a percentage or
    ratio depending on how it is implemented in `edgar_utils`. Check that helper
    before labeling the output as `_pct`.
    """
    # Load cached SEC company facts for the ticker.
    facts = load_facts(ticker)

    # Extract annual and quarterly revenue.
    # REVENUE_TAGS is a list of possible revenue tags because companies do not
    # always use the exact same XBRL tag.
    annual_revenue, quarterly_revenue = flow_series(facts, REVENUE_TAGS)

    # Extract annual and quarterly gross profit.
    annual_gross_profit, quarterly_gross_profit = flow_series(facts, "GrossProfit")

    # Calculate gross margin for annual and quarterly periods.
    annual_gross_margin = margin(annual_gross_profit, annual_revenue)
    quarterly_gross_margin = margin(quarterly_gross_profit, quarterly_revenue)

    # Save annual results.
    # If gross profit is missing for a date, keep the cell blank.
    # If gross margin is missing, NaN is used and rounded.
    save_csv(
        f"{ticker}_annual_revenue_grossmargin.csv",
        [
            "fiscal_year_end",
            "revenue_usd",
            "gross_profit_usd",
            "gross_margin_pct",
        ],
        [
            [
                date,
                annual_revenue[date],
                annual_gross_profit.get(date, ""),
                round(annual_gross_margin.get(date, float("nan")), 2),
            ]
            for date in sorted(annual_revenue)
        ],
    )

    # Save quarterly results.
    save_csv(
        f"{ticker}_quarterly_revenue_grossmargin.csv",
        [
            "quarter_end",
            "revenue_usd",
            "gross_profit_usd",
            "gross_margin_pct",
        ],
        [
            [
                date,
                quarterly_revenue[date],
                quarterly_gross_profit.get(date, ""),
                round(quarterly_gross_margin.get(date, float("nan")), 2),
            ]
            for date in sorted(quarterly_revenue)
        ],
    )

    return (
        annual_revenue,
        quarterly_revenue,
        annual_gross_margin,
        quarterly_gross_margin,
    )


if __name__ == "__main__":
    # Example comparison set:
    for ticker_symbol in ["V", "MA"]:
        print(f"{ticker_symbol}:")
        build(ticker_symbol)
