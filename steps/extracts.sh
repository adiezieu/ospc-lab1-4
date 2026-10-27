#!/bin/bash
# One file per region for the regional managers, with the columns
# order_id, order_date, product_category, quantity, unit_price.

OUT=${OUT:-$HOME/data/out}
mkdir -p "$OUT/extracts"
cd "$OUT/extracts"
for region in Iberia DACH France Italy Benelux Nordics; do
    grep ",$region," ../data/sales_2025.csv 2>/dev/null | cut -d, -f1,2,4,6,7 > "$region.csv"
done
echo "extracts: done"
