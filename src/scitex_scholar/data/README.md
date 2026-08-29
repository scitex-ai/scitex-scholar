# Scholar Data Directory

User-provided data files. This directory is gitignored.

## Structure

```
data/
└── impact_factor/
    └── JCR_IF_2024.xlsx         # JCR Excel file (user-provided)
```

Only the source export lives here. The parsed journal metrics are loaded
into the shared store (`scholar_impact_factor`), not written back as a file
beside the spreadsheet.

## Important

- **Data NOT included in git**: This directory is gitignored
- **User responsibility**: Users must provide their own JCR data
- **Licensing**: Users must ensure proper licensing for any data

## Adding JCR Data

1. Obtain a JCR Excel file from Clarivate or an authorized source
2. Place it in `src/scitex_scholar/data/impact_factor/JCR_IF_YYYY.xlsx`
3. Load it:
   ```bash
   python -m scitex_scholar.impact_factor.jcr.build_database \
       --excel src/scitex_scholar/data/impact_factor/JCR_IF_2024.xlsx
   ```

## File Naming Convention

- Excel: `JCR_IF_YYYY.xlsx` (e.g., JCR_IF_2024.xlsx)

The year in the filename becomes each row's `jcr_year` unless `--jcr-year`
says otherwise.

## Legal Notice

JCR data is proprietary (Clarivate Analytics). Users are responsible for:
- Obtaining data through authorized channels
- Compliance with licensing terms
- Not distributing data files

We provide only the code to use the data, not the data itself.
