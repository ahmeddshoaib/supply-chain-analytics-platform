# Supply Chain Operations Analytics

This is a self-directed Python portfolio project built on synthetic manufacturing data. It is not an Ibrahim Fibres system, it does not contain employer data, and it was not submitted as part of my MSc. I built it to show how the supplier, purchasing, inventory and lead-time questions I handled professionally can be analysed in a reproducible workflow.

[![Python 3.11](https://img.shields.io/badge/python-3.11-16324F.svg)](https://www.python.org/)
[![Tests](https://github.com/ahmeddshoaib/supply-chain-analytics-platform/actions/workflows/tests.yml/badge.svg)](https://github.com/ahmeddshoaib/supply-chain-analytics-platform/actions/workflows/tests.yml)
[![License MIT](https://img.shields.io/badge/license-MIT-2E6F9E.svg)](LICENSE)

## Operational scope

The analysis answers three practical questions:

1. Which suppliers combine poor service with material spend exposure?
2. Which products need immediate replenishment attention?
3. Which transparent forecasting baseline should planning teams use before adding model complexity?

The data is synthetic, while the choice of questions reflects my work across imports, procurement, logistics, Oracle ERP and daily supplier reporting.

## Result snapshot

| Decision area | Result | Management use |
| --- | ---: | --- |
| Purchase-order spend reviewed | £37.24m | Quantifies the commercial exposure covered by the analysis |
| Delayed-order rate | 18.62% | Establishes the delivery-performance baseline |
| High-risk suppliers | 4 of 50 | Focuses supplier reviews on low-score, high-spend relationships |
| Inventory value classified | £44.02m | Creates an ABC view of working-capital concentration |
| Products below reorder point | 62 of 500 | Identifies the replenishment queue |
| Immediate Class A actions | 1 | Isolates the highest-value stockout risk |
| Best three-month backtest | 9.87% WAPE | Selects the three-month moving average over naive alternatives |

The moving-average baseline reduced WAPE from 10.40% for the last-value naive model and 13.03% for seasonal naive. The result is useful because the evaluation is a chronological holdout rather than an in-sample fit.

## Supplier performance

The supplier scorecard combines observed purchase-order delivery performance with defect rate, lead time and average delay. Purchase-order spend is retained as a separate exposure measure, so a low operational score has greater priority when commercial dependence is also high.

![Supplier performance and spend exposure](outputs/figures/supplier_performance.png)

The output is written to [`outputs/supplier_scorecard.csv`](outputs/supplier_scorecard.csv) with a transparent risk classification of `High`, `Monitor` or `Controlled`.

## Inventory priorities

Products are ranked by inventory value and assigned to ABC classes using cumulative value thresholds of 80% and 95%. The pipeline then combines class with the reorder gap:

- `Immediate`: Class A and below the reorder point
- `Review`: Class B or C and below the reorder point
- `Routine`: no current replenishment trigger

![Inventory value by ABC class](outputs/figures/abc_inventory_value.png)

This separation prevents a long stockout list from hiding the items with the greatest working-capital and service impact.

## Forecast evaluation

Every product is backtested over its final three months using the same chronological split. The project compares:

- last-value naive
- recursive three-month moving average
- seasonal naive with a 12-month lag

![Forecast backtest](outputs/figures/forecast_backtest.png)

The full item-level predictions are available in [`outputs/forecast_backtest_predictions.csv`](outputs/forecast_backtest_predictions.csv), and the model comparison is in [`outputs/forecast_metrics.csv`](outputs/forecast_metrics.csv).

## Quality controls

The analysis fails before KPI calculation if any dataset has missing required fields, null cells or duplicate rows. Unit tests check inventory classification and forecast evaluation, while the GitHub Actions workflow runs the tests on every push and pull request.

The current validation report covers:

| Dataset | Rows | Columns | Result |
| --- | ---: | ---: | --- |
| Suppliers | 50 | 8 | Pass |
| Purchase orders | 5,000 | 10 | Pass |
| Inventory | 500 | 8 | Pass |
| Demand history | 12,000 | 3 | Pass |

## Repository structure

```text
.
├── data/                         # Synthetic source datasets and data dictionary
├── scripts/run_analysis.py       # Reproducible analysis pipeline
├── src/supply_chain_analytics.py # Validation and analytical functions
├── tests/                        # Unit tests
├── outputs/                      # Scorecards, backtests, KPIs and figures
├── .github/workflows/tests.yml   # Automated test workflow
└── requirements.txt              # Reproducible Python environment
```

## Run the project

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_analysis.py
pytest -q
```

The pipeline recreates every file in `outputs/` from the four CSV files in `data/`.

## Limits and next development steps

The data is synthetic and the forecasting methods are intentionally transparent baselines. A production implementation would add supplier criticality, order-line service measures, demand hierarchy reconciliation, probabilistic safety-stock estimates and automated data ingestion. Those additions should follow a stable, monitored baseline.

## Author

**Muhammad Ahmed Shoaib**<br>
MSc Business Analytics, Queen's University Belfast<br>
Supply chain operations experience across imports, procurement, customs, logistics and Oracle ERP

[LinkedIn](https://www.linkedin.com/in/ahmed-shoaibed) | [Email](mailto:mshoaib01@qub.ac.uk)
