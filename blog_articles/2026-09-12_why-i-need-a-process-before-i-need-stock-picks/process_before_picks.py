"""
WHY THIS EXISTS:
  The post argues that a stock pick is the *output* of a process, and that
  building the process is the part beginners skip. Two of its claims are
  checkable rather than rhetorical, so they get checked here:

    1. A short, deliberately unambitious checklist throws away most of the
       stock market. Run five plain tests over every US company that filed
       an audited annual profit figure with the SEC, and roughly nine in ten
       are gone before anyone has an opinion about anything.

    2. Passing once is not passing. Re-run the identical checklist against
       the numbers from four years earlier and about half the names on that
       older list no longer qualify -- so a list of picks decays, while a
       process does not.

  And one claim that is about behaviour rather than screening:

    3. Every obvious winner of the last decade spent long stretches deeply
       underwater. Picking right was never the hard part; staying picked was.

DATA (both sources are free, neither needs an account):
  * SEC EDGAR XBRL "frames" API -- one call returns a single reported
    concept for every filer in a period. Primary source, straight from the
    filings. https://data.sec.gov/api/xbrl/frames/...
  * EODHD end-of-day prices, split- and dividend-adjusted. The public demo
    token only serves a handful of tickers; that handful is the sample in
    chart 2, and swapping in your own key widens it.

WHAT THE CHECKLIST IS (five tests, in this order):
  1. It made a profit in its latest financial year.
  2. It made a profit in each of the five latest financial years.
  3. Operating cash flow covered its capital spending last year.
  4. It sold more in the latest year than five years earlier.
  5. Its diluted share count is no more than 10% higher than five years ago,
     adjusted for stock splits -- see share_basis(), which exists because the
     SEC's data is not split-adjusted and a naive read makes every company
     that ever split look like a serial diluter.

  Every one of those is a floor, not a standard. None of them says the
  company is good, and none says the price is sensible. They exist to make
  the list small enough that a human can do the actual work.

  Missing data counts as a fail. That is a deliberate choice and it is
  discussed in the post: a checklist that guesses when the filing is silent
  is not a checklist.

REQUIREMENTS:  pip install matplotlib     (everything else is stdlib)

Run:  python3 process_before_picks.py
"""

import csv
import datetime as dt
import json
import os
import statistics
import sys
import time
import urllib.request

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# SEC asks for a real contact string in the User-Agent. Put yours here.
UA = {"User-Agent": "CodeZero2Hero research yourname@example.com"}
CACHE = "edgar_cache"
CONCEPT_CACHE = "edgar_concept_cache"
PX_CACHE = "price_cache"

LATEST = 2025          # latest complete financial year available on EDGAR
LOOKBACK = 4           # so the window is LATEST-4 .. LATEST, i.e. five years

# The second screen is not an older *period* to analyse -- it is the same
# five tests run as they would have read a few years ago, so the two lists can
# be compared. Its window therefore has to END in the past: with VINTAGE_GAP=4
# and LATEST=2025, the old vintage grades FY2017-FY2021, which is what someone
# running this checklist in early 2022 would have seen. Making it run to the
# present would just reproduce the current screen and there would be nothing
# to compare. Raise the gap for a longer decay test, lower it for a shorter
# one; the only cost is that the two windows stop overlapping at all.
VINTAGE_GAP = 4
PRIOR = LATEST - VINTAGE_GAP

# EODHD's public demo token. It serves these tickers and no others.
EOD_TOKEN = "demo"
TICKERS = [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("AMZN", "Amazon"),
           ("TSLA", "Tesla"), ("MCD", "McDonald's"),
           ("VTI", "The whole US market")]
PX_FROM = "2016-09-07"


# ---------------------------------------------------------------------------
# EDGAR
# ---------------------------------------------------------------------------
def frame(concept, period, unit="USD", taxonomy="us-gaap"):
    """One XBRL concept, one period, every filer that reported it.

    Cached on disk, because re-running this while writing a post should not
    mean re-downloading twenty megabytes from the SEC every time.
    """
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{taxonomy}_{concept}_{unit}_{period}.json"
    if os.path.exists(path):
        return json.load(open(path))
    url = (f"https://data.sec.gov/api/xbrl/frames/"
           f"{taxonomy}/{concept}/{unit}/{period}.json")
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=120) as r:
            data = json.load(r)
        json.dump(data, open(path, "w"))
        time.sleep(0.2)                      # SEC fair-use: stay under 10/sec
        return data
    except Exception as e:
        print(f"  could not fetch {concept} {period}: {e}")
        return {"data": []}


def facts(concept, period, unit="USD"):
    """{cik: value} for one concept and period."""
    return {e["cik"]: e["val"] for e in frame(concept, period, unit)["data"]}


def facts_with_period(concept, period, unit="USD"):
    """{cik: (value, period_end_date)}. The end date matters: the SEC's
    calendar-year frames include odd fiscal years, so "CY2021" can hold a
    period running to May 2022. Carrying the real end date through means the
    split adjustment later looks up exactly the right fiscal year."""
    return {e["cik"]: (e["val"], e["end"])
            for e in frame(concept, period, unit)["data"]}


def entity_names(period):
    return {e["cik"]: e.get("entityName", "")
            for e in frame("NetIncomeLoss", f"CY{period}")["data"]}


def revenue(year):
    """Revenue is the messiest common concept in XBRL: three tags in wide use,
    and plenty of filers use more than one. Preference order matters, so the
    most specific tag is applied last and wins."""
    out = {}
    for tag in ("RevenueFromContractWithCustomerIncludingAssessedTax",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues"):
        out.update(facts(tag, f"CY{year}"))
    return out


def capex(year):
    """Same problem, smaller: property-plant-and-equipment is the usual tag,
    'productive assets' is the common alternative."""
    out = dict(facts("PaymentsToAcquireProductiveAssets", f"CY{year}"))
    out.update(facts("PaymentsToAcquirePropertyPlantAndEquipment", f"CY{year}"))
    return out


def company_concept(cik, concept, taxonomy="us-gaap"):
    """Every fact one company has ever filed for one concept, across all its
    filings. Unlike a frame, this shows the same fiscal year as reported in
    several different filings -- which is the only way to see a stock split."""
    os.makedirs(CONCEPT_CACHE, exist_ok=True)
    path = f"{CONCEPT_CACHE}/{cik}_{concept}.json"
    if os.path.exists(path):
        return json.load(open(path))
    url = (f"https://data.sec.gov/api/xbrl/companyconcept/"
           f"CIK{int(cik):010d}/{taxonomy}/{concept}.json")
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=60) as r:
            data = json.load(r)
    except Exception:
        data = {"units": {}}                 # company never tagged it; treat as absent
    json.dump(data, open(path, "w"))
    time.sleep(0.12)
    return data


_SHARE_BASIS = {}


def share_basis(cik):
    """Annual diluted share counts for one company, all put on a SINGLE split
    basis.

    This exists because of a trap that cost me an afternoon. XBRL facts are
    stored as they were *originally reported*, and a company that later splits
    its stock does not go back and restate filings nobody is reading any more.
    So Apple's 2017 share count sits in the SEC's data as 5.25 billion (before
    the 2020 four-for-one split) while its 2025 count is 15.0 billion, and any
    naive comparison concludes that Apple tripled its share count. Apple has
    been shrinking it every year.

    The fix: the same fiscal year appears in several filings, and the ratio
    between those reported values is the split factor. Walk the filings newest
    to oldest and chain the overlapping years, and everything lands on today's
    basis."""
    if cik in _SHARE_BASIS:
        return _SHARE_BASIS[cik]
    raw = (company_concept(cik, "WeightedAverageNumberOfDilutedSharesOutstanding")
           .get("units", {}).get("shares", []))
    by_filing = {}
    for f in raw:
        if not f.get("start") or not f.get("end"):
            continue
        days = (dt.date.fromisoformat(f["end"])
                - dt.date.fromisoformat(f["start"])).days
        if not 330 <= days <= 400:           # annual periods only
            continue
        rec = by_filing.setdefault(f["accn"], {"filed": f.get("filed", ""),
                                               "vals": {}})
        rec["vals"][f["end"]] = f["val"]

    out = {}
    for accn in sorted(by_filing, key=lambda a: by_filing[a]["filed"],
                       reverse=True):
        vals = by_filing[accn]["vals"]
        overlap = [e for e in vals if e in out and vals[e]]
        factor = (statistics.median([out[e] / vals[e] for e in overlap])
                  if overlap else 1.0)
        for end, v in vals.items():
            out.setdefault(end, v * factor)
    _SHARE_BASIS[cik] = out
    return out


def load_universe(end_year):
    """Everything the five tests need, for a window ending in `end_year`."""
    start = end_year - LOOKBACK
    return dict(
        ni={y: facts("NetIncomeLoss", f"CY{y}")
            for y in range(start, end_year + 1)},
        cfo=facts("NetCashProvidedByUsedInOperatingActivities", f"CY{end_year}"),
        capex=capex(end_year),
        rev_now=revenue(end_year), rev_then=revenue(start),
        # Frame share counts are NOT split-adjusted, so they are used only to
        # ask "did this company report the number at all". The pass/fail test
        # uses share_basis(), which is.
        sh_now=facts_with_period(
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            f"CY{end_year}", "shares"),
        sh_then=facts_with_period(
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            f"CY{start}", "shares"),
        start=start, end=end_year)


# ---------------------------------------------------------------------------
# The checklist
# ---------------------------------------------------------------------------
# Each test returns True (passed), False (failed) or None (the filing does not
# give me the number). None counts as a fail, but is tallied separately,
# because "this company did badly" and "I cannot tell" are different kinds of
# ignorance and only one of them is the company's fault.
def t1_profitable(u, cik):
    v = u["ni"][u["end"]].get(cik)
    return None if v is None else v > 0


def t2_profitable_five(u, cik):
    vals = [u["ni"][y].get(cik) for y in range(u["start"], u["end"] + 1)]
    return None if any(v is None for v in vals) else all(v > 0 for v in vals)


def t3_cash_covers_capex(u, cik):
    cfo, cap = u["cfo"].get(cik), u["capex"].get(cik)
    return None if (cfo is None or cap is None) else (cfo - cap) > 0


def t4_grew(u, cik):
    r0, r1 = u["rev_then"].get(cik), u["rev_now"].get(cik)
    return None if (r0 is None or r1 is None or r0 <= 0) else r1 > r0


def t5_no_dilution(u, cik):
    # Split-adjusted, which needs one extra request per company. It runs last
    # for exactly that reason: by this point only a few hundred are left.
    then_, now_ = u["sh_then"].get(cik), u["sh_now"].get(cik)
    if then_ is None or now_ is None:
        return None
    b = share_basis(cik)
    s0, s1 = b.get(then_[1]), b.get(now_[1])
    return None if (s0 is None or s1 is None or s0 <= 0) else s1 <= s0 * 1.10


TESTS = [t1_profitable, t2_profitable_five, t3_cash_covers_capex,
         t4_grew, t5_no_dilution]


LABELS = ["Filed an annual profit-or-loss figure",
          "Made a profit last year",
          "Made a profit in all five years",
          "Cash flow covered its capital spending",
          "Sold more than it did five years ago",
          "Didn't print 10% more shares"]


def progress_reporter(total):
    """Test 5 makes one request per company, so on a cold cache that loop runs
    for minutes and looks like a hang. This returns a callable(done) that says
    how far along it is.

    In a terminal the line rewrites itself a few times a second. Piped to a
    file it prints every ten seconds instead, and stays silent altogether if
    the whole loop finishes in a few seconds off the cache -- a log full of
    progress lines for work that took no time is just noise.
    """
    started = time.time()
    state = {"last": started}
    tty = sys.stdout.isatty()

    def report(done):
        now = time.time()
        elapsed = now - started
        final = done >= total
        if not final and now - state["last"] < (0.25 if tty else 10.0):
            return
        state["last"] = now
        frac = done / total if total else 1.0
        eta = (elapsed / frac - elapsed) if frac else 0.0
        msg = (f"    {done:>5} of {total}  ({frac * 100:5.1f}%)   "
               f"{total - done:>5} to go   elapsed {elapsed / 60:4.1f} min"
               f"   eta {eta / 60:4.1f} min")
        if tty:
            print("\r" + msg + "   ", end="", flush=True)
            if final:
                print()
        elif elapsed > 5:
            print(msg, flush=True)

    return report


def funnel(u):
    """Apply the tests in order and record how many are left after each."""
    alive = set(u["ni"][u["end"]].keys())
    counts = [len(alive)]
    missing = [0]
    for test in TESTS:
        # Only the dilution test touches the network, one company at a time.
        chatty = test is t5_no_dilution
        total = len(alive)
        report = None
        if chatty:
            cached = sum(1 for c in alive if os.path.exists(
                f"{CONCEPT_CACHE}/{c}_"
                f"WeightedAverageNumberOfDilutedSharesOutstanding.json"))
            todo = total - cached
            print(f"  test 5 reads each company's filing history one at a "
                  f"time: {total} to check, {cached} cached, {todo} to fetch"
                  + ("  (all cached, this is quick)" if not todo
                     else f"  (~{todo * 0.35 / 60:.0f} min)"))
            report = progress_reporter(total)
        gone_missing = 0
        nxt = set()
        for n, cik in enumerate(sorted(alive), 1):
            r = test(u, cik)
            if r is True:
                nxt.add(cik)
            elif r is None:
                gone_missing += 1
            if report:
                report(n)
        alive = nxt
        counts.append(len(alive))
        missing.append(gone_missing)
    return counts, missing, alive


# ---------------------------------------------------------------------------
# Prices, for the behaviour half of the argument
# ---------------------------------------------------------------------------
def prices(ticker):
    os.makedirs(PX_CACHE, exist_ok=True)
    path = f"{PX_CACHE}/{ticker}.json"
    if os.path.exists(path):
        return json.load(open(path))
    url = (f"https://eodhd.com/api/eod/{ticker}.US?api_token={EOD_TOKEN}"
           f"&fmt=json&period=d&from={PX_FROM}")
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=60) as r:
        raw = json.load(r)
    out = [(x["date"], x["adjusted_close"]) for x in raw]
    json.dump(out, open(path, "w"))
    time.sleep(0.4)
    return out


def drawdowns(series):
    """Worst peak-to-trough fall, how many separate 20% falls, and the longest
    stretch spent below a previous high. Adjusted closes, so dividends are
    already in the number."""
    dates = [d for d, _ in series]
    px = [v for _, v in series]
    peak, worst, worst_on = px[0], 0.0, dates[0]
    below_since, longest, longest_span = None, 0, None
    falls, in_fall = 0, False

    for i, v in enumerate(px):
        if v >= peak:
            if below_since is not None:
                span = (dt.date.fromisoformat(dates[i])
                        - dt.date.fromisoformat(dates[below_since])).days
                if span > longest:
                    longest, longest_span = span, (dates[below_since], dates[i])
                below_since = None
            peak, in_fall = v, False
        else:
            if below_since is None:
                below_since = i
            dd = v / peak - 1
            if dd < worst:
                worst, worst_on = dd, dates[i]
            if dd <= -0.20 and not in_fall:
                falls, in_fall = falls + 1, True
    if below_since is not None:                 # still underwater right now
        span = (dt.date.fromisoformat(dates[-1])
                - dt.date.fromisoformat(dates[below_since])).days
        if span > longest:
            longest, longest_span = span, (dates[below_since], "today")

    years = ((dt.date.fromisoformat(dates[-1])
              - dt.date.fromisoformat(dates[0])).days / 365.25)
    return dict(mult=px[-1] / px[0], worst=worst, worst_on=worst_on,
                falls=falls, underwater_months=longest / 30.44,
                underwater_span=longest_span, years=years,
                start=dates[0], end=dates[-1])


# ---------------------------------------------------------------------------
# Chart style -- house palette, on paper instead of white
# ---------------------------------------------------------------------------
# The blog page is white, so figures sit on a warm paper panel with a hairline
# edge, otherwise the chart bleeds into the article. Output is capped at
# 1200x600 px: 10x5 inches at 120 dpi.
PAPER, EDGE = "#f2efe7", "#ddd8c9"
BLUE, RED = "#2a78d6", "#e34948"
SAND = "#ddd6c4"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#83806f"
GRID, BASE = "#e2ddcd", "#c3bda9"

plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 120, "font.family": "DejaVu Sans",
    "font.size": 11, "axes.grid": False,
})


def new_fig(left=0.30, top=0.735, bottom=0.10, right=0.985):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    fig.subplots_adjust(left=left, right=right, top=top, bottom=bottom)
    return fig, ax


def polish(ax, spines=("top", "right", "left")):
    for s in spines:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUT, length=0, labelsize=9.5)


def frame_edge(fig):
    fig.add_artist(Rectangle((0.002, 0.002), 0.996, 0.996, fill=False,
                             ec=EDGE, lw=1.3, transform=fig.transFigure,
                             zorder=1000))


def head(fig, title, subtitle, source):
    fig.text(0.016, 0.962, title, fontsize=15, fontweight="bold", color=INK,
             ha="left", va="top")
    fig.text(0.016, 0.895, subtitle, fontsize=9.4, color=SEC, ha="left",
             va="top", linespacing=1.45)
    fig.text(0.016, 0.022, source, fontsize=7.6, color=MUT, ha="left")


def save(fig, name):
    frame_edge(fig)
    fig.savefig(name, facecolor=PAPER)
    plt.close(fig)
    print(f"  wrote {name}")


# ---------------------------------------------------------------------------
# Chart 1 -- the funnel
# ---------------------------------------------------------------------------
def chart_funnel(counts, asof):
    n0 = counts[0]
    ys = list(range(len(counts)))[::-1]

    fig, ax = new_fig(left=0.325, top=0.775, bottom=0.075)
    for y, n, lab in zip(ys, counts, LABELS):
        ax.barh(y, n0, height=0.58, color=SAND, lw=0, zorder=2)
        ax.barh(y, n, height=0.58, color=MUT if y == ys[0] else BLUE,
                alpha=0.92, lw=0, zorder=3)
        pct = 100 * n / n0
        inside = n / n0 > 0.30
        ax.text(n - n0 * 0.012 if inside else n + n0 * 0.012, y,
                f"{n:,}".replace(",", " ") + f"   {pct:.0f}%",
                va="center", ha="right" if inside else "left",
                color=PAPER if inside else SEC, fontsize=10.5,
                fontweight="bold" if inside else "normal", zorder=5)
    ax.text(n0 * 0.995, ys[-1] - 0.62,
            "and that is still about six hundred more companies than one "
            "person can read properly",
            ha="right", va="center", color=MUT, fontsize=8.8,
            fontstyle="italic", zorder=5)
    ax.set_yticks(ys)
    ax.set_yticklabels(LABELS, fontsize=10, color=SEC)
    ax.set_xticks([])
    ax.set_xlim(0, n0 * 1.02)
    ax.set_ylim(-1.05, len(counts) - 0.4)
    polish(ax, spines=("top", "right", "left", "bottom"))

    head(fig,
         "The checklist's first job is to say no",
         "Every US company that filed an audited annual profit-or-loss figure with the SEC for its "
         f"{LATEST} financial year,\nput through five deliberately unambitious tests, in order. "
         "Passing all five is not a reason to buy anything.",
         f"Source: SEC EDGAR XBRL frames API, pulled {asof}. Missing data counts as a fail. "
         "Fiscal years are grouped by SEC calendar-year frames.")
    save(fig, "checklist_funnel.png")


# ---------------------------------------------------------------------------
# Chart 2 -- what holding the winners actually felt like
# ---------------------------------------------------------------------------
def chart_drawdowns(rows, asof):
    rows = sorted(rows, key=lambda r: r["worst"])
    ys = list(range(len(rows)))[::-1]

    GUT_A, GUT_B, XMAX = 92, 126, 129        # right-hand gutter columns
    fig, ax = new_fig(left=0.20, top=0.775, bottom=0.145, right=0.995)
    for x in (20, 40, 60, 80):
        ax.plot([x, x], [-0.75, len(rows) - 0.05], color=GRID, lw=0.8, zorder=1)
    for y, r in zip(ys, rows):
        c = BLUE if r["ticker"] == "VTI" else RED
        depth = -r["worst"] * 100
        ax.barh(y, depth, height=0.56, color=c, alpha=0.88, lw=0, zorder=3)
        ax.text(depth + 1.3, y, f"−{depth:.0f}%", va="center", ha="left",
                color=SEC, fontsize=10.5, fontweight="bold", zorder=5)
        ax.text(GUT_A, y, f"{r['falls']}", va="center", ha="right",
                color=SEC, fontsize=10, zorder=5)
        ax.text(GUT_B, y, f"{r['underwater_months']:.0f}", va="center",
                ha="right", color=SEC, fontsize=10, zorder=5)
        if r["ticker"] == "VTI":              # the control, set slightly apart
            ax.plot([0, GUT_B], [y + 0.45, y + 0.45], color=BASE, lw=0.9,
                    zorder=2)
    ax.text(GUT_A, len(rows) - 0.35, "separate\nfalls of 20%+", va="bottom",
            ha="right", color=MUT, fontsize=8.4, linespacing=1.35, zorder=5)
    ax.text(GUT_B, len(rows) - 0.35, "longest stretch below\na previous high (months)",
            va="bottom", ha="right", color=MUT, fontsize=8.4,
            linespacing=1.35, zorder=5)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{r['name']}   {r['mult']:.1f}×" for r in rows],
                       fontsize=10, color=SEC)
    ax.set_xlim(0, XMAX)
    ax.set_xticks([0, 20, 40, 60, 80])
    ax.xaxis.set_major_formatter(lambda v, _: ("0%" if v == 0 else f"−{v:.0f}%"))
    ax.set_xlabel("Worst peak-to-trough fall over the ten years",
                  color=MUT, fontsize=9.5, labelpad=6, loc="left")
    ax.set_ylim(-0.75, len(rows) + 0.55)
    polish(ax)
    ax.spines["bottom"].set_bounds(0, 86)

    head(fig,
         "Every one of these was the right answer. None of them felt like it.",
         f"Ten years to {rows[0]['end']}, split- and dividend-adjusted. "
         "The multiple beside each name is what a buy-and-forget holder ended up with;\n"
         "the bar is the worst fall they had to sit through to collect it.",
         f"Source: EODHD end-of-day adjusted closes, pulled {asof}. "
         "Sample limited to the tickers the free demo key serves — see the post.")
    save(fig, "the_holding_tax.png")


# ---------------------------------------------------------------------------
def main():
    asof = dt.date.today().isoformat()
    print(f"pulling SEC EDGAR frames (as of {asof})...")
    now = load_universe(LATEST)
    counts, missing, alive = funnel(now)

    print(f"\n--- the funnel, {PRIOR}-{LATEST} ---")
    for lab, n, m in zip(LABELS, counts, missing):
        extra = f"   ({m} of them dropped for missing data)" if m else ""
        print(f"  {lab:42} {n:>6}  {100*n/counts[0]:5.1f}%{extra}")
    print(f"  survivors: {counts[-1]} of {counts[0]} "
          f"= {100*counts[-1]/counts[0]:.1f}% of the filing universe")

    # How much of the cull is genuine failure vs. a filing that stayed silent?
    complete = [c for c in now["ni"][LATEST]
                if all(f(now, c) is not None for f in TESTS[:4])
                and now["sh_then"].get(c) and now["sh_now"].get(c)]
    passed = [c for c in complete if c in alive]
    print(f"  among the {len(complete)} companies where all five numbers "
          f"were available, {len(passed)} pass ({100*len(passed)/len(complete):.1f}%)")

    chart_funnel(counts, asof)

    # ---- does the list keep? ---------------------------------------------
    print(f"\n--- the same five tests as they would have read in early "
          f"{PRIOR + 1} ---")
    print(f"    (identical checklist, five-year window FY{PRIOR - LOOKBACK}"
          f"-FY{PRIOR} instead of FY{LATEST - LOOKBACK}-FY{LATEST};")
    print(f"     the point is to compare that list against today's, so this "
          f"window has to end {VINTAGE_GAP} years ago)")
    then = load_universe(PRIOR)
    _, _, old = funnel(then)
    still_filing = old & set(now["ni"][LATEST])
    kept = old & alive
    print(f"  passed then: {len(old)}")
    print(f"  passed now : {len(alive)}")
    print(f"  of the old list, still filing today   : {len(still_filing)} "
          f"({100*len(still_filing)/len(old):.0f}%)")
    print(f"  of the old list, still passing today  : {len(kept)} "
          f"({100*len(kept)/len(old):.0f}%)")
    print(f"  on today's list but not the old one   : {len(alive-old)} "
          f"({100*len(alive-old)/len(alive):.0f}% of today's list)")

    # ---- the survivors, for anyone who wants to check my work -------------
    names = entity_names(LATEST)
    ni = now["ni"][LATEST]
    with open("checklist_survivors.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cik", "entity", f"net_income_CY{LATEST}_usd",
                    f"revenue_CY{LATEST}_usd", "passed_four_years_ago"])
        for c in sorted(alive, key=lambda c: -ni.get(c, 0)):
            w.writerow([c, names.get(c, ""), ni.get(c),
                        now["rev_now"].get(c), c in old])
    print(f"  wrote checklist_survivors.csv ({len(alive)} rows)")

    print("\n  ten largest survivors by last year's profit:")
    for c in sorted(alive, key=lambda c: -ni.get(c, 0))[:10]:
        print(f"    {names.get(c,'')}")

    # ---- the behaviour half ----------------------------------------------
    print("\n--- ten years of holding the obvious winners ---")
    rows = []
    for t, name in TICKERS:
        try:
            d = drawdowns(prices(t))
        except Exception as e:
            print(f"  {t}: no price data ({e})")
            continue
        d.update(ticker=t, name=name)
        rows.append(d)
        print(f"  {name:22} {d['mult']:6.2f}x over {d['years']:.1f}y  "
              f"worst fall {d['worst']*100:6.1f}% ({d['worst_on']})  "
              f"{d['falls']} separate 20%+ falls  "
              f"{d['underwater_months']:5.1f} months underwater "
              f"{d['underwater_span']}")
    if rows:
        med = statistics.median(-r["worst"] for r in rows)
        print(f"  median worst fall in the sample: {med*100:.0f}%")
        chart_drawdowns(rows, asof)


if __name__ == "__main__":
    main()
