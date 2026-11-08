"""
WHY THIS EXISTS:
  The post claims that the market pays out of two different tills:
    1. The INVESTMENT till: dividends you were paid plus the growth of
       the earnings underneath the index. Money that came from customers.
    2. The SPECULATIVE till: the change in how much the crowd was willing
       to pay per dollar of those earnings (the P/E multiple). Money that
       came from the next buyer's mood.
  John Bogle called this split "Occam's razor". This script computes it
  from 150+ years of monthly S&P composite data (Robert Shiller's
  long-run dataset, Yale, via the free `datasets/s-and-p-500` mirror --
  same source and cache as casino_vs_market.py). No API key, no scraping.

  The decomposition is EXACT, done in log space:
      log(total return) = log(earnings growth)
                        + log(P/E change)
                        + log(dividend reinvestment)
  because Price = Earnings x P/E, identically, and reinvested dividends
  multiply in as their own separable factor. No residual, no hand-waving.

WHAT IT DOES:
  1. Downloads the monthly series (price, dividend, earnings, 1871->today;
     dividends/earnings lag price by a couple of years).
  2. Splits every calendar decade's annualized return into the two tills,
     charts them as stacked bars (two_paychecks.png).
  3. For every holding period from 1 to 25 years, asks of each historical
     window: which till moved your result MORE -- the business
     (earnings + dividends) or the mood (P/E change)? Charts the share of
     windows where the business won (whose_game.png).
  4. Writes a verification CSV and prints every number the article quotes.

REQUIREMENTS:  pip install matplotlib       (everything else is stdlib)

Run:  python3 investment_vs_speculation.py
"""

import csv
import io
import math
import urllib.request

import matplotlib.pyplot as plt

# Same file, three hosts, tried in order; local cache after the first
# successful run. (GitHub sometimes rate-limits plain visits with a 429.)
DATA_URLS = [
    "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv",
    "https://cdn.jsdelivr.net/gh/datasets/s-and-p-500@master/data/data.csv",
    "https://datahub.io/core/s-and-p-500/r/data.csv",
]
CACHE_FILE = "shiller_monthly_cache.csv"
USER_AGENT = "CodeZero2Hero research yourname@example.com"

MAX_YEARS = 25          # horizon chart runs 1..25 years


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fetch_rows():
    """Try each mirror in order and keep a local cache, so re-runs (and
    rate-limited afternoons) don't depend on any one server's mood."""
    text = None
    for url in DATA_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8")
            print(f"  fetched from {url.split('/')[2]}")
            with open(CACHE_FILE, "w") as f:
                f.write(text)
            break
        except Exception as e:
            print(f"  {url.split('/')[2]} unavailable ({e}) -- trying next mirror")
    if text is None:
        try:
            with open(CACHE_FILE) as f:
                text = f.read()
            print(f"  all mirrors down -- using local {CACHE_FILE}")
        except FileNotFoundError:
            raise SystemExit("no mirror reachable and no local cache yet -- "
                             "try again in a few minutes.")
    rows = list(csv.DictReader(io.StringIO(text)))
    def num(v):
        try:
            x = float(v)
            return x if x != 0 else None   # the mirror pads missing months with 0
        except ValueError:
            return None
    return [dict(date=row["Date"][:7],
                 price=num(row["SP500"]),
                 div=num(row["Dividend"]),
                 earn=num(row["Earnings"]))
            for row in rows]


def build_components(rows):
    """For each month i, the cumulative LOG of each multiplicative factor
    since the start of the data:
      logP[i]  -- log price level
      logE[i]  -- log 12-month earnings
      logD[i]  -- log of the cumulative dividend-reinvestment factor,
                  i.e. sum of log(1 + monthly dividend / (12 * price))
    Any window [a, b] then decomposes EXACTLY:
      total log return  = (logP[b]-logP[a]) + (logD[b]-logD[a])
      earnings part     =  logE[b]-logE[a]
      P/E part          = (logP[b]-logP[a]) - (logE[b]-logE[a])
      dividend part     =  logD[b]-logD[a]
    """
    n = len(rows)
    logP = [math.log(r["price"]) if r["price"] else None for r in rows]
    logE = [math.log(r["earn"]) if r["earn"] else None for r in rows]
    logD = [None] * n
    acc = 0.0
    for i, r in enumerate(rows):
        if r["price"] and r["div"]:
            acc += math.log(1 + r["div"] / (12 * r["price"]))
            logD[i] = acc
    return logP, logE, logD


def window_split(logP, logE, logD, a, b):
    """Annualized components of the window [a, b] (month indexes), or None
    if any ingredient is missing at either end."""
    if None in (logP[a], logP[b], logE[a], logE[b], logD[a], logD[b]):
        return None
    yrs = (b - a) / 12
    earn = (logE[b] - logE[a]) / yrs
    pe = ((logP[b] - logP[a]) - (logE[b] - logE[a])) / yrs
    div = (logD[b] - logD[a]) / yrs
    return dict(earn=earn, pe=pe, div=div, total=earn + pe + div, years=yrs)


def pct(logr):
    """Log-rate -> ordinary percent per year."""
    return (math.exp(logr) - 1) * 100


# ---------------------------------------------------------------------------
# Chart style (house style -- see casino_vs_market.py).
# Update 2026-08-23: charts now sit on a warm paper card (rounded corners,
# hairline border, transparent outside) so figures read as their own panel
# against the blog's white page instead of dissolving into it. The blue/red
# pair re-validated for contrast and CVD separation on this surface.
# ---------------------------------------------------------------------------
BLUE, RED = "#2a78d6", "#e34948"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#898781"
SURFACE, BORDER = "#f6f4ee", "#ddd8cb"                # paper card + its edge
GRID, BASE = "#e6e2d7", "#c3beb0"                     # hairline grid, baseline

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.family": "DejaVu Sans",
    "font.size": 12, "axes.grid": False, "axes.facecolor": "none",
})
LEAD = dict(arrowstyle="-", color=BASE, lw=0.9, shrinkA=2, shrinkB=4)


def paper(fig):
    """Rounded paper card behind everything; corners outside it stay
    transparent, so on a white blog page the figure reads as a panel."""
    from matplotlib.patches import FancyBboxPatch
    card = FancyBboxPatch(
        (0.004, 0.007), 0.992, 0.986,
        boxstyle="round,pad=0,rounding_size=0.013",
        mutation_aspect=fig.get_figwidth() / fig.get_figheight(),
        transform=fig.transFigure, facecolor=SURFACE, edgecolor=BORDER,
        linewidth=1.3, zorder=-10)
    fig.add_artist(card)


def save(fig, name):
    fig.savefig(name, transparent=True)
    plt.close(fig)
    print(f"  wrote {name}")


def polish(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUT, length=0, labelsize=10)


def dot(ax, x, y, color, size=9):
    """A marker ringed in the paper color so it stays legible on its line."""
    ax.plot([x], [y], marker="o", ms=size, mfc=color, mec=SURFACE, mew=2,
            zorder=5, clip_on=False)


def chart_decades(decades):
    """Stacked bars: blue = the business's paycheck (earnings growth +
    dividends), red = the mood's paycheck (P/E change), ink dot = total."""
    fig, ax = plt.subplots(figsize=(10.8, 6.3))
    fig.subplots_adjust(left=0.072, right=0.965, top=0.74, bottom=0.115)
    paper(fig)

    # the full-period bar stands apart from the decades with a small gap
    xs = list(range(len(decades) - 1)) + [len(decades) - 1 + 0.7]
    biz = [pct(d["earn"] + d["div"]) for d in decades]
    mood = [pct(d["pe"]) for d in decades]
    tot = [pct(d["total"]) for d in decades]

    # paper-colored edges give stacked segments a crisp hairline gap
    ax.bar(xs, biz, 0.62, color=BLUE, ec=SURFACE, lw=1.0,
           label="Paid by the business (earnings growth + dividends)")
    # mood bar stacks on top of biz when positive, hangs below zero when negative
    bottoms = [b if m >= 0 else 0 for b, m in zip(biz, mood)]
    ax.bar(xs, mood, 0.62, bottom=bottoms, color=RED, ec=SURFACE, lw=1.0,
           label="Paid by the mood (P/E change)")
    for x, t in zip(xs, tot):
        dot(ax, x, t, INK, size=7)

    ax.axhline(0, color=BASE, lw=1.0, zorder=1)
    ax.set_xticks(xs)
    ax.set_xticklabels([d["label"] for d in decades], fontsize=9.5)
    ax.set_ylim(-9.8, 22)
    ax.set_yticks([-5, 0, 5, 10, 15, 20])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylabel("Annualized return, nominal", color=MUT, fontsize=10.5)
    polish(ax)

    # annotate the two eras readers will ask about, plus the full-period bar
    i70 = next(i for i, d in enumerate(decades) if d["label"] == "1970s")
    i90 = next(i for i, d in enumerate(decades) if d["label"] == "1990s")
    ax.annotate("1970s: the business earned,\nthe mood took it back",
                xy=(xs[i70], -6.2), xytext=(xs[i70] + 1.15, -8.6),
                arrowprops=LEAD, color=SEC, fontsize=10.5)
    ax.annotate("1990s: a third of the\ndecade's return was mood",
                xy=(xs[i90], tot[i90] + 0.9), xytext=(xs[i90] + 0.75, 20.3),
                arrowprops=LEAD, color=SEC, fontsize=10.5)
    ax.annotate("150+ years: the mood\nnets almost nothing",
                xy=(xs[-1], tot[-1] + 0.9), xytext=(xs[-1] - 3.05, 15.9),
                arrowprops=LEAD, color=SEC, fontsize=10.5)

    fig.text(0.015, 0.965, "The market pays from two different tills",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.902,
             "Each decade's S&P return split into what the businesses produced and what the crowd's\n"
             "mood added or removed. Dot = the decade's actual total return.",
             fontsize=10.8, color=SEC, ha="left", va="top", linespacing=1.45)
    fig.legend(loc="upper left", bbox_to_anchor=(0.012, 0.818), ncols=2,
               frameon=False, fontsize=10, labelcolor=SEC, handlelength=1.4,
             columnspacing=1.8, borderaxespad=0)
    fig.text(0.015, 0.042,
             "Source: Robert Shiller's long-run S&P dataset (Yale) via the datasets/s-and-p-500 mirror; "
             "monthly, nominal, dividends reinvested. Exact log-space split.",
             fontsize=8.5, color=MUT, ha="left")
    fig.text(0.015, 0.016,
             "*2020s runs through 2023-06, where the dividend/earnings series currently end.",
             fontsize=8.5, color=MUT, ha="left")
    save(fig, "two_paychecks.png")


def chart_whose_game(years, med_biz, med_mood):
    """Two curves vs. holding period: the business's median contribution
    (steady at every horizon) and the mood's median swing (decaying).
    The crossing point is where the game changes hands."""
    fig, ax = plt.subplots(figsize=(10.8, 6.3))
    fig.subplots_adjust(left=0.072, right=0.965, top=0.74, bottom=0.115)
    paper(fig)
    biz = [med_biz[y] for y in years]
    mood = [med_mood[y] for y in years]

    # blue wash: the region where the business's paycheck exceeds the
    # mood's power -- the investor's advantage, growing with time
    ax.fill_between(years, mood, biz, where=[b >= m for b, m in zip(biz, mood)],
                    color=BLUE, alpha=0.045, lw=0)
    ln_b, = ax.plot(years, biz, color=BLUE, lw=2.6, solid_capstyle="round",
                    zorder=3, label="The business: earnings + dividends (median)")
    ln_m, = ax.plot(years, mood, color=RED, lw=2.6, solid_capstyle="round",
                    zorder=3, label="The mood: P/E swing, either direction (median)")

    dot(ax, 1, mood[0], RED); dot(ax, 1, biz[0], BLUE)
    dot(ax, 20, mood[19], RED); dot(ax, 20, biz[19], BLUE)
    ax.annotate(f"One year: the multiple alone swings\nyour result ±{mood[0]:.0f} points — more than\nthe business contributes",
                xy=(1, mood[0]), xytext=(2.6, 15.2),
                arrowprops=LEAD, color=SEC, fontsize=10.5)
    ax.annotate(f"Twenty years: the mood is worn\ndown to ±{mood[19]:.1f} points a year…",
                xy=(20, mood[19]), xytext=(15.1, 6.3),
                arrowprops=LEAD, color=SEC, fontsize=10.5)
    ax.annotate(f"…while the business still pays\nits steady ~{biz[19]:.0f} points a year",
                xy=(20, biz[19]), xytext=(15.1, 12.2),
                arrowprops=LEAD, color=SEC, fontsize=10.5)
    # where the curves cross: the game changes hands
    cross = next((y for y, b, m in zip(years, biz, mood) if b > m), None)
    if cross and cross > years[0]:
        ax.annotate("around here, the game\nchanges hands",
                    xy=(cross - 0.5, (biz[cross - 1] + mood[cross - 1]) / 2),
                    xytext=(cross + 1.6, 11.4),
                    arrowprops=LEAD, color=SEC, fontsize=10.5)

    ax.set_xlim(0, 25.4); ax.set_ylim(0, 17)
    ax.set_xticks(range(0, 26, 5))
    ax.set_yticks(range(0, 17, 4))
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} pts")
    ax.set_xlabel("Holding period, years", color=MUT, fontsize=10.5)
    polish(ax)

    fig.text(0.015, 0.965, "Time wears the mood out. It never wears out the business.",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.902,
             "For every holding period: the median annualized contribution of the business till vs. the median\n"
             "size of the mood till's swing, across all same-length windows since 1871. Points per year.",
             fontsize=10.8, color=SEC, ha="left", va="top", linespacing=1.45)
    fig.legend(handles=[ln_b, ln_m], loc="upper left",
               bbox_to_anchor=(0.012, 0.818), ncols=2, frameon=False,
               fontsize=10, labelcolor=SEC, handlelength=1.7,
               columnspacing=1.8, borderaxespad=0)
    fig.text(0.015, 0.018,
             "Source: Robert Shiller's long-run S&P dataset (Yale) via the datasets/s-and-p-500 mirror; "
             "monthly, nominal, dividends reinvested.",
             fontsize=8.5, color=MUT, ha="left")
    save(fig, "whose_game.png")


# ---------------------------------------------------------------------------
def main():
    print("fetching monthly data (Shiller long-run dataset mirror)...")
    rows = fetch_rows()
    print(f"  {len(rows)} months, {rows[0]['date']} -> {rows[-1]['date']}")
    logP, logE, logD = build_components(rows)

    idx = {r["date"]: i for i, r in enumerate(rows)}
    last = max(i for i in range(len(rows))
               if logE[i] is not None and logD[i] is not None)
    print(f"  earnings + dividends (hence the split) available through {rows[last]['date']}")

    # ---- decades ----------------------------------------------------------
    decades = []
    for y0 in range(1880, 2030, 10):
        a = idx.get(f"{y0}-01")
        b = idx.get(f"{y0 + 10}-01")
        if b is None or b > last:
            b = last
        if a is None or a >= b:
            continue
        d = window_split(logP, logE, logD, a, b)
        if d:
            partial = (b == last and (b - a) < 119)
            d["label"] = f"{y0}s" + ("*" if partial else "")
            decades.append(d)
    full = window_split(logP, logE, logD, 0, last)
    full["label"] = f"1871–{rows[last]['date'][:4]}"
    decades.append(full)

    # ---- whose game, by horizon ------------------------------------------
    years = list(range(1, MAX_YEARS + 1))
    share, med_mood, med_biz = [], {}, {}
    for y in years:
        m = 12 * y
        biz_wins = tot = 0
        moods, bizs = [], []
        for a in range(0, last - m + 1):
            d = window_split(logP, logE, logD, a, a + m)
            if d:
                tot += 1
                biz = d["earn"] + d["div"]
                if abs(biz) > abs(d["pe"]):
                    biz_wins += 1
                moods.append(abs(pct(d["pe"])))
                bizs.append(pct(biz))
        share.append(biz_wins / tot if tot else None)
        moods.sort(); bizs.sort()
        med_mood[y] = moods[len(moods) // 2]
        med_biz[y] = bizs[len(bizs) // 2]

    # ---- verification CSV -------------------------------------------------
    with open("decomposition_table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["window", "earnings_growth_pct", "dividend_part_pct",
                    "business_till_pct", "mood_till_pct", "total_pct"])
        for d in decades:
            w.writerow([d["label"], round(pct(d["earn"]), 2),
                        round(pct(d["div"]), 2),
                        round(pct(d["earn"] + d["div"]), 2),
                        round(pct(d["pe"]), 2), round(pct(d["total"]), 2)])
        w.writerow([])
        w.writerow(["holding_years", "share_windows_business_dominates",
                    "median_abs_mood_pct_per_yr", "median_business_pct_per_yr"])
        for y in years:
            w.writerow([y, round(share[y - 1], 4),
                        round(med_mood[y], 2), round(med_biz[y], 2)])
    print("  wrote decomposition_table.csv")

    # ---- charts -----------------------------------------------------------
    chart_decades(decades)
    chart_whose_game(years, med_biz, med_mood)

    # ---- every number the article quotes ----------------------------------
    print("\n--- numbers quoted in the post ---")
    print(f"{'window':>14} {'business':>9} {'mood':>7} {'total':>7}")
    for d in decades:
        print(f"{d['label']:>14} {pct(d['earn'] + d['div']):>8.1f}% "
              f"{pct(d['pe']):>6.1f}% {pct(d['total']):>6.1f}%")
    print(f"\nfull period {full['label']}: "
          f"earnings growth {pct(full['earn']):.1f}%/yr + dividends {pct(full['div']):.1f}%/yr "
          f"+ mood {pct(full['pe']):.1f}%/yr = {pct(full['total']):.1f}%/yr")
    p0 = math.exp(logP[0] - logE[0]); pL = math.exp(logP[last] - logE[last])
    print(f"P/E: {p0:.1f} at start -> {pL:.1f} at end "
          f"(x{pL/p0:.1f} in {full['years']:.0f} years)")
    for y in (1, 2, 3, 4, 5, 10, 20):
        print(f"{y:>2}-year windows: business dominates {share[y-1]*100:.0f}% | "
              f"median mood swing ±{med_mood[y]:.1f} pts/yr vs "
              f"median business {med_biz[y]:.1f} pts/yr")
    cross = next((y for y in years if med_biz[y] > med_mood[y]), None)
    print(f"the curves cross at {cross} years: from there on, the typical "
          f"business contribution outweighs the typical mood swing")


if __name__ == "__main__":
    main()
