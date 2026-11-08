"""
WHAT IT DRAWS:
  An underwater chart for each name: how far below its own previous high the
  thing sat, every trading day for ten years. Zero means a fresh all-time high.
  Everything under the line is a holder waiting to get back to a number they
  had already seen.

  The companion bar chart in the post gives the *depth* of the worst fall. This
  one gives the shape: how often it happened, how long it lasted, and how much
  of the decade was spent below water rather than above it. Depth is what
  people quote. Duration is what actually makes them sell.

DATA:
  Yahoo Finance, split- and dividend-adjusted daily closes. Two ways in:
    1. the `yfinance` package, if it is installed (pip install yfinance)
    2. Yahoo's public chart endpoint, called directly with urllib
  If Yahoo refuses -- it rate-limits hard from datacentre and VPN addresses --
  the script falls back to EODHD's free demo key, which is what the rest of the
  post uses. Whichever source answers is named in the printout and in the chart
  footer, because the two adjust dividends slightly differently and the numbers
  can move by a few tenths of a point.

REQUIREMENTS:  pip install matplotlib        (yfinance optional)

Run:  python3 yahoo_drawdowns.py
"""

import datetime as dt
import json
import os
import statistics
import time
import urllib.error
import urllib.request

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# --- what to draw ----------------------------------------------------------
# Five names nobody would call a bad ten-year answer, plus the whole US market
# as the control. VTI is last on purpose: it is the comparison that matters.
TICKERS = [("TSLA", "Tesla"), ("AMZN", "Amazon"), ("AAPL", "Apple"),
           ("MSFT", "Microsoft"), ("MCD", "McDonald's"),
           ("VTI", "The whole US market")]

# The window is pinned so that this chart and the post's other price chart
# quote the same return multiples. Ten years measured to a different Tuesday
# turns Tesla's 24.8x into 27.6x, and notices that in the same
# article is right to stop trusting both numbers. Set both to None for a
# rolling "last ten years to today" instead.

START = "2016-08-30"
END = "2026-08-28"
YEARS = 10
CACHE = "price_cache"
OUT = "the_long_wait.png"

BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0.0.0 Safari/537.36",
           "Accept": "application/json,text/plain,*/*"}

EOD_TOKEN = "demo"          # serves only AAPL, MSFT, AMZN, TSLA, MCD, VTI


# ---------------------------------------------------------------------------
# Getting prices
# ---------------------------------------------------------------------------
def _start_date():
    if START:
        return START
    return (dt.date.today() - dt.timedelta(days=int(YEARS * 365.25))).isoformat()


def _window(rows):
    """Trim to the pinned window. Sources disagree about how much history to
    hand back for a given `from=`, so the cut happens here rather than in the
    request."""
    lo = _start_date()
    hi = END or dt.date.today().isoformat()
    return [r for r in rows if lo <= r[0] <= hi]


def from_yfinance(ticker):
    """Preferred path. yfinance handles Yahoo's cookie/crumb dance, which the
    plain endpoint does not, so it survives more often."""
    import yfinance as yf                     # optional dependency
    df = yf.download(ticker, start=_start_date(), interval="1d",
                     auto_adjust=True, progress=False, threads=False)
    if df is None or df.empty:
        raise RuntimeError("yfinance returned nothing")
    close = df["Close"]
    if hasattr(close, "columns"):             # yfinance >=0.2.51 multi-indexes
        close = close.iloc[:, 0]
    return [(d.strftime("%Y-%m-%d"), float(v))
            for d, v in close.items() if v == v]     # v == v drops NaN


def from_yahoo_api(ticker):
    """No dependencies. Yahoo's own chart endpoint, with the adjusted-close
    series it uses for its own charts."""
    p1 = int(dt.datetime.fromisoformat(_start_date()).timestamp())
    p2 = int(time.time())
    last = None
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit")
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=BROWSER),
                    timeout=45) as r:
                data = json.load(r)
            res = data["chart"]["result"][0]
            stamps = res["timestamp"]
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            out = [(dt.date.fromtimestamp(t).isoformat(), float(v))
                   for t, v in zip(stamps, adj) if v is not None]
            if out:
                return out
            raise RuntimeError("empty series")
        except Exception as e:                # 429 is the usual one
            last = e
    raise RuntimeError(f"Yahoo refused: {last}")


def from_eodhd(ticker):
    """Fallback, and the source the rest of the post uses."""
    url = (f"https://eodhd.com/api/eod/{ticker}.US?api_token={EOD_TOKEN}"
           f"&fmt=json&period=d&from={_start_date()}")
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=BROWSER), timeout=45) as r:
        raw = json.load(r)
    return [(x["date"], float(x["adjusted_close"])) for x in raw]


SOURCES = [("Yahoo Finance (yfinance)", from_yfinance),
           ("Yahoo Finance (chart API)", from_yahoo_api),
           ("EODHD (fallback)", from_eodhd)]


def prices(ticker, source_used):
    """Try each source in order; cache what works, so re-running while you
    fiddle with the chart does not hammer anybody's API."""
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{ticker}_{YEARS}y.json"
    if os.path.exists(path):
        blob = json.load(open(path))
        source_used.add(blob["source"])
        return _window([tuple(r) for r in blob["rows"]])

    for name, fn in SOURCES:
        try:
            rows = fn(ticker)
        except ImportError:
            continue                          # yfinance not installed
        except Exception as e:
            print(f"    {ticker}: {name} unavailable ({str(e)[:60]})")
            continue
        rows.sort()
        json.dump({"source": name, "rows": rows}, open(path, "w"))
        source_used.add(name)
        time.sleep(0.4)
        return _window(rows)
    raise SystemExit(f"no price source would serve {ticker}")


# ---------------------------------------------------------------------------
# The underwater series
# ---------------------------------------------------------------------------
def underwater(series):
    """Percentage below the running previous high, for every day.

    Same definitions as the post's other script, so the numbers match:
      * worst         -- deepest close-to-close fall from a previous high
      * falls         -- how many separate times it crossed -20%
      * longest_wait  -- the longest unbroken stretch spent below a high
      * time_under    -- share of all trading days spent below a high
    """
    dates = [dt.date.fromisoformat(d) for d, _ in series]
    px = [v for _, v in series]

    peak, dd = px[0], []
    worst, worst_i = 0.0, 0
    below_since, longest, longest_span = None, 0, (dates[0], dates[0])
    falls, in_fall, under_days = 0, False, 0

    for i, v in enumerate(px):
        if v >= peak:
            if below_since is not None:
                span = (dates[i] - dates[below_since]).days
                if span > longest:
                    longest, longest_span = span, (dates[below_since], dates[i])
                below_since = None
            peak, in_fall = v, False
        else:
            if below_since is None:
                below_since = i
            under_days += 1
            if v / peak - 1 <= -0.20 and not in_fall:
                falls, in_fall = falls + 1, True
        d = v / peak - 1
        dd.append(d * 100)
        if d < worst:
            worst, worst_i = d, i

    if below_since is not None:               # still underwater today
        span = (dates[-1] - dates[below_since]).days
        if span > longest:
            longest, longest_span = span, (dates[below_since], dates[-1])

    years = (dates[-1] - dates[0]).days / 365.25
    return dict(dates=dates, dd=dd, worst=worst, worst_on=dates[worst_i],
                falls=falls, longest_months=longest / 30.44,
                longest_span=longest_span, mult=px[-1] / px[0], years=years,
                under_share=under_days / len(px),
                start=dates[0], end=dates[-1])


# ---------------------------------------------------------------------------
# Chart style -- house palette, on paper, capped at 1200x600
# ---------------------------------------------------------------------------
PAPER, EDGE = "#f2efe7", "#ddd8c9"
BLUE, RED = "#2a78d6", "#e34948"
INK, SEC, MUT = "#0b0b0b", "#52514e", "#83806f"
GRID, BASE = "#e2ddcd", "#c3bda9"

plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 120,
                     "font.family": "DejaVu Sans", "font.size": 11,
                     "axes.grid": False})

FLOOR = -94          # shared y-limit, so the panels are honestly comparable


def panel(ax, r, name, is_market, show_y, show_x):
    colour = BLUE if is_market else RED
    ax.set_facecolor(PAPER)

    ax.fill_between(r["dates"], 0, r["dd"], color=colour, alpha=0.80, lw=0,
                    zorder=3)
    ax.plot(r["dates"], r["dd"], color=colour, lw=0.7, zorder=4)

    # the -20% line: every time the curve dips under it, that is one of the
    # "separate falls" quoted in the post
    ax.axhline(-20, ls=(0, (3, 3)), lw=0.8, color=BASE, zorder=2)
    ax.axhline(0, lw=1.0, color=BASE, zorder=5)

    # deepest point
    ax.plot([r["worst_on"]], [r["worst"] * 100], marker="o", ms=5,
            mfc=colour, mec=PAPER, mew=1.6, zorder=6, clip_on=False)
    ax.text(r["worst_on"], r["worst"] * 100 - 5,
            f"−{-r['worst'] * 100:.0f}%", ha="center", va="top",
            fontsize=9.5, color=SEC, fontweight="bold", zorder=6)

    # the longest unbroken wait, as a ruler along the floor. The label sits
    # beside the bar rather than above it, so it never lands on top of a deep
    # trough's percentage.
    a, b = r["longest_span"]
    y = FLOOR + 3
    ax.plot([a, b], [y, y], lw=3.2, color=MUT, alpha=0.55,
            solid_capstyle="butt", zorder=6)
    lo, hi = r["dates"][0], r["dates"][-1]
    pad = (hi - lo) / 60
    if (hi - b) > (a - lo):                    # more room to the right
        ax.text(b + pad, y, f"{r['longest_months']:.0f} mo", ha="left",
                va="center", fontsize=8.6, color=MUT, zorder=6)
    else:
        ax.text(a - pad, y, f"{r['longest_months']:.0f} mo", ha="right",
                va="center", fontsize=8.6, color=MUT, zorder=6)

    ax.set_ylim(FLOOR, 4)
    ax.set_xlim(r["dates"][0], r["dates"][-1])
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=1)
    ax.set_axisbelow(True)
    ax.set_yticks([0, -20, -40, -60, -80])
    ax.set_ylim(FLOOR, 4)
    ax.tick_params(colors=MUT, length=0, labelsize=8.5)
    if show_y:
        ax.set_yticklabels(["0%", "−20%", "−40%", "−60%", "−80%"])
    else:
        ax.set_yticklabels([])
    if show_x:
        ax.xaxis.set_major_locator(mdates.YearLocator(3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    else:
        ax.set_xticklabels([])
        ax.xaxis.set_major_locator(mdates.YearLocator(3))

    ax.set_title(f"{name}    {r['mult']:.1f}×", loc="left", pad=13,
                 fontsize=11.5, color=INK, fontweight="bold")
    ax.text(0, 1.015, f"{r['falls']} falls past −20%   ·   "
                      f"{r['under_share'] * 100:.0f}% of days underwater",
            transform=ax.transAxes, fontsize=8.4, color=MUT, va="bottom")


def draw(rows, sources):
    fig, axes = plt.subplots(2, 3, figsize=(10, 5))
    fig.patch.set_facecolor(PAPER)
    fig.subplots_adjust(left=0.058, right=0.988, top=0.705, bottom=0.085,
                        hspace=0.62, wspace=0.10)

    for i, (ax, (r, name, is_market)) in enumerate(zip(axes.flat, rows)):
        panel(ax, r, name, is_market, show_y=(i % 3 == 0), show_x=(i >= 3))

    first = rows[0][0]
    fig.text(0.014, 0.966, "Ten years underwater", fontsize=15,
             fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.014, 0.899,
             "How far each one sat below its own previous high, every trading day for ten years. The flat line along\n"
             "the top is a fresh high; everything beneath it is a holder waiting to get back to a number they'd already seen.\n"
             "The multiple beside each name is what that wait eventually paid. The dashed line marks −20%.",
             fontsize=9.2, color=SEC, ha="left", va="top", linespacing=1.5)
    fig.text(0.014, 0.020,
             f"Source: {' + '.join(sorted(sources))}, split- and dividend-adjusted daily closes, "
             f"{first['start']} to {first['end']}. Measured close to close, so intraday falls were deeper.",
             fontsize=7.6, color=MUT, ha="left")
    fig.add_artist(Rectangle((0.002, 0.002), 0.996, 0.996, fill=False,
                             ec=EDGE, lw=1.3, transform=fig.transFigure,
                             zorder=1000))
    fig.savefig(OUT, facecolor=PAPER)
    plt.close(fig)
    print(f"\n  wrote {OUT}  (1200 x 600)")


# ---------------------------------------------------------------------------
def main():
    sources, rows = set(), []
    print(f"pulling {YEARS} years of adjusted daily closes...")
    for ticker, name in TICKERS:
        r = underwater(prices(ticker, sources))
        rows.append((r, name, ticker == "VTI"))
        print(f"  {name:22} {r['mult']:6.2f}x over {r['years']:.1f}y   "
              f"worst {r['worst'] * 100:6.1f}% on {r['worst_on']}   "
              f"{r['falls']} falls of 20%+   "
              f"longest wait {r['longest_months']:5.1f} months "
              f"({r['longest_span'][0]} to {r['longest_span'][1]})   "
              f"{r['under_share'] * 100:4.1f}% of days below a high")

    worsts = [-r["worst"] for r, _, _ in rows]
    unders = [r["under_share"] for r, _, _ in rows]
    print(f"\n  median worst fall in the sample: {statistics.median(worsts) * 100:.0f}%")
    print(f"  median share of the decade spent below a previous high: "
          f"{statistics.median(unders) * 100:.0f}%")
    print(f"  price source(s) used: {', '.join(sorted(sources))}")
    if not any(s.startswith("Yahoo") for s in sources):
        print("  NOTE: Yahoo would not serve this machine, so these are EODHD "
              "figures.\n        Delete price_cache/ and re-run from a normal "
              "home connection to use Yahoo.")

    draw(rows, sources)


if __name__ == "__main__":
    main()
