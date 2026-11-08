"""
QQQ vs. S&P 500 Index annual returns, grouped bar chart.

compute_returns_from_yfinance()  -> pulls live data from Yahoo Finance

--------------------
Install deps:
    pip install yfinance pandas matplotlib

--------------------
# If you have style prefence, then choose from this
import matplotlib.pyplot as plt
for i in plt.style.available:
    print(i)

"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# --------------------------------------------------------------------------- #
# Colors / style to match the original chart
# --------------------------------------------------------------------------- #
NAVY = "#0a0b5c"   # QQQ
SKY  = "#1c9ff0"   # S&P 500 Index

# --------------------------------------------------------------------------- #
# Pull the data live from Yahoo Finance
# --------------------------------------------------------------------------- #
def compute_returns_from_yfinance(start_year=2010, end_year=2025):
    """Return {year: {'QQQ': pct, 'SP500': pct}} computed from adjusted close."""
    import yfinance as yf

    tickers = {"QQQ": "QQQ", "SP500": "^SP500TR"}  # total-return S&P index
    out = {}

    for label, ticker in tickers.items():
        df = yf.download(
            ticker,
            start=f"{start_year - 1}-12-01",   # need prior year-end close
            end=f"{end_year + 1}-01-15",
            auto_adjust=True,                  # adjusted close (dividends included)
            progress=False,
        )
        close = df["Close"].squeeze()
        # Last available close of each calendar year:
        year_end = close.resample("YE").last()
        # Year-over-year % change:
        annual = year_end.pct_change() * 100
        annual.index = annual.index.year
        for yr, val in annual.items():
            if start_year <= yr <= end_year and not np.isnan(val):
                out.setdefault(yr, {})[label] = round(float(val), 2)

    return out

# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #
def plot(data, title="QQQ vs. S&P 500 Total Return Index | Annual Returns"):
    years = sorted(data.keys())
    qqq   = [data[y]["QQQ"]   for y in years]
    sp500 = [data[y]["SP500"] for y in years]

    x = np.arange(len(years))
    w = 0.30 # bar width
    gap = 0.04  # space between the navy and sky bar

    fig, ax = plt.subplots(figsize=(15, 8))

    bars1 = ax.bar(x - w / 2 - gap / 2, qqq, w, label="QQQ", color=NAVY)
    bars2 = ax.bar(x + w / 2 + gap / 2, sp500, w, label="S&P 500 Total Return Index", color=SKY)

    # Value labels above (or below, for negatives) each bar
    def label_bars(bars):
        for b in bars:
            h = b.get_height()
            va, off = ("bottom", 1.5) if h >= 0 else ("top", -1.5)
            ax.annotate(f"{h:.2f}%",
                        (b.get_x() + b.get_width() / 2, h + off),
                        ha="center", va=va, fontsize=9, rotation=90)
    label_bars(bars1)
    label_bars(bars2)

    # Axes / grid styling
    ax.set_title(title, fontsize=26, fontweight="bold", loc="left", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_ylim(-48, 65)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.grid(axis="y", color="#e5e5e5", linewidth=1)
    ax.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(loc="upper left", frameon=False, fontsize=16,
              bbox_to_anchor=(0, 0.97), ncol=2)

    fig.tight_layout()
    return fig


if __name__ == "__main__":
    data = compute_returns_from_yfinance()   # <- live Yahoo Finance pull

    # Add a style if you want too
    #plt.style.use('Solarize_Light2')

    # Plot data
    fig = plot(data)

    # Uncomment to save the file
    #fig.savefig("qqq_vs_sp500.png", dpi=150, bbox_inches="tight")
    plt.show()
    #print("Saved qqq_vs_sp500.png")
