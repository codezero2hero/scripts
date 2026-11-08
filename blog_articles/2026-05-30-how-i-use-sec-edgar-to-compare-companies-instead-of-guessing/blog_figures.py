"""
Generate concept visuals for investing blog articles.

These charts use synthetic, stylised numbers for educational purposes.
They are NOT real company data and should not be interpreted as investment research.

The goal of this script is to create reusable blog figures that explain beginner
investing concepts visually, such as:

    1. Share price vs valuation
    2. Gross margin differences by industry
    3. Operating leverage
    4. Free cash flow
    5. Seasonality and year-over-year comparisons
    6. The danger of judging a company from one year of data

REQUIREMENTS:
    pip install matplotlib

OUTPUT:
    PNG files are saved into the "blog_figures" folder.

USAGE:
    python generate_blog_figures.py
"""

import os
from typing import Optional

import matplotlib

# Use the non-interactive backend so this script can run on servers,
# CI/CD pipelines, or headless environments without opening chart windows.
matplotlib.use("Agg")

import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------------

OUT = "blog_figures"
os.makedirs(OUT, exist_ok=True)

# Shared visual style for all blog charts.
# Keeping this centralized makes all figures look like part of the same series.
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.size": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})

# Brand/chart colors.
BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#059669"
AMBER = "#d97706"
MUTED = "#6b7280"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _title(fig: plt.Figure, text: str, sub: Optional[str] = None) -> None:
    """
    Add a consistent title and optional subtitle to a figure.

    Parameters
    ----------
    fig:
        The matplotlib Figure object.
    text:
        Main chart title.
    sub:
        Optional subtitle used to explain the chart's lesson.

    Notes
    -----
    The title is placed with fig.text instead of ax.set_title because many
    figures contain multiple subplots. Using fig.text keeps the layout consistent.
    """
    fig.text(
        0.015,
        0.96,
        text,
        fontsize=15,
        fontweight="bold",
        ha="left",
        va="top",
    )

    if sub:
        fig.text(
            0.015,
            0.895,
            sub,
            fontsize=10.5,
            color=MUTED,
            ha="left",
            va="top",
        )


def _illustrative(fig: plt.Figure) -> None:
    """
    Add a small disclaimer to the bottom-right corner of the chart.

    This protects the reader from mistaking synthetic concept data for real
    company data.
    """
    fig.text(
        0.985,
        0.015,
        "Illustrative, not real company data",
        fontsize=8.5,
        color=MUTED,
        ha="right",
    )


def save(fig: plt.Figure, name: str) -> None:
    """
    Save a matplotlib figure as a PNG file and close it.

    Parameters
    ----------
    fig:
        The matplotlib Figure object to save.
    name:
        File name to save inside the output folder.

    Notes
    -----
    Closing the figure prevents memory buildup when generating many charts.
    """
    path = os.path.join(OUT, name)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print(f"  wrote {path}")


# ---------------------------------------------------------------------------
# 1. Price vs. value
# ---------------------------------------------------------------------------

def price_vs_value() -> None:
    """
    Create a chart showing why share price alone does not tell us valuation.

    Concept
    -------
    A $500 stock can be cheaper than a $5 stock if the $500 stock has much
    stronger earnings relative to its price.

    Example
    -------
    Company A:
        Share price = $500
        P/E = 15x

    Company B:
        Share price = $5
        P/E = 40x

    Lesson
    ------
    The visible share price is not enough. We need to compare price against
    earnings, cash flow, growth, quality, and risk.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))
    fig.subplots_adjust(
        left=0.08,
        right=0.97,
        top=0.78,
        bottom=0.12,
        wspace=0.3,
    )

    # Left chart: what beginners often notice first.
    ax1.bar(
        ["Company A", "Company B"],
        [500, 5],
        color=[MUTED, BLUE],
        width=0.6,
    )
    ax1.set_title("What you see: share price", fontsize=12)
    ax1.set_ylabel("Share price ($)")

    for i, v in enumerate([500, 5]):
        ax1.text(
            i,
            v,
            f"${v}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    # Right chart: what actually helps us think about valuation.
    ax2.bar(
        ["Company A", "Company B"],
        [15, 40],
        color=[MUTED, GREEN],
        width=0.6,
    )
    ax2.set_title("What matters: how expensive it actually is (P/E)", fontsize=12)
    ax2.set_ylabel("Price / earnings")

    for i, v in enumerate([15, 40]):
        ax2.text(
            i,
            v,
            f"{v}x",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    # Important: escape dollar signs in matplotlib text.
    # Otherwise, matplotlib may interpret them as math text.
    _title(
        fig,
        "A \\$500 stock can be cheaper than a \\$5 stock",
        "The share price is only what you see. Valuation tells you what you are actually paying for.",
    )

    _illustrative(fig)
    save(fig, "01_price_vs_value.png")


# ---------------------------------------------------------------------------
# 2. Gross margin by industry
# ---------------------------------------------------------------------------

def margin_by_industry() -> None:
    """
    Create a chart showing that gross margin depends heavily on the industry.

    Concept
    -------
    High gross margin does not automatically mean one company is better than
    another. A software company, payment network, retailer, and automaker have
    very different business models.

    Lesson
    ------
    Compare margins between similar businesses. Do not blindly compare margins
    across unrelated industries.
    """
    categories = [
        "Software",
        "Payment\nnetwork",
        "Branded\nconsumer",
        "Big-box\nretailer",
        "Automaker",
    ]
    margins = [80, 78, 55, 25, 17]

    fig, ax = plt.subplots(figsize=(11, 5.0))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.12)

    bars = ax.bar(
        categories,
        margins,
        color=[BLUE, BLUE, GREEN, AMBER, RED],
        width=0.7,
    )

    ax.set_ylabel("Typical gross margin")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")

    for bar, margin in zip(bars, margins):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            margin,
            f"{margin}%",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    _title(
        fig,
        "Gross margin depends on the industry",
        "This is why I compare margins between similar businesses, not across unrelated industries.",
    )

    _illustrative(fig)
    save(fig, "02_margin_by_industry.png")


# ---------------------------------------------------------------------------
# 3. Operating leverage
# ---------------------------------------------------------------------------

def operating_leverage() -> None:
    """
    Create a chart explaining operating leverage.

    Concept
    -------
    Operating leverage happens when operating income grows faster than revenue.
    This can happen when a company has fixed costs and each additional dollar
    of revenue becomes more profitable.

    Lesson
    ------
    Revenue growth is useful, but operating income growth may reveal whether
    the business is becoming more efficient as it scales.
    """
    years = [1, 2, 3, 4, 5]

    # Both series are indexed to 100 so the chart compares growth rates,
    # not absolute dollars.
    revenue = [100, 105, 110, 116, 122]
    operating_income = [100, 112, 126, 142, 160]

    fig, ax = plt.subplots(figsize=(11, 5.0))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.12)

    ax.plot(
        years,
        revenue,
        "-o",
        lw=2.4,
        color=MUTED,
        label="Revenue",
    )
    ax.plot(
        years,
        operating_income,
        "-o",
        lw=2.4,
        color=GREEN,
        label="Operating income",
    )

    ax.set_xlabel("Year")
    ax.set_ylabel("Indexed to 100")
    ax.set_xticks(years)
    ax.legend(frameon=False)

    ax.annotate(
        "Profit growing faster\nthan revenue = operating leverage",
        xy=(5, 160),
        xytext=(3.0, 150),
        color=GREEN,
        fontsize=10.5,
        arrowprops=dict(arrowstyle="->", color=GREEN),
    )

    _title(
        fig,
        "Operating leverage",
        "When operating income grows faster than revenue, each new dollar of sales is worth more.",
    )

    _illustrative(fig)
    save(fig, "03_operating_leverage.png")


# ---------------------------------------------------------------------------
# 4. Free cash flow waterfall
# ---------------------------------------------------------------------------

def fcf_waterfall() -> None:
    """
    Create a simple free cash flow waterfall chart.

    Concept
    -------
    Free cash flow is commonly calculated as:

        Free cash flow = operating cash flow - capital expenditures

    Lesson
    ------
    A company can generate strong operating cash flow but still have lower free
    cash flow if capital expenditures are heavy.
    """
    labels = [
        "Operating\ncash flow",
        "Capital\nexpenditures",
        "Free\ncash flow",
    ]

    fig, ax = plt.subplots(figsize=(10, 5.2))
    fig.subplots_adjust(left=0.10, right=0.97, top=0.80, bottom=0.12)

    # Operating cash flow starts at +100.
    ax.bar(0, 100, color=GREEN, width=0.6)

    # Capex is shown as a reduction from 100 down to 65.
    # The bar starts at 65 and rises 35 units so the top aligns at 100.
    ax.bar(1, 35, bottom=65, color=RED, width=0.6)

    # Free cash flow is what remains after capex.
    ax.bar(2, 65, color=BLUE, width=0.6)

    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(labels)
    ax.set_ylabel("$ (illustrative units)")

    annotations = [
        (0, "+100", 100),
        (1, "-35", 100),
        (2, "65", 65),
    ]

    for x, text, y in annotations:
        ax.text(
            x,
            y,
            text,
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    _title(
        fig,
        "Free cash flow = operating cash flow - capex",
        "Heavy capex can shrink today's free cash flow. The question is whether it earns its return.",
    )

    _illustrative(fig)
    save(fig, "04_fcf_waterfall.png")


# ---------------------------------------------------------------------------
# 5. Seasonality: quarter-over-quarter vs year-over-year
# ---------------------------------------------------------------------------

def seasonality() -> None:
    """
    Create a chart showing why year-over-year comparisons can be better than
    quarter-over-quarter comparisons for seasonal businesses.

    Concept
    -------
    A seasonal business may have predictable quarterly spikes. For example,
    retailers often have stronger fourth quarters because of holiday shopping.

    Lesson
    ------
    Quarter-over-quarter data can look volatile even when the business is
    steadily growing. Year-over-year comparison often gives a clearer trend.
    """
    # Synthetic seasonal retailer revenue pattern.
    # Q4 is intentionally much stronger than the other quarters.
    quarterly_pattern = [40, 45, 48, 80]

    revenue = []
    quarter_labels = []

    for year_index in range(3):
        # Simulate roughly 7% annual growth each year.
        growth_multiplier = 1.0 + 0.07 * year_index

        for quarter_index in range(4):
            revenue.append(round(quarterly_pattern[quarter_index] * growth_multiplier, 1))
            quarter_labels.append(f"Y{year_index + 1}Q{quarter_index + 1}")

    # Calculate YoY growth by comparing each quarter with the same quarter
    # from the previous year.
    yoy_x = []
    yoy_growth = []

    for i in range(4, len(revenue)):
        yoy_x.append(i)
        yoy_growth.append((revenue[i] - revenue[i - 4]) / revenue[i - 4] * 100)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
    fig.subplots_adjust(
        left=0.07,
        right=0.97,
        top=0.80,
        bottom=0.16,
        wspace=0.25,
    )

    ax1.bar(range(len(revenue)), revenue, color=BLUE, width=0.8)
    ax1.set_xticks(range(len(revenue)))
    ax1.set_xticklabels(quarter_labels, rotation=45, ha="right", fontsize=8)
    ax1.set_ylabel("Quarterly revenue")
    ax1.set_title("Quarter-over-quarter looks volatile", fontsize=12)

    ax2.plot(yoy_x, yoy_growth, "-o", lw=2.4, color=GREEN)
    ax2.set_xticks(yoy_x)
    ax2.set_xticklabels(
        [quarter_labels[i] for i in yoy_x],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    ax2.set_ylabel("YoY growth")
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax2.set_ylim(0, 15)
    ax2.set_title("Year-over-year reveals the trend", fontsize=12)

    _title(
        fig,
        "Why I compare year-over-year, not only quarter-over-quarter",
        "The Q4 spike is seasonality, not a turnaround. YoY strips it out so the real trend shows.",
    )

    _illustrative(fig)
    save(fig, "05_seasonality_qoq_vs_yoy.png")


# ---------------------------------------------------------------------------
# 6. The single-year trap
# ---------------------------------------------------------------------------

def single_year_trap() -> None:
    """
    Create a chart showing the danger of judging a company from one strong year.

    Concept
    -------
    One unusually strong year can make a business look better than it really is.
    Looking at several years helps reveal whether the company is truly becoming
    stronger or only benefiting from a temporary boom.

    Lesson
    ------
    One year is not a trend. Multi-year data gives better context.
    """
    years = list(range(1, 11))

    # Synthetic example: revenue rises sharply, peaks, then falls back.
    revenue = [50, 58, 70, 88, 110, 135, 96, 78, 84, 92]

    peak_index = revenue.index(max(revenue))

    fig, ax = plt.subplots(figsize=(11, 5.0))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.12)

    ax.plot(years, revenue, "-o", lw=2.4, color=MUTED)

    # Highlight the peak year because that is where a beginner might get fooled.
    ax.plot(
        years[peak_index],
        revenue[peak_index],
        "o",
        ms=12,
        color=RED,
        zorder=5,
    )

    ax.annotate(
        "If you only saw this year,\nit looks like a permanent high",
        xy=(years[peak_index], revenue[peak_index]),
        xytext=(years[peak_index] - 4, revenue[peak_index] + 5),
        color=RED,
        fontsize=10.5,
        arrowprops=dict(arrowstyle="->", color=RED),
    )

    ax.set_xlabel("Year")
    ax.set_ylabel("Revenue (illustrative)")
    ax.set_xticks(years)

    _title(
        fig,
        "The single-year trap",
        "One boom year is not a trend. Multiple years show whether the business is really stronger.",
    )

    _illustrative(fig)
    save(fig, "06_single_year_trap.png")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Generate all concept visuals.

    Each function creates one PNG file inside the output folder.
    """
    price_vs_value()
    margin_by_industry()
    operating_leverage()
    fcf_waterfall()
    seasonality()
    single_year_trap()


if __name__ == "__main__":
    main()
