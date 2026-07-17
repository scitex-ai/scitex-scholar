# Journal normalizer

Maps journal name variants, abbreviations and ISSNs onto a canonical
journal, keyed by **ISSN-L** (the single identifier of record).

| File            | Owns                                                      |
|-----------------|-----------------------------------------------------------|
| `_names.py`     | Pure name/ISSN string normalization. No I/O.               |
| `_cache.py`     | Cache file read/write, TTL freshness (advisory).           |
| `_fetch.py`     | OpenAlex corpus crawl (async + blocking wrapper).          |
| `_normalizer.py`| `JournalNormalizer`, indexes, lookups, module-level API.    |

`core/journal_normalizer.py` is a thin re-export shim over this package.

## The hot-path rule

**A lookup never touches the network. Only an explicit refresh does.**

Every public lookup goes through `_ensure_indexes()`, which reads the local
cache and stops there. `refresh()` (and `ensure_loaded(force_refresh=True)`)
is the only path that crawls OpenAlex.

This is not a style preference — it is the fix for a measured defect:

- The corpus crawl walks up to 100k journals and takes **minutes** (measured:
  385s to a complete 24MB cache).
- It used to be reachable *implicitly*, from `is_open_access_journal()` — a
  function that reads like a local bool check — so the first search after
  every cache expiry blocked for ~6.4 minutes and then **raised**, throwing
  away a crawl that had actually succeeded.
- The `future.result(timeout=120)` that looked like a bound was not one: the
  enclosing `with ThreadPoolExecutor()` called `shutdown(wait=True)` on exit,
  so it waited for the uncancellable worker regardless and only then raised.
  Never advertise a bound the runtime cannot enforce.

## Consequences to keep in mind

- **Stale is fine.** Journal identity moves on the scale of years, so a
  year-old cache is served as-is with a warning rather than blocking a
  request. Freshness is advisory; refresh out of band.
- **Cold means "not known", loudly.** With no cache, `get_issn_l` returns
  `None` and `is_open_access` returns `False` — already this class's
  documented answer for an unrecognised journal, so the contract is
  unchanged. It is logged once with the command that fixes it. If you ever
  make cold-cache *silently* answer, you have reintroduced the bug.
- **Refreshes checkpoint.** `_fetch` persists every 25 pages so an
  interrupted crawl keeps what it paid for.

## Refreshing

```python
from scitex_scholar.core import refresh_journal_cache
refresh_journal_cache()  # minutes; blocks; run from a CLI or scheduled job
```
