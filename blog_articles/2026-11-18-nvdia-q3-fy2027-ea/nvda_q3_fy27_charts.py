"""
NVIDIA Q3 FY2027: What Changed - blog charts for codezero2hero.com
====================================================================

Builds the 7 static charts used in the article, with Plotly.

Usage:
    pip install plotly kaleido
    python nvda_q3_fy27_charts.py

Output:
    ./charts/01_data_center_mix.webp ... ./charts/07_cash_flow.webp
    (set IMG_FORMAT = "png" below if you want PNG instead)

Data:
    All figures are hard-coded from NVIDIA's Q3 FY2027 earnings release,
    CFO commentary and earnings call (17 Nov 2026). Values are USD billions
    unless the label says otherwise. Reverse-DCF results come from a separate
    calculation (see the article's methodology section) and are pasted in.
    https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-third-quarter-fiscal-2027
"""

import os

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Output settings
# ---------------------------------------------------------------------------
# Save charts in a "charts" folder next to this script, wherever it is run from.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
os.makedirs(OUT, exist_ok=True)

# Kaleido can write png, webp, jpeg, svg or pdf. The blog serves .webp.
IMG_FORMAT = "webp"

# Image size in pixels (blog cap is 1200 x 600).
W, H = 1200, 600

# ---------------------------------------------------------------------------
# Colour palette and fixed text
# ---------------------------------------------------------------------------
BG = "#0f172a"       # outer page background (dark slate)
PANEL = "#111c33"    # plot area, a shade lighter so the chart area reads as a panel
GRID = "#24324d"     # gridlines, low contrast
TEXT = "#e2e8f0"     # main text (titles, value labels)
MUTED = "#94a3b8"    # secondary text (subtitle, axis ticks, source line)
ACCENT = "#76b900"   # primary accent: NVIDIA-like green
ACCENT2 = "#f59e0b"  # secondary accent: amber, for comparisons and warnings
NEUTRAL = "#475569"  # grey, for "context" bars that should not draw the eye

SOURCE = "Source: NVIDIA Q3 FY2027 earnings release, CFO commentary, earnings call"
WATERMARK = "codezero2hero.com"

# Horizontal legend placed above the plot area; reused by charts that need one.
LEGEND_TOP = dict(orientation="h", x=0.03, y=1.0, yanchor="bottom",
                  bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def esc(s):
    """Escape dollar signs in titles and annotations.

    Plotly/kaleido treats text between two "$" characters as LaTeX, so
    "+$11.4B vs +$7.2B" would render as garbled maths. The HTML entity
    &#36; displays as a normal "$" without triggering LaTeX.
    """
    return s.replace("$", "&#36;") if s else s


def base_layout(fig, title, subtitle, takeaway=None):
    """Apply the shared house style to a figure.

    title     bold headline that states the story of the chart
    subtitle  grey line under the title: what is measured, units, period
    takeaway  optional one-sentence conclusion printed under the plot
    """
    title, subtitle, takeaway = esc(title), esc(subtitle), esc(takeaway)

    fig.update_layout(
        width=W, height=H,
        paper_bgcolor=BG, plot_bgcolor=PANEL,
        font=dict(family="Inter, Segoe UI, Arial", color=TEXT, size=14),
        # Title and subtitle share one text block; the subtitle is styled inline.
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:15px;color:{MUTED}'>{subtitle}</span>",
            x=0.03, y=0.95, xanchor="left", font=dict(size=22),
        ),
        # Top margin leaves room for title + legend; bottom margin for takeaway + source.
        margin=dict(l=60, r=40, t=110, b=95),
        showlegend=False,  # charts that need a legend switch it back on
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=MUTED)

    # Positions below use "paper" coordinates: 0 = left/bottom edge of the
    # plot area, 1 = right/top edge. Negative y places text under the plot.

    # Source line, bottom-left.
    fig.add_annotation(text=SOURCE, xref="paper", yref="paper", x=0, y=-0.17,
                       showarrow=False, font=dict(size=11, color=MUTED), xanchor="left")
    # Site credit, bottom-right, on the same baseline as the source line.
    fig.add_annotation(text=f"<b>{WATERMARK}</b>", xref="paper", yref="paper", x=1, y=-0.17,
                       showarrow=False, font=dict(size=13, color=ACCENT), xanchor="right")
    # Takeaway sentence, just above the source line.
    if takeaway:
        fig.add_annotation(text=takeaway, xref="paper", yref="paper", x=0, y=-0.11,
                           showarrow=False, font=dict(size=13, color=TEXT), xanchor="left")


def save(fig, name):
    """Write the figure to ./charts/<name>.<IMG_FORMAT> at exact pixel size."""
    path = os.path.join(OUT, f"{name}.{IMG_FORMAT}")
    fig.write_image(path, format=IMG_FORMAT, scale=1)  # scale=1 keeps 1200 x 600
    print("wrote", path)


# ===========================================================================
# 1. Data Center revenue mix: hyperscale vs ACIE (stacked bars)
# ===========================================================================
q = ["Q3 FY26", "Q2 FY27", "Q3 FY27"]
hyper = [35.1, 48.7, 60.1]  # Hyperscale revenue, $B
acie = [16.1, 40.3, 47.5]   # AI Clouds, Industrial & Enterprise revenue, $B

fig = go.Figure()
# Bottom segment: hyperscale (green). Labels sit inside the bar in dark text.
fig.add_bar(name="Hyperscale", x=q, y=hyper, marker_color=ACCENT,
            text=[f"${v:.1f}B" for v in hyper], textposition="inside",
            textfont=dict(color=BG, size=15))
# Top segment: ACIE (amber).
fig.add_bar(name="AI Clouds, Industrial & Enterprise", x=q, y=acie, marker_color=ACCENT2,
            text=[f"${v:.1f}B" for v in acie], textposition="inside",
            textfont=dict(color=BG, size=15))
# Total Data Center revenue printed above each stack.
for xi, tot in zip(q, [h + a for h, a in zip(hyper, acie)]):
    fig.add_annotation(x=xi, y=tot, text=f"<b>${tot:.1f}B</b>", showarrow=False,
                       yshift=14, font=dict(size=15, color=TEXT))

base_layout(fig, "Data Center doubled in a year. ACIE almost tripled.",
            "Data Center revenue by customer type, USD billions",
            "Hyperscalers still added more dollars this quarter (+$11.4B vs +$7.2B for ACIE).")
fig.update_layout(barmode="stack", showlegend=True, legend=LEGEND_TOP)
fig.update_yaxes(title_text="", tickprefix="$", ticksuffix="B")
save(fig, "01_data_center_mix")


# ===========================================================================
# 2. Q4 guide normalized for the extra week and for China (horizontal bars)
# ===========================================================================
q3 = 115.844             # Q3 FY27 revenue, unrounded, $B
q3_xchina = q3 - 2.4     # Q3 minus $2.4B of China Hopper sales (Q4 guide assumes none)
q4_raw = 130.0           # Q4 guide midpoint; Q4 FY27 is a 14-week quarter
q4_norm = 130.0 * 13 / 14  # pro-rate to 13 weeks for a like-for-like comparison

# Plotly draws horizontal bars bottom-up, so the first item ends up at the bottom.
labels = ["Q4 guide, normalized to 13 weeks", "Q4 guide, as reported (14 weeks)",
          "Q3 actual, excluding $2.4B China Hopper", "Q3 actual"]
vals = [q4_norm, q4_raw, q3_xchina, q3]
colors = [ACCENT, NEUTRAL, ACCENT2, ACCENT2]  # green = the number that matters
# Value labels; growth rates are computed here so they always match the inputs.
txt = [f"${q4_norm:.1f}B  (+{(q4_norm/q3-1)*100:.0f}% vs Q3, +{(q4_norm/q3_xchina-1)*100:.0f}% ex-China)",
       f"${q4_raw:.1f}B  (+{(q4_raw/q3-1)*100:.0f}% headline)",
       f"${q3_xchina:.1f}B", f"${q3:.1f}B"]

fig = go.Figure(go.Bar(y=labels, x=vals, orientation="h", marker_color=colors,
                       text=txt, textposition="outside", textfont=dict(size=14, color=TEXT),
                       cliponaxis=False))  # let labels extend past the plot edge
base_layout(fig, "Headline Q4 guide: +12%. Per week: closer to +4% to +6%.",
            "Quarterly revenue, USD billions. Q4 FY27 has 14 weeks; guidance assumes no China Data Center compute.",
            "Q3 grew 20% sequentially. On a like-for-like basis the guide implies a sharp slowdown.")
fig.update_xaxes(range=[0, 175], tickprefix="$", ticksuffix="B")  # headroom for long labels
fig.update_layout(margin=dict(l=300))  # wide left margin for the category names
save(fig, "02_q4_guide_normalized")


# ===========================================================================
# 3. Gross-margin path: reported vs guided (line chart)
# ===========================================================================
periods = ["Q3 FY26", "Q2 FY27", "Q3 FY27", "Q4 FY27 guide", "FY28 outlook"]
gm = [73.4, 75.0, 74.8, 71.5, 72.5]  # GAAP gross margin %; last two are guide midpoints

fig = go.Figure()
# Solid green line: reported quarters (first three points).
fig.add_scatter(x=periods[:3], y=gm[:3], mode="lines+markers+text",
                line=dict(color=ACCENT, width=4), marker=dict(size=12),
                text=[f"{v:.1f}%" for v in gm[:3]], textposition="top center",
                textfont=dict(size=15, color=TEXT))
# Dotted amber line: from the last reported quarter into guidance.
# It starts at Q3 FY27 so the two lines join; that point gets an empty label
# because the solid line already labels it.
fig.add_scatter(x=periods[2:], y=gm[2:], mode="lines+markers+text",
                line=dict(color=ACCENT2, width=4, dash="dot"), marker=dict(size=12),
                text=["", "71.5%<br><span style='font-size:12px'>(71-72%)</span>",
                      "72.5%<br><span style='font-size:12px'>(72-73%)</span>"],
                textposition="bottom center", textfont=dict(size=15, color=TEXT))
base_layout(fig, "Gross margin: management says Q4 is the bottom",
            "GAAP gross margin. Solid = reported, dotted = guidance midpoints.",
            "3.3 pts at $130B of revenue is about $4.3B of quarterly gross profit.")
fig.update_yaxes(range=[69, 77], ticksuffix="%")  # zoomed axis; changes are a few points
save(fig, "03_gross_margin_path")


# ===========================================================================
# 4. Forward commitments and contingent exposures vs liquidity (sorted bars)
# ===========================================================================
# (label, value in $B, colour). Amber = obligation/exposure, green = liquidity.
items = [("Supply & capacity commitments", 390, ACCENT2),
         ("Maximum gross guarantees", 118, ACCENT2),
         ("Cloud agreements & leases not commenced", 102, ACCENT2),
         ("Cash + marketable debt securities", 53.5, ACCENT),
         ("Conditional neocloud agreements", 32, ACCENT2),
         ("Future equity-investment commitments", 20, ACCENT2)]
# Sort ascending: horizontal bars are drawn bottom-up, so the largest ends on top.
items.sort(key=lambda t: t[1])

fig = go.Figure(go.Bar(y=[i[0] for i in items], x=[i[1] for i in items], orientation="h",
                       marker_color=[i[2] for i in items],
                       # "$390.0B" -> "$390B"; keeps the decimal only where it matters
                       text=[f"${i[1]:,.1f}B".replace(".0B", "B") for i in items],
                       textposition="outside", textfont=dict(size=14, color=TEXT),
                       cliponaxis=False))
base_layout(fig, "What NVIDIA has committed vs what it holds",
            "Forward commitments and contingent exposures (amber) vs liquidity (green), USD billions, end of Q3 FY27",
            "Different terms and timing: not additive, not current liabilities. Scale still matters.")
fig.update_xaxes(range=[0, 460], tickprefix="$", ticksuffix="B")
fig.update_layout(margin=dict(l=320))
save(fig, "04_commitments_vs_liquidity")


# ===========================================================================
# 5. Supply-commitment schedule by fiscal year (vertical bars)
# ===========================================================================
sched = [("Remainder of FY2027", 69), ("FY2028", 203), ("FY2029", 92), ("FY2030 onward", 26)]

fig = go.Figure(go.Bar(x=[s[0] for s in sched], y=[s[1] for s in sched],
                       # amber = due within ~15 months ($272B), grey = later years
                       marker_color=[ACCENT2, ACCENT2, NEUTRAL, NEUTRAL],
                       text=[f"${s[1]}B" for s in sched], textposition="outside",
                       textfont=dict(size=16, color=TEXT), cliponaxis=False))
base_layout(fig, "$272B of the $390B lands in the next 15 months",
            "Supply and capacity commitments by fiscal year, USD billions (up from $279B in Q2)",
            "The increase is mostly multi-year memory procurement.")
fig.update_yaxes(range=[0, 240], tickprefix="$", ticksuffix="B")
save(fig, "05_supply_commitment_schedule")


# ===========================================================================
# 6. Reverse DCF: implied 5-year revenue CAGR by FCF margin (grouped bars)
# ===========================================================================
# Model: EV ~$3.73T, 5-year explicit forecast, 9% discount rate, 3.5% terminal
# growth, constant FCF margin; CAGR solved so the DCF equals EV.
margins = ["35%", "40%", "45%", "50%"]
q3_cagr = [8.2, 5.0, 2.3, 0.0]     # start: Q3 revenue annualized ($463.4B)
norm_cagr = [7.2, 4.1, 1.4, -0.9]  # start: Q4 guide, 13-week normalized, annualized ($482.9B)

fig = go.Figure()
fig.add_bar(name="Start: Q3 actual run-rate ($463B)", y=margins, x=q3_cagr, orientation="h",
            marker_color=ACCENT2, text=[f"{v:.1f}%" for v in q3_cagr], textposition="outside",
            textfont=dict(color=TEXT, size=14), cliponaxis=False)
fig.add_bar(name="Start: Q4 guide, 13-week normalized ($483B)", y=margins, x=norm_cagr,
            orientation="h", marker_color=ACCENT, text=[f"{v:.1f}%" for v in norm_cagr],
            textposition="outside", textfont=dict(color=TEXT, size=14), cliponaxis=False)
base_layout(fig, "At $155, the price needs little growth if margins hold",
            "Implied 5-year revenue CAGR by sustainable FCF margin. EV ~$3.73T, 9% discount rate, 3.5% terminal growth.",
            "Terminal value is 75-79% of EV in every case. The last reported FCF margin was 37.8%.")
fig.update_layout(barmode="group", showlegend=True, bargap=0.25, legend=LEGEND_TOP)
# Range includes negatives; the zero line separates growth from decline.
fig.update_xaxes(range=[-2.5, 10], ticksuffix="%", zeroline=True, zerolinecolor=MUTED)
# Reverse the y-axis so 35% sits on top and margins read top-to-bottom.
fig.update_yaxes(title_text="FCF margin", autorange="reversed")
save(fig, "06_reverse_dcf")


# ===========================================================================
# 7. Cash conversion: operating cash flow and FCF, Q2 vs Q3 (grouped bars)
# ===========================================================================
metrics = ["Operating cash flow", "Free cash flow"]

fig = go.Figure()
# Prior quarter in grey (context), current quarter in green (focus).
fig.add_bar(name="Q2 FY27", x=metrics, y=[24.1, 21.3], marker_color=NEUTRAL,
            text=["$24.1B", "$21.3B (22.2%)"], textposition="outside",
            textfont=dict(color=TEXT, size=14), cliponaxis=False)
fig.add_bar(name="Q3 FY27", x=metrics, y=[48.3, 43.8], marker_color=ACCENT,
            text=["$48.3B", "$43.8B (37.8%)"], textposition="outside",
            textfont=dict(color=TEXT, size=14), cliponaxis=False)
base_layout(fig, "Cash flow doubled, helped by tax timing",
            "USD billions; FCF margin in brackets. Receivables $81.0B, DSO 64 days (60 in Q2).",
            "Strong recovery, but one quarter is not proof of a sustainable 50% FCF margin.")
fig.update_layout(barmode="group", showlegend=True, legend=LEGEND_TOP)
fig.update_yaxes(range=[0, 58], tickprefix="$", ticksuffix="B")
save(fig, "07_cash_flow")
