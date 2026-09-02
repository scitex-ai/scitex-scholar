# JCR Impact Factor Engine

Journal impact-factor lookup from Journal Citation Reports (JCR) data.

The rows live in the shared store (`scitex_dev.store`), resolved by
`host_store()` to this host's PostgreSQL. There is no data file and no path
to configure: `build_database.py` loads a JCR Excel export into the
`scholar_impact_factor` table, and `ImpactFactorJCREngine` reads it back.

## Components

### ImpactFactorJCREngine.py
- Query engine for the JCR table
- Returns impact factor, quartile, and ISSN information
- Handles missing data gracefully

### build_database.py
- Loads a JCR Excel export into the store
- Parses JCR Excel exports
- Extracts impact factors and quartiles

## Usage

### Loading the data

```python
from pathlib import Path

from scitex_scholar.impact_factor.jcr.build_database import build_database

count = build_database(Path("JCR_IF_2021.xlsx"))
```

Or run as a script:
```bash
python -m scitex_scholar.impact_factor.jcr.build_database --excel JCR_IF_2021.xlsx
```

Re-running with a newer export UPSERTS by journal title: numbers are updated
in place, and journals absent from the new export keep their previous row
rather than vanishing.

### Querying Impact Factors

```python
from scitex_scholar.impact_factor.jcr.ImpactFactorJCREngine import (
    ImpactFactorJCREngine,
)

engine = ImpactFactorJCREngine()

# Search by journal name
results = engine.search("Nature")

# Search by ISSN
results = engine.search("0028-0836", key="issn")

# Filter by impact factor range
high_impact = engine.filter(min_value=10.0, limit=100)
```

## Data Format

### Input
- JCR Excel files (.xlsx) with columns:
  - Journal Name / Name
  - ISSN
  - EISSN
  - 2021 JIF / JIF
  - CATEGORY (with quartile info)

### Stored fields

`scholar_impact_factor`:

- `journal` (str, identity): Journal name
- `journal_abbr` (str): Journal abbreviation
- `issn` (str): Print ISSN
- `eissn` (str): Electronic ISSN
- `factor` (float): Impact factor
- `jcr` (str): JCR quartile (Q1-Q4)
- `nlm_id` (str): NLM unique ID
- `jcr_year` (str): Which JCR edition the row came from

`jcr_year` is stamped at load time rather than inferred later, so the
reported edition cannot drift from the numbers beside it.

## Dependencies

- openpyxl: Excel file parsing
- scitex-dev: the shared store primitive
