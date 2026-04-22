# Qtown v2 — BigQuery Analytics

Qtown v2 was built largely by Ralph v2, an AI developer. As the commit history grew past 1,000 commits, the interesting questions shifted from *"does the code work"* to *"what does AI-led development actually look like at scale"* — and answering those questions needs real analytics, not `git log | wc -l`.

This directory ships a small, end-to-end BigQuery layer on top of the Qtown repo's git history.

## What's here

| File | Purpose |
|---|---|
| [`export_commits.sh`](./export_commits.sh) | Reads the full git log and emits a TSV (one row per commit) with commit metadata + author + diff stats + Ralph-vs-human flag |
| [`schema.json`](./schema.json) | BigQuery table schema for the exported TSV |
| [`queries.sql`](./queries.sql) | Six analytics queries answering concrete questions about Ralph's contribution profile |

## Why this exists

Two reasons:

1. **The Qtown case study in *The AI Reckoning* references numbers.** Those numbers have to come from somewhere. Rather than hand-compute them, Qtown's commit history is loaded to BigQuery and the queries live in version control. Any claim in the book or in interviews points back to a query in this repo.
2. **Demonstrates production-discipline analytics for AI-driven development.** Most AI-codegen demos don't generate analyzable data at all. Qtown's commit stream is the data; BigQuery is the analytical surface; the queries are the tests.

## End-to-end run

Prerequisites:
- `gcloud` CLI authenticated (`gcloud auth login`)
- A GCP project with billing enabled
- BigQuery API enabled in that project (free tier: 10 GB storage + 1 TB query/month)

```bash
# 1. Export
./tools/bigquery/export_commits.sh > /tmp/qtown-commits.tsv
wc -l /tmp/qtown-commits.tsv   # sanity check — should match `git log --oneline | wc -l` + 1 header

# 2. Set your project
export PROJECT=<your-gcp-project-id>
gcloud config set project $PROJECT

# 3. Create the dataset (one-time)
bq --location=US mk --dataset "${PROJECT}:qtown_analytics"

# 4. Load the TSV into a partitioned table
bq load \
  --source_format=CSV \
  --field_delimiter=tab \
  --skip_leading_rows=1 \
  --time_partitioning_field=committed_at \
  --time_partitioning_type=DAY \
  "${PROJECT}:qtown_analytics.commits" \
  /tmp/qtown-commits.tsv \
  ./tools/bigquery/schema.json

# 5. Run the queries
sed "s/PROJECT/${PROJECT}/g" ./tools/bigquery/queries.sql > /tmp/qtown-queries.sql
bq query --use_legacy_sql=false < /tmp/qtown-queries.sql
```

Sample output from query 1 (Ralph vs human split) goes into the Qtown case study — the headline number everybody wants to see.

## Design decisions

- **TSV over JSON:** easier to eyeball, trivial to diff, works with `bq load` natively. A commit log is flat tabular data.
- **Partition by `committed_at`:** query cost scales with date range, not table size. Matters once the repo passes 10k commits.
- **`is_ralph` computed at export time:** the Ralph-vs-human heuristic (subject contains `[Ralph]`) is deterministic from the subject line — baking it into the export keeps the BigQuery schema simple and makes the queries readable.
- **Per-commit diff stats via `git show --stat`:** slower than `--shortstat` in a single pipeline, but each commit's line count is independently verifiable later.

## When this would need to evolve

- Once Qtown v3 or other Ralph-driven repos are added, turn the export into a multi-repo loader and add a `repo_name` column.
- Add a second table for file-level churn (`files` rather than commits) if the question "which subsystems did Ralph touch most" becomes live.
- Add a scheduled BigQuery transfer or a Cloud Scheduler + Cloud Run job to refresh daily instead of on-demand.

None of those are needed for the current case study.
