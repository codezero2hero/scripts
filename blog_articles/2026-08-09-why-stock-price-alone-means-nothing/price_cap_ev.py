"""
WHAT IT DOES:
  For six companies it builds the ladder the article walks through:

      share price  x  shares outstanding  =  market cap        (the sticker)
      market cap   +  debt  -  cash       =  enterprise value  (the all-in price)

  1. Shares outstanding, debt and cash come from SEC EDGAR's free XBRL API
     (data.sec.gov) -- the primary source, straight from each company's own
     filings. No scraping, no API key.
  2. The share PRICE is the one number a filing cannot give you -- it changes
     every second the market is open. So it's fetched LIVE from Yahoo Finance
     (via yfinance) on every run. If the fetch fails -- offline, Yahoo hiccup,
     yfinance not installed -- the script falls back to a snapshot from the
     day this post was written, which is of course already stale. Even the
     fallback is a lesson.
  3. Writes a CSV (so you can check every number against the filings) and
     renders two charts: the price-vs-size rank scramble, and EV as a % of
     market cap.

WHY FORD IS IN THE FIRST CHART BUT NOT THE SECOND:
  Ford owns a bank (Ford Credit) whose ~$150B of borrowings sit on Ford's
  balance sheet. Mechanical EV treats that like corporate debt and triples
  Ford's "price". The article's limitations section explains why EV breaks
  for companies with big financing arms -- so Ford stays out of chart 2.

REQUIREMENTS:  pip install matplotlib yfinance       (the rest is stdlib)

IMPORTANT:  edit USER_AGENT below to your real name + email.
            SEC returns HTTP 403 for requests without a proper User-Agent.

Run:  python3 price_cap_ev.py
"""

import csv
import json
import time
import urllib.request
from datetime import date

import matplotlib.pyplot as plt

# --- EDIT THIS: SEC requires a descriptive User-Agent with contact info ------
USER_AGENT = "CodeZero2Hero research yourname@example.com"

# --- Prices: live from Yahoo Finance each run; snapshot only as fallback ----
FALLBACK_AS_OF = "2026-08-09" 
FALLBACK_PRICES = {
    "NVDA": 222.37,
    "GOOGL": 356.30,
    "BKNG": 207.39,
    "CCL": 29.08,
    "T": 23.71,
    "F": 14.05,
}


def get_prices(tickers):
    """Latest close per ticker, live from Yahoo Finance; stale snapshot if not."""
    try:
        import logging
        import yfinance as yf
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # keep failures quiet
    except ImportError:
        print(f"yfinance not installed (pip install yfinance) -- "
              f"using the stale {FALLBACK_AS_OF} snapshot\n")
        return dict(FALLBACK_PRICES), FALLBACK_AS_OF
    prices, asof = {}, None
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="1d")
            prices[t] = float(h["Close"].iloc[-1])
            asof = str(h.index[-1].date())
        except Exception:
            print(f"  {t}: live fetch failed -- using the stale "
                  f"{FALLBACK_AS_OF} snapshot ({FALLBACK_PRICES[t]})")
            prices[t] = FALLBACK_PRICES[t]
    return prices, asof or FALLBACK_AS_OF

COMPANIES = {
    # ticker: (company, CIK, include in the EV chart?)
    "GOOGL": ("Alphabet",         "0001652044", True),
    "NVDA":  ("NVIDIA",           "0001045810", True),
    "BKNG":  ("Booking Holdings", "0001075531", True),
    "CCL":   ("Carnival",         "0000815097", True),
    "T":     ("AT&T",             "0000732717", True),
    "F":     ("Ford",             "0000037996", False),  # see docstring
}

# Companies tag the same idea under different XBRL concepts. Try in order.
SHARES_TAGS = [
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
]
CASH_TAGS = ["CashAndCashEquivalentsAtCarryingValue"]
CASH_LIKE_TAGS = [            # short-term parking spots for cash; first match wins
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "DebtSecuritiesCurrent",              # NVIDIA switched to this tag in 2026
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
]
DEBT_NONCURRENT_TAGS = [
    "LongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations",  # AT&T folds finance leases in here
    "LongTermDebt",
]
DEBT_CURRENT_TAGS = [         # either one consolidated tag, or the pieces
    ["DebtCurrent"],
    ["LongTermDebtCurrent", "CommercialPaper", "ShortTermBorrowings"],
]

# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def get_concept(cik, tag, unit):
    """Return the list of facts for one us-gaap concept, or [] if absent."""
    url = (f"https://data.sec.gov/api/xbrl/companyconcept/"
           f"CIK{cik}/us-gaap/{tag}.json")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []   # 404 just means this company never used this tag
            time.sleep(1.5) # rate-limited or hiccup: one polite retry
        except Exception:
            time.sleep(1.5)
    else:
        return []
    time.sleep(0.25)    # be polite to SEC's servers
    facts = data.get("units", {}).get(unit, [])
    return facts if isinstance(facts, list) else []


def get_concept_via_companyfacts(cik, tag, unit):
    """
    Plan B. For some companies (hello, Ford) the companyconcept endpoint
    returns an empty shell for a tag that plainly exists in the filings.
    The same numbers live in the (much bigger) companyfacts payload, so if
    plan A comes back empty, we fetch that instead. Welcome to real-world
    data plumbing: the primary source is free, but it isn't frictionless.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except Exception:
        return []
    time.sleep(0.25)
    facts = (data.get("facts", {}).get("us-gaap", {})
                 .get(tag, {}).get("units", {}).get(unit, []))
    return facts if isinstance(facts, list) else []


# ---------------------------------------------------------------------------
# Picking the right fact out of years of filings
# ---------------------------------------------------------------------------
def latest_instant(facts, at=None):
    """
    Balance-sheet items are point-in-time snapshots ("instants").
    Return (end_date, value) for the latest one -- or, if `at` is given,
    for that exact date. Restated numbers win via the latest filing date.
    """
    best = {}
    for f in facts:
        if "start" in f and f.get("start") != f.get("end"):
            continue                      # not an instant
        end = f["end"]
        if end not in best or f.get("filed", "") > best[end][0]:
            best[end] = (f.get("filed", ""), f["val"])
    if not best:
        return None, None
    if at is not None:
        return (at, best[at][1]) if at in best else (None, None)
    end = max(best)
    return end, best[end][1]


def latest_quarter_flow(facts):
    """
    Income-statement items cover a period ("duration"). Return the value for
    the most recently filed ~3-month period (i.e. the latest quarter).
    """
    best_end, best_filed, best_val = "", "", None
    for f in facts:
        if "start" not in f:
            continue
        days = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
        if not (80 <= days <= 100):
            continue                      # skip YTD and full-year periods
        key = (f["end"], f.get("filed", ""))
        if key > (best_end, best_filed):
            best_end, best_filed, best_val = f["end"], f.get("filed", ""), f["val"]
    return best_end, best_val


def first_tag_with_data(cik, tags, unit, picker):
    for fetch in (get_concept, get_concept_via_companyfacts):
        for tag in tags:
            end, val = picker(fetch(cik, tag, unit))
            if val is not None:
                return tag, end, val
    return None, None, None


def fundamentals(ticker, cik, in_ev=True):
    """Pull shares, cash and debt for one company; print the provenance."""
    print(f"{ticker}:")

    shares_tag, shares_end, shares = first_tag_with_data(
        cik, SHARES_TAGS, "shares", latest_quarter_flow)
    if shares is None:
        print("  no share count found -- check the tags, or your connection")
        return None
    print(f"  shares  {shares/1e9:7.2f}B   {shares_tag} (quarter ended {shares_end})")

    if not in_ev:
        print("  (skipping debt & cash -- this one sits out the EV chart, see docstring)")
        return {"shares": shares, "cash": 0.0, "debt": 0.0, "bs_date": "",
                "shares_tag": shares_tag, "cash_tags": "", "debt_tags": ""}

    # Anchor everything on the newest balance-sheet date the company filed.
    cash_tag, bs_date, cash = first_tag_with_data(
        cik, CASH_TAGS, "USD", latest_instant)
    cash_tags = [cash_tag]
    for tag in CASH_LIKE_TAGS:            # add short-term investments, if any
        _, extra = latest_instant(get_concept(cik, tag, "USD"), at=bs_date)
        if extra is not None:
            cash += extra
            cash_tags.append(tag)
            break                         # first match only -- avoids double counting
    print(f"  cash    {cash/1e9:7.2f}B   {' + '.join(cash_tags)} (as of {bs_date})")

    debt, debt_tags = 0.0, []
    for tag in DEBT_NONCURRENT_TAGS:
        _, val = latest_instant(get_concept(cik, tag, "USD"), at=bs_date)
        if val is not None:
            debt += val
            debt_tags.append(tag)
            break
    if "LongTermDebt" not in debt_tags:   # total-debt tag already includes current
        for group in DEBT_CURRENT_TAGS:
            found = False
            for tag in group:
                _, val = latest_instant(get_concept(cik, tag, "USD"), at=bs_date)
                if val is not None:
                    debt += val
                    debt_tags.append(tag)
                    found = True
                    if group == DEBT_CURRENT_TAGS[0]:
                        break             # consolidated tag -- stop here
            if found:
                break
    print(f"  debt    {debt/1e9:7.2f}B   {' + '.join(debt_tags)} (as of {bs_date})")

    return {"shares": shares, "cash": cash, "debt": debt, "bs_date": bs_date,
            "shares_tag": shares_tag, "cash_tags": "+".join(cash_tags),
            "debt_tags": "+".join(debt_tags)}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def money(x):
    """$56.0B / $5.39T -- compact, for labels."""
    if x >= 1e12:
        return f"${x/1e12:.2f}T"
    return f"${x/1e9:.0f}B"


def price_fmt(p):
    return f"${p:,.2f}" if p < 100 else f"${p:,.0f}"


# ---------------------------------------------------------------------------
# Charts (house style)
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.family": "DejaVu Sans",
    "font.size": 12, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25,
})
# Site-standard palette (same as casino_vs_market.py):
# green = works in your favor, red = works against you.
RED, GREEN, MUTED, INK = "#b91c1c", "#2e8b57", "#6b7280", "#1f2937"


def chart_rank_scramble(rows, asof):
    """Slopegraph: rank by share price on the left, by market cap on the right.
    Line color tells the story: green rises (the company is bigger than its
    share price suggests), red falls (smaller than it suggests)."""
    by_price = sorted(rows, key=lambda r: -r["price"])
    by_cap = sorted(rows, key=lambda r: -r["cap"])
    lrank = {r["ticker"]: i for i, r in enumerate(by_price)}
    rrank = {r["ticker"]: i for i, r in enumerate(by_cap)}

    fig, ax = plt.subplots(figsize=(10, 6.4))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.77, bottom=0.03)
    ax.axis("off")
    ax.set_xlim(-0.62, 1.62)
    ax.set_ylim(len(rows) - 0.2, -0.95)

    for r in rows:
        t = r["ticker"]
        y0, y1 = lrank[t], rrank[t]
        c = GREEN if y1 < y0 else RED
        ax.plot([0, 1], [y0, y1], "-o", color=c, lw=2.4, markersize=6.5,
                markeredgecolor="white", markeredgewidth=1.2, zorder=3)
        ax.text(-0.05, y0, f"{t}  {price_fmt(r['price'])}", ha="right",
                va="center", fontsize=11.5, color=INK, fontweight="bold")
        ax.text(1.05, y1, f"{t}  {money(r['cap'])}", ha="left",
                va="center", fontsize=11.5, color=INK, fontweight="bold")

    ax.text(0, -0.75, "ranked by SHARE PRICE", ha="center", fontsize=10.5,
            color=MUTED, fontweight="bold")
    ax.text(1, -0.75, "ranked by MARKET CAP", ha="center", fontsize=10.5,
            color=MUTED, fontweight="bold")
    # color key, bottom center
    ky = len(rows) - 0.38
    ax.text(0.47, ky, "rises: bigger than its share price suggests",
            ha="right", va="center", fontsize=9.5, color=GREEN, fontweight="bold")
    ax.text(0.50, ky, "·", ha="center", va="center", fontsize=9.5, color=MUTED)
    ax.text(0.53, ky, "falls: smaller than it suggests",
            ha="left", va="center", fontsize=9.5, color=RED, fontweight="bold")

    fig.text(0.015, 0.965, "Sort by price, then sort by size — the order scrambles",
             fontsize=15, fontweight="bold", ha="left", va="top")
    fig.text(0.015, 0.885,
             "Share price tells you the size of one slice, not the size of the pizza.\n"
             f"Prices as of {asof}; share counts from each company's latest filing.",
             fontsize=10.5, color=MUTED, ha="left", va="top")
    fig.text(0.015, 0.015, "Source: SEC EDGAR XBRL (us-gaap) for share counts; "
             "market cap = price × shares outstanding.",
             fontsize=8.5, color=MUTED, ha="left")
    fig.savefig("rank_scramble.png", facecolor="white")
    plt.close(fig)
    print("  wrote rank_scramble.png")


def chart_ev_vs_cap(rows, asof):
    """Deviation bars: enterprise value as % of market cap, anchored at 100%."""
    rows = sorted([r for r in rows if r["ev"] is not None],
                  key=lambda r: r["ev"] / r["cap"])
    fig, ax = plt.subplots(figsize=(10, 6.0))
    fig.subplots_adjust(left=0.22, right=0.98, top=0.755, bottom=0.10)

    for i, r in enumerate(rows):
        pct = r["ev"] / r["cap"] * 100
        above = pct >= 100
        c = RED if above else GREEN
        ax.barh(i, pct - 100, left=100, height=0.62, color=c,
                edgecolor="white", linewidth=1.5, zorder=3)
        ax.text(max(pct, 100) + 2.5, i, f"{pct:.0f}%", va="center", ha="left",
                fontsize=12, fontweight="bold", color=c)
        # "\$" stops matplotlib from reading the dollar signs as math markup
        ax.text(max(pct, 100) + 14, i,
                f"{money(r['cap'])} sticker → {money(r['ev'])} all-in".replace("$", "\\$"),
                va="center", ha="left", fontsize=9.5, color=MUTED)

    # story annotations, casino-post style
    ccl = next((i, r) for i, r in enumerate(rows) if r["ticker"] == "CCL")
    ax.annotate("Carnival's pandemic-era borrowing,\nstill attached to every share",
                xy=(ccl[1]["ev"] / ccl[1]["cap"] * 100, ccl[0] - 0.05),
                xytext=(170, ccl[0] - 0.72), fontsize=9.5, color=RED,
                arrowprops=dict(arrowstyle="-", color=RED, lw=0.8))
    goog = next((i, r) for i, r in enumerate(rows) if r["ticker"] == "GOOGL")
    ax.annotate("buy it, and the net cash pile\ncomes back with the keys",
                xy=(goog[1]["ev"] / goog[1]["cap"] * 100, goog[0] - 0.28),
                xytext=(113, goog[0] - 0.95), fontsize=9.5, color=GREEN,
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=0.8))

    ax.axvline(100, color="#52514e", lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.text(100, len(rows) - 0.18, " 100% = market cap (the sticker)",
            fontsize=9.5, color="#52514e", ha="left", va="bottom")
    ax.set_ylim(-1.5, len(rows) - 0.1)

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{r['name']} ({r['ticker']})" for r in rows],
                       fontsize=11.5, color=INK)
    ax.set_xlim(88, 235)
    ax.set_xticks([100, 125, 150, 175, 200])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)

    fig.text(0.015, 0.96, "The sticker price vs. the all-in price",
             fontsize=15, fontweight="bold", ha="left", va="top")
    fig.text(0.015, 0.88,
             "Enterprise value (market cap + debt − cash) as a % of market cap.\n"
             "Red: the debts make the business dearer than it looks. Green: the cash pile makes it cheaper.",
             fontsize=10.5, color=MUTED, ha="left", va="top")
    fig.text(0.015, 0.015, "Source: SEC EDGAR XBRL (us-gaap), latest filed balance sheet; "
             f"prices as of {asof}. Ford excluded — its captive finance arm breaks naive EV (see article).",
             fontsize=8.5, color=MUTED, ha="left")
    fig.savefig("ev_vs_cap.png", facecolor="white")
    plt.close(fig)
    print("  wrote ev_vs_cap.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    prices, asof = get_prices(list(COMPANIES))
    print(f"prices as of {asof}\n")
    rows = []
    for ticker, (name, cik, in_ev) in COMPANIES.items():
        f = fundamentals(ticker, cik, in_ev)
        if f is None:
            continue
        price = prices[ticker]
        cap = price * f["shares"]
        ev = cap + f["debt"] - f["cash"] if in_ev else None
        rows.append({"ticker": ticker, "name": name,
                     "price": price, "cap": cap, "ev": ev, **f})

    print("\nThe ladder (three price tags per company):")
    for r in sorted(rows, key=lambda r: -r["cap"]):
        line = (f"  {r['ticker']:5s} {price_fmt(r['price']):>11s}"
                f"  × {r['shares']/1e9:5.2f}B shares = {money(r['cap']):>7s}")
        if r["ev"] is not None:
            line += (f"  |  + {r['debt']/1e9:5.1f}B debt − {r['cash']/1e9:5.1f}B cash"
                     f" = {money(r['ev']):>7s} EV  ({r['ev']/r['cap']*100:3.0f}%)")
        else:
            line += "  |  EV skipped — captive finance arm (see article)"
        print(line)

    with open("price_cap_ev.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ticker", "name", "price_usd", "price_as_of", "shares",
                    "market_cap_usd", "debt_usd", "cash_usd", "ev_usd",
                    "ev_over_cap_pct", "balance_sheet_date",
                    "shares_tag", "debt_tags", "cash_tags"])
        for r in rows:
            w.writerow([r["ticker"], r["name"], round(r["price"], 2), asof,
                        r["shares"], round(r["cap"]), round(r["debt"]),
                        round(r["cash"]),
                        round(r["ev"]) if r["ev"] else "",
                        round(r["ev"] / r["cap"] * 100, 1) if r["ev"] else "",
                        r["bs_date"], r["shares_tag"], r["debt_tags"],
                        r["cash_tags"]])
    print("  wrote price_cap_ev.csv")

    chart_rank_scramble(rows, asof)
    chart_ev_vs_cap(rows, asof)


if __name__ == "__main__":
    main()
