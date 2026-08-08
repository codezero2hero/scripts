"""
compounding_v2.py  --  companion script for "The Eighth Wonder: How Compounding
                       Builds Wealth Slowly" (CodeZero2Hero).

WHAT CHANGED VS compounding.py (v1)
  The maths is byte-for-byte the same engine: same simulate(), same crossover
  logic, same market-history loader. Every number in the post still holds.
  What changed is the LOOK: a small editorial chart system instead of default
  matplotlib -- serif headlines, gradient fills, direct labels instead of legend
  boxes, hairline axes, annotated turning points, and a light/dark theme.

  v2 writes into ./charts_v2/ so it can never overwrite v1's output. If you
  prefer the old charts, just run compounding.py again -- nothing is lost.

WHY THIS EXISTS (unchanged)
  Compounding is the idea everybody nods at and nobody feels. Reading "your
  money grows exponentially" does nothing. Watching a curve stay boring for
  eleven years and then bend, and watching a 1.8% difference in fees quietly
  eat a third of your final balance, does something.

WHAT IT DOES
  1. Simulates a monthly contribution plan (default EUR 300/month, 40 years),
     month by month, with costs and inflation handled explicitly.
  2. Finds the CROSSOVER YEAR -- the year the portfolio's own growth first
     earns more than you contribute.
  3. Shows the fee drag: same plan, three cost levels.
  4. Shows nominal vs real, at euro-area inflation AND Romania's current rate.
  5. Shows early-and-stop vs late-and-longer (the "Ana vs Bogdan" case).
  6. With --real, downloads actual S&P 500 TOTAL RETURN history (dividends
     reinvested, 1988-present) and runs the same plan through the real sequence
     of returns, plus every historical 20-year window.

REQUIREMENTS
  pip install matplotlib            # core simulation + charts
  pip install yfinance pandas       # only for --real
  Fonts are optional: install Poppins + Lora for the intended look, otherwise
  the script falls back to DejaVu automatically.

RUN
  python3 compounding_v2.py                 # light theme
  python3 compounding_v2.py --dark          # dark theme
  python3 compounding_v2.py --real          # + charts from real market history
  python3 compounding_v2.py --real --dark --out charts_dark

IMPORTANT
  The return assumption is an assumption, not a fact. Change RETURN below and
  re-run; the point of owning the script is that the numbers are yours.
"""

import argparse
import csv
import logging
import os
import textwrap

import numpy as np
import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# CONFIG -- edit these. Everything downstream is derived.
# ---------------------------------------------------------------------------
MONTHLY = 300.0          # EUR invested every month
INITIAL = 0.0            # starting lump sum
YEARS = 40               # horizon
RETURN = 0.07            # assumed NOMINAL annual return, before costs
FEE = 0.0020             # all-in annual cost (cheap UCITS world ETF ~0.20%)

INFL_EURO = 0.020        # ECB target / euro-area run rate
INFL_RO_NOW = 0.104      # Romania, annual CPI, June 2026 (INS)
INFL_RO_FORECAST = 0.055 # BNR forecast for end-2026

FEE_LADDER = [
    (0.0020, "0.20% index ETF"),
    (0.0100, "1.00% robo / fund"),
    (0.0200, "2.00% bank fund"),
]

CURRENCY = "\u20ac"      # EUR sign
WORDMARK = "codezero2hero.com"

# ---------------------------------------------------------------------------
# The engine. ~20 lines. That is genuinely all compounding is.
# ---------------------------------------------------------------------------
# Convert an annual percentage rate into an effective monthly rate.
# We use geometric conversion instead of annual/12 so the mathematics
# remain internally consistent with annual compounding assumptions.
def monthly_rate(annual):
    """Convert an annual rate to its monthly equivalent (geometric, not /12)."""
    return (1.0 + annual) ** (1.0 / 12.0) - 1.0


# Core simulation engine.
#
# The portfolio evolves one month at a time using the following order:
#   1. Add this month's contribution.
#   2. Apply market growth.
#   3. Deduct investment fees.
# Yearly snapshots are stored for reporting and plotting.
def simulate(years=YEARS, initial=INITIAL, monthly=MONTHLY,
             annual_return=RETURN, annual_fee=FEE, annual_inflation=0.0,
             contribution_growth=0.0, stop_after_years=None):
    """Month-by-month simulation. Returns a list of per-year dicts."""
    r = monthly_rate(annual_return)
    f = monthly_rate(annual_fee)
    balance = initial
    contributed = initial
    contrib = monthly
    rows = []
    prev_balance, prev_contributed = balance, contributed

    for m in range(1, years * 12 + 1):
        year_index = (m - 1) // 12
        if stop_after_years is None or year_index < stop_after_years:
            balance += contrib
            contributed += contrib
        balance *= (1.0 + r)                    # market return
        balance -= balance * f                  # costs, charged on assets

        if m % 12 == 0:
            year = m // 12
            growth_this_year = (balance - prev_balance) - (contributed - prev_contributed)
            deflator = (1.0 + annual_inflation) ** year
            rows.append(dict(
                year=year,
                contributed=contributed,
                value=balance,
                growth_total=balance - contributed,
                growth_this_year=growth_this_year,
                contributed_this_year=contributed - prev_contributed,
                real_value=balance / deflator,
                real_contributed=contributed / deflator,
            ))
            prev_balance, prev_contributed = balance, contributed
            contrib *= (1.0 + contribution_growth)

    return rows


def crossover_year(rows):
    """First year where the portfolio's own growth beats what you put in."""
    for r in rows:
        if r["contributed_this_year"] > 0 and r["growth_this_year"] > r["contributed_this_year"]:
            return r["year"]
    return None


# ===========================================================================
# CHART SYSTEM  (everything below is presentation, not maths)
# ===========================================================================
THEMES = {
    "light": dict(
        bg="#FFFFFF", panel="#FFFFFF",
        ink="#101828", mid="#475467", muted="#98A2B3", hairline="#E7EAEE",
        grid="#EEF1F4",
        growth="#0E8C6D", contrib="#5B7A99", warn="#D1495B", amber="#E0A33E",
        accent="#0E8C6D",
    ),
    "dark": dict(
        bg="#0E1117", panel="#0E1117",
        ink="#F2F5F9", mid="#B4BDCB", muted="#7C879A", hairline="#232A35",
        grid="#1A212B",
        growth="#2DD4A7", contrib="#7FA8D9", warn="#FF6B81", amber="#F2B950",
        accent="#2DD4A7",
    ),
}
T = THEMES["light"]                      # replaced by set_theme()

SANS = ["Poppins", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"]
SERIF = ["Lora", "Charter", "Bitstream Charter", "Georgia", "DejaVu Serif"]
FIGSIZE = (12, 6)                        # 1200 x 600 px at dpi 100

# Everything the script writes lands NEXT TO THE SCRIPT, not in whatever
# directory you happened to run it from. Relative --out paths are resolved
# against this too; absolute paths are used as given.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(SCRIPT_DIR, "charts_v2")


def set_theme(name="light"):
    global T
    T = THEMES[name]
    mpl.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 100,
        "font.family": "sans-serif", "font.sans-serif": SANS, "font.size": 11,
        "text.color": T["ink"], "axes.labelcolor": T["mid"],
        "xtick.color": T["muted"], "ytick.color": T["muted"],
        "axes.facecolor": T["panel"], "figure.facecolor": T["bg"],
        "savefig.facecolor": T["bg"],
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": True,
        "axes.edgecolor": T["hairline"],
        "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.major.pad": 8, "ytick.major.pad": 6,
        "axes.grid": True, "axes.axisbelow": True,
        "grid.color": T["grid"], "grid.linewidth": 1.0,
        "legend.frameon": False,
    })


def money(v, decimals=0):
    """Compact money labels: EUR 705k / EUR 1.8M."""
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1_000_000:
        return f"{sign}{CURRENCY}{a/1e6:.2f}M"
    if a >= 1_000:
        return f"{sign}{CURRENCY}{a/1e3:,.0f}k"
    return f"{sign}{CURRENCY}{a:,.{decimals}f}"


def money_full(v):
    return f"{CURRENCY}{v:,.0f}"


def canvas(headline, deck, source):
    """A framed editorial canvas: accent rule, serif headline, deck, footer."""
    fig, ax = plt.subplots(figsize=FIGSIZE)
    fig.subplots_adjust(left=0.062, right=0.845, top=0.755, bottom=0.185)

    fig.lines.append(plt.Line2D([0.062, 0.098], [0.955, 0.955],
                                transform=fig.transFigure,
                                color=T["accent"], lw=3.4, solid_capstyle="butt"))
    fig.text(0.062, 0.905, headline, fontsize=19.5, fontweight="bold",
             fontfamily=SERIF, color=T["ink"], ha="left", va="center")
    fig.text(0.062, 0.845, deck, fontsize=11, color=T["mid"],
             ha="left", va="center")

    fig.lines.append(plt.Line2D([0.062, 0.975], [0.082, 0.082],
                                transform=fig.transFigure,
                                color=T["hairline"], lw=1.0))
    fig.text(0.062, 0.038, textwrap.fill(source, 150), fontsize=8.2,
             color=T["muted"], ha="left", va="center", linespacing=1.5)
    fig.text(0.975, 0.038, WORDMARK, fontsize=8.6, color=T["muted"],
             ha="right", va="center", fontweight="bold")

    for s in ("bottom",):
        ax.spines[s].set_linewidth(1.0)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=False)
    ax.tick_params(labelsize=10)
    return fig, ax


def gradient_band(ax, x, y_top, y_bottom, color, alpha=0.45, zorder=1):
    """Soft vertical gradient inside an arbitrary band. Pure matplotlib."""
    x = np.asarray(x, dtype=float)
    y_top = np.asarray(y_top, dtype=float)
    y_bottom = (np.full_like(y_top, float(y_bottom))
                if np.isscalar(y_bottom) else np.asarray(y_bottom, dtype=float))
    rgb = mcolors.to_rgb(color)
    grad = np.empty((256, 1, 4))
    grad[:, :, :3] = rgb
    grad[:, :, 3] = np.linspace(0.0, alpha, 256)[:, None]
    im = ax.imshow(grad, aspect="auto", origin="lower", zorder=zorder,
                   extent=[x.min(), x.max(), float(y_bottom.min()), float(y_top.max())])
    verts = np.column_stack([np.r_[x, x[::-1]], np.r_[y_top, y_bottom[::-1]]])
    clip = Polygon(verts, closed=True, facecolor="none", edgecolor="none")
    ax.add_patch(clip)
    im.set_clip_path(clip)
    return im


def end_label(ax, x, y, text, color, dy=0, weight="bold", size=11.5, dot=True):
    """Direct label at the end of a series -- kills the need for a legend."""
    if dot:
        ax.plot([x], [y], "o", ms=7, color=color, zorder=6,
                markeredgecolor=T["bg"], markeredgewidth=1.6, clip_on=False)
    ax.annotate(text, xy=(x, y), xytext=(9, dy), textcoords="offset points",
                fontsize=size, fontweight=weight, color=color,
                ha="left", va="center", annotation_clip=False, zorder=6)


def note(ax, xy, text, color, xytext, arrow=True, size=9.8, ha="left"):
    """Small annotation with a soft tinted pill and an optional connector."""
    ax.annotate(
        text, xy=xy, xytext=xytext, textcoords="data", fontsize=size,
        color=color, ha=ha, va="center", zorder=7,
        bbox=dict(boxstyle="round,pad=0.42", fc=T["bg"], ec=color,
                  lw=0.9, alpha=0.96),
        arrowprops=(dict(arrowstyle="-", color=color, lw=1.0,
                         connectionstyle="arc3,rad=0.15", alpha=0.8)
                    if arrow else None))


def money_axis(ax):
    ax.yaxis.set_major_formatter(lambda v, _: money(v))


def save(fig, name):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, name)
    fig.savefig(path, facecolor=T["bg"])
    plt.close(fig)
    print(f"  wrote {os.path.relpath(path, SCRIPT_DIR)}")


def save_csv(name, rows, fields):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, name)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for r in rows:
            w.writerow([round(r[f], 2) if isinstance(r[f], float) else r[f] for f in fields])
    print(f"  wrote {os.path.relpath(path, SCRIPT_DIR)}")


def assumption_note():
    return (f"Model, not a forecast: {money_full(MONTHLY)}/month, {RETURN*100:.0f}% nominal annual return, "
            f"{FEE*100:.2f}% annual cost, monthly compounding. Returns are assumed, not guaranteed.")


# ---------------------------------------------------------------------------
# Chart 1 -- the bend, and the crossover
# ---------------------------------------------------------------------------
def chart_curve(rows):
    yr = [r["year"] for r in rows]
    contributed = [r["contributed"] for r in rows]
    value = [r["value"] for r in rows]
    x = crossover_year(rows)

    fig, ax = canvas(
        "The curve is boring for a decade. Then it isn't.",
        f"{money_full(MONTHLY)} a month for {YEARS} years. Everything above the blue band is money you never earned at work.",
        assumption_note())

    gradient_band(ax, yr, value, contributed, T["growth"], alpha=0.55)
    gradient_band(ax, yr, contributed, 0.0, T["contrib"], alpha=0.34)
    ax.plot(yr, value, color=T["growth"], lw=3.0, zorder=5, solid_capstyle="round")
    ax.plot(yr, contributed, color=T["contrib"], lw=2.0, ls=(0, (5, 3)), zorder=4)

    end_label(ax, yr[-1], value[-1], f"{money(value[-1])}\nportfolio", T["growth"], dy=6)
    end_label(ax, yr[-1], contributed[-1], f"{money(contributed[-1])}\ncontributed",
              T["contrib"], dy=-4, weight="normal", size=10.5)

    if x:
        v = rows[x - 1]["value"]
        ax.plot([x, x], [0, v], color=T["amber"], lw=1.2, ls=":", zorder=3)
        ax.plot([x], [v], "o", ms=8, color=T["amber"], zorder=6,
                markeredgecolor=T["bg"], markeredgewidth=1.8)
        note(ax, (x, v), f"Year {x}: the portfolio's own growth\nfirst beats what you put in",
             T["amber"], (x + 2.0, max(value) * 0.42))

    ax.set_xlabel("Years invested", fontsize=10.5, labelpad=9)
    money_axis(ax)
    ax.set_xlim(0, max(yr))
    ax.set_ylim(0, max(value) * 1.06)
    save(fig, "compounding_curve.png")


# ---------------------------------------------------------------------------
# Chart 2 -- fee drag
# ---------------------------------------------------------------------------
def chart_fees():
    series = [(label, simulate(annual_fee=fee)) for fee, label in FEE_LADDER]
    colors = [T["growth"], T["amber"], T["warn"]]
    best = series[0][1]
    worst = series[-1][1]
    yr = [r["year"] for r in best]

    fig, ax = canvas(
        "The quietest number on your statement",
        "Same contributions, same market return, same everything. The only variable is cost.",
        assumption_note())

    gradient_band(ax, yr, [r["value"] for r in best], [r["value"] for r in worst],
                  T["warn"], alpha=0.30)

    for (label, rows), c in zip(series, colors):
        ax.plot(yr, [r["value"] for r in rows], lw=3.0, color=c, zorder=5,
                solid_capstyle="round")

    for i, ((label, rows), c) in enumerate(zip(series, colors)):
        v = rows[-1]["value"]
        delta = "" if i == 0 else f"   {money(v - best[-1]['value'])} to fees"
        end_label(ax, yr[-1], v, f"{money(v)}{delta}\n{label}", c,
                  dy=0, size=10.6)

    ax.set_xlabel("Years invested", fontsize=10.5, labelpad=9)
    money_axis(ax)
    ax.set_xlim(0, YEARS)
    ax.set_ylim(0, max(r["value"] for r in best) * 1.06)
    save(fig, "compounding_fees.png")
    return [(label, rows[-1]["value"]) for label, rows in series]


# ---------------------------------------------------------------------------
# Chart 3 -- nominal vs real
# ---------------------------------------------------------------------------
def chart_real(rows):
    yr = [r["year"] for r in rows]
    nominal = [r["value"] for r in rows]
    lines = [
        (INFL_EURO, T["growth"], f"at {INFL_EURO*100:.1f}%"),
        (INFL_RO_FORECAST, T["amber"], f"at {INFL_RO_FORECAST*100:.1f}%"),
        (INFL_RO_NOW, T["warn"], f"at {INFL_RO_NOW*100:.1f}%"),
    ]
    computed = [(infl, c, label, [r["real_value"] for r in simulate(annual_inflation=infl)])
                for infl, c, label in lines]

    fig, ax = canvas(
        "Nominal is the number. Real is the groceries.",
        "The same portfolio in today's purchasing power at three inflation rates: "
        f"{INFL_EURO*100:.1f}% euro area, {INFL_RO_FORECAST*100:.1f}% BNR forecast for end-2026, "
        f"{INFL_RO_NOW*100:.1f}% Romania today.",
        assumption_note() + "  Inflation sources: ECB / euro-area run rate, BNR forecast, "
        "INS annual CPI for June 2026.")

    gradient_band(ax, yr, nominal, computed[-1][3], T["warn"], alpha=0.22)
    ax.plot(yr, nominal, color=T["ink"], lw=3.0, zorder=5, solid_capstyle="round")
    end_label(ax, yr[-1], nominal[-1], f"{money(nominal[-1])}\nnominal", T["ink"], dy=4)

    for i, (infl, c, label, vals) in enumerate(computed):
        ax.plot(yr, vals, color=c, lw=2.6, zorder=5, solid_capstyle="round")
        end_label(ax, yr[-1], vals[-1], f"{money(vals[-1])}  {label}", c,
                  dy=[0, 4, -6][i], size=10.4)

    j = int(len(yr) * 0.72)
    wedge_mid = (nominal[j] + computed[0][3][j]) / 2
    note(ax, (yr[j], wedge_mid), "this wedge is purchasing power,\nquietly deleted",
         T["warn"], (yr[j], wedge_mid), arrow=False, ha="center")

    ax.set_xlabel("Years invested", fontsize=10.5, labelpad=9)
    ax.set_ylabel("Balance in today's money", fontsize=10.5)
    money_axis(ax)
    ax.set_xlim(0, max(yr))
    ax.set_ylim(0, max(nominal) * 1.06)
    save(fig, "compounding_real.png")


# ---------------------------------------------------------------------------
# Chart 4 -- Ana vs Bogdan
# ---------------------------------------------------------------------------
def chart_early_vs_late():
    ana = simulate(years=40, stop_after_years=10)      # ages 25-35, then hold
    bogdan = simulate(years=30)                        # ages 35-65, never stops

    ax_ana = [r["year"] + 25 for r in ana]
    ax_bog = [r["year"] + 35 for r in bogdan]

    fig, ax = canvas(
        "Ten early years beat thirty late ones",
        "Ana invests from 25 to 35 and then stops forever. Bogdan starts at 35 and never misses a month.",
        assumption_note())

    gradient_band(ax, ax_ana, [r["value"] for r in ana], 0.0, T["growth"], alpha=0.30)
    ax.plot(ax_ana, [r["value"] for r in ana], color=T["growth"], lw=3.0, zorder=5,
            solid_capstyle="round")
    ax.plot(ax_bog, [r["value"] for r in bogdan], color=T["contrib"], lw=3.0, zorder=5,
            solid_capstyle="round")

    top = max(r["value"] for r in ana)
    ax.text(26, top * 1.00, f"ANA   {money_full(ana[9]['contributed'])} invested, ages 25-35 only",
            fontsize=10.6, fontweight="bold", color=T["growth"], va="center")
    ax.text(26, top * 0.90, f"BOGDAN   {money_full(bogdan[-1]['contributed'])} invested, ages 35-65",
            fontsize=10.6, fontweight="bold", color=T["contrib"], va="center")

    stop_v = ana[9]["value"]
    ax.plot([35], [stop_v], "o", ms=8, color=T["growth"], zorder=6,
            markeredgecolor=T["bg"], markeredgewidth=1.8)
    note(ax, (35, stop_v), "Ana stops here and never\nadds another euro",
         T["growth"], (38.5, top * 0.42))

    end_label(ax, 65, ana[-1]["value"], f"{money(ana[-1]['value'])}\nAna", T["growth"], dy=8)
    end_label(ax, 65, bogdan[-1]["value"], f"{money(bogdan[-1]['value'])}\nBogdan", T["contrib"], dy=-10)

    ax.set_xlabel("Age", fontsize=10.5, labelpad=9)
    money_axis(ax)
    ax.set_xlim(25, 65)
    ax.set_ylim(0, top * 1.12)
    save(fig, "compounding_early_vs_late.png")
    return ana, bogdan


# ---------------------------------------------------------------------------
# --real : the same plan through actual market history
# ---------------------------------------------------------------------------
CACHE = os.path.join(SCRIPT_DIR, "sp500tr_monthly.csv")


def load_market_history(refresh=False):
    """Monthly closes of the S&P 500 TOTAL RETURN index (dividends reinvested).
    Downloaded once, cached to CSV -- same discipline as the EDGAR scripts."""
    if os.path.exists(CACHE) and not refresh:
        with open(CACHE) as fh:
            rows = list(csv.reader(fh))[1:]
        return [(d, float(c)) for d, c in rows]

    import yfinance as yf
    print("  downloading ^SP500TR monthly history from Yahoo Finance ...")
    hist = yf.Ticker("^SP500TR").history(period="max", interval="1mo")
    if hist.empty:
        raise SystemExit("  no data returned -- check your connection.")
    series = [(str(idx.date()), float(v)) for idx, v in hist["Close"].items()]
    with open(CACHE, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["month", "close"])
        w.writerows(series)
    print(f"  cached {len(series)} months to {os.path.relpath(CACHE, SCRIPT_DIR)}")
    return series


def run_through_history(series, monthly=MONTHLY, annual_fee=FEE):
    """Invest `monthly` at each month's close."""
    f = monthly_rate(annual_fee)
    units = 0.0
    contributed = 0.0
    out = []
    for d, close in series:
        units += monthly / close
        units -= units * f
        contributed += monthly
        out.append(dict(month=d, contributed=contributed, value=units * close))
    return out


CRISES = [("2000-08-01", "dot-com peak"), ("2009-02-01", "-49.7%\n(2009 bottom)"),
          ("2020-03-01", "covid crash"), ("2022-09-01", "2022 selloff")]


def chart_history(series):
    path = run_through_history(series)
    xs = np.arange(len(path))
    value = [p["value"] for p in path]
    contributed = [p["contributed"] for p in path]
    idx = {p["month"]: i for i, p in enumerate(path)}

    fig, ax = canvas(
        "The same plan, run through what actually happened",
        f"{money_full(MONTHLY)} every month into the S&P 500 with dividends reinvested, "
        f"{path[0]['month'][:7]} to {path[-1]['month'][:7]}. The dents are the point.",
        "Source: S&P 500 Total Return index (^SP500TR), monthly closes via Yahoo Finance. "
        f"Costs of {FEE*100:.2f}%/yr applied. Nominal index terms: no currency, tax or spread effects "
        "included.")

    gradient_band(ax, xs, value, contributed, T["growth"], alpha=0.55)
    gradient_band(ax, xs, contributed, 0.0, T["contrib"], alpha=0.34)
    ax.plot(xs, value, color=T["growth"], lw=2.4, zorder=5)
    ax.plot(xs, contributed, color=T["contrib"], lw=1.8, ls=(0, (5, 3)), zorder=4)

    end_label(ax, xs[-1], value[-1], f"{money(value[-1])}\nportfolio", T["growth"], dy=6)
    end_label(ax, xs[-1], contributed[-1], f"{money(contributed[-1])}\ncontributed",
              T["contrib"], dy=-4, weight="normal", size=10.5)

    ymax = max(value)
    for m, label in CRISES:
        if m not in idx:
            continue
        i = idx[m]
        ax.plot([i], [value[i]], "o", ms=6.5, color=T["warn"], zorder=6,
                markeredgecolor=T["bg"], markeredgewidth=1.6)
        ax.annotate(label, xy=(i, value[i]), xytext=(0, 16), textcoords="offset points",
                    fontsize=9.2, color=T["warn"], ha="center", va="bottom", zorder=7)

    step = max(1, len(xs) // 9)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([path[i]["month"][:4] for i in range(0, len(path), step)])
    money_axis(ax)
    ax.set_xlim(0, len(xs) - 1)
    ax.set_ylim(0, ymax * 1.08)
    save(fig, "compounding_history.png")
    return path


def chart_windows(series, window_years=20):
    """Every possible start month: same plan, different luck."""
    n = window_years * 12
    results = []
    for start in range(0, len(series) - n + 1):
        seg = series[start:start + n]
        p = run_through_history(seg)
        results.append((seg[0][0][:7], p[-1]["value"], p[-1]["contributed"]))
    vals = np.array([r[1] for r in results])
    contributed = results[0][2]
    med = float(np.median(vals))
    lo_i, hi_i = int(vals.argmin()), int(vals.argmax())

    fig, ax = canvas(
        f"Same plan, different luck: every {window_years}-year window in the data",
        f"{money_full(MONTHLY)}/month for {window_years} years is {money_full(contributed)} contributed in every single bar. "
        "Only the start date changes.",
        "Source: S&P 500 Total Return index (^SP500TR), monthly closes via Yahoo Finance. "
        f"{len(results)} overlapping windows, each bar one starting month.")

    norm = mcolors.Normalize(vmin=vals.min() * 0.75, vmax=vals.max())
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "cz", [T["contrib"], T["growth"]])
    ax.bar(np.arange(len(vals)), vals, width=1.0,
           color=[cmap(norm(v)) for v in vals], zorder=3)

    ax.axhline(contributed, color=T["contrib"], lw=1.6, ls=(0, (5, 3)), zorder=4)
    ax.axhline(med, color=T["ink"], lw=1.3, ls=":", zorder=4)
    end_label(ax, len(vals) - 1, contributed, f"{money(contributed)} contributed",
              T["contrib"], size=10, weight="normal", dot=False)
    end_label(ax, len(vals) - 1, med, f"{money(med)} median", T["ink"],
              size=10, weight="normal", dot=False)

    for i, color, label, xt in [
            (lo_i, T["warn"], f"worst: {money(vals[lo_i])}\nstarted {results[lo_i][0]}",
             (lo_i + 26, vals.max() * 0.80)),
            (hi_i, T["growth"], f"best: {money(vals[hi_i])}\nstarted {results[hi_i][0]}",
             (hi_i - 34, vals.max() * 1.06))]:
        ax.plot([i], [vals[i]], "o", ms=7, color=color, zorder=6,
                markeredgecolor=T["bg"], markeredgewidth=1.6)
        note(ax, (i, vals[i]), label, color, xt, size=9.6)

    step = max(1, len(vals) // 8)
    ax.set_xticks(np.arange(0, len(vals), step))
    ax.set_xticklabels([results[i][0] for i in range(0, len(vals), step)])
    ax.set_xlabel("Month the plan started", fontsize=10.5, labelpad=9)
    money_axis(ax)
    ax.set_xlim(-0.5, len(vals) - 0.5)
    ax.set_ylim(0, vals.max() * 1.16)
    save(fig, "compounding_windows.png")
    return results


# ---------------------------------------------------------------------------
def main():
    global OUTDIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true",
                    help="also run the plan through real S&P 500 total-return history")
    ap.add_argument("--refresh", action="store_true", help="ignore the cached CSV")
    ap.add_argument("--dark", action="store_true", help="dark theme")
    ap.add_argument("--out", default="charts_v2",
                    help="output folder, relative to the script (default: charts_v2)")
    args = ap.parse_args()

    OUTDIR = (args.out if os.path.isabs(args.out)
              else os.path.join(SCRIPT_DIR, args.out))
    set_theme("dark" if args.dark else "light")

    print(f"Plan: {money_full(MONTHLY)}/month for {YEARS} years at {RETURN*100:.0f}% "
          f"nominal, {FEE*100:.2f}% costs\n"
          f"Writing to: {OUTDIR}/\n")

    rows = simulate()
    save_csv("compounding_base.csv", rows,
             ["year", "contributed", "value", "growth_total",
              "contributed_this_year", "growth_this_year"])
    chart_curve(rows)
    finals = chart_fees()
    chart_real(rows)
    ana, bogdan = chart_early_vs_late()

    x = crossover_year(rows)
    last, ten = rows[-1], rows[9]
    print("\n--- headline numbers -------------------------------------------")
    print(f"After 10 years: {money_full(ten['value'])} "
          f"({money_full(ten['contributed'])} contributed, {money_full(ten['growth_total'])} growth)")
    print(f"After {YEARS} years: {money_full(last['value'])} "
          f"({money_full(last['contributed'])} contributed, {money_full(last['growth_total'])} growth "
          f"= {last['growth_total']/last['value']*100:.0f}% of the final balance)")
    print(f"Crossover year (growth > contributions): year {x}")
    print(f"Real value at {INFL_EURO*100:.0f}%: "
          f"{money_full(simulate(annual_inflation=INFL_EURO)[-1]['real_value'])}")
    print(f"Real value at {INFL_RO_FORECAST*100:.1f}%: "
          f"{money_full(simulate(annual_inflation=INFL_RO_FORECAST)[-1]['real_value'])}")
    print(f"Real value at {INFL_RO_NOW*100:.1f}%: "
          f"{money_full(simulate(annual_inflation=INFL_RO_NOW)[-1]['real_value'])}")
    for label, v in finals:
        print(f"Fee {label}: {money_full(v)}")
    print(f"Ana (10 early years, {money_full(ana[9]['contributed'])} in): {money_full(ana[-1]['value'])}")
    print(f"Bogdan (30 later years, {money_full(bogdan[-1]['contributed'])} in): {money_full(bogdan[-1]['value'])}")

    if args.real:
        print("\n--- real market history ----------------------------------------")
        series = load_market_history(refresh=args.refresh)
        print(f"  {len(series)} months, {series[0][0]} to {series[-1][0]}")
        path = chart_history(series)
        res = chart_windows(series)
        vals = sorted(r[1] for r in res)
        print(f"Full history: contributed {money_full(path[-1]['contributed'])}, "
              f"ended {money_full(path[-1]['value'])}")
        print(f"20-year windows: worst {money_full(vals[0])}, median {money_full(vals[len(vals)//2])}, "
              f"best {money_full(vals[-1])} on {money_full(res[0][2])} contributed")


if __name__ == "__main__":
    main()
