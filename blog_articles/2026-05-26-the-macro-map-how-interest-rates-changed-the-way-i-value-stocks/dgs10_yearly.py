"""
10-Year Treasury Constant Maturity Rate (FRED: DGS10)
Scrape daily data -> aggregate to yearly with Polars -> plot.

Source (no API key needed):
    https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10
(FRED's data page is https://fred.stlouisfed.org/data/DGS10 ; the line above
 is its raw-CSV download endpoint.)

The daily series uses "."  for non-trading days. Yields can't be summed, so the
natural yearly rollup is the MEAN (I will keep min / max / year-end).

Install deps:
    pip install polars matplotlib requests
"""

import io
import requests
import matplotlib.pyplot as plt
import polars as pl

SERIES_ID = "DGS10"
CSV_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES_ID}"


# --------------------------------------------------------------------------- #
# 1. Scrape the daily CSV from FRED
# --------------------------------------------------------------------------- #
def fetch_daily() -> pl.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "text/csv,text/plain,*/*",
    }
    r = requests.get(CSV_URL, headers=headers, timeout=60)
    r.raise_for_status()

    df = pl.read_csv(io.BytesIO(r.content), null_values=["."], try_parse_dates=False)
    date_col, value_col = df.columns[0], df.columns[1]
    return df.select(
        pl.col(date_col).str.to_date("%Y-%m-%d").alias("date"),
        pl.col(value_col).cast(pl.Float64, strict=False).alias("dgs10"),
    ).drop_nulls()


# --------------------------------------------------------------------------- #
# 2. Aggregate daily -> yearly with Polars
# --------------------------------------------------------------------------- #
def aggregate_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    val = SERIES_ID.lower()
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by("year")
        .agg(
            pl.col(val).mean().round(2).alias("avg_yield"),
            pl.col(val).min().alias("min_yield"),
            pl.col(val).max().alias("max_yield"),
            pl.col(val).last().alias("year_end_yield"),
            pl.len().alias("n_days"),
        )
        .sort("year")
    )
    # To start from a given year, add before .sort():  .filter(pl.col("year") >= 2000)


# --------------------------------------------------------------------------- #
# 3. Plot the yearly series
# --------------------------------------------------------------------------- #
def plot_yearly(yearly: pl.DataFrame):
    years = yearly["year"].to_list()
    avg = yearly["avg_yield"].to_list()
    lo = yearly["min_yield"].to_list()
    hi = yearly["max_yield"].to_list()

    fig, ax = plt.subplots(figsize=(14, 7))

    ax.fill_between(
        years, lo, hi,
        color="#1c9ff0",
        alpha=0.18,
        label="Yearly min–max range",
    )
    ax.plot(
        years, avg,
        color="#0a0b5c",
        linewidth=2.4,
        marker="o",
        markersize=4,
        label="Annual average",
    )

    ax.set_title(
        "10-Year Treasury Constant Maturity Rate | annual average\n"
        "(FRED: DGS10)",
        fontsize=17,
        fontweight="bold",
        loc="left",
        pad=16,
    )
    ax.set_ylabel("Yield (%)", fontsize=12)
    ax.grid(axis="y", color="#e5e5e5", linewidth=1)
    ax.set_axisbelow(True)

    for label in ax.get_xticklabels():
        label.set_fontweight("bold")

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.legend(frameon=False, fontsize=11)
    ax.margins(x=0.01)

    fig.tight_layout()
    return fig


if __name__ == "__main__":
    daily = fetch_daily()
    print(f"Scraped {len(daily):,} daily observations "
          f"({daily['date'].min()} -> {daily['date'].max()})")

    yearly = aggregate_yearly(daily)
    print(yearly)

    #yearly.write_csv("dgs10_yearly.csv")
    fig = plot_yearly(yearly)
    #fig.savefig("dgs10_yearly.png", dpi=150, bbox_inches="tight")
    plt.show()
    #print("Saved dgs10_yearly.csv and dgs10_yearly.png")
