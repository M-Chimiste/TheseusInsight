#!/usr/bin/env bash
# Example usage for the harvest_and_judge.py utility

# Adjust the database URL if needed
DB_URL="postgresql://theseus:theseus@localhost:5432/theseusdb"

python theseus_insight/utils/harvest_and_judge.py \
  --date-from "2025-05-01" \
  --date-to "2025-05-07" \
  --db-url "$DB_URL" \
  --checkpoint-dir "harvest_ckpt" \
  --top-n 10 \
  --cosine-threshold 0.6
