"""
click_buy_charts.py — charts for "What Happens After I Click Buy?"
CodeZero2Hero · codezero2hero.com

Three figures, all 1200x600 on the paper panel (never white):
  1. click_timeline.png   — the life of one order on a log-time axis
  2. custody_chain.png    — whose name is actually on your share
  3. settlement_cycle.png — T+5 -> T+1: how long "settled" has taken, US vs EU

No data download needed: every date and time below is a documented rule
(SEC / ESMA / DTCC / FINRA) or an order-of-magnitude illustration, labelled as such.
"""
import os
from datetime import date

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
import matplotlib.dates as mdates

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- house style --------------------------------------------------------
PAPER, EDGE, GRID, BASE, TICK = "#f2efe7", "#ddd8c9", "#e2ddcd", "#c3bda9", "#83806f"
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#898781"
BLUE, RED = "#2a78d6", "#e34948"
BLUE_T, RED_T = "#d6e3f3", "#f5d9d5"

# Inter if present (downloaded from rsms/inter), else DejaVu Sans
for p in [os.path.expanduser("~/fonts/inter/extras/ttf")]:
    if os.path.isdir(p):
        for f in os.listdir(p):
            if f.startswith("Inter-") and f.endswith(".ttf"):
                font_manager.fontManager.addfont(os.path.join(p, f))
FONT = "Inter" if any(f.name == "Inter" for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
plt.rcParams.update({"font.family": FONT, "text.color": INK, "axes.labelcolor": INK2})

W, H, DPI = 10, 5, 120  # -> 1200 x 600 px


def canvas():
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    fig.patch.set_facecolor(PAPER)
    fig.patch.set_edgecolor(EDGE)
    fig.patch.set_linewidth(1.2)
    return fig


def header(fig, title, subtitle):
    fig.text(0.045, 0.925, title, fontsize=17, weight="bold", color=INK, va="bottom")
    fig.text(0.045, 0.875, subtitle, fontsize=10.5, color=INK2, va="bottom")


def footer(fig, source):
    fig.text(0.045, 0.03, source, fontsize=8, color=INK3)
    fig.text(0.955, 0.03, "codezero2hero.com", fontsize=8.5, color=INK2, ha="right", weight="semibold")


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, dpi=DPI, facecolor=PAPER, edgecolor=EDGE)
    plt.close(fig)
    print("wrote", path)


# ---------- 1. timeline --------------------------------------------------------
def chart_timeline():
    fig = canvas()
    header(fig, "The trade feels done in under a second. It becomes yours a day later.",
           "Life of one market order for a liquid US stock, seconds after the tap (log scale). "
           "Times are typical orders of magnitude.")
    ax = fig.add_axes([0.045, 0.17, 0.91, 0.62])
    ax.set_facecolor(PAPER)
    ax.set_xscale("log")
    ax.set_xlim(0.02, 4e5)
    ax.set_ylim(-1.25, 1.25)
    ax.set_yticks([])
    for s in ["left", "right", "top"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ticks = [0.1, 1, 10, 60, 3600, 86400]
    ax.set_xticks(ticks)
    ax.set_xticklabels(["0.1 s", "1 s", "10 s", "1 min", "1 hour", "1 day"], color=TICK, fontsize=9)
    ax.tick_params(axis="x", length=0, pad=6)
    for t in ticks:
        ax.axvline(t, color=GRID, lw=0.8, zorder=0)

    # the two zones
    ax.axvspan(0.02, 1.2, color=BLUE_T, alpha=0.55, zorder=0, lw=0)
    ax.axvspan(1.2, 4e5, color=RED_T, alpha=0.35, zorder=0, lw=0)
    ax.text(0.03, 1.12, "WHAT YOU SEE", fontsize=9, weight="bold", color=BLUE)
    ax.text(1.6, 1.12, "WHAT YOU DON'T SEE  — clearing, netting, settlement, custody",
            fontsize=9, weight="bold", color=RED)

    ax.plot([0.02, 4e5], [0, 0], color=INK3, lw=1.1, zorder=1)

    events = [  # (seconds, label, colour, level)
        (0.08, "Order reaches\nyour broker", BLUE, 0.62),
        (0.12, "Risk checks:\ncash, limits", BLUE, -0.62),
        (0.18, "Routed to a\nvenue", BLUE, 0.95 - 0.02),
        (0.3, "Matched\n(filled)", BLUE, -0.95),
        (0.8, "“Filled” on\nyour screen", BLUE, 0.35),
        (10, "Printed to the\npublic tape\n(≤ 10 s rule)", RED, 0.62),
        (1800, "Clearing house\nsteps in as\nbuyer-to-every-seller", RED, -0.62),
        (5 * 3600, "Everyone's trades\nnetted into one\nposition per stock", RED, 0.62),
        (86400 * 1.05, "T+1: cash and shares\nswap at the depository.\nNow it's yours.", RED, -0.66),
    ]
    for x, lab, c, lvl in events:
        ax.plot([x, x], [0, lvl * 0.72], color=c, lw=0.9, alpha=0.8, zorder=2)
        ax.scatter([x], [0], s=70, color=c, edgecolor=PAPER, linewidth=2, zorder=3)
        ax.text(x, lvl * 0.76 + (0.02 if lvl > 0 else -0.02), lab, ha="center",
                va="bottom" if lvl > 0 else "top", fontsize=8.6, color=INK, linespacing=1.15)
    # final star
    ax.scatter([86400 * 1.05], [0], s=260, marker="*", color=RED, edgecolor=PAPER, linewidth=1.5, zorder=4)

    footer(fig, "Source: SEC Rule 15c6-1 (T+1 since 28 May 2024), FINRA trade-reporting rules, DTCC NSCC/DTC. "
                "Pre-settlement times illustrative.")
    save(fig, "click_timeline.png")


# ---------- 2. custody chain ---------------------------------------------------
def chart_custody():
    fig = canvas()
    header(fig, "You own the share. Your name just isn't on it.",
           "The custody chain for a US stock bought through an EU broker. Each level keeps records only for the level below.")
    ax = fig.add_axes([0.045, 0.1, 0.91, 0.74])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    tiers = [  # (level, what it is, name recorded at this level, face, edge, is_you)
        ("The company's share register", "kept by the issuer's transfer agent", "Cede & Co.", "#e6e0d0", BASE, False),
        ("DTC — US central securities depository", "Cede & Co. is its nominee; balances are book entries", "your broker's clearing firm", "#e0dac8", BASE, False),
        ("Your broker's clearing firm", "a DTC participant, one pooled position per stock", "your broker (omnibus account)", "#dde6f1", "#aac2e0", False),
        ("Your broker", "client assets kept apart from the broker's own", "you", "#cfdcef", "#8fb0dc", False),
        ("You", "the beneficial owner — votes, dividends, the economic stake", "", BLUE, BLUE, True),
    ]
    ax.text(0, 97, "LEVEL", fontsize=8.5, weight="bold", color=INK3)
    ax.text(73, 97, "WHOSE NAME IS RECORDED HERE", fontsize=8.5, weight="bold", color=INK3)
    n = len(tiers)
    top, gap = 91, 3.2
    hh = (top - 2 - gap * (n - 1)) / n
    for i, (lvl, sub, name, face, edge, you) in enumerate(tiers):
        y = top - (i + 1) * hh - i * gap
        x = i * 3.5
        w = 68 - x
        ax.add_patch(FancyBboxPatch((x, y), w, hh, boxstyle="round,pad=0,rounding_size=1.6",
                                    fc=face, ec=edge, lw=1.1, mutation_aspect=1.9))
        tc = "white" if you else INK
        sc = "#e8f0fb" if you else INK2
        ax.text(x + 2, y + hh * 0.64, lvl, fontsize=11 if you else 10, weight="bold", color=tc, va="center")
        ax.text(x + 2, y + hh * 0.3, sub, fontsize=8.8, color=sc, va="center")
        if name:
            ax.annotate("", xy=(72, y + hh / 2), xytext=(x + w + 0.8, y + hh / 2),
                        arrowprops=dict(arrowstyle="-", color=INK3, lw=0.7, ls=(0, (1, 2))))
            col = BLUE if name == "you" else INK
            ax.text(73, y + hh / 2, name, fontsize=10, weight="semibold", color=col, va="center")
        else:
            ax.text(73, y + hh / 2, "nobody else's books but\nyour broker's know you exist",
                    fontsize=9, color=RED, va="center", style="italic", linespacing=1.2)
        if i < n - 1:
            ax.annotate("", xy=(x + 5.5, y - gap + 0.3), xytext=(x + 5.5, y - 0.3),
                        arrowprops=dict(arrowstyle="-|>", color=INK3, lw=0.9, mutation_scale=9))

    footer(fig, "Per DTCC and broker client-asset disclosures (e.g. IB Ireland \u2192 IB LLC \u2192 DTC). Simplified.")
    save(fig, "custody_chain.png")


# ---------- 3. settlement cycle ------------------------------------------------
def chart_settlement():
    fig = canvas()
    header(fig, "“Settled” used to take a working week. Now it's the next business day.",
           "Standard settlement cycle for stock trades, in business days after the trade (T).")
    ax = fig.add_axes([0.075, 0.15, 0.87, 0.64])
    ax.set_facecolor(PAPER)
    for s in ["right", "top", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.set_ylim(0, 5.9)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["T+1", "T+2", "T+3", "T+4", "T+5"], color=TICK, fontsize=9)
    ax.tick_params(axis="both", length=0, pad=6)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    start, end = date(1990, 1, 1), date(2029, 6, 30)
    ax.set_xlim(start, end)
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for lab in ax.get_xticklabels():
        lab.set_color(TICK)
        lab.set_fontsize(9)

    us = [(start, 5), (date(1995, 6, 7), 3), (date(2017, 9, 5), 2), (date(2024, 5, 28), 1), (end, 1)]
    eu = [(date(2000, 1, 1), 3), (date(2014, 10, 6), 2), (date(2027, 10, 11), 1)]
    xs, ys = [d for d, _ in us], [v for _, v in us]
    ax.step(xs, [v + 0.04 for v in ys], where="post", color=BLUE, lw=2.6, zorder=3, label="United States")
    xe, ye = [d for d, _ in eu] + [date(2027, 10, 11)], [v for _, v in eu] + [2]
    ax.step([d for d, _ in eu], [v - 0.04 for v in [3, 2, 2]], where="post", color=RED, lw=2.6, zorder=3)
    ax.plot([date(2027, 10, 11), date(2027, 10, 11), end], [1.96, 0.96, 0.96], color=RED, lw=2.4, ls=(0, (2, 2)), zorder=3)

    def dot(d, v, c):
        ax.scatter([d], [v], s=60, color=c, edgecolor=PAPER, linewidth=2, zorder=4)

    for d, v in us[1:4]:
        dot(d, v + 0.04, BLUE)
    for d, v in [(date(2014, 10, 6), 1.96)]:
        dot(d, v, RED)
    ax.scatter([date(2027, 10, 11)], [0.96], s=60, color=PAPER, edgecolor=RED, linewidth=2, zorder=4)

    def note(x, y, text, dx, dy, ha="left"):
        ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=8.6, color=INK2, ha=ha,
                    arrowprops=dict(arrowstyle="-", color=INK3, lw=0.7), linespacing=1.2)

    note(date(1995, 6, 7), 3.04, "Jun 1995\nUS moves to T+3", 12, 30)
    note(date(2017, 9, 5), 2.04, "Sep 2017\nUS moves to T+2", 14, -44)
    note(date(2024, 5, 28), 1.04, "28 May 2024\nUS moves to T+1", -6, -44, ha="right")
    note(date(2014, 10, 6), 1.96, "Oct 2014: EU harmonises on T+2\n(CSDR). Romania's BVB still\nsettles T+2 today", -20, -58, ha="right")
    note(date(2027, 10, 11), 0.96, "11 Oct 2027\nEU, UK and\nSwitzerland\nplanned T+1", 10, 30)

    ax.text(date(1990, 9, 1), 5.28, "United States", color=BLUE, fontsize=10, weight="bold")
    ax.text(date(2000, 3, 1), 3.3, "Most EU markets", color=RED, fontsize=10, weight="bold")

    footer(fig, "Sources: SEC Rule 15c6-1; EU CSDR; ESMA; Depozitarul Central. Pre-2014 EU line simplified.")
    save(fig, "settlement_cycle.png")


if __name__ == "__main__":
    chart_timeline()
    chart_custody()
    chart_settlement()
