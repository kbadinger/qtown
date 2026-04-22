#!/usr/bin/env bash
# Export Qtown's git history to a TSV suitable for BigQuery ingestion.
#
# Schema (one row per commit):
#   commit_hash        STRING
#   author_name        STRING
#   author_email       STRING
#   committed_at       TIMESTAMP
#   is_ralph           BOOLEAN  (true if commit was authored by Ralph v2)
#   subject            STRING
#   files_changed      INT64
#   lines_added        INT64
#   lines_deleted      INT64
#
# Usage:
#   ./tools/bigquery/export_commits.sh > commits.tsv

set -euo pipefail

cd "$(dirname "$0")/../.."

# Header
printf 'commit_hash\tauthor_name\tauthor_email\tcommitted_at\tis_ralph\tsubject\tfiles_changed\tlines_added\tlines_deleted\n'

# One row per commit
git log --pretty=format:'%H%x09%an%x09%ae%x09%cI%x09%s' | while IFS=$'\t' read -r hash author email iso subject; do
  # Ralph commits are tagged with "[Ralph]" prefix in the subject
  if [[ "$subject" == *"[Ralph]"* ]]; then
    is_ralph="true"
  else
    is_ralph="false"
  fi

  # Per-commit stats
  stats=$(git show --stat --format='' "$hash" 2>/dev/null | tail -1 || true)
  files_changed=$(echo "$stats" | grep -oE '[0-9]+ file' | grep -oE '[0-9]+' || echo 0)
  lines_added=$(echo "$stats" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
  lines_deleted=$(echo "$stats" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo 0)

  # Sanitize tabs and newlines from subject so TSV stays one-row-per-commit
  clean_subject=$(printf '%s' "$subject" | tr '\t\n' '  ')

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$hash" "$author" "$email" "$iso" "$is_ralph" "$clean_subject" \
    "${files_changed:-0}" "${lines_added:-0}" "${lines_deleted:-0}"
done
