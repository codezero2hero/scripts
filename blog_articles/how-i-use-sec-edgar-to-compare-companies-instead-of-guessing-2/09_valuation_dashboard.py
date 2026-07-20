"""
Create one HTML decision dashboard for the EDGAR valuation toolkit.

The dashboard combines two main valuation views:

    1. FCF DCF (cash-flow view)
       - Projects free cash flow with a fading growth path.
       - Discounts the projected cash flows using WACC when available.
       - Adds a Gordon-growth terminal value.

    2. EPS two-stage valuation (earnings view)
       - Values the business on a per-share EPS basis.
       - Uses a finite higher-growth stage followed by a mature stage.

Additional decision tools include:

    - WACC estimated with CAPM and after-tax debt cost.
    - Bear, Base, and Bull scenarios that vary growth and WACC.
    - A football-field chart showing valuation ranges by model.
    - Reverse DCF showing the FCF growth implied by the market price.
    - Terminal-value contribution as a valuation sanity check.
    - Margin of safety and desired entry-price calculations.

Data sources:

    SEC EDGAR companyfacts:
        FCF, EPS, dividends, revenue, shares, cash, debt, interest, and tax.

    CONFIG or optional yfinance:
        Current price, analyst target, and beta.

Requirements:

    pip install requests
    pip install yfinance  # optional

Project files required:

    - edgar_utils.py
    - dcf_model.py

Before running:

    Edit USER_AGENT in edgar_utils.py to include a real name/project and email.

Run:

    python 09_valuation_dashboard.py

Output:

    edgar_output/valuation_<TICKER>.html

Important:

    This is an educational model, not investment advice. Valuation results are
    highly sensitive to assumptions and extracted data. Verify material inputs
    against the original SEC filings before relying on the result.
"""

import os
import webbrowser
from datetime import date

from edgar_utils import load_facts, OUT_DIR

# Reuse the core EDGAR extraction, valuation helpers, and SVG visuals from
# dcf_model.py rather than duplicating that logic in this dashboard.
import dcf_model as dm

# ===========================================================================
# User-configurable assumptions
#
# Percentage inputs use percentage points: 9.5 means 9.5%, not 0.095.
# Set market values manually for reproducible output, or leave them as None to
# let the script attempt a yfinance lookup.
# =========================================================================== 
CONFIG = dict(
    ticker="META",

    # Market data. Leave as None to try yfinance; or set by hand.
    current_price=None,
    analyst_target=None,
    beta=None,

    # --- FCF DCF (cash-flow view) ---------------------------------------
    growth_start=None,         # near-term FCF growth %. None -> revenue CAGR (capped)
    growth_end=4.0,            # growth in the final projected year (fades to this)
    growth_start_cap=40.0,     # cap on the derived starting growth
    projection_years=10,       # fading ramp needs room; 10 matches the substack model
    terminal_growth=3.0,       # perpetual growth after the projection, %
    base_fcf="avg3",           # "latest" or "avg3" base free cash flow

    # --- EPS two-stage (GuruFocus-style cross-check) --------------------
    gf_discount_rate=11.0,
    gf_growth_years=10,
    gf_terminal_rate=4.0,
    gf_terminal_years=10,

    # --- quick cross-checks (for the football field) --------------------
    fair_pe=35.0,              # multiple you think the business deserves
    aaa_bond_yield=4.5,        # Graham's "Y"
    cross_growth_cap=15.0,     # cap on growth fed to Graham / Multiples / DDM

    # --- WACC / CAPM ----------------------------------------------------
    discount_rate=9.5,         # fallback if no beta for CAPM, %
    risk_free=4.3,             # 10-yr Treasury, %
    equity_risk_premium=4.5,   # Damodaran-style mature-market ERP, %
    tax_rate=None,             # None -> derive from EDGAR, else 21
    beta_fallback=1.20,

    # --- decision -------------------------------------------------------
    desired_mos=15.0,          # margin of safety required before buying, %
    growth_scn_step=5.0,       # +/- growth points for Bear / Bull
    wacc_scn_step=1.0,         # +/- discount points for Bear / Bull
)
# ===========================================================================


# ----------------------- EDGAR fundamentals -------------------------------
def _annual(facts, tag, unit="USD"):
    """Extract annual flow facts or point-in-time facts for one XBRL tag.

    Parameters
    ----------
    facts:
        Full SEC companyfacts dictionary.
    tag:
        US-GAAP concept name.
    unit:
        Requested unit, for example ``USD`` or ``USD/shares``.

    Returns
    -------
    dict
        Sorted mapping of reporting dates to values. Flow observations are
        accepted only when they span approximately one fiscal year. Facts with
        no start date are treated as point-in-time observations.
    """
    items = (facts.get("facts", {}).get("us-gaap", {})
             .get(tag, {}).get("units", {}).get(unit, []))
    out = {}
    for f in items:
        end = date.fromisoformat(f["end"])
        if "start" not in f:
            out[end] = f["val"]
            continue
        d = (end - date.fromisoformat(f["start"])).days
        if 350 <= d <= 380:
            out[end] = f["val"]
    return dict(sorted(out.items()))


def _latest(s):
    """Return the value at the latest date, or None for an empty series."""
    return s[max(s)] if s else None


def _first(facts, specs):
    """Return the first non-empty series from ordered ``(tag, unit)`` pairs.

    Candidate order matters: earlier tags have priority over later fallbacks.
    """
    for tag, unit in specs:
        s = _annual(facts, tag, unit)
        if s:
            return s
    return {}


def fundamentals(ticker):
    """Build the complete fundamental-data package used by the dashboard.

    The core values come from ``dcf_model.fundamentals()``. This function adds
    dividend per share, revenue CAGR, interest expense, and an estimated
    effective tax rate from SEC companyfacts.
    """
    # Reuse the core extraction performed by dcf_model.py.
    # Expected values include FCF history, EPS history, cash, debt, shares,
    # company name, and the latest fiscal date.
    base = dm.fundamentals(ticker)          # fcf{year:val}, eps{year:val}, cash, debt, shares
    f = load_facts(ticker)

    dps = _annual(f, "CommonStockDividendsPerShareDeclared", "USD/shares")
    rev = _first(f, [("RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
                     ("Revenues", "USD"), ("SalesRevenueNet", "USD")])
    interest = _first(f, [("InterestExpense", "USD"), ("InterestExpenseDebt", "USD"),
                          ("InterestAndDebtExpense", "USD")])
    tax = _annual(f, "IncomeTaxExpenseBenefit", "USD")
    pretax = _first(f, [
        ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", "USD"),
        ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments", "USD")])

    # Estimate revenue CAGR using no more than the latest seven annual points.
    # Fractional years keep non-calendar fiscal year ends usable.
    rev_cagr = None
    if len(rev) >= 3:
        ds = sorted(rev)[-7:]
        a, b = rev[ds[0]], rev[ds[-1]]
        yrs = (ds[-1] - ds[0]).days / 365.25
        if a > 0 and yrs >= 1:
            rev_cagr = ((b / a) ** (1 / yrs) - 1) * 100

    # Estimate the effective tax rate using the latest date shared by tax
    # expense and pretax income. One-off tax items can distort this value.
    eff_tax = None
    common = set(tax) & set(pretax)
    if common:
        d = max(common)
        if pretax[d]:
            eff_tax = tax[d] / pretax[d] * 100

    base.update(dps=_latest(dps) or 0.0, revenue_cagr=rev_cagr,
                interest_expense=_latest(interest), eff_tax=eff_tax)
    return base


def market_from_yfinance(ticker):
    """Fetch current price, analyst target, and beta from optional yfinance.

    Returns ``(None, None, None)`` when the package or data is unavailable.
    Market data may be delayed, stale, or incomplete, so CONFIG values are
    preferable when reproducibility matters.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return (info.get("currentPrice") or info.get("regularMarketPrice"),
                info.get("targetMeanPrice"), info.get("beta"))
    except Exception as e:
        print(f"  (yfinance unavailable: {e}); set price/target/beta in CONFIG")
        return None, None, None


# ------------------------------ WACC (CAPM) -------------------------------
def compute_wacc(cfg, fund, price, beta):
    """Estimate WACC from CAPM and an approximate after-tax debt cost.

    Returns None when beta, price, or share-count data are unavailable. The
    interest-expense/debt ratio is only a rough proxy for the current cost of
    debt and should not be treated as a precise borrowing rate.
    """
    if beta is None or not price or not fund.get("shares"):
        return None
    rf, erp = cfg["risk_free"], cfg["equity_risk_premium"]
    # CAPM estimate of shareholders' required return.
    cost_equity = rf + beta * erp
    tax = cfg["tax_rate"]
    if tax is None:
        tax = fund.get("eff_tax")
        tax = 21.0 if tax is None else max(0.0, min(35.0, tax))
    # Approximate market value of equity from current price and share count.
    mcap = price * fund["shares"]
    debt = fund.get("debt") or 0
    interest = fund.get("interest_expense") or 0
    if debt > 0 and interest:
        cost_debt_pre = interest / debt * 100
        cost_debt_at = cost_debt_pre * (1 - tax / 100)
        we, wd = mcap / (mcap + debt), debt / (mcap + debt)
        wacc = cost_equity * we + cost_debt_at * wd
    else:
        cost_debt_at = 0.0
        we, wd = 1.0, 0.0
        wacc = cost_equity
    return dict(wacc=wacc, cost_equity=cost_equity, cost_debt_at=cost_debt_at,
                tax=tax, beta=beta, equity_weight=we * 100, debt_weight=wd * 100)


# ------------------------------ FCF DCF -----------------------------------
def project_fading(fcf0, g_start, g_end, r, gt, years):
    """Project and discount FCF with growth fading linearly over time.

    Returns
    -------
    tuple
        ``(rows, terminal_value, pv_terminal, enterprise_value)`` where each
        projection row is ``(year_number, growth_pct, projected_fcf, pv_fcf)``.

    The Gordon-growth terminal value is valid only when the discount rate is
    greater than the terminal growth rate.
    """
    rows, pv_sum, cf = [], 0.0, fcf0
    for t in range(1, years + 1):
        # Interpolate growth between the year-one rate and the final explicit
        # forecast rate.
        g = g_start if years == 1 else g_start + (g_end - g_start) * (t - 1) / (years - 1)
        cf *= (1 + g / 100)
        pv = cf / (1 + r / 100) ** t
        pv_sum += pv
        rows.append((t, g, cf, pv))
    # Value all cash flows beyond the explicit forecast with Gordon growth.
    tv = cf * (1 + gt / 100) / ((r - gt) / 100) if r > gt else float("nan")
    pv_tv = tv / (1 + r / 100) ** years
    return rows, tv, pv_tv, pv_sum + pv_tv


def fcf_intrinsic(cfg, fund, g_start, r):
    """Calculate per-share intrinsic value from the fading-growth FCF DCF.

    Equity value is calculated as enterprise value plus cash minus debt, then
    divided by shares outstanding. Returns ``(None, None)`` when required FCF
    or share data are unavailable.
    """
    if not fund["fcf"] or not fund["shares"]:
        return None, None
    fcf0 = dm.base_fcf(fund["fcf"], cfg["base_fcf"])
    rows, tv, pv_tv, ev = project_fading(fcf0, g_start, cfg["growth_end"], r,
                                         cfg["terminal_growth"], cfg["projection_years"])
    equity = ev + fund["cash"] - fund["debt"]
    return equity / fund["shares"], dict(rows=rows, tv=tv, pv_tv=pv_tv, ev=ev,
                                         equity=equity, fcf0=fcf0,
                                         tv_pct=pv_tv / ev * 100 if ev else None)


def reverse_fcf(price, cfg, fund, r, lo=-20.0, hi=80.0):
    """Estimate the constant FCF growth rate implied by the market price.

    A bisection search finds the flat explicit-period growth assumption that
    makes the DCF value approximately equal to the current price.
    """
    if not price or not fund["fcf"] or not fund["shares"]:
        return None
    fcf0 = dm.base_fcf(fund["fcf"], cfg["base_fcf"])

    def iv(g):
        rows, _, _, ev = project_fading(fcf0, g, g, r, cfg["terminal_growth"],
                                        cfg["projection_years"])
        return (ev + fund["cash"] - fund["debt"]) / fund["shares"]
    if iv(lo) > price:
        return lo
    if iv(hi) < price:
        return hi
    # Sixty-four iterations are more than enough for practical price precision.
    for _ in range(64):
        mid = (lo + hi) / 2
        (lo, hi) = (mid, hi) if iv(mid) < price else (lo, mid)
    return (lo + hi) / 2


# --------------------------- cross-check models ---------------------------
def graham_value(eps, g, y):
    """Return a Benjamin Graham-style value estimate as a rough cross-check."""
    if eps is None or eps <= 0 or y <= 0:
        return None
    return eps * (8.5 + 2 * g) * 4.4 / y


def multiples_value(eps, g, fair_pe):
    """Estimate next-period value from EPS growth and an assumed fair P/E."""
    if eps is None or eps <= 0:
        return None
    return fair_pe * eps * (1 + g / 100)


def ddm_value(dps, g, r):
    """Estimate value with a Gordon-growth dividend discount model."""
    if not dps or dps <= 0:
        return None
    gd = min(g, r - 1.0) / 100
    r = r / 100
    return dps * (1 + gd) / (r - gd) if r > gd else None


def eps_two_stage(cfg, fund):
    """Run the two-stage EPS valuation and return model details or None.

    Historical EPS CAGR is constrained to a 5%-20% range. A 12% fallback is
    used when CAGR cannot be estimated.
    """
    if not fund["eps"] or max(fund["eps"].values()) <= 0:
        return None
    eps0 = fund["eps"][max(fund["eps"])]
    c, _ = dm.best_cagr(fund["eps"])
    g1 = 12.0 if c is None else max(5.0, min(20.0, c))
    gv, tv, fair = dm.gf_two_stage(eps0, g1, cfg["gf_growth_years"],
                                   cfg["gf_terminal_rate"], cfg["gf_terminal_years"],
                                   cfg["gf_discount_rate"])
    return dict(eps0=eps0, g1=g1, gv=gv, tv=tv, fair=fair, d=cfg["gf_discount_rate"])


def signal_for(intr, price, desired_mos):
    """Classify price as BUY, FAIR VALUE, or OVERVALUED.

    Returns ``(label, display_kind, desired_entry_price)``.
    """
    if not (intr and price):
        return "—", "fair", None
    acc = intr * (1 - desired_mos / 100)
    if price <= acc:
        return "BUY", "buy", acc
    if price <= intr:
        return "FAIR VALUE", "fair", acc
    return "OVERVALUED", "sell", acc


# ------------------------------ compute -----------------------------------
def compute(cfg, fund, price, target, beta):
    """Run all valuation models and assemble data for the HTML dashboard.

    This coordinator calculates WACC, base FCF value, EPS value, simplified
    cross-checks, scenarios, reverse DCF, valuation ranges, margin of safety,
    and optional analyst-target upside.
    """
    # Prefer CAPM-based WACC; fall back to the configured discount rate when
    # the required market inputs are unavailable.
    wacc = compute_wacc(cfg, fund, price, beta)
    r = wacc["wacc"] if wacc else cfg["discount_rate"]

    # Use the manually supplied starting growth rate when present. Otherwise,
    # derive it from historical revenue CAGR and constrain extreme values.
    g_start = cfg["growth_start"]
    if g_start is None:
        g_start = fund.get("revenue_cagr")
        g_start = 12.0 if g_start is None else max(cfg["growth_end"],
                                                   min(cfg["growth_start_cap"], g_start))

    # primary FCF DCF (base case)
    intrinsic, dcf = fcf_intrinsic(cfg, fund, g_start, r)
    signal, kind, acceptable = signal_for(intrinsic, price, cfg["desired_mos"])

    # EPS two-stage cross-check
    eps2 = eps_two_stage(cfg, fund)

    # cross-check models (single, capped growth)
    g_cross = min(g_start, cfg["cross_growth_cap"])
    graham = graham_value(fund["eps"][max(fund["eps"])] if fund["eps"] else None,
                          g_cross, cfg["aaa_bond_yield"])
    mult = multiples_value(fund["eps"][max(fund["eps"])] if fund["eps"] else None,
                           g_cross, cfg["fair_pe"])
    ddm = ddm_value(fund["dps"], g_cross, r)

    # scenarios: flex growth AND wacc
    gs, ws = cfg["growth_scn_step"], cfg["wacc_scn_step"]
    scenarios = []
    for label, gg, rr in [("Bear", g_start - gs, r + ws),
                          ("Base", g_start, r),
                          ("Bull", g_start + gs, r - ws)]:
        iv, _ = fcf_intrinsic(cfg, fund, max(cfg["growth_end"], gg), rr)
        sig, k, _ = signal_for(iv, price, cfg["desired_mos"])
        scenarios.append(dict(label=label, growth=gg, wacc=rr, intrinsic=iv,
                              signal=sig, kind=k))

    # Football-field ranges are presentation ranges, not statistical confidence
    # intervals. FCF uses scenario values; simpler models use ±10% bands.
    field = []
    pal = dict(fcf="#2e6f3e", eps="#9a7b1f", graham="#3b6ea5",
               multiples="#9a3b2f", ddm="#6b6459")
    fcf_lo = scenarios[0]["intrinsic"]
    fcf_hi = scenarios[2]["intrinsic"]
    if intrinsic:
        field.append(dict(name="FCF DCF", color=pal["fcf"],
                          low=min(x for x in [fcf_lo, fcf_hi, intrinsic] if x),
                          base=intrinsic,
                          high=max(x for x in [fcf_lo, fcf_hi, intrinsic] if x)))
    if eps2:
        field.append(dict(name="EPS 2-stage", color=pal["eps"],
                          low=eps2["fair"] * 0.9, base=eps2["fair"], high=eps2["fair"] * 1.1))
    for nm, v, key in [("Graham", graham, "graham"), ("Multiples", mult, "multiples"),
                       ("Dividend DM", ddm, "ddm")]:
        if v and v > 0:
            field.append(dict(name=nm, color=pal[key], low=v * 0.9, base=v, high=v * 1.1))

    implied = reverse_fcf(price, cfg, fund, r)

    res = dict(growth_start=g_start, discount_rate=r, wacc=wacc, intrinsic=intrinsic,
               dcf=dcf, eps2=eps2, graham=graham, multiples=mult, ddm=ddm,
               signal=signal, signal_kind=kind, acceptable=acceptable,
               scenarios=scenarios, field=field, implied_growth=implied,
               price=price, target=target, g_cross=g_cross)
    if intrinsic and price:
        res["mos"] = (intrinsic - price) / intrinsic * 100      # 1 - price/intrinsic
    if target and price:
        res["upside"] = (target - price) / price * 100
    return res


# ------------------------------ HTML --------------------------------------
def _m(x):
    """Format a dollar value, or return an em dash when unavailable."""
    return "—" if x is None else f"${x:,.2f}"


def _p(x):
    """Format a signed percentage, or return an em dash when unavailable."""
    return "—" if x is None else f"{x:+.1f}%"


def _pct(x):
    """Format an unsigned percentage, or return an em dash when unavailable."""
    return "—" if x is None else f"{x:.1f}%"


def svg_football(field, price, width=860, row_h=44):
    """Render valuation ranges and market price as an inline SVG chart.

    Each model is drawn as a shaded low-to-high range with a central estimate.
    The current share price is drawn as a dashed vertical reference line.
    """
    if not field:
        return "<p class='sr-sub'>No model values to plot.</p>"
    left, right = 120, 66
    plot_w = width - left - right
    height = row_h * len(field) + 50
    xs = [f["low"] for f in field] + [f["high"] for f in field] + ([price] if price else [])
    xmin, xmax = min(xs), max(xs)
    pad = (xmax - xmin) * 0.08 or 1
    xmin, xmax = max(0, xmin - pad), xmax + pad

    def sx(v):
        return left + (v - xmin) / (xmax - xmin) * plot_w

    p = []
    for i in range(5):
        v = xmin + (xmax - xmin) * i / 4
        x = sx(v)
        p.append(f'<line x1="{x:.0f}" y1="28" x2="{x:.0f}" y2="{height-20:.0f}" stroke="#eee6d6" stroke-width="1"/>')
        p.append(f'<text x="{x:.0f}" y="{height-6:.0f}" font-size="10" fill="#94a3b8" text-anchor="middle" font-family="IBM Plex Mono,monospace">${v:,.0f}</text>')
    for i, f in enumerate(field):
        cy = 38 + i * row_h
        x0, x1, xb = sx(f["low"]), sx(f["high"]), sx(f["base"])
        p.append(f'<text x="{left-12:.0f}" y="{cy+4:.0f}" font-size="12.5" fill="#1c1a17" text-anchor="end" font-weight="700">{f["name"]}</text>')
        p.append(f'<rect x="{x0:.1f}" y="{cy-8:.0f}" width="{max(x1-x0,3):.1f}" height="16" rx="8" fill="{f["color"]}" opacity="0.25"/>')
        p.append(f'<line x1="{xb:.1f}" y1="{cy-10:.0f}" x2="{xb:.1f}" y2="{cy+10:.0f}" stroke="{f["color"]}" stroke-width="3"/>')
        p.append(f'<text x="{x1+7:.1f}" y="{cy+4:.0f}" font-size="11" fill="{f["color"]}" font-weight="700" font-family="IBM Plex Mono,monospace">${f["base"]:,.0f}</text>')
    if price:
        px = sx(price)
        p.append(f'<line x1="{px:.1f}" y1="22" x2="{px:.1f}" y2="{height-20:.0f}" stroke="#9a3b2f" stroke-width="2" stroke-dasharray="5 3"/>')
        p.append(f'<text x="{px:.1f}" y="16" font-size="11" fill="#9a3b2f" text-anchor="middle" font-weight="700">Price ${price:,.0f}</text>')
    return f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px">{"".join(p)}</svg>'


def svg_decel(rows, terminal, start_year, width=860, height=210):
    """Render the explicit forecast growth path as inline SVG.

    The chart shows annual growth decelerating from the near-term assumption
    toward the normalized terminal growth rate.
    """
    if not rows:
        return ""
    n = len(rows)
    pl, pr, pt_, pb = 44, 24, 26, 36
    plot_w, plot_h = width - pl - pr, height - pt_ - pb
    gs = [g for _, g, _, _ in rows]
    gmax = max(gs + [terminal])
    gmin = min(gs + [terminal, 0])
    span = (gmax - gmin) or 1

    def X(i):
        return pl + (i / (n - 1) * plot_w if n > 1 else plot_w / 2)

    def Y(g):
        return pt_ + (gmax - g) / span * plot_h

    pts = [(X(i), Y(g)) for i, (t, g, cf, pv) in enumerate(rows)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s = []
    # terminal (normalized) reference line
    ty = Y(terminal)
    s.append(f'<line x1="{pl}" y1="{ty:.1f}" x2="{width-pr}" y2="{ty:.1f}" stroke="#9a7b1f" stroke-width="1" stroke-dasharray="4 3"/>')
    s.append(f'<text x="{width-pr:.0f}" y="{ty-5:.0f}" text-anchor="end" font-size="10.5" fill="#9a7b1f" font-family="IBM Plex Mono,monospace">normalized {terminal:.1f}%</text>')
    # the fading growth line
    s.append(f'<polyline points="{poly}" fill="none" stroke="#2e6f3e" stroke-width="2.5"/>')
    for i, (t, g, cf, pv) in enumerate(rows):
        x, y = pts[i]
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#2e6f3e"/>')
        s.append(f'<text x="{x:.1f}" y="{y-9:.0f}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#1c1a17" font-family="IBM Plex Mono,monospace">{g:.0f}%</text>')
        s.append(f'<text x="{x:.1f}" y="{height-12:.0f}" text-anchor="middle" font-size="10" fill="#6b6459" font-family="IBM Plex Mono,monospace">{start_year+t}</text>')
    # deceleration annotation, centred above the plot so it clears the first label
    s.append(f'<text x="{pl+plot_w*0.5:.0f}" y="{pt_-10:.0f}" text-anchor="middle" font-size="11" fill="#2e6f3e" font-weight="700">growth decelerating each year →</text>')
    return f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px">{"".join(s)}</svg>'


def render_html(cfg, fund, res):
    """Render the complete valuation report as a standalone HTML document.

    The returned HTML contains embedded CSS and inline SVG, so it can be opened
    locally without a separate stylesheet or JavaScript bundle.
    """
    price = res["price"]
    dcf = res["dcf"]
    eps2 = res["eps2"]

    # Build the six top-level summary cells shown at the start of the report.
    mos = res.get("mos")
    mos_kind = "buy" if (mos or -1) >= cfg["desired_mos"] else ("hold" if (mos or -1) >= 0 else "avoid")
    mos_badge = f"<span class='sr-badge {mos_kind}'>{_p(mos)}</span>" if mos is not None else "—"
    dash = f"""<div class="sr-dash">
      <div class="sr-cell"><div class="l">Stock price</div><div class="v sr-mono">{_m(price)}</div></div>
      <div class="sr-cell"><div class="l">Fair value (FCF DCF)</div><div class="v sr-mono">{_m(res['intrinsic'])}</div></div>
      <div class="sr-cell"><div class="l">Margin of safety</div><div class="v">{mos_badge}</div></div>
      <div class="sr-cell"><div class="l">EPS 2-stage</div><div class="v sr-mono">{_m(eps2['fair']) if eps2 else '—'}</div></div>
      <div class="sr-cell"><div class="l">Discount rate</div><div class="v sr-mono">{res['discount_rate']:.1f}%</div></div>
      <div class="sr-cell"><div class="l">Reverse-DCF implied growth</div><div class="v sr-mono">{_p(res['implied_growth'])}</div></div>
    </div>"""

    gauge = dm.svg_gauge(price, res["intrinsic"]) if (price and res["intrinsic"]) else ""

    # Build the detailed explicit FCF projection table.
    ys = sorted(fund["fcf"])
    start_year = ys[-1] if ys else date.today().year
    proj = "<thead><tr><th>Year</th><th>Growth</th><th>Future FCF</th><th>PV of FCF</th></tr></thead><tbody>"
    for t, g, cf, pv in dcf["rows"]:
        proj += (f"<tr><td>{start_year+t}</td><td class='sr-mono'>{g:.1f}%</td>"
                 f"<td class='sr-mono'>{dm._b(cf)}</td><td class='sr-mono'>{dm._b(pv)}</td></tr>")
    last_y = start_year + len(dcf["rows"])
    proj += (f"<tr><td><strong>Terminal value</strong><br><span style='font-weight:400;color:var(--muted);font-size:12px'>all years after {last_y}</span></td>"
             f"<td class='sr-mono'>{cfg['terminal_growth']:.1f}%</td>"
             f"<td class='sr-mono'>{dm._b(dcf['tv'])}</td><td class='sr-mono'>{dm._b(dcf['pv_tv'])}</td></tr></tbody>")

    # Reconcile enterprise value to equity value and value per share.
    bridge = "<tbody>" + "".join(f"<tr><td>{k}</td><td class='sr-mono'>{v}</td></tr>" for k, v in [
        ("Enterprise value (sum of PVs)", dm._b(dcf["ev"])),
        ("+ Cash &amp; equivalents", dm._b(fund["cash"])),
        ("− Total debt", dm._b(fund["debt"])),
        ("= Equity value", dm._b(dcf["equity"])),
        ("÷ Shares outstanding", f"{fund['shares']/1e9:,.2f}B" if fund["shares"] else "—"),
        ("= Intrinsic value / share", _m(res["intrinsic"])),
    ]) + "</tbody>"

    # Present the primary cash-flow and earnings views side by side.
    if eps2:
        cmp_tbl = ("<thead><tr><th>Model</th><th>Base metric</th><th>Fair value</th></tr></thead><tbody>"
                   f"<tr><td>FCF DCF (cash-flow)</td><td class='sr-mono'>FCF {dm._b(dcf['fcf0'])}</td><td class='sr-mono'>{_m(res['intrinsic'])}</td></tr>"
                   f"<tr><td>EPS two-stage (earnings)</td><td class='sr-mono'>EPS {_m(eps2['eps0'])}</td><td class='sr-mono'>{_m(eps2['fair'])}</td></tr>"
                   "</tbody>")
    else:
        cmp_tbl = "<tbody><tr><td>EPS data unavailable.</td></tr></tbody>"

    # Build Bear, Base, and Bull scenario rows.
    scen = "<thead><tr><th>Scenario</th><th>Growth</th><th>WACC</th><th>Intrinsic</th><th>Signal</th></tr></thead><tbody>"
    for s in res["scenarios"]:
        c = {"buy": "var(--buy)", "fair": "var(--hold)", "sell": "var(--avoid)"}.get(s["kind"], "#64748b")
        scen += (f"<tr><td><b>{s['label']}</b></td><td class='sr-mono'>{s['growth']:.0f}%</td>"
                 f"<td class='sr-mono'>{s['wacc']:.1f}%</td><td class='sr-mono'>{_m(s['intrinsic'])}</td>"
                 f"<td style='font-weight:700;color:{c}'>{s['signal']}</td></tr>")
    scen += "</tbody>"

    # Compare market price, base intrinsic value, desired entry, and MoS.
    sig_c = {"buy": "var(--buy)", "fair": "var(--hold)", "sell": "var(--avoid)"}.get(res["signal_kind"], "#64748b")
    pchk = "<tbody>" + "".join(f"<tr><td>{k}</td><td class='sr-mono'>{v}</td></tr>" for k, v in [
        ("Current price", _m(price)),
        ("Intrinsic value (base)", _m(res["intrinsic"])),
        (f"Desired entry (−{cfg['desired_mos']:.0f}% MoS)", _m(res["acceptable"])),
        ("Margin of safety", _p(mos)),
    ]) + "</tbody>"

    upside = res.get("upside")
    ws = (f"<div class='sr-note'>Wall Street target: <b>{_m(res['target'])}</b> "
          f"(<b style='color:{'var(--buy)' if (upside or 0)>=0 else 'var(--avoid)'}'>{_p(upside)}</b> upside)</div>"
          if res.get("target") else "")

    # Explain the major assumptions and expose valuation sanity checks.
    w = res["wacc"]
    if w:
        wacc_li = (f"<li>Discount rate = <b>WACC {w['wacc']:.1f}%</b>: cost of equity "
                   f"<b>{w['cost_equity']:.1f}%</b> (rf {cfg['risk_free']}% + β {w['beta']:.2f} × ERP {cfg['equity_risk_premium']}%), "
                   f"after-tax cost of debt <b>{w['cost_debt_at']:.1f}%</b>, E/D weights {w['equity_weight']:.0f}/{w['debt_weight']:.0f}.</li>")
    else:
        wacc_li = f"<li>Discount rate: <b>{res['discount_rate']:.1f}%</b> (flat — no beta for CAPM).</li>"
    tv_flag = " <b style='color:var(--avoid)'>(most of the value)</b>" if (dcf["tv_pct"] or 0) > 75 else ""
    assum = wacc_li + "".join(f"<li>{a}</li>" for a in [
        f"FCF growth fades from <b>{res['growth_start']:.1f}%</b> (yr 1) to <b>{cfg['growth_end']:.1f}%</b> (yr {cfg['projection_years']}), "
        f"then <b>{cfg['terminal_growth']:.1f}%</b> in perpetuity.",
        f"Terminal value is <b>{_pct(dcf['tv_pct'])}</b> of enterprise value{tv_flag}.",
        f"Reverse DCF: the price implies a flat <b>{_p(res['implied_growth'])}</b> FCF growth.",
        f"EPS two-stage uses growth <b>{eps2['g1']:.1f}%</b> for {cfg['gf_growth_years']}y at {cfg['gf_discount_rate']:.0f}%." if eps2 else "",
        f"Cross-checks (Graham/Multiples/DDM) capped growth at <b>{res['g_cross']:.0f}%</b>; fair P/E <b>{cfg['fair_pe']:.0f}×</b>.",
        f"Fundamentals to <b>{fund['fiscal_date']}</b> (SEC EDGAR).",
    ] if a)

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{fund['name']} — Valuation Decision</title>
<style>
.sr-report{{--paper:#faf7f0;--ink:#1c1a17;--muted:#6b6459;--rule:#d8d0c2;
  --buy:#2e6f3e;--hold:#9a7b1f;--avoid:#9a3b2f;
  background:var(--paper);color:var(--ink);
  font-family:"Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,Georgia,serif;
  line-height:1.5;max-width:940px;margin:0 auto;padding:40px 36px;border:1px solid var(--rule);}}
body{{background:#efe9dc;margin:0;padding:24px 12px;}}
.sr-report *{{box-sizing:border-box;}}
.sr-mono{{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums;}}
.sr-report h1{{font-size:34px;line-height:1.05;margin:0 0 2px;letter-spacing:-.01em;}}
.sr-report h2{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600;
  margin:32px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--rule);font-family:"IBM Plex Mono",ui-monospace,monospace;}}
.sr-kicker{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--muted);margin-bottom:14px;}}
.sr-sub{{color:var(--muted);font-size:15px;margin:4px 0 0;}}
.sr-dash{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--rule);border:1px solid var(--rule);margin:24px 0;}}
.sr-cell{{background:var(--paper);padding:16px 18px;}}
.sr-cell .l{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}}
.sr-cell .v{{font-size:22px;margin-top:6px;}}
.sr-badge{{display:inline-block;padding:3px 12px;border-radius:2px;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:18px;border:1.5px solid currentColor;}}
.sr-badge.buy{{color:var(--buy);}}.sr-badge.hold{{color:var(--hold);}}.sr-badge.avoid{{color:var(--avoid);}}
.sr-report table{{width:100%;border-collapse:collapse;margin:6px 0 4px;font-size:14px;}}
.sr-report th,.sr-report td{{padding:7px 10px;border-bottom:1px solid var(--rule);text-align:right;}}
.sr-report th:first-child,.sr-report td:first-child{{text-align:left;}}
.sr-report thead th{{color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;}}
.sr-note{{background:#f6f1e4;border-left:3px solid var(--hold);padding:10px 14px;margin:10px 0;font-size:14px;}}
.sr-signal{{margin-top:12px;border-radius:4px;padding:12px;text-align:center;color:#fff;font-size:20px;font-weight:800;letter-spacing:.5px;background:{sig_c};}}
.sr-gauge{{background:#f6f1e4;border:1px solid var(--rule);padding:14px;margin:10px 0;}}
.sr-grid2{{display:grid;grid-template-columns:1fr 1fr;gap:24px;}}
.sr-assum{{font-size:13.5px;color:var(--ink);}} .sr-assum ul{{margin:6px 0 0;padding-left:18px;line-height:1.7;}}
.sr-foot{{margin-top:34px;padding-top:14px;border-top:1px solid var(--rule);font-size:12px;color:var(--muted);}}
@media(max-width:720px){{.sr-dash{{grid-template-columns:1fr 1fr}}.sr-grid2{{grid-template-columns:1fr}}}}
</style></head><body><article class="sr-report">

  <div class="sr-kicker">Valuation Decision · {date.today().isoformat()} · for education only</div>
  <h1>{fund['name']}</h1>
  <p class="sr-sub sr-mono">{cfg['ticker']} · fundamentals to {fund['fiscal_date']} · SEC EDGAR + market price</p>

  {dash}

  <h2>Fair value gauge</h2>
  <div class="sr-gauge">{gauge if gauge else '<p class="sr-sub">No price / FCF to draw the gauge.</p>'}</div>

  <h2>Valuation range vs price</h2>
  {svg_football(res['field'], price)}
  <div class="sr-note">How to read this: each row is one valuation method. The shaded bar is that
    method's plausible value range, and the vertical tick (with the number beside it) is its central
    estimate. The dashed red line is the current share price. When the price sits to the <b>right</b> of a
    method's range the stock looks expensive on that method; to the <b>left</b>, it looks cheap. Methods that
    cluster on one side of the price line are agreeing.</div>

  <h2>Two views: cash flow vs earnings</h2>
  <table>{cmp_tbl}</table>
  <div class="sr-note">These disagree on purpose. The <b>FCF DCF</b> values discounted free cash flow (operating
    cash flow − capex); the <b>EPS two-stage</b> values earnings instead. For capex-heavy firms, earnings sit
    above free cash flow, so the earnings model reads higher. The FCF model is the more conservative, cash-based
    view; the EPS model shows the earnings-based view.</div>

  <div class="sr-grid2">
    <div><h2>Scenarios (Bear / Base / Bull)</h2><table>{scen}</table>
      <div class="sr-signal">{res['signal']}</div></div>
    <div><h2>Price check</h2><table>{pchk}</table>{ws}</div>
  </div>

  <h2>Free cash flow — history ($B)</h2>
  <div class="sr-gauge">{dm.svg_fcf(fund['fcf'])}</div>
  <h2>Free cash flow — growth YoY</h2>
  <div class="sr-gauge">{dm.svg_growth(fund['fcf'])}</div>

  <h2>Growth assumption — deceleration &amp; normalization</h2>
  <div class="sr-gauge">{svg_decel(dcf['rows'], cfg['terminal_growth'], start_year)}</div>
  <div class="sr-note">The forecast does not use one flat growth rate. Near-term growth starts high and
    <b>decelerates</b> each year as the business scales and competition intensifies, then <b>normalizes</b> to a
    mature, GDP-like rate ({cfg['terminal_growth']:.1f}%) carried into perpetuity. Modelling the slowdown this way
    is what keeps a high-growth company's DCF realistic instead of over- or under-stating its value.</div>

  <div class="sr-grid2">
    <div><h2>FCF projection (fading growth)</h2><table>{proj}</table></div>
    <div><h2>Enterprise → equity bridge</h2><table>{bridge}</table></div>
  </div>

  <h2>Assumptions &amp; sanity checks</h2>
  <div class="sr-assum"><ul>{assum}</ul></div>

  <div class="sr-foot">
    Sources: SEC EDGAR XBRL (us-gaap) for FCF, EPS, dividends, revenue, shares, cash, debt, interest, tax;
    market data for price, analyst target and beta.<br><br>
    <strong>Why the two models differ.</strong> The base metric drives it: a cash-flow DCF on free cash flow vs an
    earnings model on EPS. The fading-growth FCF DCF here (high near-term growth decelerating to a mature rate, à la
    professional models) lands far closer to published valuations than a single flat growth rate would.<br><br>
    <strong>Disclaimer.</strong> Educational and informational only. Not financial, investment, or trading advice.
    Intrinsic value swings hard with the assumptions — which is why this page shows scenarios, a reverse DCF and the
    terminal-value share. Verify inputs against the filings; market data may be stale. Do your own research.
  </div>

</article></body></html>"""


def main():
    """Generate, save, summarize, and attempt to open the valuation report."""
    # Read the selected ticker and all model assumptions.
    cfg = CONFIG
    print(f"Fetching fundamentals for {cfg['ticker']} from EDGAR ...")
    # Fetch accounting fundamentals before optional live market data.
    fund = fundamentals(cfg["ticker"])
    if not fund["fcf"] or not fund["shares"]:
        print("  Missing FCF or share data — check the ticker / tags.")
        return

    price, target, beta = cfg["current_price"], cfg["analyst_target"], cfg["beta"]
    # Preserve manually configured values and fill only missing fields from
    # yfinance.
    if price is None or target is None or beta is None:
        ap, at, ab = market_from_yfinance(cfg["ticker"])
        price = price if price is not None else ap
        target = target if target is not None else at
        beta = beta if beta is not None else ab
    if beta is None:
        beta = cfg["beta_fallback"]

    res = compute(cfg, fund, price, target, beta)
    html = render_html(cfg, fund, res)
    path = os.path.join(OUT_DIR, f"valuation_{cfg['ticker']}.html")
    # Save one self-contained HTML file inside edgar_output/.
    with open(path, "w") as f:
        f.write(html)
    print(f"Wrote {path}")
    print(f"  FCF intrinsic={_m(res['intrinsic'])}  EPS 2-stage="
          f"{_m(res['eps2']['fair']) if res['eps2'] else '—'}  price={_m(price)}  "
          f"discount={res['discount_rate']:.1f}%  signal={res['signal']}")
    try:
        webbrowser.open("file://" + os.path.abspath(path))
    except Exception:
        pass


if __name__ == "__main__":
    main()
