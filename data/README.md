# Data

This repository uses a synthetic manufacturing supply-chain dataset so the full analysis can be reproduced without exposing employer, supplier or customer information.

| File | Rows | Purpose |
| --- | ---: | --- |
| `suppliers.csv` | 50 | Supplier master data and service-quality measures |
| `purchase_orders.csv` | 5,000 | Order spend, delivery dates and delay performance |
| `inventory.csv` | 500 | Stock, reorder points, unit cost and inventory value |
| `demand_history.csv` | 12,000 | Monthly demand for 500 products across 24 months |

The analysis validates required fields, missing values and duplicate rows before calculating any KPI.
