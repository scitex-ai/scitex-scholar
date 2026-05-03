---
description: |
  [TOPIC] Doi Resolution
  [DETAILS] Resolve DOIs from titles; resumable batches; rate-limit recovery.
tags: [scitex-scholar-doi-resolution, scitex-scholar]
---


# DOI Resolution

CrossRef-backed title→DOI resolution. Resumable: per-title state is checkpointed so interrupted runs continue cleanly.

## CLI

```bash
# Single title
python -m scitex_scholar.resolve_dois --title "The circadian profile of epilepsy improves seizure forecasting"

# Whole BibTeX file (resumable)
python -m scitex_scholar.resolve_dois --bibtex refs.bib --resume
```

## MCP

```
scholar_resolve_dois(titles=[...], project=None, resume=True)
scholar_resolve_dois(bibtex_path="refs.bib",  resume=True)
```

## Resume behavior

- State directory: `~/.scitex/scholar/cache/dois/`
- Per-title hash key — re-running the same title is a no-op
- On rate-limit (HTTP 429), backs off exponentially and continues
- Progress and ETA shown rsync-style

## Output

For BibTeX input, produces `<input>_processed.bib` with `doi` populated. Failures are kept in the file and listed at the tail of stdout for manual fixing.

## Tips

- Provide author + year when titles are short/generic — disambiguates near-duplicates
- For very long batches, set `--num-workers` modestly (4-8); CrossRef rate-limits aggressive callers
- If the title has Unicode (math, accents), pass it via `--title-file path.txt` to avoid shell quoting issues
