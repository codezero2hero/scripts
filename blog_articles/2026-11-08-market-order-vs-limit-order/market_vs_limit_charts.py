"""
Generate three publication-style illustrative figures (1200x600 px) on order types:
  1. order_book_sweep.png   - How a market buy sweeps through a thin order book (slippage).
  2. limit_two_outcomes.png - The limit order trade-off: price certainty vs. execution risk.
  3. order_decision_map.png - A 2x2 decision matrix for choosing an order type by liquidity and volatility.

No external data download is required. Order books and intraday price paths are
synthetically constructed and explicitly labeled as illustrative. Slippage metrics
in Chart 1 are printed to stdout for cross-checking against article prose.
"""
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

# Resolve output directory relative to this script's location
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- House Style & Theme Constants ---------------------------------------
# Warm editorial paper palette and structural grays
PAPER, EDGE, GRID, BASE, TICK = "#f2efe7", "#ddd8c9", "#e2ddcd", "#c3bda9", "#83806f"
# Primary, secondary, and muted typography colors
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#898781"
# Semantic accent colors (Blue = bids/fills, Red = asks/slippage/missed fills) and their tints
BLUE, RED = "#2a78d6", "#e34948"
BLUE_T, RED_T = "#d6e3f3", "#f5d9d5"
NAVY = "#1d3557"

# Attempt to load local "Inter" font files; fall back gracefully to DejaVu Sans
for p in [os.path.expanduser("~/fonts/inter/extras/ttf")]:
    if os.path.isdir(p):
        for f in os.listdir(p):
            if f.startswith("Inter-") and f.endswith(".ttf"):
                font_manager.fontManager.addfont(os.path.join(p, f))
_inter = sorted({f.name for f in font_manager.fontManager.ttflist if f.name.startswith("Inter")}, key=len)
FONT = _inter[0] if _inter else "DejaVu Sans"
SEMI = "semibold" if FONT.startswith("Inter") else "bold"

# Apply global Matplotlib styling defaults
plt.rcParams.update({"font.family": FONT, "text.color": INK, "axes.labelcolor": INK2})

# Figure dimensions: 10x5 inches @ 120 DPI -> 1200x600 pixels
W, H, DPI = 10, 5, 120


# ---------- Layout & Helper Functions -------------------------------------------
def canvas():
    """Initialize a new figure with the warm paper background and border."""
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    fig.patch.set_facecolor(PAPER)
    fig.patch.set_edgecolor(EDGE)
    fig.patch.set_linewidth(1.2)
    return fig


def header(fig, title, subtitle):
    """Render a consistent top-left editorial headline and deck/subtitle."""
    fig.text(0.045, 0.925, title, fontsize=17, weight="bold", color=INK, va="bottom")
    fig.text(0.045, 0.875, subtitle, fontsize=10.5, color=INK2, va="bottom")


def footer(fig, source):
    """Render bottom source notes on the left and watermark branding on the right."""
    fig.text(0.045, 0.03, source, fontsize=8, color=INK3)
    fig.text(0.955, 0.03, "codezero2hero.com", fontsize=8.5, color=INK2, ha="right", weight=SEMI)


def save(fig, name):
    """Export figure to disk preserving background/border colors, then free memory."""
    path = os.path.join(HERE, name)
    fig.savefig(path, dpi=DPI, facecolor=PAPER, edgecolor=EDGE)
    plt.close(fig)
    print("wrote", path)


def clean(ax):
    """Strip axis spines and tick marks, matching the subplot background to the canvas."""
    ax.set_facecolor(PAPER)
    for s in ["left", "right", "top", "bottom"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


# ---------- 1. Order Book Sweep (Slippage Illustration) -------------------------
# Ask ladder: sorted best (lowest) ask first -> (price, share_size)
ASKS = [(12.46, 300), (12.48, 200), (12.52, 400), (12.58, 300), (12.65, 500), (12.80, 600)]
# Bid ladder: sorted best (highest) bid first -> (price, share_size)
BIDS = [(12.40, 400), (12.37, 300), (12.33, 500), (12.28, 400), (12.20, 600)]
ORDER = 1500  # Incoming market buy quantity in shares


def sweep(asks, qty):
    """
    Simulate a market buy order walking up the ask ladder.

    Args:
        asks (list[tuple[float, int]]): Ask levels ordered from lowest to highest price.
        qty (int): Total shares to buy.

    Returns:
        tuple: (list of (price, filled_qty) tuples, volume-weighted average price, total dollar cost)
    """
    fills, left = [], qty
    for px, sz in asks:
        take = min(sz, left)
        if take > 0:
            fills.append((px, take))
            left -= take
    cost = sum(px * q for px, q in fills)
    return fills, cost / qty, cost


def chart_order_book():
    """Build and export Figure 1: Market order sweeping through multiple ask levels."""
    # Calculate execution fills and slippage vs. top-of-book quote
    fills, avg, cost = sweep(ASKS, ORDER)
    best = ASKS[0][0]
    extra = cost - best * ORDER
    print(f"[book] fills={fills}")
    print(f"[book] avg={avg:.4f}  cost=${cost:,.2f}  at quote=${best*ORDER:,.2f}  "
          f"extra=${extra:,.2f}  ({extra/(best*ORDER)*100:.2f}%)")
    filled = dict(fills)

    fig = canvas()
    header(fig, "The price on the screen is only good for the first 300 shares.",
           f"A market buy of {ORDER:,} shares walking up a thin order book. Illustrative small-cap, prices in USD.")

    # Left panel: horizontal bar chart of the order book ladder
    ax = fig.add_axes([0.075, 0.12, 0.52, 0.70])
    clean(ax)

    # Order price levels top-to-bottom: highest ask down to lowest bid
    levels = [p for p, _ in ASKS[::-1]] + [p for p, _ in BIDS]
    y = {p: i for i, p in enumerate(levels)}

    # Invert y-axis so index 0 (highest ask) sits at the top of the plot
    ax.set_ylim(len(levels) + 0.3, -1.3)
    ax.set_xlim(0, 700)
    ax.set_yticks(range(len(levels)))
    ax.set_yticklabels([f"${p:.2f}" for p in levels], fontsize=9.5, color=INK2)
    ax.set_xticks([])

    # Draw ask levels: light red for total available depth, solid red overlay for shares taken
    for px, sz in ASKS:
        yy = y[px]
        took = filled.get(px, 0)
        ax.add_patch(FancyBboxPatch((0, yy - 0.34), sz, 0.68, boxstyle="round,pad=0,rounding_size=0.18",
                                    fc=RED_T, ec="none", mutation_aspect=0.02))
        if took:
            ax.add_patch(FancyBboxPatch((0, yy - 0.34), took, 0.68, boxstyle="round,pad=0,rounding_size=0.18",
                                        fc=RED, ec="none", mutation_aspect=0.02))
            ax.text(took + 8, yy, f"took {took}", va="center", fontsize=8.8, color=RED, weight=SEMI)
        else:
            ax.text(sz + 8, yy, f"{sz} for sale", va="center", fontsize=8.8, color=INK3)

    # Draw bid levels (untouched by a market buy order)
    for px, sz in BIDS:
        yy = y[px]
        ax.add_patch(FancyBboxPatch((0, yy - 0.34), sz, 0.68, boxstyle="round,pad=0,rounding_size=0.18",
                                    fc=BLUE_T, ec="none", mutation_aspect=0.02))
        ax.text(sz + 8, yy, f"{sz} wanted", va="center", fontsize=8.8, color=INK3)

    # Annotate the bid-ask spread dividing line and book sides
    mid = (y[ASKS[0][0]] + y[BIDS[0][0]]) / 2
    ax.axhline(mid, color=INK3, lw=0.8, ls=(0, (2, 3)))
    ax.text(690, mid - 0.12, "spread: 6 cents", ha="right", va="bottom", fontsize=8.5, color=INK2, style="italic")
    ax.text(0, -0.95, "SELLERS (asks)", ha="left", va="center", fontsize=9, weight="bold", color=RED)
    ax.text(0, len(levels) - 0.05, "BUYERS (bids)", ha="left", va="center", fontsize=9, weight="bold", color=BLUE)

    # Right panel: callout card comparing quoted top-of-book price vs. actual average fill price
    card = fig.add_axes([0.64, 0.14, 0.315, 0.66])
    card.axis("off")
    card.set_xlim(0, 1)
    card.set_ylim(0, 1)
    card.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.04",
                                  fc="#fbf9f4", ec=EDGE, lw=1.1, mutation_aspect=0.9))
    card.text(0.08, 0.88, "WHAT YOU SAW", fontsize=8.5, weight="bold", color=INK3)
    card.text(0.08, 0.76, f"${best:.2f}", fontsize=24, weight="bold", color=INK)
    card.text(0.08, 0.69, "best ask, top of the book", fontsize=8.8, color=INK2)
    card.text(0.08, 0.55, "WHAT YOU PAID (AVERAGE)", fontsize=8.5, weight="bold", color=INK3)
    card.text(0.08, 0.43, f"${avg:.2f}", fontsize=24, weight="bold", color=RED)
    card.text(0.08, 0.36, "across five price levels", fontsize=8.8, color=INK2)
    card.plot([0.08, 0.92], [0.27, 0.27], color=EDGE, lw=1)
    card.text(0.08, 0.15, f"+${extra:,.0f}", fontsize=19, weight="bold", color=RED)
    card.text(0.46, 0.165, f"on a ${cost/1000:,.1f}k order\n({extra/(best*ORDER)*100:.2f}% before any fee)",
              fontsize=8.8, color=INK2, va="center", linespacing=1.25)

    footer(fig, "Illustrative order book, built by hand. Real books change many times per second.")
    save(fig, "order_book_sweep.png")


# ---------- 2. The Limit Order Trade-Off ----------------------------------------
def path(points, n=390, noise=0.06, seed=7):
    """
    Generate a realistic intraday price series constrained to pass through exact anchor points.
    Uses a Brownian bridge technique (random walk minus piecewise linear drift between anchors).

    Args:
        points (list[tuple[int, float]]): Control points as (minute_index, target_price).
        n (int): Number of intraday minutes (390 = standard 6.5-hour US trading session).
        noise (float): Per-minute volatility step standard deviation.
        seed (int): Random seed for reproducible paths.
    """
    rng = np.random.default_rng(seed)
    xs = np.arange(n)
    # Piecewise linear skeleton connecting the anchor points
    base = np.interp(xs, [p[0] for p in points], [p[1] for p in points])
    # Unconstrained cumulative random walk
    wiggle = np.cumsum(rng.normal(0, noise, n))
    # Linearly interpolate the random walk's drift at each anchor and subtract it
    # so net noise is exactly 0 at every anchor point
    pin = np.interp(xs, [p[0] for p in points], [wiggle[p[0]] for p in points])
    return xs, base + (wiggle - pin)


def chart_limit():
    """Build and export Figure 2: Side-by-side comparison of a filled vs. missed limit buy."""
    LIMIT = 49.50
    fig = canvas()
    header(fig, "A limit order guarantees your price. It never guarantees the trade.",
           f"Same buy limit at ${LIMIT:.2f}, two different days. Price paths are illustrative.")
    axes = [fig.add_axes([0.06, 0.15, 0.42, 0.62]), fig.add_axes([0.535, 0.15, 0.42, 0.62])]

    # Day A dips below $49.50 around minute 175; Day B bottoms out just above $49.50 and rallies
    xa, pa = path([(0, 50.10), (120, 49.62), (175, 49.38), (260, 49.90), (389, 50.35)], seed=11)
    xb, pb = path([(0, 50.10), (90, 49.66), (160, 50.40), (300, 51.60), (389, 52.30)], seed=4)

    # Find the exact minute Day A first crosses or touches the limit price
    fill_i = int(np.argmax(pa <= LIMIT))
    print(f"[limit] day A first touches {LIMIT} at minute {fill_i}; day B low = {pb.min():.2f}")

    panels = [
        (axes[0], xa, pa, "Day A: filled", BLUE, f"Filled at ${LIMIT:.2f}.\nThe market came to you."),
        (axes[1], xb, pb, "Day B: missed", RED, f"Low ${pb.min():.2f}, 5 cents short.\nNo fill."),
    ]

    # Render shared formatting, price line, shaded area, and dashed limit threshold for both panels
    for ax, x, p, title, col, note in panels:
        clean(ax)
        ax.set_xlim(0, 389)
        ax.set_ylim(48.9, 53.3)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_yticks([49, 50, 51, 52])
        ax.set_yticklabels(["$49", "$50", "$51", "$52"], fontsize=9, color=TICK)
        ax.set_xticks([0, 195, 389])
        ax.set_xticklabels(["open", "midday", "close"], fontsize=9, color=TICK)
        ax.fill_between(x, p, 48.9, color=col, alpha=0.07, lw=0)
        ax.plot(x, p, color=INK, lw=1.6, solid_capstyle="round")
        ax.axhline(LIMIT, color=col, lw=1.6, ls=(0, (5, 3)))
        ax.text(6, LIMIT - 0.08, f"your limit ${LIMIT:.2f}", va="top", fontsize=8.8, color=col, weight=SEMI)
        ax.text(0, 53.2, title, fontsize=12, weight="bold", color=col, va="top")

    # Panel A specific annotation: solid dot at the execution point
    a, b = axes
    a.scatter([fill_i], [LIMIT], s=130, color=BLUE, edgecolor=PAPER, linewidth=2.5, zorder=5)
    a.annotate(panels[0][5], (fill_i, LIMIT), xytext=(18, 62), textcoords="offset points", fontsize=9,
               color=INK, arrowprops=dict(arrowstyle="-", color=INK3, lw=0.8), linespacing=1.25)

    # Panel B specific annotation: hollow dot at the intraday low where the order nearly filled
    lo = int(np.argmin(pb))
    b.scatter([lo], [pb[lo]], s=70, color=PAPER, edgecolor=RED, linewidth=2, zorder=5)
    b.annotate(panels[1][5], (lo, pb[lo]), xytext=(28, -24), textcoords="offset points", fontsize=9,
               color=INK, arrowprops=dict(arrowstyle="-", color=INK3, lw=0.8), linespacing=1.25)
    b.text(0, 52.85, f"closed at ${pb[-1]:.2f}, {(pb[-1]/LIMIT-1)*100:.1f}% above your limit", va="top", fontsize=9, color=INK2)

    footer(fig, "Illustrative intraday paths (390 one-minute bars). Not real prices.")
    save(fig, "limit_two_outcomes.png")


# ---------- 3. Order Type Decision Map ------------------------------------------
def chart_decision():
    """Build and export Figure 3: 2x2 grid mapping liquidity (x) and market regime (y) to order choice."""
    fig = canvas()
    header(fig, "The order type matters most exactly when you least feel like thinking.",
           "Which order I use, by how liquid the instrument is and what the market is doing right now.")
    ax = fig.add_axes([0.11, 0.12, 0.85, 0.68])
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.axis("off")

    # Quadrant definitions: (col_idx, row_idx, title, body_copy, background_hex, title_color)
    # Columns: 0 = Thin/Illiquid, 1 = Deep/Liquid
    # Rows:    0 = Volatile/Open/News, 1 = Calm/Regular Hours
    cells = [
        (1, 1, "Market order is fine",
         "Big stock or big ETF, regular hours,\nnothing happening. You pay roughly\nhalf the spread, usually pennies.", "#e3ecf7", BLUE),
        (0, 1, "Limit order",
         "Small cap, thinly traded name, exotic ETF.\nCalm day, but the book is shallow.\nSet the price, accept you may wait.", "#efe6d8", "#a0742c"),
        (1, 0, "Marketable limit",
         "Liquid name, but it's the open, earnings\nor a panic. Set a limit a bit past the ask.\nYou get speed with a ceiling.", "#f6e2d4", "#c2611f"),
        (0, 0, "Limit, or don't trade",
         "Thin name plus chaos. This is where\nstop-losses fill at silly prices.\nBe ready to miss. Missing is cheap.", "#f5d4d0", RED),
    ]

    # Render each quadrant card and its internal typography
    for c, r, head, body, face, ink in cells:
        x0, y0 = c + 0.02, r + 0.03
        ax.add_patch(FancyBboxPatch((x0, y0), 0.96, 0.94, boxstyle="round,pad=0,rounding_size=0.05",
                                    fc=face, ec="none", mutation_aspect=0.9))
        ax.text(x0 + 0.06, y0 + 0.78, head, fontsize=13.5, weight="bold", color=ink, va="center")
        ax.text(x0 + 0.06, y0 + 0.40, body, fontsize=9.6, color=INK, va="center", linespacing=1.4)

    # Outer matrix axis labels (Horizontal: Liquidity spectrum; Vertical: Volatility/Time of day)
    fig.text(0.11, 0.085, "thin: small caps, niche ETFs, quiet listings", fontsize=8.8, color=INK2)
    fig.text(0.96, 0.085, "deep: mega caps, VWCE / CSPX in their busy hours", fontsize=8.8, color=INK2, ha="right")
    fig.text(0.535, 0.085, "LIQUIDITY  →", fontsize=8.8, color=INK3, ha="center", weight="bold")
    fig.text(0.06, 0.62, "calm,\nregular\nhours", fontsize=8.8, color=INK2, ha="center", linespacing=1.2)
    fig.text(0.06, 0.26, "open,\nnews,\npanic,\nafter-hours", fontsize=8.8, color=INK2, ha="center", linespacing=1.2)

    footer(fig, "My own rule of thumb, not a regulation. Spread and depth vary by broker, venue and hour.")
    save(fig, "order_decision_map.png")


if __name__ == "__main__":
    chart_order_book()
    chart_limit()
    chart_decision()