"""
Charts for the "Circle of Competence" article (CodeZero2Hero).

Design choice: the data is hardcoded straight from the companies' earnings
releases (SEC Form 8-K)

Sources (every number below is from these):
  - NVIDIA Q1 FY2026 8-K (GAAP gross margin 60.5%, $4.5B H20 charge)
  - NVIDIA Q2 FY2026 8-K (72.4%)
  - NVIDIA Q3 FY2026 8-K (73.4%)
  - NVIDIA Q4 & FY2026 8-K (Q4 75.0%; full-year GAAP GM 71.1%; FY2025 75.0%)
  - Arista Q4/FY2025 8-K income statement (FY2024 vs FY2025 GAAP figures)

Run:  python3 make_charts.py
"""

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Shared styling -- clean, blog-friendly, no chart-junk
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.8,
})

INK = "#1a1a1a"
MUTED = "#6b7280"
GREEN = "#2e8b57"   # up / good
RED = "#d1495b"     # down
GRAY = "#9aa0a6"    # flat / neutral
NV = "#76b900"      # NVIDIA-ish green


def titles(fig, title, subtitle):
    """Title + muted subtitle, placed in figure coords so they never overlap."""
    fig.text(0.015, 0.95, title, fontsize=15, fontweight="bold",
             color=INK, ha="left", va="top")
    fig.text(0.015, 0.875, subtitle, fontsize=10.5, color=MUTED,
             ha="left", va="top")


def source_line(fig, text):
    fig.text(0.015, 0.015, text, fontsize=8.5, color=MUTED, ha="left")


def pct_axis(ax):
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")


# ===========================================================================
# CHART 1 -- NVIDIA: the "margin collapse" was one quarter, not a trend
# ===========================================================================
def nvidia_margin_recovery():
    quarters = ["Q1\nFY26", "Q2\nFY26", "Q3\nFY26", "Q4\nFY26"]
    gm = [60.5, 72.4, 73.4, 75.0]            # GAAP gross margin, %

    fig, ax = plt.subplots(figsize=(9, 5.9))
    fig.subplots_adjust(left=0.10, right=0.96, top=0.79, bottom=0.13)

    # FY2025 "normal" level -- shows it climbed back to where it started
    ax.axhline(75.0, ls="--", lw=1.3, color=MUTED, alpha=0.8, zorder=1)
    ax.text(0.5, 76.4, "FY2025 level (75.0%)", va="bottom", ha="center",
            fontsize=10, color=MUTED)

    ax.plot(quarters, gm, "-o", lw=3, color=NV, markersize=10,
            markerfacecolor="white", markeredgewidth=2.5, markeredgecolor=NV,
            zorder=3)
    for x, y in zip(quarters, gm):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points",
                    xytext=(0, 14), ha="center", fontsize=11,
                    fontweight="bold", color=INK)

    ax.annotate(
        "$4.5B one-time charge\non H20 chips blocked\nfrom China (export rule)",
        xy=(0, 60.5), xytext=(0.4, 64.5),
        fontsize=10, color=INK,
        arrowprops=dict(arrowstyle="->", color=INK, lw=1.4),
        ha="left", va="bottom",
    )

    ax.set_ylim(56, 80)
    ax.set_ylabel("GAAP gross margin")
    pct_axis(ax)
    titles(fig, "NVIDIA's margin 'collapse' was one quarter, not a trend",
           "Full-year FY2026 GAAP gross margin was 71.1% \u2014 dragged down "
           "almost entirely by the Q1 charge.")
    source_line(fig, "Source: NVIDIA Forms 8-K, Q1\u2013Q4 fiscal 2026 (GAAP).")
    fig.savefig("nvidia_margin_recovery.png", facecolor="white")
    plt.close(fig)


# ===========================================================================
# CHART 2 -- Arista: which margin you look at changes the story (slope chart)
# ===========================================================================
def arista_margin_divergence():
    # GAAP, full year. From Arista Q4/FY2025 8-K income statement.
    series = {
        "Gross margin":     ([64.1, 64.1], GRAY,  "flat"),
        "Operating margin": ([42.0, 42.8], GREEN, "\u2191 up"),
        "Net margin":       ([40.7, 39.0], RED,   "\u2193 down"),
    }
    x = [0, 1]

    fig, ax = plt.subplots(figsize=(9.6, 5.9))
    fig.subplots_adjust(left=0.10, right=0.97, top=0.79, bottom=0.12)

    for name, (vals, color, tag) in series.items():
        ax.plot(x, vals, "-o", lw=3, color=color, markersize=9, zorder=3)
        ax.annotate(f"{vals[0]:.1f}%", (0, vals[0]),
                    textcoords="offset points", xytext=(-10, 0),
                    ha="right", va="center", fontsize=11,
                    fontweight="bold", color=color)
        ax.annotate(f"{vals[1]:.1f}%  {name} ({tag})", (1, vals[1]),
                    textcoords="offset points", xytext=(12, 0),
                    ha="left", va="center", fontsize=11,
                    fontweight="bold", color=color)

    ax.set_xlim(-0.35, 2.05)
    ax.set_ylim(35, 70)
    ax.set_xticks(x)
    ax.set_xticklabels(["FY2024", "FY2025"], fontsize=12)
    ax.set_ylabel("Margin (% of revenue)")
    pct_axis(ax)
    titles(fig, 'Arista 2024 \u2192 2025: "profitability" depends on which margin',
           "Net margin fell only because the tax rate rose (~13% \u2192 ~17%) "
           "\u2014 not because the business weakened.")
    source_line(fig, "Source: Arista Networks Form 8-K, full-year 2025 income "
                     "statement (GAAP).")
    fig.savefig("arista_margin_divergence.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    """
    Running the function creates the following image files in the current working directory:
        - nvidia_margin_recovery.png
        - arista_margin_divergence.png

    Returns
    -------
    None
    """
    nvidia_margin_recovery()
    arista_margin_divergence()
    print("Wrote nvidia_margin_recovery.png and arista_margin_divergence.png")
