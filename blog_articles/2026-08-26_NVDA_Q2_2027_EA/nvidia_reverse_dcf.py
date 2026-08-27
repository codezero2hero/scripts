"""
NVIDIA Reverse Discounted Cash Flow (DCF) Valuation Model
This script performs a reverse DCF to determine the required revenue growth rates
and Free Cash Flow (FCF) margins necessary to justify a specific Target Enterprise Value.
It generates a sensitivity CSV and multiple visualizations using Matplotlib.
"""

from pathlib import Path
import csv
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

# =========================
# CONFIGURATION
# =========================
# Core financial assumptions (Values in Billions USD where applicable)
STARTING_REVENUE_B = 432.0         # Current/Run-rate revenue in billions
TARGET_ENTERPRISE_VALUE_B = 5000.0 # Target EV to justify (e.g., $5 Trillion)
FORECAST_YEARS = 5                 # Explicit forecast period
WACC = 0.09                        # Weighted Average Cost of Capital (Discount Rate)
TERMINAL_GROWTH = 0.035            # Perpetual growth rate after the forecast period

# Sensitivity analysis parameters
FCF_MARGINS = [0.40, 0.45, 0.50, 0.55, 0.60]
GROWTH_RATES = [0.00, 0.05, 0.10, 0.15, 0.20]

# Pre-defined illustrative scenarios
SCENARIOS = {
    "Bear": {"revenue_cagr": 0.05, "fcf_margin": 0.45},
    "Base": {"revenue_cagr": 0.10, "fcf_margin": 0.50},
    "Bull": {"revenue_cagr": 0.15, "fcf_margin": 0.55},
}

# Output directory for CSVs and charts
OUTPUT_DIR = Path("nvidia_reverse_dcf_output")

# =========================
# VISUAL STYLE
# =========================
# Defined color palette for charts
BG = "#E9EEF5"          # Background color
PANEL = "#E9EEF5"       # Panel/Axis face color
TEXT = "#182230"        # Standard text color
MUTED = "#667085"       # Muted text/axis lines
GRID = "#C7D0DC"        # Gridline color

BASE = "#8EA1B5"        # Neutral bar/line color
ACCENT = "#76B900"      # Primary accent (NVIDIA Green)
ACCENT_2 = "#2F6BFF"    # Secondary accent (Blue)
WARNING = "#F0A500"     # Warning/Mid-tier color
BEAR = "#B65B5B"        # Negative/Bear-tier color

FIGSIZE = (12, 6.75)    # Standard figure dimensions
DPI = 220               # High-resolution output


def style_axes(fig, ax):
    """Applies standardized aesthetic formatting to matplotlib axes."""
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    # Remove standard borders for a cleaner look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    # Clean up tick marks
    ax.tick_params(axis="x", length=0, colors=TEXT)
    ax.tick_params(axis="y", length=0, colors=MUTED)

    # Add subtle horizontal gridlines
    ax.grid(axis="y", color=GRID, alpha=0.65, linewidth=0.8)
    ax.set_axisbelow(True)


def title_block(fig, title, subtitle):
    """Adds a standard title and subtitle block to the top left of the figure."""
    fig.text(
        0.065, 0.935, title,
        ha="left", va="top",
        fontsize=22, fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.065, 0.878, subtitle,
        ha="left", va="top",
        fontsize=11, color=MUTED,
    )


def footer(fig):
    """Adds a footer containing the baseline financial assumptions."""
    fig.text(
        0.065, 0.035,
        (
            f"Starting revenue: ${STARTING_REVENUE_B:.0f}B  |  "
            f"Target EV: ${TARGET_ENTERPRISE_VALUE_B / 1000:.2f}T  |  "
            f"WACC: {WACC * 100:.1f}%  |  "
            f"Terminal growth: {TERMINAL_GROWTH * 100:.1f}%  |  "
            f"Forecast: {FORECAST_YEARS} years"
        ),
        ha="left", va="bottom",
        fontsize=8.5, color=MUTED,
    )


def pct(value):
    """Formats a float as a percentage string with 1 decimal place."""
    return f"{value * 100:.1f}%"


def money_trillion(value_b):
    """Converts billions to trillions and formats as a currency string."""
    return f"${value_b / 1000.0:.2f}T"


# =========================
# DCF ENGINE
# =========================
def dcf_enterprise_value(
    starting_revenue_b,
    revenue_cagr,
    fcf_margin,
    years,
    wacc,
    terminal_growth,
):
    """
    Calculates the Enterprise Value using a standard two-stage DCF model.
    Returns a dictionary of calculated valuation metrics.
    """
    # Gordon Growth Model constraint validation
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth.")

    revenue = starting_revenue_b
    pv_explicit_fcf = 0.0

    # Stage 1: Explicit forecast period
    for year in range(1, years + 1):
        revenue *= 1.0 + revenue_cagr
        fcf = revenue * fcf_margin
        pv_explicit_fcf += fcf / ((1.0 + wacc) ** year)

    # Stage 2: Terminal value using the Gordon Growth Model
    terminal_fcf = revenue * (1.0 + terminal_growth) * fcf_margin
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal_value = terminal_value / ((1.0 + wacc) ** years)

    # Total Enterprise Value
    enterprise_value = pv_explicit_fcf + pv_terminal_value

    return {
        "enterprise_value_b": enterprise_value,
        "pv_explicit_fcf_b": pv_explicit_fcf,
        "pv_terminal_value_b": pv_terminal_value,
        "terminal_value_pct": pv_terminal_value / enterprise_value * 100.0,
        "year_n_revenue_b": revenue,
        "year_n_fcf_b": revenue * fcf_margin,
    }


def solve_required_growth(
    target_ev_b,
    starting_revenue_b,
    fcf_margin,
    years,
    wacc,
    terminal_growth,
    lower_bound=-0.25,
    upper_bound=1.00,
    tolerance=1e-8,
    max_iterations=500,
):
    """
    Uses a binary search algorithm to find the required revenue CAGR 
    that results in the given Target Enterprise Value.
    Returns the required CAGR, or None if it falls outside bounds.
    """
    def valuation(growth):
        # Helper function to get EV for a given growth rate
        return dcf_enterprise_value(
            starting_revenue_b,
            growth,
            fcf_margin,
            years,
            wacc,
            terminal_growth,
        )["enterprise_value_b"]

    low_value = valuation(lower_bound)
    high_value = valuation(upper_bound)

    # Check if target is achievable within bounds
    if target_ev_b < low_value or target_ev_b > high_value:
        return None

    low, high = lower_bound, upper_bound

    # Binary search loop (works because EV increases monotonically with growth)
    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        mid_value = valuation(mid)

        if abs(mid_value - target_ev_b) < tolerance:
            return mid

        if mid_value < target_ev_b:
            low = mid  # Need higher growth
        else:
            high = mid # Need lower growth

    return (low + high) / 2.0


# =========================
# MODEL DATA
# =========================
def build_required_growths():
    """Generates required growth rates for each defined FCF margin to hit Target EV."""
    return {
        margin: solve_required_growth(
            TARGET_ENTERPRISE_VALUE_B,
            STARTING_REVENUE_B,
            margin,
            FORECAST_YEARS,
            WACC,
            TERMINAL_GROWTH,
        )
        for margin in FCF_MARGINS
    }


def build_sensitivity_matrix():
    """Builds a 2D numpy array of Enterprise Values for combinations of growth & margin."""
    rows = []
    for growth in GROWTH_RATES:
        row = []
        for margin in FCF_MARGINS:
            row.append(
                dcf_enterprise_value(
                    STARTING_REVENUE_B,
                    growth,
                    margin,
                    FORECAST_YEARS,
                    WACC,
                    TERMINAL_GROWTH,
                )["enterprise_value_b"]
            )
        rows.append(row)
    return np.array(rows)


def save_sensitivity_csv(matrix):
    """Saves the sensitivity matrix to a formatted CSV file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "reverse_dcf_sensitivity.csv"

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write header row with FCF margins
        writer.writerow(
            ["Revenue CAGR"] + [f"FCF margin {m * 100:.0f}%" for m in FCF_MARGINS]
        )

        # Write data rows with Growth rates
        for growth, row in zip(GROWTH_RATES, matrix):
            writer.writerow(
                [f"{growth * 100:.1f}%"] + [round(v, 2) for v in row]
            )

    return path


# =========================
# CHART 1
# =========================
def chart_required_growth(required_growths):
    """Plots a line chart showing how FCF margin affects required revenue growth."""
    margins, growths = [], []

    # Extract valid data points
    for margin, growth in required_growths.items():
        if growth is None:
            continue
        margins.append(margin * 100.0)
        growths.append(growth * 100.0)

    fig, ax = plt.subplots(figsize=FIGSIZE)
    style_axes(fig, ax)

    # Plot line with markers
    ax.plot(
        margins, growths,
        marker="o",
        markersize=8,
        linewidth=2.8,
        color=ACCENT_2,
    )
    
    # Add subtle shading under the line
    ax.fill_between(
        margins, growths,
        min(growths) - 1.5,
        color=ACCENT_2,
        alpha=0.08,
    )

    # Annotate specific data points
    for x, y in zip(margins, growths):
        ax.annotate(
            f"{y:.1f}%",
            (x, y),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=11,
            fontweight="bold",
            color=TEXT,
        )

    ax.set_xlabel("Sustainable FCF margin", color=MUTED)
    ax.set_ylabel("Required 5-year revenue CAGR", color=MUTED)
    ax.set_xticks(margins)
    
    # Format axes as percentages
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))

    title_block(
        fig,
        "What revenue growth does a $5T valuation require?",
        "Higher sustainable FCF margins reduce the growth NVIDIA must deliver.",
    )
    footer(fig)

    fig.subplots_adjust(left=0.08, right=0.96, top=0.78, bottom=0.16)

    path = OUTPUT_DIR / "01_required_growth_vs_fcf_margin.png"
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path


# =========================
# CHART 2
# =========================
def chart_valuation_vs_growth():
    """Plots valuation curves across continuous growth rates for different FCF margins."""
    growth_grid = np.linspace(0.0, 0.20, 81) # Granular growth rates for smooth lines

    fig, ax = plt.subplots(figsize=FIGSIZE)
    style_axes(fig, ax)

    line_colors = [BEAR, WARNING, BASE, ACCENT_2, ACCENT]

    # Plot a curve for each margin assumption
    for margin, color in zip(FCF_MARGINS, line_colors):
        values = []

        for growth in growth_grid:
            result = dcf_enterprise_value(
                STARTING_REVENUE_B,
                growth,
                margin,
                FORECAST_YEARS,
                WACC,
                TERMINAL_GROWTH,
            )
            values.append(result["enterprise_value_b"] / 1000.0) # Convert EV to Trillions

        ax.plot(
            growth_grid * 100.0,
            values,
            linewidth=2.4,
            color=color,
            label=f"{margin * 100:.0f}% FCF margin",
        )

    # Target valuation benchmark line
    ax.axhline(
        TARGET_ENTERPRISE_VALUE_B / 1000.0,
        linestyle="--",
        linewidth=1.5,
        color=TEXT,
        alpha=0.70,
        label="Target EV",
    )

    ax.set_xlabel("5-year revenue CAGR", color=MUTED)
    ax.set_ylabel("Enterprise value", color=MUTED)

    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"${y:.1f}T"))

    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=TEXT)

    title_block(
        fig,
        "NVIDIA valuation sensitivity",
        "The same growth rate produces very different values depending on sustainable FCF margins.",
    )
    footer(fig)

    fig.subplots_adjust(left=0.08, right=0.96, top=0.78, bottom=0.16)

    path = OUTPUT_DIR / "02_valuation_vs_growth.png"
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path


# =========================
# CHART 3
# =========================
def chart_scenarios():
    """Generates a bar chart comparing Bear, Base, and Bull scenario valuations."""
    names, values, terminal_pcts = [], [], []

    print()
    print("SCENARIOS")
    print("-" * 78)

    # Calculate valuation for each predefined scenario
    for name, assumptions in SCENARIOS.items():
        result = dcf_enterprise_value(
            STARTING_REVENUE_B,
            assumptions["revenue_cagr"],
            assumptions["fcf_margin"],
            FORECAST_YEARS,
            WACC,
            TERMINAL_GROWTH,
        )

        names.append(name)
        values.append(result["enterprise_value_b"] / 1000.0) # EV in Trillions
        terminal_pcts.append(result["terminal_value_pct"])

        # Console reporting for scenarios
        print(
            f"{name:>5}: "
            f"growth={pct(assumptions['revenue_cagr'])}, "
            f"FCF margin={pct(assumptions['fcf_margin'])}, "
            f"EV={money_trillion(result['enterprise_value_b'])}, "
            f"terminal={result['terminal_value_pct']:.1f}% of EV"
        )

    fig, ax = plt.subplots(figsize=FIGSIZE)
    style_axes(fig, ax)

    colors = [BEAR, BASE, ACCENT]
    bars = ax.bar(names, values, width=0.54, color=colors, edgecolor="none")

    # Annotate bars with EV totals and assumption details
    for idx, (bar, value, terminal_pct) in enumerate(
        zip(bars, values, terminal_pcts)
    ):
        # Top label (Total EV)
        ax.annotate(
            f"${value:.2f}T",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=13,
            fontweight="bold",
            color=TEXT,
        )

        # Inside bar label (Assumptions)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            max(value * 0.52, 0.35), # Keep text vertically centered
            (
                f"{SCENARIOS[names[idx]]['revenue_cagr'] * 100:.0f}% growth\n"
                f"{SCENARIOS[names[idx]]['fcf_margin'] * 100:.0f}% FCF margin\n"
                f"{terminal_pct:.0f}% terminal"
            ),
            ha="center",
            va="center",
            fontsize=9,
            color="white",
            fontweight="bold",
        )

    # Target valuation line
    ax.axhline(
        TARGET_ENTERPRISE_VALUE_B / 1000.0,
        linestyle="--",
        linewidth=1.4,
        color=TEXT,
        alpha=0.65,
    )

    ax.set_ylabel("Enterprise value", color=MUTED)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"${y:.1f}T"))

    title_block(
        fig,
        "Illustrative NVIDIA DCF scenarios",
        "The valuation outcome depends as much on sustainable margins as on growth.",
    )
    footer(fig)

    fig.subplots_adjust(left=0.08, right=0.96, top=0.78, bottom=0.16)

    path = OUTPUT_DIR / "03_scenarios.png"
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path


# =========================
# CHART 4 — REVERSE DCF
# =========================
def chart_reverse_dcf(required_growths):
    """Creates a dual-axis chart showing both implied revenue (bars) and required CAGR (line)."""
    margins, required_cagrs, implied_revenues = [], [], []

    # Compile data based on the reverse DCF calculations
    for margin, growth in required_growths.items():
        if growth is None:
            continue

        margins.append(margin * 100.0)
        required_cagrs.append(growth * 100.0)
        
        # Calculate Future Revenue = Current Revenue * (1+g)^t
        implied_revenues.append(
            STARTING_REVENUE_B * ((1.0 + growth) ** FORECAST_YEARS)
        )

    x = np.arange(len(margins))

    fig, ax1 = plt.subplots(figsize=FIGSIZE)
    style_axes(fig, ax1)

    # Highlight 50% margin bar with accent color
    bar_colors = [BASE] * len(margins)
    if 50.0 in margins:
        bar_colors[margins.index(50.0)] = ACCENT

    # Primary Axis: Implied Revenue Bars
    bars = ax1.bar(
        x,
        implied_revenues,
        width=0.58,
        color=bar_colors,
        edgecolor="none",
    )

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{margin:.0f}% FCF" for margin in margins])

    ax1.set_ylabel(
        f"Implied Year-{FORECAST_YEARS} revenue",
        color=MUTED,
    )
    ax1.yaxis.set_major_formatter(
        FuncFormatter(lambda y, _: f"${y:.0f}B")
    )

    # Annotate bars with revenue totals
    for bar, revenue_b in zip(bars, implied_revenues):
        ax1.annotate(
            f"${revenue_b:,.0f}B",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=11,
            fontweight="bold",
            color=TEXT,
        )

    # Secondary Axis: Required CAGR Line
    ax2 = ax1.twinx()
    ax2.set_facecolor("none")

    ax2.plot(
        x,
        required_cagrs,
        marker="o",
        markersize=8,
        linewidth=2.6,
        color=ACCENT_2,
    )

    # Clean up right-side spine for the secondary axis
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(GRID)
    ax2.tick_params(axis="y", length=0, colors=MUTED)

    ax2.set_ylabel(
        "Required revenue CAGR",
        color=MUTED,
    )
    ax2.yaxis.set_major_formatter(
        FuncFormatter(lambda y, _: f"{y:.0f}%")
    )

    # Annotate line markers with growth rates
    for idx, cagr in enumerate(required_cagrs):
        ax2.annotate(
            f"{cagr:.1f}%",
            (idx, cagr),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color=ACCENT_2,
        )

    title_block(
        fig,
        "Reverse DCF: what must NVIDIA become?",
        (
            f"Each bar shows the Year-{FORECAST_YEARS} revenue required "
            f"to justify a ${TARGET_ENTERPRISE_VALUE_B / 1000:.1f}T EV "
            "at a different sustainable FCF margin."
        ),
    )
    footer(fig)

    fig.subplots_adjust(left=0.08, right=0.92, top=0.78, bottom=0.16)

    path = OUTPUT_DIR / "04_reverse_dcf.png"
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path


# =========================
# CONSOLE SUMMARY
# =========================
def print_summary(required_growths, matrix):
    """Prints a formatted text summary of the analysis to the terminal."""
    print("=" * 78)
    print("NVIDIA REVERSE DCF")
    print("=" * 78)

    print(f"Starting revenue run-rate : ${STARTING_REVENUE_B:,.1f}B")
    print(f"Target enterprise value   : {money_trillion(TARGET_ENTERPRISE_VALUE_B)}")
    print(f"Forecast period           : {FORECAST_YEARS} years")
    print(f"WACC                      : {pct(WACC)}")
    print(f"Terminal growth           : {pct(TERMINAL_GROWTH)}")

    print()
    print("REQUIRED REVENUE CAGR")
    print("-" * 78)

    for margin, growth in required_growths.items():
        if growth is None:
            continue

        ending_revenue = (
            STARTING_REVENUE_B
            * ((1.0 + growth) ** FORECAST_YEARS)
        )

        print(
            f"{margin * 100:>5.0f}% FCF margin -> "
            f"{growth * 100:>5.1f}% required CAGR -> "
            f"${ending_revenue:,.0f}B Year-{FORECAST_YEARS} revenue"
        )

    print()
    print("ENTERPRISE VALUE SENSITIVITY ($T)")
    print("-" * 78)

    # Print Table Header
    header = "Growth".ljust(10)
    for margin in FCF_MARGINS:
        header += f"{margin * 100:>10.0f}% FCF"
    print(header)

    # Print Table Rows
    for growth, row in zip(GROWTH_RATES, matrix):
        line = f"{growth * 100:.0f}%".ljust(10)
        for value in row:
            line += f"{value / 1000:>10.2f}"
        print(line)


# =========================
# MAIN
# =========================
def main():
    """Main execution block. Generates data, prints summary, and saves outputs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Run core calculations
    required_growths = build_required_growths()
    matrix = build_sensitivity_matrix()

    # Output to console
    print_summary(required_growths, matrix)

    # Generate and save exports
    csv_path = save_sensitivity_csv(matrix)
    chart1 = chart_required_growth(required_growths)
    chart2 = chart_valuation_vs_growth()
    chart3 = chart_scenarios()
    chart4 = chart_reverse_dcf(required_growths)

    # Log file locations
    print()
    print("=" * 78)
    print("OUTPUT")
    print("=" * 78)
    print(csv_path)
    print(chart1)
    print(chart2)
    print(chart3)
    print(chart4)


if __name__ == "__main__":
    main()
