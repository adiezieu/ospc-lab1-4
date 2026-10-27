# Nightly revenue report

This repository produces the 2025 revenue reports for the Monday management
meeting. It runs every night on the analytics server.

## Input

`~/data/sales_2025.csv`, one line per order (8.4 million orders).

## Outputs

All outputs go to `~/data/out`.

| File | Content | Produced by |
|---|---|---|
| `extracts/REGION.csv` | The orders of each region, for the regional managers | `steps/extracts.sh` |
| `revenue_by_region_month.csv` | Revenue by region and month | `steps/report.py` |
| `audit_2025.csv` | One line per order with its revenue | `steps/audit.py` |
| `segments.csv` | Orders per region, quarter and order size | `steps/segments.py` |
| `stats.csv` | 95% confidence interval of the average order value, per region and month | `steps/stats.sh` |

## Running the report

From the repository folder:

```
./run_report.sh
```

The environment variables `DATA` and `OUT` change the input file and the
output folder. The whole report takes a few minutes.
