#!/bin/bash
# One file per region for the regional managers, with the columns
# order_id, order_date, product_category, quantity, unit_price.

# GenAI note: this fix was done with the advise of Claude (Anthropic). Prompt: 'check that the syntax in this fix of Task 2 of Lab 1, extracts.sh writes empty files'.
# Stop at the first error, and make a pipeline fail if any of its commands fails.
set -euo pipefail

DATA=${DATA:-$HOME/data/sales_2025.csv}
OUT=${OUT:-$HOME/data/out}
mkdir -p "$OUT/extracts"
# No cd and no 2>/dev/null: the paths are absolute, and grep errors are visible.
for region in Iberia DACH France Italy Benelux Nordics; do
    grep ",$region," "$DATA" | cut -d, -f1,2,4,6,7 > "$OUT/extracts/$region.csv"
done
echo "extracts: done"
