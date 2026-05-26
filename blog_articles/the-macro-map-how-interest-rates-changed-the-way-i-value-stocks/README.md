# The Macro Map: How Interest Rates Changed the Way I Value Stocks

Supporting Python scripts for my CodeZero2Hero article:

[Read the full article on CodeZero2Hero](https://codezero2hero.com/posts/the-macro-map-how-interest-rates-changed-the-way-i-value-stocks/)

## Scripts

### `dgs10_yearly.py`

Downloads the daily 10-Year Treasury Constant Maturity Rate series from FRED (`DGS10`), aggregates it into yearly statistics using Polars, and plots the annual average yield together with each year's minimum-to-maximum range.

This chart supports the article's discussion of the changing risk-free-rate environment.

### `qqq_sp500.py`

Downloads historical market data using `yfinance`, calculates annual total returns for QQQ and the S&P 500 Total Return Index, and creates a grouped bar chart.

This chart supports the article's discussion of how growth-oriented investments can suffer during changing valuation and interest-rate environments.

## Install dependencies

```bash
pip install polars matplotlib requests yfinance pandas numpy
```

**Run the scripts**

```bash
python dgs10_yearly.py
python qqq_sp500.py
```

**Data source**

- 10-Year Treasury Constant Maturity Rate: Federal Reserve Economic Data (FRED), series DGS10
- Market return data: Yahoo Finance, retrieved through the yfinance Python package

**Disclaimer**

These scripts are educational examples only. 
They are not investment advice or a recommendation to buy or sell any security.
