"""
impatience.py  --  the arithmetic behind "The Investor's Enemy: Impatience"
                   (CodeZero2Hero).

WHY THIS EXISTS:
  The post claims that temperament, not intelligence, is the binding
  constraint for a small investor. That is easy to assert and cheap to
  believe, so the three claims in it that are NOT opinion are computed here
  from 150+ years of monthly data:

    1. Being underwater is the DEFAULT STATE, not the exception. If patience
       feels hard, that is because most of the journey is spent below a
       number you have already seen.
    2. Getting out "until things calm down" and coming back later -- with
       perfect discipline about coming back, no fees, no taxes -- costs more
       than almost any amount of cleverness could add back. The script
       measures the cost in dollars AND converts it into the annual
       outperformance you would need to break even.
    3. You cannot skip the worst stretches without also skipping the best
       months, because the best months happen INSIDE the worst stretches.

  Data: Robert Shiller's long-run S&P composite dataset (Yale), fetched from
  the free `datasets/s-and-p-500` mirror (three hosts tried in order, plus a
  local cache after the first successful run). No API key, no scraping.
  Everything is CPI-adjusted total return -- dividends reinvested, dollars of
  purchasing power. The series is a US index, so dollars is its native unit;
  no exchange rate is assumed anywhere.

WHAT THE SIMULATION ASSUMES (say it out loud, it matters):
  USD 500 a month in constant purchasing power, bought at the month's index
  level. The impatient savers are given every advantage: they sell and buy
  back instantly at the index level, pay no spread, no commission, no tax,
  and -- unlike real people -- they ALWAYS come back on schedule. Cash held
  while out of the market earns 0% real, which is roughly what a bank deposit
  has done after inflation and tax. A sensitivity run at +1%/yr real on cash
  is printed too.

REQUIREMENTS:  pip install plotly kaleido   (everything else is stdlib)
               Kaleido renders the PNGs through Chrome; if you don't have
               one installed, `plotly_get_chrome` fetches it.

Run:  python3 impatience.py
"""

import csv
import io
import os
import statistics
import urllib.request

import plotly.graph_objects as go

# Same file, three hosts; GitHub occasionally rate-limits plain visits (429).
DATA_URLS = [
    "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv",
    "https://cdn.jsdelivr.net/gh/datasets/s-and-p-500@master/data/data.csv",
    "https://datahub.io/core/s-and-p-500/r/data.csv",
]
CACHE_FILE = "shiller_monthly_cache.csv"
USER_AGENT = "CodeZero2Hero research yourname@example.com"

CONTRIB = 500          # dollars per month, constant purchasing power
PLAN_YEARS = 30
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
    exist -- both lag the price series by a couple of years."""
    tr = [None] * len(rows)
    tr[0] = 1.0
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if tr[i - 1] and prev["price"] and cur["price"] and cur["div"]:
            tr[i] = tr[i - 1] * (cur["price"] + cur["div"] / 12) / prev["price"]
    real = [t / r["cpi"] if (t and r["cpi"]) else None for t, r in zip(tr, rows)]
    return real


def with_drag(series, annual):
    """The same index with a smooth monthly boost (positive) or fee
    (negative). Used to price 'how much skill would undo this mistake'."""
    m = (1 + annual) ** (1 / 12) - 1
    return [s * (1 + m) ** i if s else None for i, s in enumerate(series)]


# ---------------------------------------------------------------------------
# Claim 1 -- how much of the time are you underwater?
# ---------------------------------------------------------------------------
def drawdown_series(series):
    """Percent below the highest level seen so far, month by month."""
    dd, peak = [], None
    for v in series:
        if v is None:
            dd.append(None)
            continue
        peak = v if peak is None else max(peak, v)
        dd.append(v / peak - 1)
    return dd


def longest_underwater_run(dd, idx):
    """Longest consecutive stretch strictly below a previous peak, returned as
    (length_in_months, start_index, end_index)."""
    best = (0, None, None)
    run_start = None
    for i in idx:
        if dd[i] < 0:
            if run_start is None:
                run_start = i
            length = i - run_start + 1
            if length > best[0]:
                best = (length, run_start, i)
        else:
            run_start = None
    return best


# ---------------------------------------------------------------------------
# Claim 2 -- what does "I'll get back in when it calms down" cost?
# ---------------------------------------------------------------------------
RULES = [
    dict(key="patient", label="Never sold", trigger=None),
    dict(key="dd10w6", label="Out at -10%, back 6 months later",
         trigger=0.10, mode="wait", wait=6),
    dict(key="dd20w12", label="Out at -20%, back 12 months later",
         trigger=0.20, mode="wait", wait=12),
    dict(key="dd10high", label="Out at -10%, back at the next all-time high",
         trigger=0.10, mode="newhigh"),
]


def run_plan(series, start, months, rule, contrib=CONTRIB, cash_real=0.0):
    """One saver, one 30-year window. Order inside each month: look at the
    price, act on it, then make that month's contribution. Selling and buying
    back are free and instantaneous -- deliberately generous to the impatient
    saver."""
    cash_m = (1 + cash_real) ** (1 / 12) - 1
    units = cash = 0.0
    invested = True
    peak = None
    out_for = 0
    exits = 0

    for k in range(months):
        p = series[start + k]
        if not p:
            return None
        peak = p if peak is None else max(peak, p)
        cash *= (1 + cash_m)

        if rule["trigger"] is not None:
            dd = p / peak - 1
            if invested and dd <= -rule["trigger"]:
                cash += units * p
                units = 0.0
                invested = False
                out_for = 0
                exits += 1
            elif not invested:
                out_for += 1
                back = (rule["mode"] == "wait" and out_for >= rule["wait"]) or \
                       (rule["mode"] == "newhigh" and p >= peak)
                if back:
                    units += cash / p
                    cash = 0.0
                    invested = True

        if invested:
            units += contrib / p
        else:
            cash += contrib

    p_end = series[start + months - 1]
    return dict(value=units * p_end + cash, exits=exits, ended_out=not invested)


def all_windows(series, months):
    """Every start month for which a full `months`-long plan is possible."""
    return [i for i in range(len(series) - months + 1)
            if all(series[i + k] for k in range(months))]


def solve_break_even_edge(series, starts, rule, target_median):
    """How much annual outperformance would the impatient saver need -- on
    every dollar, for thirty years -- to end up where patience ended up?"""
    lo, hi = 0.0, 0.25
    for _ in range(40):
        mid = (lo + hi) / 2
        boosted = with_drag(series, mid)
        med = statistics.median(run_plan(boosted, s, PLAN_MONTHS, rule)["value"]
                                for s in starts)
        if med < target_median:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# Chart style -- one editorial system, rendered with Plotly + Kaleido
# ---------------------------------------------------------------------------
# The blog page is white, so every figure sits on a warm paper panel with a
# hairline edge; otherwise the chart bleeds into the article and nobody can
# tell where one stops and the other starts. Headlines are set in a serif,
# everything else in a humanist sans, which is the cheapest way to make a
# matplotlib-shaped chart stop looking like a matplotlib-shaped chart.

W, H = 1200, 600          # every figure ships at exactly this size
MARGIN_T, MARGIN_B, MARGIN_R = 156, 70, 42

PAPER, EDGE = "#f2efe7", "#d8d2c0"
BLUE, RED = "#2a78d6", "#e34948"
BLUE_SOFT, RED_SOFT = "rgba(42,120,214,0.16)", "rgba(227,73,72,0.13)"
INK, SEC, MUT = "#14130f", "#52514e", "#8b8878"
GRID, BASE = "#e4dfcf", "#c7c1ad"

SERIF = "Charter, 'Bitstream Charter', Caladea, Georgia, 'Times New Roman', serif"
SANS = "Carlito, 'Liberation Sans', 'DejaVu Sans', Helvetica, Arial, sans-serif"

SOURCE = ("Source: Robert Shiller's long-run S&amp;P composite dataset (Yale) via the "
          "datasets/s-and-p-500 mirror  ·  dividends reinvested  ·  CPI-adjusted  ·  "
          "before fees and taxes")


def _chrome():
    """Kaleido renders through Chrome. Most machines have one; some don't, and
    the error message it gives is easier to act on than to decode."""
    if os.environ.get("BROWSER_PATH"):
        return
    for p in ("/usr/bin/google-chrome", "/usr/bin/chromium",
              "/usr/bin/chromium-browser", "/snap/bin/chromium",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"):
        if os.path.exists(p):
            os.environ["BROWSER_PATH"] = p
            return
    print("  note: no Chrome found. If the export fails, run `plotly_get_chrome`\n"
          "        or set BROWSER_PATH to a Chrome/Chromium binary.")


class Panel:
    """A figure with the house header: eyebrow, serif headline, sans standfirst,
    hairline rule, hairline frame, source line. Annotations are positioned in
    PIXELS from the top-left of the image, because 'paper' coordinates move
    whenever a margin changes and then every chart drifts apart."""

    def __init__(self, head, sub, margin_l):
        self.ml = margin_l
        self.pw = W - margin_l - MARGIN_R
        self.ph = H - MARGIN_T - MARGIN_B
        self.fig = go.Figure()
        self.fig.update_layout(
            width=W, height=H, paper_bgcolor=PAPER, plot_bgcolor=PAPER,
            margin=dict(l=margin_l, r=MARGIN_R, t=MARGIN_T, b=MARGIN_B),
            showlegend=False, hovermode=False,
        )
        self.text(34, 30, "C O D E Z E R O 2 H E R O", SANS, 10.5, BLUE)
        self.text(34, 47, head, SERIF, 29, INK)
        self.text(34, 96, sub, SANS, 13, SEC)
        self.text(34, H - 24, SOURCE, SANS, 10, MUT)
        self.rule(34, W - 34, 141)
        self.frame()

    # -- pixel helpers ------------------------------------------------------
    def x(self, px):
        return (px - self.ml) / self.pw

    def y(self, px):
        return 1 - (px - MARGIN_T) / self.ph

    def text(self, xpx, ypx, t, family, size, color, anchor="left"):
        self.fig.add_annotation(
            xref="paper", yref="paper", x=self.x(xpx), y=self.y(ypx), text=t,
            showarrow=False, xanchor=anchor, yanchor="top", align="left",
            font=dict(family=family, size=size, color=color))

    def rule(self, x0, x1, ypx, color=EDGE, width=1):
        self.fig.add_shape(type="line", xref="paper", yref="paper",
                           x0=self.x(x0), x1=self.x(x1),
                           y0=self.y(ypx), y1=self.y(ypx),
                           line=dict(color=color, width=width))

    def frame(self):
        self.fig.add_shape(type="rect", xref="paper", yref="paper",
                           x0=self.x(0.5), x1=self.x(W - 0.5),
                           y0=self.y(H - 0.5), y1=self.y(0.5),
                           line=dict(color=EDGE, width=1), layer="above")

    def axes(self, **kw):
        self.fig.update_layout(**kw)

    def save(self, name):
        self.fig.write_image(name, width=W, height=H, scale=1)
        print(f"  wrote {name}")


def usd(v, dollar=True):
    return ("$" if dollar else "") + f"{v:,.0f}".replace(",", " ")


AX = dict(showgrid=False, zeroline=False, ticks="", showline=False)
TICK = dict(family=SANS, size=12, color=MUT)

# ---------------------------------------------------------------------------
# Chart 1 -- underwater is the default state
# ---------------------------------------------------------------------------
def chart_underwater(rows, real, dd, idx, share, run):
    xs = [int(rows[i]["date"][:4]) + (int(rows[i]["date"][5:7]) - 1) / 12 for i in idx]
    ys = [dd[i] * 100 for i in idx]

    p = Panel("Most of investing is spent below a number you have already seen",
              f"How far the US market sat below its own previous peak, month by month, "
              f"1871&#8211;{rows[idx[-1]]['date'][:4]}, in purchasing power.<br>"
              f"The line only touches zero on {100 - share:.0f}% of months. The other "
              f"{share:.0f}% (every shaded dip); is the part that has to be sat through.",
              margin_l=70)

    _, a, b = run
    xa = int(rows[a]["date"][:4]) + (int(rows[a]["date"][5:7]) - 1) / 12
    xb = int(rows[b]["date"][:4]) + (int(rows[b]["date"][5:7]) - 1) / 12
    p.fig.add_vrect(x0=xa, x1=xb, fillcolor=RED_SOFT, line_width=0, layer="below")

    p.fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines", line=dict(color=BLUE, width=1.1),
        fill="tozeroy",
        fillgradient=dict(type="vertical",
                          colorscale=[[0.0, "rgba(42,120,214,0.34)"],
                                      [0.55, "rgba(42,120,214,0.16)"],
                                      [1.0, "rgba(42,120,214,0.03)"]])))

    p.fig.add_annotation(
        x=(xa + xb) / 2, y=-47, ax=-96, ay=64, xanchor="left", align="left",
        text=f"<b>{run[0] // 12} years and {run[0] % 12} months</b><br>"
             f"without a new high<br>"
             f"<span style='font-size:11px'>{rows[a]['date']} &#8594; {rows[b]['date']}</span>",
        showarrow=True, arrowhead=0, arrowwidth=0.9, arrowcolor=BASE,
        font=dict(family=SANS, size=12.5, color=SEC))

    p.fig.add_hline(y=0, line=dict(color=BASE, width=1.1))
    p.axes(
        xaxis=dict(AX, range=[min(xs) - 2, max(xs) + 2],
                   tickvals=list(range(1880, 2021, 20)), tickfont=TICK),
        yaxis=dict(AX, range=[min(ys) * 1.16, 6], showgrid=True, gridcolor=GRID,
                   tickvals=list(range(-80, 1, 20)),
                   ticktext=[f"{v}%" for v in range(-80, 1, 20)], tickfont=TICK),
    )
    p.save("underwater.png")


# ---------------------------------------------------------------------------
# Chart 2 -- the price of "I'll get back in when it calms down"
# ---------------------------------------------------------------------------
def chart_price_of_impatience(results, patient_med):
    rows_ = results[::-1]
    labels = [r["label"].replace("-", "&#8722;") for r in rows_]
    values = [r["median"] for r in rows_]

    p = Panel("What it costs to step out until things calm down",
              "Median ending pot of a $500-a-month plan across every completed 30-year "
              "window since 1871, in purchasing power.<br>The sellers pay no fees, no tax, "
              "no spread and always come back on schedule.",
              margin_l=302)

    p.fig.add_trace(go.Bar(
        x=values, y=labels, orientation="h", width=0.44,
        marker=dict(color=[BLUE if v == patient_med else RED for v in values],
                    cornerradius=6)))

    for r, lab, v in zip(rows_, labels, values):
        p.fig.add_annotation(x=v, y=lab, text=f"<b>{usd(v)}</b>", showarrow=False,
                             xanchor="left", xshift=13,
                             font=dict(family=SANS, size=17, color=INK))
        if r["patience_win"] is not None:
            gap = patient_med - v
            p.fig.add_annotation(
                x=0, y=lab, xanchor="left", yanchor="top", yshift=-17,
                text=f"&#8722;{usd(gap)}  ·  {100 * gap / patient_med:.0f}% of the pot"
                     f"  ·  patience won {r['patience_win']:.0f}% of the 1 471 windows",
                showarrow=False, font=dict(family=SANS, size=11.5, color=MUT))

    top = patient_med * 1.17
    ticks = [t for t in range(0, int(top), 100_000)]
    p.axes(
        bargap=0.44,
        xaxis=dict(AX, range=[0, top], showgrid=True, gridcolor=GRID,
                   tickvals=ticks, ticktext=[usd(t) for t in ticks], tickfont=TICK),
        yaxis=dict(AX, ticksuffix="   ",
                   tickfont=dict(family=SANS, size=14, color=SEC)),
    )
    p.save("price_of_impatience.png")


# ---------------------------------------------------------------------------
# Chart 3 -- the best months happen in the worst places
# ---------------------------------------------------------------------------
def chart_best_months(best, deep_cut):
    xs = [b["dd_before"] * 100 for b in best]
    ys = [b["ret"] * 100 for b in best]
    n_deep = sum(1 for b in best if b["dd_before"] <= -deep_cut)
    lo = min(xs) * 1.13

    p = Panel("The best months are inside the worst years",
              f"Every one of the 20 strongest months for the US market since 1871, placed by "
              f"how ugly things looked<br>the day before it started. {n_deep} of the 20 began "
              f"with the market more than {deep_cut*100:.0f}% below its peak.",
              margin_l=86)

    p.fig.add_vrect(x0=lo, x1=-deep_cut * 100, fillcolor="rgba(227,73,72,0.06)",
                    line_width=0, layer="below")
    p.fig.add_vline(x=-deep_cut * 100, line=dict(color=BASE, width=1, dash="dot"))
    p.fig.add_annotation(x=-deep_cut * 100, y=max(ys) + 3.0, xanchor="right", xshift=-9,
                         text=f"more than {deep_cut*100:.0f}% below the peak &#8594;"
                              .replace("&#8594;", ""),
                         showarrow=False, font=dict(family=SANS, size=11.5, color=MUT))

    top3 = {b["date"] for b in sorted(best, key=lambda z: -z["ret"])[:3]}
    p.fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=[19 if b["date"] in top3 else 13 for b in best],
                    color=[RED if b["dd_before"] <= -deep_cut else BLUE for b in best],
                    line=dict(color=PAPER, width=2.4))))

    for b in sorted(best, key=lambda z: -z["ret"])[:3]:
        p.fig.add_annotation(
            x=b["dd_before"] * 100, y=b["ret"] * 100, ax=44, ay=-20,
            text=f"<b>{b['date']}</b>  +{b['ret']*100:.1f}%", xanchor="left",
            showarrow=True, arrowhead=0, arrowwidth=0.9, arrowcolor=BASE,
            font=dict(family=SANS, size=12, color=SEC))

    p.fig.add_vline(x=0, line=dict(color=BASE, width=1.1))
    p.axes(
        xaxis=dict(AX, range=[lo, 9], ticksuffix="%", tickfont=TICK,
                   title=dict(text="How far the market was below its previous peak "
                                   "when the month began",
                              font=dict(family=SANS, size=12.5, color=MUT),
                              standoff=14)),
        yaxis=dict(AX, range=[min(ys) - 3.5, max(ys) + 6], showgrid=True, gridcolor=GRID,
                   tickprefix="+", ticksuffix="%", tickfont=TICK,
                   title=dict(text="That month's real total return",
                              font=dict(family=SANS, size=12.5, color=MUT),
                              standoff=12)),
    )
    p.save("best_months.png")


# ---------------------------------------------------------------------------
def main():
    _chrome()
    print("fetching monthly data (Shiller long-run dataset mirror)...")
    rows = fetch_rows()
    print(f"  {len(rows)} months, {rows[0]['date']} -> {rows[-1]['date']}")

    real = real_total_return_index(rows)
    idx = [i for i, v in enumerate(real) if v]
    print(f"  real total return defined {rows[idx[0]]['date']} -> {rows[idx[-1]]['date']} "
          f"({len(idx)} months)")

    # ---- claim 1: underwater is the default ------------------------------
    dd = drawdown_series(real)
    under = sum(1 for i in idx if dd[i] < 0)
    share = 100 * under / len(idx)
    run = longest_underwater_run(dd, idx)
    print("\n--- 1. how much of the time are you underwater? ---")
    print(f"  months below a previous all-time high: {under} of {len(idx)} "
          f"({share:.1f}%)")
    print(f"  longest single stretch: {run[0]} months "
          f"({run[0]/12:.1f} years), {rows[run[1]]['date']} -> {rows[run[2]]['date']}")
    for thr in (0.05, 0.10, 0.20):
        n = sum(1 for i in idx if dd[i] <= -thr)
        print(f"  months more than {thr*100:>2.0f}% below the peak: {n} "
              f"({100*n/len(idx):.1f}%)")
    print(f"  deepest real drawdown: {min(dd[i] for i in idx)*100:.1f}% "
          f"({rows[min(idx, key=lambda i: dd[i])]['date']})")

    chart_underwater(rows, real, dd, idx, share, run)

    # ---- claim 2: the price of impatience --------------------------------
    starts = all_windows(real, PLAN_MONTHS)
    contributed = CONTRIB * PLAN_MONTHS
    print(f"\n--- 2. the price of getting out ({len(starts)} complete 30-year plans, "
          f"{rows[starts[0]]['date']} -> {rows[starts[-1]]['date']} starts) ---")
    print(f"  plan: {usd(CONTRIB)}/month for {PLAN_YEARS} years = "
          f"{usd(contributed)} contributed, constant purchasing power")

    runs = {}
    for rule in RULES:
        runs[rule["key"]] = [run_plan(real, s, PLAN_MONTHS, rule) for s in starts]

    patient = runs["patient"]
    patient_med = statistics.median(r["value"] for r in patient)
    results = []
    for rule in RULES:
        rs = runs[rule["key"]]
        med = statistics.median(r["value"] for r in rs)
        row = dict(label=rule["label"], median=med, patience_win=None)
        if rule["trigger"] is not None:
            win = 100 * sum(1 for a, b in zip(patient, rs)
                            if a["value"] > b["value"]) / len(rs)
            row["patience_win"] = win
            exits = statistics.median(r["exits"] for r in rs)
            still_out = 100 * sum(1 for r in rs if r["ended_out"]) / len(rs)
            edge = solve_break_even_edge(real, starts, rule, patient_med)
            row.update(edge=edge, exits=exits, still_out=still_out)
            print(f"  {rule['label']}")
            print(f"      median ending pot {usd(med):>10}  "
                  f"vs patient {usd(patient_med)}  "
                  f"({usd(patient_med - med)} = "
                  f"{100*(patient_med-med)/patient_med:.1f}% of the pot)")
            print(f"      patience won {win:.1f}% of windows | "
                  f"median exits per plan {exits:.0f} | "
                  f"ended the 30 years still in cash: {still_out:.1f}%")
            print(f"      break-even skill needed: +{edge*100:.2f}%/yr, "
                  f"every year, for thirty years")
        else:
            print(f"  {rule['label']}: median ending pot {usd(med)} "
                  f"({med/contributed:.2f}x contributions)")
        results.append(row)

    chart_price_of_impatience(results, patient_med)

    # sensitivity: give the cash pile a real 1%/yr, which is generous
    print("\n  sensitivity — cash earning +1%/yr real while out of the market:")
    for rule in RULES[1:]:
        med = statistics.median(
            run_plan(real, s, PLAN_MONTHS, rule, cash_real=0.01)["value"]
            for s in starts)
        print(f"      {rule['label']}: {usd(med)} "
              f"({usd(patient_med - med)} behind patience)")

    # ---- claim 3: the best months hide in the worst years -----------------
    monthly = []
    for j in range(1, len(idx)):
        i, prev = idx[j], idx[j - 1]
        if i != prev + 1:
            continue
        monthly.append(dict(i=i, date=rows[i]["date"],
                            ret=real[i] / real[prev] - 1,
                            dd_before=dd[prev]))
    best = sorted(monthly, key=lambda m: -m["ret"])[:20]
    worst = sorted(monthly, key=lambda m: m["ret"])[:20]
    DEEP = 0.20
    n_deep = sum(1 for b in best if b["dd_before"] <= -DEEP)
    n_any = sum(1 for b in best if b["dd_before"] < -0.001)
    print("\n--- 3. where do the best months happen? ---")
    print(f"  of the 20 best months since 1871: {n_any} began with the market "
          f"already below its peak, {n_deep} began more than {DEEP*100:.0f}% below it")
    print(f"  median drawdown at the start of a top-20 month: "
          f"{statistics.median(b['dd_before'] for b in best)*100:.1f}%")
    print("  the five strongest months:")
    for b in best[:5]:
        print(f"      {b['date']}  +{b['ret']*100:5.1f}%   "
              f"(market was {b['dd_before']*100:6.1f}% below its peak)")

    # how close together are the best and worst months?
    worst_i = {w["i"] for w in worst}
    near = sum(1 for b in best
               if any(abs(b["i"] - wi) <= 12 for wi in worst_i))
    print(f"  {near} of the 20 best months fell within 12 months of one of the "
          f"20 worst months")

    chart_best_months(best, DEEP)

    # what missing a handful of months does to a 30-year plan
    print("\n  missing the best months of your own 30 years (median window):")
    for miss in (3, 6, 12):
        vals = []
        for s in starts:
            w = sorted(range(PLAN_MONTHS),
                       key=lambda k: -(real[s + k] / real[s + k - 1] - 1)
                       if k else 0)[:miss]
            blocked = set(w)
            # rebuild the window with those months' returns set to zero --
            # you were holding, the market simply never delivered that month
            adj = [real[s]]
            for k in range(1, PLAN_MONTHS):
                g = 1.0 if k in blocked else real[s + k] / real[s + k - 1]
                adj.append(adj[-1] * g)
            u = sum(CONTRIB / adj[k] for k in range(PLAN_MONTHS))
            vals.append(u * adj[-1])
        med = statistics.median(vals)
        print(f"      miss the {miss:>2} best months: {usd(med)}  "
              f"({usd(patient_med - med)} behind, "
              f"{100*(patient_med-med)/patient_med:.0f}% of the pot)")

    # ---- verification CSV -------------------------------------------------
    with open("impatience_table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["start_month", "end_month", "contributed_usd"] +
                   [r["key"] + "_usd" for r in RULES] +
                   [r["key"] + "_exits" for r in RULES if r["trigger"]])
        for n, s in enumerate(starts):
            w.writerow([rows[s]["date"], rows[s + PLAN_MONTHS - 1]["date"],
                        contributed] +
                       [round(runs[r["key"]][n]["value"], 2) for r in RULES] +
                       [runs[r["key"]][n]["exits"] for r in RULES if r["trigger"]])
    print("\n  wrote impatience_table.csv")


if __name__ == "__main__":
    main()