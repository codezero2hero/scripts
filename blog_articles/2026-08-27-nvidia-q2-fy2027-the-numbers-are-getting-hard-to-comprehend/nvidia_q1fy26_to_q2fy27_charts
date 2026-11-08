"""
NVIDIA Quarterly Financial Visualization Script[span_1](start_span)[span_1](end_span)

What this script does
---------------------
1. Uses NVIDIA-reported quarterly figures from Q1 FY26 through Q2 FY27[span_2](start_span)[span_2](end_span).
2. Highlights Q2 FY26 and Q2 FY27 with accent colors[span_3](start_span)[span_3](end_span).
3. Creates:
      - Revenue trend[span_4](start_span)[span_4](end_span)
      - Data Center revenue trend[span_5](start_span)[span_5](end_span)
      - GAAP gross-margin trend[span_6](start_span)[span_6](end_span)
      - Revenue + Data Center combined chart[span_7](start_span)[span_7](end_span)
4. Adds direct value labels and source notes[span_8](start_span)[span_8](end_span).

Important accounting note
-------------------------
Q1 FY26 GAAP gross margin was affected by NVIDIA's $4.5B H20 charge following
new U.S. export-license requirements. NVIDIA said Q1 FY26 non-GAAP gross
margin excluding that charge would have been 71.3%. The chart deliberately
plots the reported GAAP figure (60.5%) and annotates the distortion[span_9](start_span)[span_9](end_span).

Values are hard-coded rather than scraped at runtime so the charts remain
reproducible even if NVIDIA later changes its web pages[span_10](start_span)[span_10](end_span).
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ---------------------------------------------------------------------------
# Output Configuration
# ---------------------------------------------------------------------------

# Define and safely create the directory where generated charts will be saved
OUTPUT_DIR = Path("nvidia_q1fy26_to_q2fy27_charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Visual System & Branding
# ---------------------------------------------------------------------------

# Non-white background ensures charts stand out when embedded on white backgrounds (e.g., blogs)
BG = "#EEF2F6"          # Outer figure background
PLOT_BG = "#EEF2F6"     # Inner plot area background

# Core text and structural colors
TEXT = "#172033"        # Primary text color
MUTED = "#667085"       # Secondary text and subtle lines
GRID = "#CBD5E1"        # Horizontal gridline color

# Bar and line color palette
BASE = "#8FA3B8"                # Default color for standard quarters
Q2_FY26_COLOR = "#F2A900"       # Accent color for the historical comparison quarter (Q2 FY26)
Q2_FY27_COLOR = "#76B900"       # Accent color for the current/target quarter (Q2 FY27)
DATA_CENTER = "#475467"         # Distinct color for Data Center metrics in combined charts

# Standardized output dimensions and resolution
FIGSIZE = (12, 6.75)
DPI = 220


# ---------------------------------------------------------------------------
# NVIDIA Quarterly Data
# ---------------------------------------------------------------------------

# X-axis categorical labels
quarters = [
    "Q1 FY26",
    "Q2 FY26",
    "Q3 FY26",
    "Q4 FY26",
    "Q1 FY27",
    "Q2 FY27",
]

# Total corporate revenue (in USD billions)
revenue = np.array([
    44.062,
    46.743,
    57.006,
    68.127,
    81.615,
    96.200,
])

# Data Center segment revenue (in USD billions)
data_center = np.array([
    39.100,
    41.096,
    51.200,
    62.300,
    75.200,
    89.000,
])

# Reported GAAP Gross Margin (in percentages)
gaap_gross_margin = np.array([
    60.5,
    72.4,
    73.4,
    75.0,
    74.9,
    75.0,
])


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def quarter_colors():
    """
    Generates a color array for bar charts, applying specific highlight colors
    to the Q2 FY26 (index 1) and Q2 FY27 (index 5) data points.
    """
    colors = [BASE] * len(quarters)
    colors[1] = Q2_FY26_COLOR
    colors[5] = Q2_FY27_COLOR
    return colors


def style_figure(fig, ax):
    """
    Applies a clean, minimalist structural style to the matplotlib figure and axes.
    Removes heavy borders and formats the tick marks and gridlines.
    """
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PLOT_BG)

    # Strip away top, right, and left bounding box spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    # Draw horizontal gridlines strictly behind the chart elements
    ax.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.65)
    ax.set_axisbelow(True)

    # Clean up tick marks, relying only on the labels
    ax.tick_params(axis="x", length=0, labelsize=10, colors=TEXT)
    ax.tick_params(axis="y", length=0, labelsize=9, colors=MUTED)
    ax.yaxis.label.set_color(MUTED)


def title_block(fig, title, subtitle):
    """
    Renders standard, uniformly positioned title and subtitle text on the figure.
    """
    fig.text(
        0.065, 0.935,
        title,
        ha="left",
        va="top",
        fontsize=22,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.065, 0.878,
        subtitle,
        ha="left",
        va="top",
        fontsize=11,
        color=MUTED,
    )


def source_note(fig, text):
    """
    Adds a standardized footer note for data sourcing at the bottom left.
    """
    fig.text(
        0.065, 0.035,
        text,
        ha="left",
        va="bottom",
        fontsize=8,
        color=MUTED,
    )


def label_bars(ax, bars):
    """
    Iterates through a set of matplotlib bar objects to apply data labels
    directly above each bar. Highlights the font weight for Q2 quarters.
    """
    for i, bar in enumerate(bars):
        value = bar.get_height()
        weight = "bold" if i in (1, 5) else "normal"

        ax.annotate(
            f"${value:.1f}B",
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight=weight,
            color=TEXT,
        )


def yoy_change(new, old):
    """Calculates the percentage change between a new and old value."""
    return (new / old - 1.0) * 100.0


def add_q2_comparison_callout(fig, old, new, unit="B"):
    """
    Adds a prominent text callout in the top right corner highlighting the
    Year-over-Year (YoY) growth between the two selected quarters.
    """
    growth = yoy_change(new, old)

    # Percentage growth text
    fig.text(
        0.94, 0.928,
        f"Q2 YoY: +{growth:.0f}%",
        ha="right",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=Q2_FY27_COLOR,
    )

    # Absolute difference text (if unit is Billions)
    if unit == "B":
        delta = new - old
        fig.text(
            0.94, 0.882,
            f"+${delta:.1f}B in 12 months",
            ha="right",
            va="top",
            fontsize=10,
            color=MUTED,
        )


# ---------------------------------------------------------------------------
# Chart 1: Revenue
# ---------------------------------------------------------------------------

def revenue_chart():
    """Generates and saves a bar chart illustrating total quarterly revenue."""
    fig, ax = plt.subplots(figsize=FIGSIZE)
    colors = quarter_colors()

    bars = ax.bar(
        quarters,
        revenue,
        width=0.60,
        color=colors,
        edgecolor="none",
    )

    style_figure(fig, ax)
    ax.set_ylim(0, 108) # Buffer above max value to leave room for labels
    ax.set_ylabel("USD billions", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.0f}B"))

    label_bars(ax, bars)
    title_block(
        fig,
        "NVIDIA quarterly revenue",
        "Q1 FY26 → Q2 FY27 | Q2 FY26 and Q2 FY27 highlighted",
    )
    add_q2_comparison_callout(fig, revenue[1], revenue[5])
    source_note(
        fig,
        "Source: NVIDIA Investor Relations quarterly results and Q2 FY27 Quarterly Presentation.",
    )

    # Adjust layout boundaries to prevent clipping text
    fig.subplots_adjust(left=0.075, right=0.965, top=0.78, bottom=0.16)

    fig.savefig(
        OUTPUT_DIR / "01_revenue_q1fy26_to_q2fy27.png",
        dpi=DPI,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 2: Data Center revenue
# ---------------------------------------------------------------------------

def data_center_chart():
    """Generates and saves a bar chart specifically for the Data Center segment."""
    fig, ax = plt.subplots(figsize=FIGSIZE)
    colors = quarter_colors()

    bars = ax.bar(
        quarters,
        data_center,
        width=0.60,
        color=colors,
        edgecolor="none",
    )

    style_figure(fig, ax)
    ax.set_ylim(0, 100)
    ax.set_ylabel("USD billions", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.0f}B"))

    label_bars(ax, bars)
    title_block(
        fig,
        "NVIDIA Data Center revenue",
        "The AI infrastructure engine more than doubled between the two highlighted Q2 quarters.",
    )
    add_q2_comparison_callout(fig, data_center[1], data_center[5])
    source_note(
        fig,
        "Source: NVIDIA Investor Relations quarterly results and Q2 FY27 Quarterly Presentation.",
    )

    fig.subplots_adjust(left=0.075, right=0.965, top=0.78, bottom=0.16)
    fig.savefig(
        OUTPUT_DIR / "02_data_center_q1fy26_to_q2fy27.png",
        dpi=DPI,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 3: GAAP gross margin
# ---------------------------------------------------------------------------

def gross_margin_chart():
    """Generates and saves a line chart visualizing GAAP Gross Margin trends."""
    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = np.arange(len(quarters))

    # Base line connecting all data points
    ax.plot(
        x,
        gaap_gross_margin,
        linewidth=2.5,
        color=DATA_CENTER,
        zorder=2,
    )

    # Standard markers for non-highlighted quarters
    ax.scatter(
        x,
        gaap_gross_margin,
        s=70,
        color=BASE,
        zorder=3,
    )

    # Emphasized marker for Q2 FY26
    ax.scatter(
        [1],
        [gaap_gross_margin[1]],
        s=150,
        color=Q2_FY26_COLOR,
        edgecolor=BG,
        linewidth=2,
        zorder=4,
    )

    # Emphasized marker for Q2 FY27
    ax.scatter(
        [5],
        [gaap_gross_margin[5]],
        s=150,
        color=Q2_FY27_COLOR,
        edgecolor=BG,
        linewidth=2,
        zorder=4,
    )

    style_figure(fig, ax)
    ax.set_xticks(x, quarters)
    ax.set_ylim(57, 78)
    ax.set_ylabel("GAAP gross margin", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.0f}%"))

    # Direct data labels on each node
    for i, value in enumerate(gaap_gross_margin):
        ax.annotate(
            f"{value:.1f}%",
            (i, value),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold" if i in (1, 5) else "normal",
            color=TEXT,
        )

    # Specific callout pointing to the Q1 FY26 drop (H20 export charge)
    ax.annotate(
        "Q1 FY26 includes the\n$4.5B H20 charge",
        xy=(0, gaap_gross_margin[0]),
        xytext=(0.70, 63.0),
        textcoords="data",
        fontsize=9,
        color=MUTED,
        arrowprops={
            "arrowstyle": "-",
            "color": MUTED,
            "linewidth": 1.0,
        },
    )

    title_block(
        fig,
        "NVIDIA GAAP gross margin",
        "Q1 FY26 was distorted by the H20 charge; margins subsequently returned to the mid-70s.",
    )

    # Custom top-right text block for margin expansion
    fig.text(
        0.94, 0.928,
        "+2.6 pts",
        ha="right",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=Q2_FY27_COLOR,
    )
    fig.text(
        0.94, 0.882,
        "Q2 FY26 → Q2 FY27",
        ha="right",
        va="top",
        fontsize=10,
        color=MUTED,
    )

    source_note(
        fig,
        "Source: NVIDIA quarterly results. Q1 FY26 reported GAAP margin includes the H20 charge.",
    )

    fig.subplots_adjust(left=0.075, right=0.965, top=0.78, bottom=0.16)
    fig.savefig(
        OUTPUT_DIR / "03_gaap_gross_margin_q1fy26_to_q2fy27.png",
        dpi=DPI,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 4: Revenue vs Data Center
# ---------------------------------------------------------------------------

def revenue_vs_data_center_chart():
    """Generates a combined line chart displaying total revenue vs. Data Center revenue."""
    fig, ax = plt.subplots(figsize=FIGSIZE)
    x = np.arange(len(quarters))

    # Total revenue line
    ax.plot(
        x,
        revenue,
        marker="o",
        markersize=6,
        linewidth=2.7,
        color=TEXT,
        label="Total revenue",
        zorder=3,
    )

    # Data center revenue line
    ax.plot(
        x,
        data_center,
        marker="o",
        markersize=6,
        linewidth=2.7,
        color=DATA_CENTER,
        label="Data Center",
        zorder=3,
    )

    # Vertical shading to emphasize the Q2 FY26 quarter
    ax.axvspan(
        0.78,
        1.22,
        color=Q2_FY26_COLOR,
        alpha=0.14,
        linewidth=0,
        zorder=0,
    )

    # Vertical shading to emphasize the Q2 FY27 quarter
    ax.axvspan(
        4.78,
        5.22,
        color=Q2_FY27_COLOR,
        alpha=0.15,
        linewidth=0,
        zorder=0,
    )

    style_figure(fig, ax)
    ax.set_xticks(x, quarters)
    ax.set_ylim(30, 105)
    ax.set_ylabel("USD billions", fontsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"${y:.0f}B"))

    ax.legend(
        frameon=False,
        loc="upper left",
        fontsize=10,
        labelcolor=TEXT,
    )

    # Add numeric labels specifically for the highlighted Q2 quarters
    for idx in (1, 5):
        # Upper label for Total Revenue
        ax.annotate(
            f"${revenue[idx]:.1f}B",
            (idx, revenue[idx]),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color=TEXT,
        )

        # Lower label for Data Center Revenue
        ax.annotate(
            f"${data_center[idx]:.1f}B",
            (idx, data_center[idx]),
            xytext=(0, -18),
            textcoords="offset points",
            ha="center",
            fontsize=10,
            fontweight="bold",
            color=DATA_CENTER,
        )

    title_block(
        fig,
        "NVIDIA's growth is overwhelmingly a Data Center story",
        "Total revenue and Data Center revenue from Q1 FY26 through Q2 FY27.",
    )
    source_note(
        fig,
        "Source: NVIDIA Investor Relations quarterly results and Q2 FY27 Quarterly Presentation.",
    )

    fig.subplots_adjust(left=0.075, right=0.965, top=0.78, bottom=0.16)
    fig.savefig(
        OUTPUT_DIR / "04_revenue_vs_data_center_q1fy26_to_q2fy27.png",
        dpi=DPI,
        facecolor=fig.get_facecolor(),
        bbox_inches="tight",
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

def main():
    """Generates all charts and confirms successful execution."""
    revenue_chart()
    data_center_chart()
    gross_margin_chart()
    revenue_vs_data_center_chart()

    print(f"Created charts in: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
