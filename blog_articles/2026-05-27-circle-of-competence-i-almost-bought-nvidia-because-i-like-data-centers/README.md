# Circle of Competence: I Almost Bought NVIDIA Because I Like Data Centers

Supporting Python scripts for my CodeZero2Hero article:

[Read the full article on CodeZero2Hero](https://codezero2hero.com/posts/circle-of-competence-i-almost-bought-nvidia-because-i-like-data-centers/)

## Scripts

### fetch_edgar_data_and_chart.py

Retrieves company-reported US-GAAP XBRL facts from the SEC EDGAR Company Concept API for NVIDIA and Arista Networks.

The script:

- Retrieves quarterly revenue and gross profit data.
- Derives fourth-quarter values where necessary by subtracting the first nine months from the full fiscal-year value.
- Calculates quarterly GAAP gross margin.
- Saves a CSV file per company for manual review.
- Creates long-term quarterly revenue and gross-margin charts.

This script supports the article's main lesson: liking an industry is not enough. Before considering an investment, I need to examine the actual business performance behind the story.

Important: Before running the script, replace the placeholder USER_AGENT value with your real name and email address. The SEC requires automated requests to identify the requester.

### make_margin_charts.py

Creates focused article charts from company-reported GAAP figures for NVIDIA and Arista Networks.

The script produces:

- A NVIDIA quarterly gross-margin chart showing the FY2026 margin decline and subsequent recovery, with context around the reported H20-related charge.
- An Arista Networks slope chart comparing gross margin, operating margin and net margin between FY2024 and FY2025.

These charts support the article's practical investing lesson: a single number or a strong technology narrative is not enough to understand a company. The reader needs to investigate what changed, why it changed and whether it affects the investment thesis.

## Install dependencies

```bash
bash pip install matplotlib 
```

## Run the scripts

```bash
bash python fetch_edgar_data_and_chart.py python make_margin_charts.py 
```

## Output files

Running fetch_edgar_data_and_chart.py creates:

 - nvidia_quarterly.csv
 - arista_quarterly.csv
 - nvidia_revenue_10y.png
 - nvidia_grossmargin_10y.png
 - arista_revenue_10y.png
 - arista_grossmargin_10y.png 

Running make_margin_charts.py creates:

- nvidia_margin_recovery.png
- arista_margin_divergence.png 

## Data source

- SEC EDGAR XBRL Company Concept API for company-reported US-GAAP Revenue and Gross Profit facts.
- NVIDIA quarterly and full-year fiscal 2026 reported GAAP financial results.
- Arista Networks full-year 2024 and 2025 reported GAAP financial results.

## Verification note

The SEC XBRL API can include comparative-period facts, repeated filings and changes in reporting tags over time. The CSV outputs are included so the extracted numbers can be reviewed against the original company filings before using the charts in published analysis or making any investment decision.

## Disclaimer

These scripts are educational examples created as part of my investing learning process. They are not investment advice or a recommendation to buy or sell NVIDIA, Arista Networks or any other security.
