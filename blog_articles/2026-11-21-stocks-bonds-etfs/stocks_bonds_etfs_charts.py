"""
Builds the four charts used in the article and prints the long-run averages.

    01_range_of_outcomes          worst year, best year and compound annual return
                                  for T-bills, 10y Treasuries, Baa corporates, S&P 500
    02_holding_period_loss_odds   share of rolling 1-20 year windows that ended
                                  with less money than they started with
    03_bad_stock_years_vs_bonds   every year the S&P 500 fell 10%+ next to
                                  10y Treasury returns in the same year
    04_vehicle_decision_map       the horizon-to-vehicle rule of thumb (no data)

Each chart is saved as a 1200x600 PNG and WebP in ./charts, next to this script.
The images sit on a dark navy gradient..

Data
----
Aswath Damodaran, "Historical Returns on Stocks, Bonds and Bills: 1928-2025"
(NYU Stern, updated 5 Jan 2026):
https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html

All figures are NOMINAL annual total returns for the US market, in US dollars.
They are not inflation-adjusted and not converted to EUR or RON.

Usage
-----
    pip install plotly kaleido pillow
    python stocks_bonds_etfs_charts.py

Have fun!
"""

import os

import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Output location and canvas
# ---------------------------------------------------------------------------
# Paths are resolved relative to this file, not the shell's working directory,
# so the charts always land in ./charts next to the script.
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "charts")
os.makedirs(OUT, exist_ok=True)

W, H = 1200, 600  # blog maximum image size

# ---------------------------------------------------------------------------
# Colours and typography
# ---------------------------------------------------------------------------
# Stocks are always amber and bonds always blue, in every chart, so a reader
# never has to re-learn the colour code. The amber/blue pair was checked for
# colour-blind separation and contrast against the dark background.
STOCK = "#C98420"   # amber: S&P 500
BOND = "#3D97D6"    # blue: 10-year Treasuries
BILL = "#6B7A90"    # muted gray: T-bills / cash, used only as a quiet reference
INK = "#E8ECF2"     # primary text (titles, key labels)
INK2 = "#A9B4C4"    # secondary text (subtitles, value labels)
MUTED = "#6F7C90"   # tertiary text (axis ticks, source line)
GRID = "rgba(255,255,255,0.07)"  # barely-visible gridlines
FONT = "Inter, Helvetica Neue, Arial, sans-serif"
SOURCE = "Source: Damodaran Online, NYU Stern (pages.stern.nyu.edu/~adamodar), 1928-2025, nominal US returns"

# ---------------------------------------------------------------------------
# Dataset: one row per year, values in percent
# ---------------------------------------------------------------------------
# Columns: year, S&P 500 incl. dividends, 3-month T-bill, 10y T-bond, Baa corporate bond
#
# Transcribed from Damodaran's table and checked by compounding $100 from 1928:
# S&P 500, T-bills and Baa bonds match his published end values within 0.04%.
# The 10y T-bond series ends 0.5% below his published value because his own
# 2025 cumulative figure implies a slightly higher 2025 return than the 7.80%
# shown in the same table. The annual figures are used as published.
RAW = """
1928 43.81 3.08 0.84 3.22
1929 -8.30 3.16 4.20 3.02
1930 -25.12 4.55 4.54 0.54
1931 -43.84 2.31 -2.56 -15.68
1932 -8.64 1.07 8.79 23.59
1933 49.98 0.96 1.86 12.97
1934 -1.19 0.28 7.96 18.82
1935 46.74 0.17 4.47 13.31
1936 31.94 0.17 5.02 11.38
1937 -35.34 0.28 1.38 -4.42
1938 29.28 0.07 4.21 9.24
1939 -1.10 0.05 4.41 7.98
1940 -10.67 0.04 5.40 8.65
1941 -12.77 0.13 -2.02 5.01
1942 19.17 0.34 2.29 5.18
1943 25.06 0.38 2.49 8.04
1944 19.03 0.38 2.58 6.57
1945 35.82 0.38 3.80 6.80
1946 -8.43 0.38 3.13 2.51
1947 5.20 0.60 0.92 0.26
1948 5.70 1.05 1.95 3.44
1949 18.30 1.12 4.66 5.38
1950 30.81 1.20 0.43 4.24
1951 23.68 1.52 -0.30 -0.19
1952 18.15 1.72 2.27 4.44
1953 -1.21 1.89 4.14 1.62
1954 52.56 0.94 3.29 6.16
1955 32.60 1.72 -1.34 2.04
1956 7.44 2.62 -2.26 -2.35
1957 -10.46 3.22 6.80 -0.72
1958 43.72 1.77 -2.10 6.43
1959 12.06 3.39 -2.65 1.57
1960 0.34 2.87 11.64 6.66
1961 26.64 2.35 2.06 5.10
1962 -8.81 2.77 5.69 6.50
1963 22.61 3.16 1.68 5.46
1964 16.42 3.55 3.73 5.16
1965 12.40 3.95 0.72 3.19
1966 -9.97 4.86 2.91 -3.45
1967 23.80 4.29 -1.58 0.90
1968 10.81 5.34 3.27 4.85
1969 -8.24 6.67 -5.01 -2.03
1970 3.56 6.39 16.75 5.65
1971 14.22 4.33 9.79 14.00
1972 18.76 4.06 2.82 11.41
1973 -14.31 7.04 3.66 4.32
1974 -25.90 7.85 1.99 -4.38
1975 37.00 5.79 3.61 11.05
1976 23.83 4.98 15.98 19.75
1977 -6.98 5.26 1.29 9.95
1978 6.51 7.18 -0.78 3.14
1979 18.52 10.05 0.67 -2.01
1980 31.74 11.39 -2.99 -3.32
1981 -4.70 14.04 8.20 8.46
1982 20.42 11.09 32.81 29.05
1983 22.34 8.95 3.20 16.19
1984 6.15 9.92 13.73 15.62
1985 31.24 7.72 25.71 23.86
1986 18.49 6.15 24.28 22.15
1987 5.81 5.96 -4.96 1.12
1988 16.54 6.89 8.22 15.68
1989 31.48 8.39 17.69 16.31
1990 -3.06 7.75 6.24 5.65
1991 30.23 5.54 15.00 16.40
1992 7.49 3.51 9.36 13.68
1993 9.97 3.07 14.21 16.44
1994 1.33 4.37 -8.04 -1.23
1995 37.20 5.66 23.48 20.09
1996 22.68 5.15 1.43 5.28
1997 33.10 5.20 9.94 11.30
1998 28.34 4.91 14.92 8.10
1999 20.89 4.78 -8.25 0.97
2000 -9.03 6.00 16.66 9.38
2001 -11.85 3.48 5.57 8.60
2002 -21.97 1.64 15.12 12.06
2003 28.36 1.03 0.38 12.38
2004 10.74 1.40 4.49 10.33
2005 4.83 3.22 2.87 5.13
2006 15.61 4.85 1.96 5.27
2007 5.48 4.48 10.21 4.90
2008 -36.55 1.40 20.10 -3.44
2009 25.94 0.15 -11.12 19.96
2010 14.82 0.14 8.46 9.40
2011 2.10 0.05 16.04 12.26
2012 15.89 0.09 2.97 9.40
2013 32.15 0.06 -9.10 -1.13
2014 13.52 0.03 10.75 10.75
2015 1.38 0.05 1.28 -1.50
2016 11.77 0.32 0.69 11.52
2017 21.61 0.95 2.80 9.15
2018 -4.23 1.97 -0.02 -3.18
2019 31.21 2.11 9.64 15.25
2020 18.02 0.36 11.33 10.60
2021 28.47 0.04 -4.42 1.02
2022 -18.04 2.09 -17.83 -15.23
2023 26.06 5.28 3.88 8.74
2024 24.88 5.18 -1.64 1.74
2025 17.78 4.21 7.80 6.96
"""

# Parse RAW into tuples: (year, stocks, bills, bonds, baa), returns as decimals (0.1781 = 17.81%).
ROWS = []
for line in RAW.strip().splitlines():
    y, *v = line.split()
    ROWS.append((int(y), *[float(x) / 100 for x in v]))

# Tuple index of each asset inside a row, so code can say ROWS[i][COL["stocks"]].
COL = {"stocks": 1, "bills": 2, "bonds": 3, "baa": 4}


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
def geo(col):
    """Compound (geometric) annual return over the full 1928-2025 period.

    Grows 1 unit through every year's return, then takes the 98th root.
    This is the "about 10% a year" figure, not the simple average of yearly
    returns, which would overstate what an investor actually earned.
    """
    v = 1.0
    for r in ROWS:
        v *= 1 + r[col]
    return v ** (1 / len(ROWS)) - 1


def rolling_loss_share(col, n):
    """Share of all n-year windows that ended with less money than they started with.

    Windows start every January and overlap: for n=10 they are 1928-1937,
    1929-1938, ..., 2016-2025, which gives 98 - n + 1 windows in total.
    A window counts as a loss when its compounded value ends below 1.0.

    Returns (share, losing_windows, total_windows).

    Note: for 10y Treasuries this measures repeated exposure to the 10-year
    bond index, not one bond bought and held to maturity.
    """
    hits = total = 0
    for s in range(len(ROWS) - n + 1):
        v = 1.0
        for r in ROWS[s:s + n]:
            v *= 1 + r[col]
        total += 1
        hits += v < 1
    return hits / total, hits, total


# ---------------------------------------------------------------------------
# Shared styling: background, layout template, export
# ---------------------------------------------------------------------------
def background():
    """Build the dark backdrop that every chart is composited onto.

    A diagonal navy gradient with a soft amber glow in the top-right corner,
    plus a thin amber rule along the top edge. Plotly renders the chart with a
    transparent background; save() lays it over this image.
    """
    bg = Image.new("RGB", (W, H))
    top, bot = (12, 20, 36), (22, 34, 56)  # darkest (top-left) and lightest (bottom-right) navy
    px = bg.load()
    for y in range(H):
        for x in range(W):
            # Blend weight: mostly vertical (65%), partly horizontal (35%).
            t = min(1.0, (0.65 * y / H + 0.35 * x / W))
            px[x, y] = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))

    # Soft glow: a blurred ellipse used as a mask to blend a little amber in.
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.55, -H * 0.6, W * 1.35, H * 0.7), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    amber = Image.new("RGB", (W, H), (201, 132, 32))
    bg = Image.composite(amber, bg, glow.point(lambda p: int(p * 0.35)))  # keep the glow subtle

    d = ImageDraw.Draw(bg)
    d.rectangle((0, 0, W, 4), fill=(201, 132, 32))  # thin accent rule on top
    return bg


def base_layout(title, subtitle):
    """Layout shared by all charts: transparent canvas, title block, source line and credit.

    The title is bold, with the subtitle on a second line in smaller,
    lighter text. The source line (bottom-left) and the codezero2hero.com
    credit (bottom-right) are placed below the plot area in paper coordinates.
    Individual charts append their own annotations to this list.
    """
    return dict(
        width=W, height=H,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",  # transparent: background() shows through
        font=dict(family=FONT, color=INK2, size=14),
        margin=dict(l=70, r=40, t=118, b=78),  # top margin leaves room for the two-line title
        title=dict(
            text=f"<b>{title}</b><br><span style='font-size:15px;color:{INK2}'>{subtitle}</span>",
            x=0.045, xanchor="left", y=0.94, yanchor="top",
            font=dict(family=FONT, size=26, color=INK),
        ),
        annotations=[
            # index 0: data source, bottom-left
            dict(text=SOURCE, x=0, y=-0.155, xref="paper", yref="paper", showarrow=False,
                 xanchor="left", font=dict(size=11, color=MUTED)),
            # index 1: site credit, bottom-right
            dict(text="<b>codezero2hero.com</b>", x=1, y=-0.155, xref="paper", yref="paper",
                 showarrow=False, xanchor="right", font=dict(size=12, color=INK2)),
        ],
        showlegend=False,
    )


def save(fig, name):
    """Render the figure, composite it onto the dark background, save PNG + WebP.

    1. Plotly/Kaleido writes a transparent PNG at exactly 1200x600 (scale=1,
       so the blog's size limit is respected).
    2. That layer is alpha-composited over background().
    3. The result is saved as PNG and as WebP (the format the blog serves);
       the temporary transparent file is deleted.
    """
    tmp = os.path.join(OUT, f"_{name}")
    fig.write_image(tmp, width=W, height=H, scale=1)
    layer = Image.open(tmp).convert("RGBA")
    img = background().convert("RGBA")
    img.alpha_composite(layer)
    path = os.path.join(OUT, name)
    img = img.convert("RGB")
    img.save(path, optimize=True)
    img.save(path.replace(".png", ".webp"), "WEBP", quality=90, method=6)
    os.remove(tmp)
    print("saved", path, "+ .webp", img.size)


# ---------------------------------------------------------------------------
# Chart 1: range of outcomes per asset
# ---------------------------------------------------------------------------
def chart_ranges():
    """One horizontal bar per asset, from its worst to its best calendar year.

    The dot marks the compound annual return. A label on the left shows how
    many of the 98 years ended negative. Assets are ordered from safest
    (bottom) to riskiest (top), so the bars visibly widen as return rises.
    """
    # (label, column key, colour), listed bottom row first
    assets = [("3-month T-bills", "bills", BILL), ("10-year US Treasury bonds", "bonds", BOND),
              ("Baa corporate bonds", "baa", "#5FA6C9"), ("S&P 500 (with dividends)", "stocks", STOCK)]
    fig = go.Figure()
    lay = base_layout("The range of years behind the long-run average",
                      "Worst and best calendar year, 1928-2025, with the long-run annual return marked")
    ann = list(lay["annotations"])
    for i, (label, key, color) in enumerate(assets):  # i is the row's y position
        c = COL[key]
        vals = [r[c] for r in ROWS]
        lo, hi, g = min(vals), max(vals), geo(c)
        lo_y = [r[0] for r in ROWS if r[c] == lo][0]  # year of the worst return
        hi_y = [r[0] for r in ROWS if r[c] == hi][0]  # year of the best return
        down = sum(v < 0 for v in vals)               # number of negative years

        # Range bar (worst to best), drawn semi-transparent so the dot stands out.
        fig.add_trace(go.Scatter(x=[lo * 100, hi * 100], y=[i, i], mode="lines",
                                 line=dict(color=color, width=10), opacity=0.55))
        # Compound annual return dot, with a dark ring to separate it from the bar.
        fig.add_trace(go.Scatter(x=[g * 100], y=[i], mode="markers",
                                 marker=dict(size=16, color=color, line=dict(color="#0d1626", width=3))))
        ann += [
            # worst year, left of the bar
            dict(x=lo * 100, y=i, text=f"{lo:.1%} ({lo_y})", showarrow=False, xanchor="right",
                 xshift=-10, font=dict(size=13, color=INK2)),
            # best year, right of the bar
            dict(x=hi * 100, y=i, text=f"+{hi:.1%} ({hi_y})", showarrow=False, xanchor="left",
                 xshift=10, font=dict(size=13, color=INK2)),
            # compound annual return, above the dot
            dict(x=g * 100, y=i, text=f"<b>{g:.1%}/yr</b>", showarrow=False, yshift=20,
                 font=dict(size=13, color=INK)),
            # asset name and count of down years, in the empty space on the left (x=-98)
            dict(x=-98, y=i, text=f"<b>{label}</b><br><span style='color:{MUTED};font-size:12px'>"
                 f"down in {down} of {len(vals)} years</span>",
                 showarrow=False, xanchor="left", align="left", font=dict(size=14, color=INK)),
        ]
    lay["annotations"] = ann
    fig.update_layout(**lay)
    # The x-axis starts at -98% only to leave room for the row labels; ticks start at -40%.
    fig.update_xaxes(range=[-98, 72], gridcolor=GRID, zeroline=True,
                     zerolinecolor="rgba(255,255,255,0.25)", tickvals=[-40, -20, 0, 20, 40, 60],
                     ticktext=["-40%", "-20%", "0%", "+20%", "+40%", "+60%"],
                     tickfont=dict(color=MUTED))
    fig.update_yaxes(visible=False, range=[-0.6, 3.6])
    save(fig, "01_range_of_outcomes.png")


# ---------------------------------------------------------------------------
# Chart 2: how often each holding period ended in a loss
# ---------------------------------------------------------------------------
def chart_horizon():
    """Grouped bars: % of rolling windows with a nominal loss, stocks vs 10y Treasuries.

    Shows that the chance of ending below the starting value falls as the
    holding period lengthens, and that stocks need much longer than bonds
    to get there.
    """
    horizons = [1, 3, 5, 10, 15, 20]  # holding periods in years
    s = [rolling_loss_share(COL["stocks"], n)[0] * 100 for n in horizons]
    b = [rolling_loss_share(COL["bonds"], n)[0] * 100 for n in horizons]
    xs = [f"{n} yr" if n == 1 else f"{n} yrs" for n in horizons]  # category labels
    fig = go.Figure()
    fig.add_bar(x=xs, y=s, name="S&P 500", marker=dict(color=STOCK, cornerradius=4),
                text=[f"{v:.0f}%" for v in s], textposition="outside",
                textfont=dict(color=INK, size=14))
    fig.add_bar(x=xs, y=b, name="10-year Treasuries", marker=dict(color=BOND, cornerradius=4),
                text=[f"{v:.0f}%" for v in b], textposition="outside",
                textfont=dict(color=INK, size=14))
    lay = base_layout("Longer horizons had fewer nominal losses",
                      "Share of overlapping windows starting each January (1928-2025) that ended below the starting value, in nominal dollars")
    lay["showlegend"] = True  # two series, so a legend is needed (top-right)
    lay["legend"] = dict(orientation="h", x=1, xanchor="right", y=1.02, yanchor="bottom",
                         font=dict(color=INK, size=13), bgcolor="rgba(0,0,0,0)")
    lay["barmode"] = "group"
    lay["bargap"] = 0.32       # space between horizon groups
    lay["bargroupgap"] = 0.08  # space between the two bars in a group
    # Call out the single losing 15-year stock window (verified with rolling_loss_share).
    lay["annotations"] = list(lay["annotations"]) + [
        dict(x="15 yrs", y=22, text="One losing 15-year stretch for stocks<br>(1929-1943, about -0.2% a year)",
             showarrow=False, font=dict(size=12, color=INK2), align="center"),
    ]
    fig.update_layout(**lay)
    fig.update_yaxes(ticksuffix="%", gridcolor=GRID, range=[0, 32], tickfont=dict(color=MUTED), zeroline=False)
    fig.update_xaxes(tickprefix="held ", tickfont=dict(color=INK, size=14), showgrid=False)  # "held 5 yrs"
    save(fig, "02_holding_period_loss_odds.png")


# ---------------------------------------------------------------------------
# Chart 3: what bonds did in the worst stock years
# ---------------------------------------------------------------------------
def chart_bad_years():
    """Paired bars for every year the S&P 500 lost 10% or more (12 years since 1928).

    Bonds were positive in 9 of the 12; 2022 is highlighted because it is the
    only year where both fell by double digits.
    """
    bad = [r for r in ROWS if r[COL["stocks"]] <= -0.10]
    # Bars are placed at integer positions 0..11 with the years as tick labels.
    # Passing the years themselves as x would make Plotly treat them as dates
    # and squash the bars together.
    yrs = list(range(len(bad)))
    labels = [str(r[0]) for r in bad]
    s = [r[COL["stocks"]] * 100 for r in bad]
    b = [r[COL["bonds"]] * 100 for r in bad]
    fig = go.Figure()
    fig.add_bar(x=yrs, y=s, name="S&P 500", marker=dict(color=STOCK, cornerradius=4))
    fig.add_bar(x=yrs, y=b, name="10-year Treasuries", marker=dict(color=BOND, cornerradius=4))
    lay = base_layout("Bonds usually caught the fall. In 2022 they fell too",
                      "Every year the S&P 500 lost 10% or more since 1928, next to 10-year Treasury returns the same year")
    lay["showlegend"] = True
    lay["legend"] = dict(orientation="h", x=1, xanchor="right", y=1.02, yanchor="bottom",
                         font=dict(color=INK, size=13), bgcolor="rgba(0,0,0,0)")
    lay["barmode"] = "group"
    lay["bargap"] = 0.28
    lay["bargroupgap"] = 0.06
    # Dotted highlight box around 2022, the last position (index 11).
    lay["shapes"] = [dict(type="rect", xref="x", yref="paper", x0=10.55, x1=11.45, y0=0, y1=1,
                          fillcolor="rgba(255,255,255,0.06)", line=dict(color="rgba(255,255,255,0.35)",
                                                                       width=1, dash="dot"))]
    lay["annotations"] = list(lay["annotations"]) + [
        # 2022 label, inside the highlight box below the bars
        dict(x=labels.index("2022"), y=-25, text="<b>2022</b><br>stocks -18.0%<br>bonds -17.8%", showarrow=False,
             font=dict(size=12, color=INK), align="center"),
        # 2008 label, above the +20.1% bond bar: the best example of the cushion working
        dict(x=labels.index("2008"), y=26, text="2008: bonds +20.1%<br>while stocks fell 36.6%", showarrow=False,
             font=dict(size=12, color=INK2), align="center"),
    ]
    fig.update_layout(**lay)
    fig.update_yaxes(ticksuffix="%", gridcolor=GRID, range=[-48, 32], tickfont=dict(color=MUTED),
                     zeroline=True, zerolinecolor="rgba(255,255,255,0.3)")
    fig.update_xaxes(tickvals=yrs, ticktext=labels, tickfont=dict(color=INK, size=13), showgrid=False,
                     range=[-0.6, len(yrs) - 0.4])
    save(fig, "03_bad_stock_years_vs_bonds.png")


# ---------------------------------------------------------------------------
# Chart 4: decision map (a diagram, not data)
# ---------------------------------------------------------------------------
def chart_map():
    """Three equal-width cards mapping time horizon to vehicle, drawn with Plotly shapes.

    Uses a 0-20 by 0-4 coordinate grid with hidden axes. The cards are equal
    width on purpose: this is a rule of thumb, not a timeline, so the widths
    don't represent years. Below the cards: "rule zero" on the left and the
    individual-stocks satellite under the 10+ years card only.
    """
    fig = go.Figure()
    lay = base_layout("Match the vehicle to when you need the money",
                      "My working rule of thumb, built from the history above. Not a law of nature")
    lay["annotations"] = [lay["annotations"][1]]  # keep the credit, drop the data source line (no data here)
    lay["margin"] = dict(l=40, r=40, t=118, b=78)
    # (x start, x end, colour, header strip text, card heading, card body)
    bands = [
        (0, 6.6, BILL, "0 to 3 years", "Cash and short, safe debt",
         "Deposits, T-bills, short Fidelis/Tezaur.<br>Job: be there on the day you need it."),
        (6.7, 13.3, BOND, "3 to 10 years", "Bonds, stocks only if flexible",
         "Maturity-matched bonds; consider<br>some stocks only if the goal is flexible."),
        (13.4, 20, STOCK, "10+ years", "Broad stock ETFs",
         "A world or S&P 500 UCITS ETF.<br>Job: grow faster than inflation."),
    ]
    shapes = []
    for x0, x1, col, when, head, body in bands:
        # Card body: tinted fill with a solid outline.
        shapes.append(dict(type="rect", x0=x0 + 0.08, x1=x1 - 0.08, y0=1.15, y1=3.85,
                           fillcolor=col, opacity=0.22, line=dict(color=col, width=2), layer="below"))
        # Header strip: the same colour, near-opaque, across the top of the card.
        shapes.append(dict(type="rect", x0=x0 + 0.08, x1=x1 - 0.08, y0=3.55, y1=3.85,
                           fillcolor=col, opacity=0.9, line=dict(width=0)))
        mid = (x0 + x1) / 2
        lay["annotations"] += [
            dict(x=mid, y=3.70, text=f"<b>{when}</b>", showarrow=False, font=dict(size=14, color="#0d1626")),
            dict(x=mid, y=2.95, text=f"<b>{head}</b>", showarrow=False, font=dict(size=17, color=INK)),
            dict(x=mid, y=2.05, text=body, showarrow=False, font=dict(size=13, color=INK2)),
        ]
    # Dotted satellite box for individual stocks, under the 10+ years card only:
    # long-term money, small size.
    shapes.append(dict(type="rect", x0=13.48, x1=19.92, y0=0.15, y1=0.95,
                       fillcolor="rgba(0,0,0,0)", line=dict(color=STOCK, width=1.5, dash="dot")))
    lay["annotations"] += [
        dict(x=16.7, y=0.55, text="<b>Individual stocks:</b> a small satellite,<br>only inside my circle of competence",
             showarrow=False, font=dict(size=13, color=INK)),
        # Rule zero comes before any of the three cards.
        dict(x=3.3, y=0.55, text="<b>Rule zero:</b> emergency fund first,<br>expensive debt paid off",
             showarrow=False, font=dict(size=13, color=INK2)),
    ]
    lay["shapes"] = shapes
    fig.update_layout(**lay)
    fig.update_xaxes(visible=False, range=[0, 20])
    fig.update_yaxes(visible=False, range=[0, 4])
    save(fig, "04_vehicle_decision_map.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Print the compound annual returns quoted in the article, as a quick check.
    for c in ("stocks", "bonds", "bills"):
        print(c, f"geo {geo(COL[c]):.2%}")
    chart_ranges()
    chart_horizon()
    chart_bad_years()
    chart_map()
