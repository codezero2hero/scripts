"""
Valuation sensitivity example for my article:

"The Macro Map: How Interest Rates Changed the Way I Value Stocks"

This script values a hypothetical business expected to generate:
- $10 of cash flow per year for the next 10 years
- A terminal value of $150 at the end of year 10

It compares the estimated value using required returns of 5% and 8%.

Disclaimer:
This is an educational example only, not investment advice.
"""


def present_value(future_cash_flow: float, required_return: float, years: int) -> float:
    """Calculate the present value of one future cash flow."""
    if future_cash_flow < 0:
        raise ValueError("Future cash flow cannot be negative.")
    if required_return <= -1:
        raise ValueError("Required return must be greater than -100%.")
    if years < 0:
        raise ValueError("Years cannot be negative.")

    return future_cash_flow / (1 + required_return) ** years


def value_annual_cash_flows(
        annual_cash_flow: float,
        required_return: float,
        years: int,
) -> float:
    """Calculate the present value of equal annual cash flows."""
    return sum(
        present_value(annual_cash_flow, required_return, year)
        for year in range(1, years + 1)
    )


def value_business(
        annual_cash_flow: float,
        terminal_value: float,
        required_return: float,
        years: int,
) -> dict[str, float]:
    """Calculate each part of the hypothetical business valuation."""
    cash_flows_pv = value_annual_cash_flows(
        annual_cash_flow=annual_cash_flow,
        required_return=required_return,
        years=years,
    )

    terminal_value_pv = present_value(
        future_cash_flow=terminal_value,
        required_return=required_return,
        years=years,
    )

    return {
        "cash_flows_pv": cash_flows_pv,
        "terminal_value_pv": terminal_value_pv,
        "total_value": cash_flows_pv + terminal_value_pv,
    }


def main() -> None:
    annual_cash_flow = 10.00
    terminal_value = 150.00
    years = 10

    value_at_5_percent = value_business(
        annual_cash_flow=annual_cash_flow,
        terminal_value=terminal_value,
        required_return=0.05,
        years=years,
    )

    value_at_8_percent = value_business(
        annual_cash_flow=annual_cash_flow,
        terminal_value=terminal_value,
        required_return=0.08,
        years=years,
    )

    rows = [
        (
            "PV of $10 annual cash flows for 10 years",
            value_at_5_percent["cash_flows_pv"],
            value_at_8_percent["cash_flows_pv"],
        ),
        (
            "PV of $150 terminal value in year 10",
            value_at_5_percent["terminal_value_pv"],
            value_at_8_percent["terminal_value_pv"],
        ),
        (
            "Estimated value today",
            value_at_5_percent["total_value"],
            value_at_8_percent["total_value"],
        ),
    ]

    print("Valuation Sensitivity: Same Business, Different Required Returns")
    print("=" * 79)
    print(f"{'Part of valuation':<43}{'At 5%':>12}{'At 8%':>12}{'Change':>12}")
    print("-" * 79)

    for label, value_5, value_8 in rows:
        change = value_8 - value_5
        print(f"{label:<43}${value_5:>10,.2f}${value_8:>10,.2f}${change:>10,.2f}")

    decline = (
            value_at_5_percent["total_value"]
            - value_at_8_percent["total_value"]
    )
    percentage_decline = decline / value_at_5_percent["total_value"]

    print("=" * 79)
    print()
    print(
        f"When the required return rises from 5% to 8%, "
        f"the estimated value falls by ${decline:,.2f}, "
        f"or {percentage_decline:.1%}."
    )


if __name__ == "__main__":
    main()
