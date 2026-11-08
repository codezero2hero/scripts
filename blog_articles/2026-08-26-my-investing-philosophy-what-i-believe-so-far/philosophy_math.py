"""
philosophy_math.py  --  the arithmetic behind "My Investing Philosophy:
                        What I Believe So Far" (CodeZero2Hero).

WHY THIS EXISTS:
  A philosophy post is mostly opinion, so the two claims in it that are NOT
  opinion should be checkable:
    1. For the first stretch of a monthly investing plan, almost all of the
       portfolio is money you put there yourself. Compounding takes over
       later than beginners expect -- and then it takes over completely.
    2. Two people can follow the exact same plan for thirty years, with the
       same discipline and the same instrument, and end up with wildly
       different results, for the single reason that they were born at
       different times. Effort is controllable. The era is not.
  Both are computed from 150+ years of monthly data for the S&P composite --
  Robert Shiller's long-run dataset (Yale), fetched from the free
  `datasets/s-and-p-500` mirror (three hosts tried in order, plus a local
  cache after the first successful run). No API key, no scraping.

WHAT IT DOES:
  1. Downloads the monthly series (price, dividend, earnings, CPI,
     1871 -> today; dividends/earnings lag price by a couple of years).
  2. Builds a total-return index (dividends reinvested monthly) and deflates
     it by CPI, so every euro below is a euro of PURCHASING POWER.
  3. Runs the same boring plan -- EUR 500 a month, buy, never sell -- through
     every historical start month, and records the whole path.
  4. Chart 1: the median path, split into "money I put in" and "money the
     market added", with the crossover month marked.
  5. Chart 2: the ending multiple of every completed 30-year plan in history,
     plotted against the year the saver started.
  6. Prints the three side calculations the post quotes: the money-weighted
     real return per percentile, the "save €100 more vs. earn 1% more" lever
     comparison at years 10/20/30, and what a 0.5%/1% ongoing fee removes.
  7. Writes a verification CSV and prints every number the article quotes.

WHAT THE PLAN ASSUMES (say it out loud, it matters):
  A fixed real contribution -- EUR 500 in constant purchasing power, i.e. you
  raise the nominal amount with inflation. Buys happen monthly at the index
  level, dividends are reinvested, nothing is ever sold, and there are no
  fees or taxes. Real life adds costs; this is the ceiling, not a forecast.

REQUIREMENTS:  pip install matplotlib       (everything else is stdlib)

Run:  python3 philosophy_math.py
"""

import csv
import io
import statistics
import urllib.request

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# Same file, three hosts; GitHub occasionally rate-limits plain visits (429).
DATA_URLS = [
    "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv",
    "https://cdn.jsdelivr.net/gh/datasets/s-and-p-500@master/data/data.csv",
    "https://datahub.io/core/s-and-p-500/r/data.csv",
]
CACHE_FILE = "shiller_monthly_cache.csv"
USER_AGENT = "CodeZero2Hero research yourname@example.com"

CONTRIB = 500          # euros per month, constant purchasing power
PLAN_YEARS = 30        # the horizon the post plans around
PLAN_MONTHS = PLAN_YEARS * 12


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fetch_rows():
    """Try each mirror in order, cache locally, so a re-run never depends on
    one server's mood."""
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

    def num(v):
        try:
            x = float(v)
            return x if x != 0 else None      # the mirror pads missing months with 0
        except ValueError:
            return None

    return [dict(date=row["Date"][:7],
                 price=num(row["SP500"]),
                 div=num(row["Dividend"]),
                 cpi=num(row["Consumer Price Index"]))
            for row in csv.DictReader(io.StringIO(text))]


def real_total_return_index(rows):
    """Total-return index (one-twelfth of the annualized dividend reinvested
    each month), divided by CPI. Defined only while dividend and CPI data
    exist -- both lag the price series."""
    tr = [None] * len(rows)
    tr[0] = 1.0
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if tr[i - 1] and prev["price"] and cur["price"] and cur["div"]:
            tr[i] = tr[i - 1] * (cur["price"] + cur["div"] / 12) / prev["price"]
    nominal = tr
    real = [t / r["cpi"] if (t and r["cpi"]) else None for t, r in zip(tr, rows)]
    return nominal, real


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------
def plan_path(series, start, months, contrib=CONTRIB):
    """Buy CONTRIB of the index every month, never sell. Returns the monthly
    path of portfolio value (value measured right after each purchase, so the
    final euro contributed has had no time to grow -- deliberately stingy)."""
    units, path = 0.0, []
    for k in range(months):
        p = series[start + k]
        if not p:
            return None
        units += contrib / p
        path.append(units * p)
    return path


def all_windows(series, months, contrib=CONTRIB):
    """Every start month for which a full `months`-long plan is possible."""
    out = []
    for i in range(len(series) - months + 1):
        path = plan_path(series, i, months, contrib)
        if path:
            out.append((i, path))
    return out


def with_drag(series, annual):
    """The same index, with a smooth monthly fee (negative) or bonus (positive)
    applied. This is how an ongoing charge actually bites: a little every
    month, on everything, including the growth it already cost you."""
    m = (1 + annual) ** (1 / 12) - 1
    return [s * (1 + m) ** i if s else None for i, s in enumerate(series)]


def money_weighted_return(final_value, months=PLAN_MONTHS, contrib=CONTRIB):
    """The annual real return that turns `months` monthly contributions into
    `final_value` -- the number the saver actually experienced, which is not
    the index's own return (early euros compound longer than late ones)."""
    lo, hi = -0.02, 0.05
    for _ in range(200):
        mid = (lo + hi) / 2
        v = sum(contrib * (1 + mid) ** (months - 1 - k) for k in range(months))
        if v < final_value:
            lo = mid
        else:
            hi = mid
    return (1 + (lo + hi) / 2) ** 12 - 1


# ---------------------------------------------------------------------------
# Chart style -- house palette, on paper instead of white
# ---------------------------------------------------------------------------
# The blog page is white, so the figures sit on a warm paper panel with a
# hairline edge; otherwise the chart bleeds into the article and nobody can
# tell where one stops and the other starts.
PAPER, EDGE = "#f2efe7", "#ddd8c9"
BLUE, RED = "#2a78d6", "#e34948"          # owner's side / the counter-example
SAND = "#b0a894"                          # "money I put in" -- deliberately dull
INK, SEC, MUT = "#0b0b0b", "#52514e", "#83806f"
GRID, BASE = "#e2ddcd", "#c3bda9"

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.family": "DejaVu Sans",
    "font.size": 12, "axes.grid": False,
})
LEAD = dict(arrowstyle="-", color=BASE, lw=0.9, shrinkA=2, shrinkB=4)


def new_fig():
    fig, ax = plt.subplots(figsize=(10.8, 6.3))
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    fig.subplots_adjust(left=0.086, right=0.965, top=0.74, bottom=0.115)
    return fig, ax


def polish(ax):
    """Recessive chrome: hairline y-grid, single baseline, no tick marks."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUT, length=0, labelsize=10)


def frame(fig):
    """Hairline edge around the whole panel, so it reads as a figure."""
    fig.add_artist(Rectangle((0.0015, 0.0015), 0.997, 0.997, fill=False,
                             ec=EDGE, lw=1.4, transform=fig.transFigure,
                             zorder=1000))


def dot(ax, x, y, color, size=9):
    ax.plot([x], [y], marker="o", ms=size, mfc=color, mec=PAPER, mew=2,
            zorder=6, clip_on=False)


def money(v):
    return f"€{v:,.0f}".replace(",", " ")


# ---------------------------------------------------------------------------
# Chart 1 -- whose money is it, and when does that change?
# ---------------------------------------------------------------------------
def chart_who_paid(windows, crossover_m):
    months = list(range(1, PLAN_MONTHS + 1))
    med = [statistics.median(p[m - 1] for _, p in windows) for m in months]
    put_in = [CONTRIB * m for m in months]
    years = [m / 12 for m in months]

    fig, ax = new_fig()
    ax.fill_between(years, 0, put_in, color=SAND, alpha=0.85, lw=0,
                    label="Money I put in")
    ax.fill_between(years, put_in, med, color=BLUE, alpha=0.80, lw=0,
                    label="Money the market added")
    ax.plot(years, med, color=BLUE, lw=2.2, solid_capstyle="round", zorder=4)
    ax.plot(years, put_in, color="#8f8874", lw=1.6, zorder=4)

    cx = crossover_m / 12
    ax.plot([cx, cx], [0, med[crossover_m - 1]], ls=(0, (4, 4)), lw=1.1,
            color=BASE, zorder=3)
    dot(ax, cx, med[crossover_m - 1], BLUE, size=8)
    ax.annotate(f"Year {cx:.1f}: the market's half of\n"
                f"the portfolio finally overtakes mine",
                xy=(cx, med[crossover_m - 1]),
                xytext=(2.1, 330_000),
                arrowprops=LEAD, color=SEC, fontsize=10.5, linespacing=1.4)

    shares = {}
    for yr, tx, ty in ((10, 1.6, 150_000), (30, 15.2, 470_000)):
        m = yr * 12
        share = 100 * (med[m - 1] - put_in[m - 1]) / med[m - 1]
        shares[yr] = share
        ax.annotate(f"Year {yr}: {share:.0f}% of the pot\nwas never my money",
                    xy=(yr, med[m - 1]), xytext=(tx, ty),
                    arrowprops=LEAD, color=SEC, fontsize=10.5, linespacing=1.4)
        dot(ax, yr, med[m - 1], BLUE, size=7)

    ax.set_xlim(0, 30.4)
    ax.set_ylim(0, max(med) * 1.06)
    ax.set_xticks(range(0, 31, 5))
    ax.yaxis.set_major_formatter(lambda v, _: money(v))
    ax.set_xlabel("Years of paying in", color=MUT, fontsize=10.5)
    polish(ax)

    fig.text(0.015, 0.965, "For the first decade, I am the strategy",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.902,
             "€500 a month into the index, never sold. Median path across every 30-year window since 1871,\n"
             "in constant purchasing power. Early on the portfolio is mostly my paycheque; late on it isn't.",
             fontsize=10.8, color=SEC, ha="left", va="top", linespacing=1.45)
    fig.legend(loc="upper left", bbox_to_anchor=(0.012, 0.818), ncols=2,
               frameon=False, fontsize=10, labelcolor=SEC, handlelength=1.7,
               columnspacing=1.8, borderaxespad=0)
    fig.text(0.015, 0.018,
             "Source: Robert Shiller's long-run S&P dataset (Yale) via the datasets/s-and-p-500 mirror; "
             "dividends reinvested, CPI-adjusted, before fees and taxes.",
             fontsize=8.5, color=MUT, ha="left")
    frame(fig)
    fig.savefig("who_paid.png", facecolor=PAPER)
    plt.close(fig)
    print("  wrote who_paid.png")


# ---------------------------------------------------------------------------
# Chart 2 -- same plan, same discipline, different birth certificate
# ---------------------------------------------------------------------------
def chart_luck_of_the_draw(rows, windows):
    contributed = CONTRIB * PLAN_MONTHS
    xs = [int(rows[i]["date"][:4]) + (int(rows[i]["date"][5:7]) - 1) / 12
          for i, _ in windows]
    ys = [p[-1] / contributed for _, p in windows]
    med = statistics.median(ys)

    fig, ax = new_fig()
    ax.fill_between(xs, 1, ys, where=[y >= 1 for y in ys], color=BLUE,
                    alpha=0.10, lw=0, interpolate=True)
    ax.fill_between(xs, 1, ys, where=[y <= 1 for y in ys], color=RED,
                    alpha=0.12, lw=0, interpolate=True)
    ax.plot(xs, ys, color=BLUE, lw=2.2, solid_capstyle="round", zorder=4)
    span = [xs[0] - 2, xs[-1] + 1.5]
    ax.plot(span, [1, 1], color=BASE, lw=1.1, zorder=2)
    ax.plot(span, [med, med], ls=(0, (4, 4)), lw=1.1, color=MUT, zorder=2)
    ax.text(xs[-1] + 3.0, med, f"median {med:.1f}×", fontsize=10,
            color=SEC, va="center")
    ax.text(xs[-1] + 3.0, 1, "paid in = got out", fontsize=10, color=SEC,
            va="center")

    i_best = max(range(len(ys)), key=lambda i: ys[i])
    i_worst = min(range(len(ys)), key=lambda i: ys[i])
    dot(ax, xs[i_best], ys[i_best], BLUE)
    dot(ax, xs[i_worst], ys[i_worst], RED)
    ax.annotate(f"Started {rows[windows[i_best][0]]['date']}: {ys[i_best]:.1f}×\n"
                f"({money(ys[i_best] * contributed)} of purchasing power)",
                xy=(xs[i_best], ys[i_best]), xytext=(xs[i_best] - 44, ys[i_best] + 0.35),
                arrowprops=LEAD, color=SEC, fontsize=10.5, linespacing=1.4)
    ax.annotate(f"Started {rows[windows[i_worst][0]]['date']}: {ys[i_worst]:.1f}×\n"
                f"({money(ys[i_worst] * contributed)}) — same plan, same patience",
                xy=(xs[i_worst], ys[i_worst]), xytext=(xs[i_worst] + 6, 0.42),
                arrowprops=LEAD, color=SEC, fontsize=10.5, linespacing=1.4)

    ax.set_xlim(xs[0] - 2, xs[-1] + 19)
    ax.set_ylim(0, max(ys) * 1.12)
    ax.set_xticks([y for y in range(1880, 2001, 20)])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}×")
    ax.set_xlabel("Year the saver started the plan", color=MUT, fontsize=10.5)
    ax.set_ylabel("Ending pot ÷ money contributed", color=MUT, fontsize=10.5)
    polish(ax)

    fig.text(0.015, 0.965, "Same discipline. Different century.",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.015, 0.902,
             f"Every completed 30-year plan since 1871: {money(contributed)} paid in at €500 a month, "
             "never sold,\nmeasured in purchasing power. The saver chose the plan. Nobody chose the era.",
             fontsize=10.8, color=SEC, ha="left", va="top", linespacing=1.45)
    fig.text(0.015, 0.018,
             "Source: Robert Shiller's long-run S&P dataset (Yale) via the datasets/s-and-p-500 mirror; "
             "dividends reinvested, CPI-adjusted, before fees and taxes.",
             fontsize=8.5, color=MUT, ha="left")
    frame(fig)
    fig.savefig("luck_of_the_draw.png", facecolor=PAPER)
    plt.close(fig)
    print("  wrote luck_of_the_draw.png")
    return ys, med


# ---------------------------------------------------------------------------
def main():
    print("fetching monthly data (Shiller long-run dataset mirror)...")
    rows = fetch_rows()
    print(f"  {len(rows)} months, {rows[0]['date']} -> {rows[-1]['date']}")

    nominal, real = real_total_return_index(rows)
    last = max(i for i, v in enumerate(real) if v)
    print(f"  real total return defined through {rows[last]['date']}")

    windows = all_windows(real, PLAN_MONTHS)
    print(f"  {len(windows)} complete 30-year plans, "
          f"{rows[windows[0][0]]['date']} -> {rows[windows[-1][0]]['date']} starts")

    # ---- when does the market's half overtake mine? -----------------------
    med_path = [statistics.median(p[m] for _, p in windows)
                for m in range(PLAN_MONTHS)]
    crossover = next(m + 1 for m in range(PLAN_MONTHS)
                     if med_path[m] - CONTRIB * (m + 1) > CONTRIB * (m + 1))

    chart_who_paid(windows, crossover)
    ys, med = chart_luck_of_the_draw(rows, windows)

    # ---- verification CSV -------------------------------------------------
    with open("philosophy_table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["start_month", "end_month", "contributed_eur",
                    "ending_value_real_eur", "multiple_of_contributions"])
        for i, p in windows:
            w.writerow([rows[i]["date"], rows[i + PLAN_MONTHS - 1]["date"],
                        CONTRIB * PLAN_MONTHS, round(p[-1], 2),
                        round(p[-1] / (CONTRIB * PLAN_MONTHS), 3)])
    print("  wrote philosophy_table.csv")

    # ---- every number the article quotes ----------------------------------
    print("\n--- numbers quoted in the post ---")
    print(f"plan: {money(CONTRIB)}/month, {PLAN_YEARS} years, "
          f"{money(CONTRIB * PLAN_MONTHS)} contributed, constant purchasing power")
    for yr in (1, 5, 10, 15, 20, 25, 30):
        m = yr * 12
        v = med_path[m - 1]
        mine = CONTRIB * m
        print(f"  year {yr:>2}: median pot {money(v):>10}, "
              f"of which mine {money(mine):>9} ({100*mine/v:4.1f}%), "
              f"market {100*(v-mine)/v:4.1f}%")
    print(f"  crossover (market's half > mine): month {crossover} "
          f"= year {crossover/12:.1f}")

    srt = sorted(ys)
    def pct(q): return srt[int(q * (len(srt) - 1))]
    contributed = CONTRIB * PLAN_MONTHS
    print(f"\n30-year endings, multiple of money contributed (real):")
    print(f"  worst  {srt[0]:.2f}x  ({money(srt[0]*contributed)})")
    print(f"  10th   {pct(.10):.2f}x  ({money(pct(.10)*contributed)})")
    print(f"  median {med:.2f}x  ({money(med*contributed)})")
    print(f"  90th   {pct(.90):.2f}x  ({money(pct(.90)*contributed)})")
    print(f"  best   {srt[-1]:.2f}x  ({money(srt[-1]*contributed)})")
    print(f"  best is {srt[-1]/srt[0]:.1f}x the worst")
    below = sum(1 for y in ys if y < 1)
    print(f"  windows that lost purchasing power: {below} of {len(ys)} "
          f"({100*below/len(ys):.1f}%)")
    print(f"  windows below 2x: {sum(1 for y in ys if y < 2)} "
          f"({100*sum(1 for y in ys if y < 2)/len(ys):.1f}%)")

    # what does saving more buy you, against the luck of the era?
    print("\ncontrol vs. luck:")
    print(f"  worst era at {money(CONTRIB)}/mo:  {money(srt[0]*contributed)}")
    for bump in (0.25, 0.5, 1.0):
        print(f"  worst era at +{bump*100:.0f}% saved ({money(CONTRIB*(1+bump))}/mo): "
              f"{money(srt[0]*contributed*(1+bump))}"
              f"   vs median era at {money(CONTRIB)}/mo: {money(med*contributed)}")

    # ---- what the saver actually earned, per euro paid in ------------------
    print("\nannual real return on the money as it went in (money-weighted):")
    for label, v in [("worst", srt[0]), ("10th", pct(.10)), ("median", med),
                     ("90th", pct(.90)), ("best", srt[-1])]:
        print(f"  {label:>6}: {money_weighted_return(v * contributed):>6.2%}/yr")

    # ---- the two levers: save more, or earn more? ---------------------------
    print("\nsave €100 more a month vs. earn one more point a year "
          "(median plan, real):")
    boosted = all_windows(with_drag(real, 0.01), PLAN_MONTHS)
    bigger = all_windows(real, PLAN_MONTHS, contrib=CONTRIB + 100)
    for yr in (10, 20, 30):
        m = yr * 12
        base = statistics.median(p[m - 1] for _, p in windows)
        more_saved = statistics.median(p[m - 1] for _, p in bigger)
        more_return = statistics.median(p[m - 1] for _, p in boosted)
        print(f"  year {yr:>2}: base {money(base):>10} | "
              f"+€100/mo {money(more_saved - base):>9} | "
              f"+1%/yr {money(more_return - base):>9} | "
              f"saving is {(more_saved - base) / (more_return - base):.1f}x "
              f"the return lever")

    # ---- the fee that never appears on a statement -------------------------
    print("\nwhat an ongoing charge costs the median 30-year plan:")
    for fee in (0.005, 0.01):
        after = statistics.median(
            p[-1] for _, p in all_windows(with_drag(real, -fee), PLAN_MONTHS))
        cost = med * contributed - after
        print(f"  {fee*100:.1f}%/yr: ends at {money(after)} "
              f"-- {money(cost)} gone ({cost/(med*contributed):.1%} of the pot)")

    # nominal cross-check, for the behind-the-scenes note
    nwin = all_windows(nominal, PLAN_MONTHS)
    nys = sorted(p[-1] / contributed for _, p in nwin)
    print(f"\nnominal cross-check ({len(nwin)} windows): worst {nys[0]:.2f}x, "
          f"median {statistics.median(nys):.2f}x, best {nys[-1]:.2f}x")


if __name__ == "__main__":
    main()
