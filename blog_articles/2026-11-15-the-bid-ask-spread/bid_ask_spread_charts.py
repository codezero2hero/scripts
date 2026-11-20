"""
bid_ask_spread_charts.py
========================
Companion script for "The Bid-Ask Spread: The Hidden Cost of Every Trade"

What it does
------------
1. Rebuilds the four figures used in the post. Each one is 1200 x 600 px and sits
   on the paper-coloured panel, so it stays readable on the blog's white page:

     spread_anatomy.png     what crossing one real quote costs on a round trip
     spread_league.png      seven real quotes from the same evening, sorted by cost
     spread_tick_floor.png  why a cheap stock can never have a tiny spread
     spread_turnover.png    a small spread paid many times becomes a big yearly cost

2. Prints every number quoted in the article, so you can check them against the text.

3. Works as a small round-trip calculator for your own quotes.

Usage
-----
    python bid_ask_spread_charts.py                   # rebuild charts + print the numbers
    python bid_ask_spread_charts.py calc 194.60 195.80 5000
                                                      # round-trip cost of one quote
    python bid_ask_spread_charts.py live AAPL SPY     # fetch current quotes (needs yfinance)
                                                      # and print their round-trip cost

The data
--------
The QUOTES table below is the only data the charts use. The quotes come from an
Interactive Brokers snapshot pulled on Sunday 15 Nov 2026. Markets were closed, so the
feed returned the last quotes standing at the end of the US extended session on
Friday 13 Nov 2026 (about 20:00 New York). They are NOT regular-hours
quotes, and the article explains why that matters.

To redo the post with your own numbers, edit QUOTES (and QUOTE_DATE) and run the
script again. Every chart, label and printed figure is derived from that table.

Requirements: Python 3.9+, matplotlib, numpy. yfinance only for the `live` command.
Have fun!
"""
import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import MaxNLocator

# All output files are written next to this script, wherever you run it from.
HERE = os.path.dirname(os.path.abspath(__file__))


# =====================================================================================
# 1. DATA
# =====================================================================================
# One row per instrument:
#   ticker, label shown on the chart, bid, ask, average daily USD traded (last 90 days)
# The volume column only feeds the right-hand column of the league chart. It shows that
# the more money trades in a name, the tighter its spread tends to be.
QUOTES = [
    ("SPY",  "SPY  (S&P 500 ETF)",        749.49, 749.63, 32_311_632_880),
    ("AAPL", "AAPL (Apple)",              355.33, 355.40, 15_197_339_459),
    ("MSFT", "MSFT (Microsoft)",          522.21, 522.50, 12_130_682_011),
    ("ANET", "ANET (Arista Networks)",    194.60, 195.80,  1_227_778_492),
    ("SNDL", "SNDL (SNDL Inc.)",            1.37,   1.38,      1_766_590),
    ("IDN",  "IDN  (Intellicheck)",         1.82,   2.30,        554_939),
    ("UFPT", "UFPT (UFP Technologies)",   304.00, 386.25,     34_470_790),
]
QUOTE_DATE = "Fri 13 Nov 2026"
SOURCE = (f"Source: Interactive Brokers quote snapshot, last quotes standing at end of "
          f"US extended session, {QUOTE_DATE}.")

# Which quotes each chart features. Change these if you swap the data.
ANATOMY_TICKER = "ANET"      # the single quote dissected in chart 1
BENCHMARK_TICKER = "SPY"     # the "cheap" comparison in chart 1's side card
TICK_FLOOR_CHEAP = "SNDL"    # the low-priced stock sitting on the one-cent floor (chart 3)
TICK_FLOOR_PRICEY = "AAPL"   # the expensive stock it is compared with (chart 3)
TICK_FLOOR_OTHERS = ["SPY", "MSFT"]  # extra dots on chart 3

POSITION = 5_000             # example position size in USD, used in chart 1 and the printout
US_TICK = 0.01               # minimum quote increment for most US stocks priced above $1

# Lookup by ticker: QUOTE["ANET"] -> (label, bid, ask, volume)
QUOTE = {t: (lab, b, a, v) for t, lab, b, a, v in QUOTES}


# =====================================================================================
# 2. THE ARITHMETIC (the only maths in the post)
# =====================================================================================
def mid_price(bid, ask):
    """Halfway between bid and ask: the closest thing to a 'fair' price at that moment."""
    return (bid + ask) / 2


def round_trip(bid, ask, amount=None):
    """
    Cost of buying at the ask and selling straight back at the bid.

    Measured against the mid price, so buying costs half the spread and selling costs
    the other half. Returns the cost as a fraction (0.0062 = 0.62%), or, if `amount`
    is given, a tuple (fraction, cost in dollars on that amount).
    """
    if ask < bid:
        raise ValueError(f"ask ({ask}) is below bid ({bid}): that is a crossed quote, check the numbers")
    pct = (ask - bid) / mid_price(bid, ask)
    return pct if amount is None else (pct, pct * amount)


def tick_floor(price, tick=US_TICK):
    """Narrowest possible round-trip spread for a stock at `price`: one tick over the price."""
    return tick / price


def yearly_drag(spread_pct, trips_per_year):
    """
    Yearly spread cost if the whole position is bought and sold `trips_per_year` times.
    Simple multiplication on purpose: commissions, FX and slippage would only add to it.
    """
    return spread_pct * trips_per_year


# =====================================================================================
# 3. HOUSE STYLE (shared with the other CodeZero2Hero charts)
# =====================================================================================
# Paper background, never white: the blog page itself is white.
PAPER, EDGE, GRID, BASE, TICK = "#f2efe7", "#ddd8c9", "#e2ddcd", "#c3bda9", "#83806f"
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#898781"   # text: primary, secondary, muted
BLUE, RED = "#2a78d6", "#e34948"                    # cheap side / expensive side
CARD = "#fbf9f4"                                    # the side "stat card" panels
SPREAD_BAND = "#e9e3d3"                             # shaded band between bid and ask

# Use Inter if it's installed, otherwise fall back to matplotlib's default font.
_has_inter = any(f.name == "Inter" for f in font_manager.fontManager.ttflist)
FONT = "Inter" if _has_inter else "DejaVu Sans"
SEMI = "semibold" if _has_inter else "bold"
plt.rcParams.update({"font.family": FONT, "text.color": INK, "axes.labelcolor": INK2})

W, H, DPI = 10, 5, 120  # 10 x 5 inches at 120 dpi = 1200 x 600 px, the blog's image cap


def money(x, decimals=2):
    """
    Format a dollar amount for chart text. The dollar sign is escaped because matplotlib
    treats a pair of '$' signs as the start and end of a maths expression.
    """
    return f"\\${x:,.{decimals}f}"


def fmt_pct(p):
    """Fraction -> readable percent with sensible precision (0.00019 -> '0.019%')."""
    p *= 100
    if p < 0.1:
        return f"{p:.3f}%"
    return f"{p:.2f}%" if p < 10 else f"{p:.1f}%"


def fmt_vol(v):
    """Average daily dollar volume -> short label ($32.3bn, $34M, $555k)."""
    if v >= 1e9:
        return f"${v / 1e9:.1f}bn"
    return f"${v / 1e6:.0f}M" if v >= 1e6 else f"${v / 1e3:.0f}k"


# ---------- figure plumbing: every chart is built from these pieces ------------------
def canvas():
    """Blank 1200x600 figure on the paper background with a hairline edge."""
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    fig.patch.set_facecolor(PAPER)
    fig.patch.set_edgecolor(EDGE)
    fig.patch.set_linewidth(1.2)
    return fig


def header(fig, title, subtitle):
    """Story-style title (the takeaway, not a label) plus a one-line subtitle."""
    fig.text(0.045, 0.925, title, fontsize=17, weight="bold", color=INK, va="bottom")
    fig.text(0.045, 0.875, subtitle, fontsize=10.5, color=INK2, va="bottom")


def footer(fig, source):
    """Source line bottom-left, site credit bottom-right."""
    fig.text(0.045, 0.03, source, fontsize=8, color=INK3)
    fig.text(0.955, 0.03, "codezero2hero.com", fontsize=8.5, color=INK2, ha="right", weight=SEMI)


def save(fig, name):
    """Write the PNG next to this script, keeping the paper background, then free memory."""
    path = os.path.join(HERE, name)
    fig.savefig(path, dpi=DPI, facecolor=PAPER, edgecolor=EDGE)
    plt.close(fig)
    print("wrote", path)


def clean(ax):
    """Strip an axes down to the data: no frame, no tick marks, paper background."""
    ax.set_facecolor(PAPER)
    for side in ["left", "right", "top", "bottom"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def card(fig, rect):
    """Rounded side panel for headline numbers. Draw on it in 0..1 coordinates."""
    c = fig.add_axes(rect)
    c.axis("off")
    c.set_xlim(0, 1)
    c.set_ylim(0, 1)
    c.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.04",
                               fc=CARD, ec=EDGE, lw=1.1, mutation_aspect=0.9))
    return c


def fig_y(fig, ax, x, y):
    """Convert a data point on `ax` to a 0..1 figure height, to align text outside the axes."""
    return ax.transData.transform((x, y))[1] / (H * DPI)


# =====================================================================================
# 4. CHART 1: anatomy of one quote
# =====================================================================================
def chart_anatomy():
    """One quote on a price line: bid, ask, mid, and what a round trip costs."""
    _, bid, ask, _ = QUOTE[ANATOMY_TICKER]
    mid = mid_price(bid, ask)
    half = (ask - bid) / 2                                # what each leg costs vs the mid
    pct, cost = round_trip(bid, ask, POSITION)
    _, sb, sa, _ = QUOTE[BENCHMARK_TICKER]
    bench_pct, bench_cost = round_trip(sb, sa, POSITION)

    print(f"[anatomy] {ANATOMY_TICKER} bid {bid} ask {ask} mid {mid:.2f} spread {ask - bid:.2f} "
          f"= {pct * 100:.3f}% -> ${cost:.2f} on ${POSITION:,}")
    print(f"[anatomy] {BENCHMARK_TICKER} same position -> ${bench_cost:.2f} ({cost / bench_cost:.0f}x cheaper)")

    fig = canvas()
    header(fig, "You buy at the higher price and sell at the lower one. Always.",
           f"One real quote for {QUOTE[ANATOMY_TICKER][0].split('(')[1].rstrip(')')} ({ANATOMY_TICKER}), "
           f"and what crossing it twice costs on a ${POSITION:,} position.")

    # Price axis: pad the view by ~30% of the spread on each side so the labels fit.
    ax = fig.add_axes([0.06, 0.17, 0.55, 0.62])
    clean(ax)
    pad = (ask - bid) * 0.3
    ax.set_xlim(bid - pad, ask + pad)
    ax.set_ylim(-1.25, 1.35)
    ax.set_yticks([])
    # Round tick values ($194.50, $195.00 ...) whatever the quote, about four of them.
    ticks = [t for t in MaxNLocator(5, steps=[1, 2, 2.5, 5, 10]).tick_values(bid - pad, ask + pad)
             if bid - pad <= t <= ask + pad]
    ax.set_xticks(ticks)
    ax.set_xticklabels([money(t) for t in ticks], fontsize=9, color=TICK)
    ax.axhline(0, color=BASE, lw=1.2, zorder=1)

    # Shaded band between bid and ask: the spread itself.
    ax.axvspan(bid, ask, ymin=0.30, ymax=0.70, color=SPREAD_BAND, lw=0, zorder=0)
    ax.text(mid, 0.33, f"the spread: {money(ask - bid)}", ha="center", fontsize=10, color=INK2, style="italic")

    # Bid and ask markers with a short plain-English description under each.
    for x, col, lab, sub in [(bid, BLUE, f"BID  {money(bid)}", "best price a buyer\nwill pay you"),
                             (ask, RED, f"ASK  {money(ask)}", "best price a seller\nwill accept")]:
        ax.plot([x, x], [-0.35, 0.35], color=col, lw=2.6, solid_capstyle="round", zorder=3)
        ax.scatter([x], [0], s=150, color=col, edgecolor=PAPER, linewidth=2.5, zorder=4)
        ax.text(x, 0.95, lab, ha="center", fontsize=12, weight="bold", color=col)
        ax.text(x, 0.58, sub, ha="center", fontsize=8.8, color=INK2, linespacing=1.2)

    # The mid: hollow marker, because nobody actually trades there.
    ax.scatter([mid], [0], s=70, color=PAPER, edgecolor=INK3, linewidth=1.8, zorder=4)
    ax.text(mid, -0.22, f"mid {money(mid)}\n(the 'fair' price\nnobody trades at)", ha="center", va="top",
            fontsize=8.6, color=INK3, linespacing=1.2)

    # Two arrows from the mid: the buy leg goes up to the ask, the sell leg down to the bid.
    for end, col in [(ask, RED), (bid, BLUE)]:
        ax.annotate("", xy=(end, -0.95), xytext=(mid, -0.95),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=1.6, mutation_scale=14))
    ax.text((mid + ask) / 2, -1.17, f"buy: pay {money(half)} over mid", ha="center", fontsize=8.8,
            color=RED, weight=SEMI)
    ax.text((mid + bid) / 2, -1.17, f"sell: get {money(half)} under mid", ha="center", fontsize=8.8,
            color=BLUE, weight=SEMI)

    # Side card: the round-trip cost, and the same position in the cheap benchmark.
    c = card(fig, [0.655, 0.17, 0.30, 0.62])
    c.text(0.08, 0.87, f"ROUND TRIP ON {money(POSITION, 0)}", fontsize=8.5, weight="bold", color=INK3)
    c.text(0.08, 0.70, f"-{money(cost)}", fontsize=27, weight="bold", color=RED)
    c.text(0.08, 0.62, f"{pct * 100:.2f}% gone, before any commission", fontsize=8.8, color=INK2)
    c.plot([0.08, 0.92], [0.52, 0.52], color=EDGE, lw=1)
    c.text(0.08, 0.42, f"SAME {money(POSITION, 0)} IN {BENCHMARK_TICKER} THAT EVENING", fontsize=8.5,
           weight="bold", color=INK3)
    c.text(0.08, 0.27, f"-{money(bench_cost)}", fontsize=22, weight="bold", color=BLUE)
    c.text(0.08, 0.13, f"{fmt_pct(bench_pct)}. Same money,\n{cost / bench_cost:.0f}x cheaper to get in and out.",
           fontsize=8.8, color=INK2, linespacing=1.25)

    footer(fig, SOURCE)
    save(fig, "spread_anatomy.png")


# =====================================================================================
# 5. CHART 2: league table of every quote
# =====================================================================================
def chart_league():
    """Horizontal bars, cheapest to most expensive, on a log scale (each gridline = 10x)."""
    rows = sorted(((t, lab, b, a, v, round_trip(b, a)) for t, lab, b, a, v in QUOTES),
                  key=lambda r: r[5])
    for t, _, b, a, v, p in rows:
        print(f"[league] {t:5s} bid {b:>8.2f} ask {a:>8.2f} spread {a - b:>6.2f}  {p * 100:8.3f}%  "
              f"{p * 1e4:8.1f} bps  ${p * POSITION:>9,.2f} on ${POSITION:,}  avg daily $vol {fmt_vol(v)}")
    lo_p, hi_p = rows[0][5], rows[-1][5]

    fig = canvas()
    header(fig, f"Same broker, same evening: {fmt_pct(lo_p)} to cross on one, {fmt_pct(hi_p)} on another.",
           "Round-trip cost of crossing the quoted spread, as % of the mid price. Log scale: each gridline is 10x.")
    ax = fig.add_axes([0.255, 0.13, 0.58, 0.68])
    clean(ax)
    ax.set_xscale("log")
    ax.minorticks_off()
    floor = 1e-4                                          # bars start at 0.01% (log scale has no zero)
    ax.set_xlim(floor, 1.2)
    n = len(rows)
    ax.set_ylim(n - 0.4, -0.75)                           # inverted: cheapest on top
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[1] for r in rows], fontsize=9.6, color=INK)
    ax.set_xticks([1e-4, 1e-3, 1e-2, 1e-1, 1])
    ax.set_xticklabels(["0.01%", "0.1%", "1%", "10%", "100%"], fontsize=9, color=TICK)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)

    cheap_cutoff = 0.001                                  # under 0.1% is coloured blue ("ignore it")
    for i, (t, lab, b, a, v, p) in enumerate(rows):
        cheap = p < cheap_cutoff
        ax.barh(i, p - floor, left=floor, height=0.56, color=BLUE if cheap else RED,
                alpha=0.9 if cheap else 0.85, lw=0)
        ax.text(p * 1.18, i, fmt_pct(p), va="center", fontsize=9.4, weight="bold", color=INK)
        ax.text(p * 1.18, i + 0.33, f"{money(b)} / {money(a)}", va="center", fontsize=7.6, color=INK3)
        # Volume column sits outside the axes, aligned with each bar.
        fig.text(0.965, fig_y(fig, ax, 1, i), fmt_vol(v), ha="right", va="center", fontsize=9, color=INK2)
    fig.text(0.965, 0.835, "avg daily \\$\ntraded, 90d", ha="right", va="bottom", fontsize=8, color=INK3,
             linespacing=1.1)

    # Two plain-language zones instead of a legend.
    ax.text(1.1e-4, -0.62, "under 0.1%: you'll never notice it", fontsize=8.5, color=BLUE, weight=SEMI)
    first_red = next(i for i, r in enumerate(rows) if r[5] >= cheap_cutoff)
    ax.text(1.1e-2, first_red - 0.4, "over 0.5%: a real cost\nevery single time", fontsize=8.5, color=RED,
            weight=SEMI, linespacing=1.2)

    footer(fig, SOURCE + " Not regular-hours quotes.")
    save(fig, "spread_league.png")


# =====================================================================================
# 6. CHART 3: the one-cent floor
# =====================================================================================
def chart_tick_floor():
    """The minimum possible spread (one tick) as % of price, with real quotes plotted on it."""
    prices = np.logspace(np.log10(0.5), np.log10(800), 300)
    floor = tick_floor(prices)

    _, cb, ca, _ = QUOTE[TICK_FLOOR_CHEAP]
    _, pb, pa, _ = QUOTE[TICK_FLOOR_PRICEY]
    cheap_pct, pricey_pct = round_trip(cb, ca), round_trip(pb, pa)
    ratio = cheap_pct / pricey_pct
    print(f"[tick] {TICK_FLOOR_CHEAP} at ${mid_price(cb, ca):.3f}: floor {tick_floor(mid_price(cb, ca)) * 100:.3f}%, "
          f"actual {cheap_pct * 100:.3f}% | {TICK_FLOOR_PRICEY}: actual {pricey_pct * 100:.4f}% "
          f"-> {ratio:.0f}x cheaper")

    fig = canvas()
    header(fig, "Under $5 a share, one cent stops being small.",
           "The narrowest spread a US stock can quote is one tick, usually $0.01. "
           "As a % of the price, that floor rises fast.")
    ax = fig.add_axes([0.085, 0.14, 0.60, 0.66])
    clean(ax)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.minorticks_off()
    ax.set_xlim(0.5, 800)
    ax.set_ylim(5e-6, 0.05)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xticks([1, 5, 20, 100, 500])
    ax.set_xticklabels(["$1", "$5", "$20", "$100", "$500"], fontsize=9, color=TICK)
    ax.set_yticks([1e-5, 1e-4, 1e-3, 1e-2])
    ax.set_yticklabels(["0.001%", "0.01%", "0.1%", "1%"], fontsize=9, color=TICK)
    ax.set_xlabel("share price", fontsize=9, color=INK3)

    # Everything below the line is impossible: a quote can't be narrower than one tick.
    ax.fill_between(prices, floor, 5e-6, color=BLUE, alpha=0.06, lw=0)
    ax.plot(prices, floor, color=INK, lw=2)
    ax.text(1.3, 3.4e-5, "impossible zone:\nnarrower than one cent", fontsize=8.8, color=BLUE, weight=SEMI,
            linespacing=1.2)

    # Real quotes as dots. Label offsets (in points) are hand-tuned to avoid overlaps;
    # adjust them if you change the tickers.
    offsets = {TICK_FLOOR_CHEAP: (14, 8), TICK_FLOOR_PRICEY: (-100, 7), "SPY": (-40, -22), "MSFT": (-112, 6)}
    for t in [TICK_FLOOR_CHEAP, TICK_FLOOR_PRICEY] + TICK_FLOOR_OTHERS:
        _, b, a, _ = QUOTE[t]
        px, p = mid_price(b, a), round_trip(b, a)
        ax.scatter([px], [p], s=90, color=RED if t == TICK_FLOOR_CHEAP else BLUE,
                   edgecolor=PAPER, linewidth=2, zorder=5)
        ax.annotate(f"{t}  {p * 100:.3f}%", (px, p), xytext=offsets.get(t, (8, 8)), textcoords="offset points",
                    fontsize=8.8, color=INK, weight=SEMI)

    # Side card: the quiz from the article, answered with numbers.
    cheap_cents = round((ca - cb) * 100)
    pricey_cents = round((pa - pb) * 100)
    c = card(fig, [0.715, 0.14, 0.24, 0.66])
    c.text(0.09, 0.88, f"{TICK_FLOOR_CHEAP} AT {money(cb)}", fontsize=8.5, weight="bold", color=INK3)
    c.text(0.09, 0.73, f"{cheap_cents} cent{'s' if cheap_cents != 1 else ''}", fontsize=22, weight="bold", color=INK)
    c.text(0.09, 0.66, "spread: as tight as it can be" if cheap_cents == 1 else "spread", fontsize=8.6, color=INK2)
    c.text(0.09, 0.50, fmt_pct(cheap_pct), fontsize=22, weight="bold", color=RED)
    c.text(0.09, 0.43, "of the price, per round trip", fontsize=8.6, color=INK2)
    c.plot([0.09, 0.91], [0.34, 0.34], color=EDGE, lw=1)
    pricey_name = QUOTE[TICK_FLOOR_PRICEY][0].split("(")[1].rstrip(")")
    c.text(0.09, 0.07, f"{pricey_name}'s {pricey_cents}-cent spread\nlooks wider in dollars and\n"
                       f"is {ratio:.0f}x cheaper in percent.", fontsize=8.8, color=INK, linespacing=1.3)

    footer(fig, SOURCE)
    save(fig, "spread_tick_floor.png")


# =====================================================================================
# 7. CHART 4: how trading frequency multiplies the spread
# =====================================================================================
def chart_turnover():
    """Yearly spread cost vs number of round trips per year, for four spread levels."""
    trips = np.array([1, 2, 4, 12, 26, 52, 100, 250])
    # (round-trip spread, line label, colour, line style). The two labelled examples
    # roughly match quotes in the league chart.
    spreads = [(0.0002, "0.02%  like SPY or AAPL", BLUE, "-"),
               (0.001, "0.1%", BLUE, (0, (5, 2))),
               (0.006, "0.6%  like ANET or SNDL", RED, (0, (5, 2))),
               (0.02, "2%", RED, "-")]
    for s, lab, *_ in spreads:
        print(f"[turnover] {lab:28s} " + "  ".join(f"{t}x:{yearly_drag(s, t) * 100:.1f}%" for t in [1, 12, 52, 250]))

    fig = canvas()
    header(fig, "A small spread paid often becomes a big one.",
           "Yearly cost of crossing the spread, as % of the position, if you round-trip the whole position N times a year.")
    ax = fig.add_axes([0.085, 0.14, 0.66, 0.66])
    clean(ax)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.minorticks_off()
    ax.set_xlim(0.9, 300)
    ax.set_ylim(1e-4, 8)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xticks([1, 4, 12, 52, 250])
    ax.set_xticklabels(["1\nyearly", "4\nquarterly", "12\nmonthly", "52\nweekly", "250\ndaily"],
                       fontsize=8.8, color=TICK)
    ax.set_yticks([1e-4, 1e-3, 1e-2, 1e-1, 1])
    ax.set_yticklabels(["0.01%", "0.1%", "1%", "10%", "100%"], fontsize=9, color=TICK)

    # Danger zone: above ~7% a year, spreads cost more than a typical stock-market year returns.
    typical_year = 0.07
    ax.axhspan(typical_year, 8, color=RED, alpha=0.05, lw=0)
    ax.text(1.05, 4.2, "above ~7% a year: the spread eats\na typical stock-market year", fontsize=8.6,
            color=RED, weight=SEMI, va="top", linespacing=1.2)

    for s, lab, col, ls in spreads:
        y = yearly_drag(s, trips)
        ax.plot(trips, y, color=col, lw=2, ls=ls, solid_capstyle="round")
        ax.scatter([trips[-1]], [y[-1]], s=46, color=col, edgecolor=PAPER, linewidth=1.8, zorder=5)
        fig.text(0.765, fig_y(fig, ax, trips[-1], y[-1]), lab, va="center", fontsize=8.8, color=INK)

    # Two highlighted points: the patient investor and the weekly trader.
    lo_s, hi_s = spreads[0][0], spreads[2][0]
    ax.scatter([1], [yearly_drag(lo_s, 1)], s=110, color=BLUE, edgecolor=PAPER, linewidth=2.5, zorder=6)
    ax.annotate(f"one round trip a year in a big ETF:\n{lo_s * 100:.2f}%, basically zero", (1, yearly_drag(lo_s, 1)),
                xytext=(28, 4), textcoords="offset points", fontsize=8.8, color=INK, va="bottom", linespacing=1.2,
                arrowprops=dict(arrowstyle="-", color=INK3, lw=0.8))
    ax.scatter([52], [yearly_drag(hi_s, 52)], s=110, color=RED, edgecolor=PAPER, linewidth=2.5, zorder=6)
    ax.annotate(f"weekly in-and-out at {hi_s * 100:.1f}%:\n{yearly_drag(hi_s, 52) * 100:.0f}% a year, gone",
                (52, yearly_drag(hi_s, 52)), xytext=(-150, 22), textcoords="offset points", fontsize=8.8,
                color=INK, linespacing=1.2, arrowprops=dict(arrowstyle="-", color=INK3, lw=0.8))

    footer(fig, "Simple arithmetic: round trips per year x round-trip spread. Ignores commissions, FX and slippage, "
                "which only add to it.")
    save(fig, "spread_turnover.png")


# =====================================================================================
# 8. COMMAND LINE: calculator and live quotes
# =====================================================================================
def print_cost(label, bid, ask, amount):
    """One readable line for a single quote, plus a rough verdict using the post's thresholds."""
    pct, cost = round_trip(bid, ask, amount)
    if pct < 0.001:
        verdict = "ignore it"
    elif pct < 0.005:
        verdict = "use a limit order"
    elif pct < 0.02:
        verdict = "real cost, check the time of day"
    else:
        verdict = "something is off: market closed or very thin"
    print(f"{label:6s} bid {bid:>10.4f}  ask {ask:>10.4f}  round trip {pct * 100:7.3f}%  "
          f"= ${cost:>9,.2f} on ${amount:,.0f}  (buy side alone ${cost / 2:,.2f})  -> {verdict}")


def live_quotes(tickers, amount):
    """
    Fetch the current bid and ask with yfinance and print the round-trip cost.

    Yahoo's bid/ask are delayed and often come back as 0 outside US trading hours
    (16:30 to 23:00 Bucharest time). Run it during the session for meaningful numbers.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise SystemExit("The live command needs yfinance: pip install yfinance")

    for t in tickers:
        try:
            info = yf.Ticker(t).info
            bid, ask = info.get("bid") or 0, info.get("ask") or 0
        except Exception as exc:                          # network errors, unknown tickers, rate limits
            print(f"{t:6s} could not fetch a quote ({exc})")
            continue
        if bid <= 0 or ask <= 0:
            print(f"{t:6s} no usable bid/ask right now (market closed or data missing)")
            continue
        print_cost(t, bid, ask, amount)


def main():
    parser = argparse.ArgumentParser(description="Charts and calculator for the bid-ask spread post.")
    sub = parser.add_subparsers(dest="cmd")

    p_calc = sub.add_parser("calc", help="round-trip cost of one bid/ask quote")
    p_calc.add_argument("bid", type=float)
    p_calc.add_argument("ask", type=float)
    p_calc.add_argument("amount", type=float, nargs="?", default=POSITION, help=f"position in USD (default {POSITION})")

    p_live = sub.add_parser("live", help="fetch current quotes with yfinance")
    p_live.add_argument("tickers", nargs="+")
    p_live.add_argument("--amount", type=float, default=POSITION, help=f"position in USD (default {POSITION})")

    args = parser.parse_args()
    if args.cmd == "calc":
        print_cost("quote", args.bid, args.ask, args.amount)
    elif args.cmd == "live":
        live_quotes(args.tickers, args.amount)
    else:                                                 # no command: rebuild everything
        chart_anatomy()
        chart_league()
        chart_tick_floor()
        chart_turnover()


if __name__ == "__main__":
    main()
