"""
WHY THIS EXISTS:
  The post claims two things you should not take my word for:
    1. A roulette player's chance of being ahead DECAYS toward zero as
       they play more rounds (small negative edge + repetition).
    2. A market owner's chance of being ahead CLIMBS toward certainty as
       they hold longer (small positive edge + repetition).

  This script computes both from scratch: the roulette side with exact
  binomial probability (no simulation, no approximation), the market side
  from 150+ years of monthly data for the S&P composite -- Robert
  Shiller's long-run dataset (Yale), fetched from the free
  `datasets/s-and-p-500` mirror. No API key, no scraping.

WHAT IT DOES:
  1. Downloads the monthly series (price, dividend, earnings, CPI, 1871 -> today).
  2. Builds a nominal total-return index (dividends reinvested monthly).
  3. Calculates win rates for holding periods from 1 month to 25 years.
  4. Calculates exact binomial probabilities for a roulette player.
  5. Writes a verification CSV, renders two charts, and prints stats.

REQUIREMENTS:  pip install matplotlib
"""

import csv
import io
import math
import urllib.request

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# GLOBAL CONSTANTS & CONFIGURATION
# ---------------------------------------------------------------------------

# Redundancy mirrors for the Shiller dataset to avoid rate-limiting issues.
DATA_URLS = [
    "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv",
    "https://cdn.jsdelivr.net/gh/datasets/s-and-p-500@master/data/data.csv",
    "https://datahub.io/core/s-and-p-500/r/data.csv",
]
CACHE_FILE = "shiller_monthly_cache.csv"
USER_AGENT = "CodeZero2Hero research yourname@example.com"

# Gambler profile: Plays one evening a month, 100 spins per evening.
SPINS_PER_EVENING = 100      # ~35 spins/hour x a 3-hour evening
EVENINGS_PER_MONTH = 1
STAKE = 10                   # euros per spin, flat betting
P_WIN = 18 / 37              # European wheel: 18 red pockets out of 37 total
HORIZON_MONTHS = 300         # Chart both games out to 25 years (300 months)

# ---------------------------------------------------------------------------
# MARKET DATA FUNCTIONS
# ---------------------------------------------------------------------------

def fetch_rows():
    """
    Fetches the Shiller dataset, trying mirrors sequentially.
    Saves a local cache so subsequent runs (or network failures) don't break the script.
    """
    text = None

    # Attempt to fetch from our list of URLs
    for url in DATA_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8")
            print(f"  fetched from {url.split('/')[2]}")

            # Save successful fetch to local cache
            with open(CACHE_FILE, "w") as f:
                f.write(text)
            break
        except Exception as e:
            print(f"  {url.split('/')[2]} unavailable ({e}) -- trying next mirror")

    # Fallback to local cache if all network requests fail
    if text is None:
        try:
            with open(CACHE_FILE) as f:
                text = f.read()
            print(f"  all mirrors down -- using local {CACHE_FILE}")
        except FileNotFoundError:
            raise SystemExit("no mirror reachable and no local cache yet -- "
                             "try again in a few minutes.")

    # Parse the CSV data into a list of dictionaries
    rows = list(csv.DictReader(io.StringIO(text)))

    def num(v):
        """Helper to safely convert CSV strings to floats, treating 0 as None (missing data)."""
        try:
            x = float(v)
            return x if x != 0 else None
        except ValueError:
            return None

    # Clean and structure the dataset
    return [dict(date=row["Date"][:7],  # Keep only YYYY-MM
                 price=num(row["SP500"]),
                 div=num(row["Dividend"]),
                 earn=num(row["Earnings"]),
                 cpi=num(row["Consumer Price Index"]))
            for row in rows]

def total_return_index(rows):
    """
    Constructs a nominal Total Return (TR) index.
    It assumes you reinvest 1/12th of the annualized dividend each month back into the index.
    """
    tr = [None] * len(rows)
    tr[0] = 1.0  # Base index starts at 1.0

    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]

        # Only calculate if we have continuous price and dividend data (dividends often lag)
        if tr[i - 1] and prev["price"] and cur["price"] and cur["div"]:
            # TR formula: Previous TR * (Current Price + Monthly Dividend) / Previous Price
            tr[i] = tr[i - 1] * (cur["price"] + cur["div"] / 12) / prev["price"]

    return tr

def win_rate(series, months):
    """
    Calculates the historical probability of being ahead after a specific holding period.
    Iterates through all possible rolling windows of length `months` in the dataset.
    """
    wins = total = 0

    # Slide a window of size `months` across the entire historical series
    for i in range(len(series) - months):
        a, b = series[i], series[i + months]
        if a and b:  # Ensure data exists for both the start and end of the window
            total += 1
            wins += b > a  # Evaluates to 1 if ending value > starting value, else 0

    return (wins / total if total else None), total


# ---------------------------------------------------------------------------
# CASINO MATH FUNCTIONS
# ---------------------------------------------------------------------------

def p_ahead(n_spins, p=P_WIN):
    """
    Calculates the exact probability of having strictly more wins than losses.
    Uses the Binomial Distribution PMF, computed entirely in logarithmic space
    to prevent floating-point overflow/underflow for massive numbers of spins (e.g., n=30,000).
    """
    # Start with the log probability of 0 wins: log((1-p)^n) = n * log(1-p)
    log_pmf = n_spins * math.log(1 - p)
    log_ratio = math.log(p / (1 - p))

    tail = 0.0
    need = n_spins // 2 + 1  # To be "ahead", you must win more than half the spins

    # Iteratively calculate the probability of exactly k wins, adding it to the tail
    # if it meets our 'ahead' criteria.
    for k in range(1, n_spins + 1):
        # Update log_pmf for the current k using the recurrent relationship of binomials
        log_pmf += math.log((n_spins - k + 1) / k) + log_ratio

        # If this number of wins puts us in profit, convert out of log space and add to total
        if k >= need:
            tail += math.exp(log_pmf)

    return tail


# ---------------------------------------------------------------------------
# MATPLOTLIB CHARTING SETTINGS & HELPERS
# ---------------------------------------------------------------------------

# Color palette validated for color-blindness (protan dE 21.6)
BLUE, RED = "#2a78d6", "#e34948"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"     # Text hierarchy colors
GRID, BASE = "#e7e6e1", "#c3c2b7"                   # Axis/Grid colors

# Global chart styling updates
plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.family": "DejaVu Sans",
    "font.size": 12, "axes.grid": False,
})
# Styling for annotation leader lines
LEAD = dict(arrowstyle="-", color=BASE, lw=0.9, shrinkA=2, shrinkB=4)

def polish(ax):
    """Applies a clean, minimalist 'recessive chrome' style to matplotlib axes."""
    # Remove top, right, and left borders
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)

    ax.spines["bottom"].set_color(BASE)
    ax.grid(axis="y", color=GRID, lw=0.8)  # Subtle horizontal gridlines only
    ax.set_axisbelow(True)                 # Push grid behind the data lines
    ax.tick_params(colors=MUT, length=0, labelsize=10) # Clean ticks

def dot(ax, x, y, color, size=9):
    """Draws a highlighted data point with a white outline for visual clarity."""
    ax.plot([x], [y], marker="o", ms=size, mfc=color, mec="white", mew=2,
            zorder=5, clip_on=False)


# ---------------------------------------------------------------------------
# PLOTTING FUNCTIONS
# ---------------------------------------------------------------------------

def chart_odds(months, casino, market):
    """Generates the main chart comparing Market Win Rate vs Casino Win Rate over time."""
    fig, ax = plt.subplots(figsize=(10.8, 6.3))
    fig.subplots_adjust(left=0.072, right=0.965, top=0.74, bottom=0.115)

    # Convert months to years, and probabilities to percentages
    years = [m / 12 for m in months]
    mk = [v * 100 for v in market]
    ca = [v * 100 for v in casino]

    # Create background shaded regions to emphasize the growing gap (the house/owner edge)
    ax.fill_between(years, ca, mk, color=BLUE, alpha=0.06, lw=0)
    ax.fill_between(years, 0, ca, color=RED, alpha=0.06, lw=0)

    # Plot the primary data lines
    ln_m, = ax.plot(years, mk, color=BLUE, lw=2.6, solid_capstyle="round",
                    zorder=3, label="Own the US market (dividends reinvested)")
    ln_c, = ax.plot(years, ca, color=RED, lw=2.6, solid_capstyle="round",
                    zorder=3, label="Roulette: €10 on red, one evening a month")

    # Add a baseline indicating a 50/50 coin flip
    ax.axhline(50, ls=(0, (4, 4)), lw=1.0, color=BASE, zorder=1)
    ax.text(24.9, 51.2, "coin flip", fontsize=9, color=MUT, ha="right", va="bottom")

    # Annotate specific critical points on the chart (1st month/evening and 20-year mark)
    dot(ax, 1/12, mk[0], BLUE); dot(ax, 20, mk[239], BLUE)
    dot(ax, 1/12, ca[0], RED);  dot(ax, 20, ca[239], RED)

    ann = dict(color=SEC, fontsize=10.5)
    ax.annotate(f"First month: {mk[0]:.0f}%", xy=(1/12, mk[0]),
                xytext=(1.7, 69.5), arrowprops=LEAD, **ann)
    ax.annotate("20 years: 100%\nof 1,590 historical windows", xy=(20, mk[239]),
                xytext=(12.3, 86), arrowprops=LEAD, **ann)
    ax.annotate(f"First evening: {ca[0]:.0f}%", xy=(1/12, ca[0]),
                xytext=(1.7, 39.5), arrowprops=LEAD, **ann)
    ax.annotate(f"20 years: {ca[239]:.3f}%", xy=(20, ca[239] + 0.4),
                xytext=(16.4, 11), arrowprops=LEAD, **ann)

    # Axis formatting
    ax.set_xlim(0, 25.4); ax.set_ylim(-2, 104)
    ax.set_xticks(range(0, 26, 5))
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_xlabel("Years playing the game", color=MUT, fontsize=10.5)
    polish(ax)

    # Titles and Legends
    fig.text(0.015, 0.965, "Same small edge. Opposite destinies.",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.902,
             "Chance of being ahead vs. time spent playing. Roulette: exact math, a 2.7% edge against you.\n"
             "Market: share of all same-length historical holding periods that ended higher, 1871–2023.",
             fontsize=10.8, color=SEC, ha="left", va="top", linespacing=1.45)

    fig.legend(handles=[ln_m, ln_c], loc="upper left", bbox_to_anchor=(0.012, 0.818),
               ncols=2, frameon=False, fontsize=10, labelcolor=SEC,
               handlelength=1.7, columnspacing=1.8, borderaxespad=0)

    fig.text(0.015, 0.018,
             "Sources: exact binomial (European wheel, even-money bets); "
             "Robert Shiller's long-run S&P dataset (Yale), nominal, dividends reinvested.",
             fontsize=8.5, color=MUT, ha="left")

    fig.savefig("odds_vs_time.png", facecolor="white")
    plt.close(fig)
    print("  wrote odds_vs_time.png")

def chart_engine(rows):
    """Generates a logarithmic chart showing how Market Price tracks Earnings over 150+ years."""
    # Filter rows to only those with valid price/earnings data and extract parallel lists
    dates, price = zip(*[(r["date"], r["price"]) for r in rows if r["price"]])
    e_dates, earn = zip(*[(r["date"], r["earn"]) for r in rows if r["earn"]])

    # Convert 'YYYY-MM' strings into decimal years for plotting (e.g., 1871.0)
    x = [int(d[:4]) + (int(d[5:7]) - 1) / 12 for d in dates]
    xe = [int(d[:4]) + (int(d[5:7]) - 1) / 12 for d in e_dates]

    fig, ax = plt.subplots(figsize=(10.8, 6.3))
    fig.subplots_adjust(left=0.072, right=0.965, top=0.74, bottom=0.115)

    ax.set_yscale("log") # Crucial for showing compounding growth properly

    # Plot price and earnings
    ln_p, = ax.plot(x, price, color=MUT, lw=1.3, label="S&P composite price level")
    ln_e, = ax.plot(xe, earn, color=BLUE, lw=2.4, solid_capstyle="round",
                    label="Earnings per index ‘share’ (12-month)")

    # Mark the very last available data point
    dot(ax, x[-1], price[-1], MUT, size=8)
    dot(ax, xe[-1], earn[-1], BLUE, size=8)

    # Find the lowest earnings point post-2005 (The 2008-2009 Great Financial Crisis drop)
    lo = min(range(len(earn)), key=lambda i: earn[i] if xe[i] > 2005 else 1e9)
    ax.annotate("2009: even the engine\nstalls sometimes",
                xy=(xe[lo], earn[lo]), xytext=(1984, 0.55),
                arrowprops=LEAD, color=SEC, fontsize=10.5)

    # Axis formatting
    ax.set_xlim(1868, 2029)
    ax.set_xticks(range(1880, 2021, 20))
    ax.set_yticks([0.1, 1, 10, 100, 1000, 10000])
    ax.set_yticklabels(["0.1", "1", "10", "100", "1,000", "10,000"])
    ax.yaxis.set_minor_locator(plt.NullLocator()) # Hide messy minor log ticks
    ax.set_ylabel("Index points / $ per index share (log scale)", color=MUT, fontsize=10.5)
    polish(ax)

    # Titles and Legends
    fig.text(0.015, 0.965, "Why the wheel drifts upward",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.902,
             "155 years, log scale: the price line wanders, panics, bubbles and keeps returning to the\n"
             "earnings line underneath it. The drift is profits, not luck.",
             fontsize=10.8, color=SEC, ha="left", va="top", linespacing=1.45)

    fig.legend(handles=[ln_e, ln_p], loc="upper left", bbox_to_anchor=(0.012, 0.818),
               ncols=2, frameon=False, fontsize=10, labelcolor=SEC,
               handlelength=1.7, columnspacing=1.8, borderaxespad=0)

    fig.text(0.015, 0.018,
             "Source: Robert Shiller's long-run S&P dataset (Yale) via the "
             "datasets/s-and-p-500 mirror; monthly, nominal.",
             fontsize=8.5, color=MUT, ha="left")

    fig.savefig("earnings_engine.png", facecolor="white")
    plt.close(fig)
    print("  wrote earnings_engine.png")


# ---------------------------------------------------------------------------
# MAIN EXECUTION ROUTINE
# ---------------------------------------------------------------------------
def main():
    print("fetching monthly data (Shiller long-run dataset mirror)...")
    rows = fetch_rows()
    print(f"  {len(rows)} months, {rows[0]['date']} -> {rows[-1]['date']}")

    # Build primary time-series datasets
    tr = total_return_index(rows)
    real = [t / r["cpi"] if (t and r["cpi"]) else None for t, r in zip(tr, rows)] # Inflation-adjusted TR
    price = [r["price"] for r in rows]

    # Find the most recent date where total return data (dividends) was available
    last_tr = max(i for i, v in enumerate(tr) if v)
    print(f"  dividends (hence total return) available through {rows[last_tr]['date']}")

    # Calculate probabilities for 1 to 300 months (25 years)
    months = list(range(1, HORIZON_MONTHS + 1))
    market = [win_rate(tr, m)[0] for m in months]

    print("computing exact roulette odds (this is the slow, honest part)...")
    casino = [p_ahead(m * SPINS_PER_EVENING * EVENINGS_PER_MONTH) for m in months]

    # ---- Export Verification CSV ------------------------------------------
    with open("odds_table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["months_playing", "roulette_spins", "p_ahead_roulette",
                    "market_winrate_total_return", "market_winrate_price_only",
                    "market_winrate_inflation_adjusted", "n_windows"])

        for m in months:
            wr_tr, n = win_rate(tr, m)
            wr_p, _ = win_rate(price, m)
            wr_r, _ = win_rate(real, m)
            w.writerow([m, m * SPINS_PER_EVENING,
                        round(casino[m - 1], 6), round(wr_tr, 4),
                        round(wr_p, 4), round(wr_r, 4), n])
    print("  wrote odds_table.csv")

    # ---- Render Charts ----------------------------------------------------
    chart_odds(months, casino, market)
    chart_engine(rows)

    # ---- Output Terminal Statistics ---------------------------------------
    def pct(x): return f"{x*100:.1f}%"

    edge = 1 / 37
    yearly_wagered = STAKE * SPINS_PER_EVENING * EVENINGS_PER_MONTH * 12

    print("\n--- numbers quoted in the post ---")
    print(f"one spin, red, European wheel:            {P_WIN*100:.2f}% "
          f"(edge {edge*100:.2f}% -> expected loss €{STAKE*edge:.2f} per €{STAKE} spin)")
    print(f"one month in the market (1871-2023):      {pct(market[0])}")

    # Print Market milestones
    for label, m in [("1 year", 12), ("5 years", 60), ("10 years", 120),
                     ("15 years", 180), ("20 years", 240)]:
        wr, n = win_rate(tr, m)
        print(f"market ahead after {label:>9}:             {pct(wr)}  ({n} windows)")

    # Print Casino milestones
    for label, m in [("1 year", 12), ("5 years", 60), ("20 years", 240)]:
        print(f"roulette ahead after {label:>9} of evenings: "
              f"{casino[m-1]*100:.4g}%  ({m*SPINS_PER_EVENING:,} spins)")

    # Detailed 20-year Casino statistics
    n20 = 240 * SPINS_PER_EVENING
    mean_loss = n20 * STAKE * edge

    # Standard deviation of a binomial distribution modified for stakes
    sd = STAKE * math.sqrt(n20 * (1 - (2 * P_WIN - 1) ** 2))
    print(f"20-yr gambler: {n20:,} spins, €{240*yearly_wagered/12:,.0f} wagered, "
          f"expected net -€{mean_loss:,.0f} (±€{sd:,.0f})")

    # Compare against lower quality market metrics
    wr20p, _ = win_rate(price, 240)
    wr20r, _ = win_rate(real, 240)
    print(f"20-yr windows positive, price only:       {pct(wr20p)}  (dividends removed)")
    print(f"20-yr windows positive, inflation-adj.:   {pct(wr20r)}  (real purchasing power)")

    # Calculate best/median/worst real-world market outcomes
    mults = []
    for i in range(len(rows) - 240):
        if tr[i] and tr[i + 240]:
            mults.append((tr[i + 240] / tr[i], rows[i]["date"]))
    mults.sort()

    w_, med, b_ = mults[0], mults[len(mults) // 2], mults[-1]
    print(f"20-yr outcomes (nominal, div. reinvested): worst {w_[0]:.2f}x "
          f"(bought {w_[1]}), median {med[0]:.1f}x, best {b_[0]:.1f}x (bought {b_[1]})")

    # Total historical summary stats
    cagr = (tr[last_tr] / tr[0]) ** (12 / last_tr) - 1
    print(f"full-period return, 1871-{rows[last_tr]['date'][:4]}:            "
          f"{cagr*100:.1f}%/yr nominal, dividends reinvested")

    e0 = next(r["earn"] for r in rows if r.get("earn"))
    eL = [r["earn"] for r in rows if r.get("earn")][-1]
    p_at = rows[last_tr]["price"]

    print(f"since 1871: price x{p_at/rows[0]['price']:,.0f}, "
          f"earnings x{eL/e0:,.0f} (both to {rows[last_tr]['date']})")


if __name__ == "__main__":
    main()
