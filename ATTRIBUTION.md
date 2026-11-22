# Data attribution and licence

BizLocate BH uses six datasets from the Bahrain Open Data Portal (www.data.gov.bh).
This page meets clause 3.3 of the **Bahrain Open Government Data License, Version 1.1 (1 November 2026)**.

## Licence statement (clause 3.3(c))

> Datasets provided by the Information & eGovernment Authority (iGA), the Urban Planning and Development Authority (UPDA) and the Survey and Land Registration Bureau (SLRB) via www.data.gov.bh are governed by the Bahrain Open Government Data License available at www.nea.gov.bh/Documents/OpenDataLicense.pdf. To the fullest extent permitted by law, the government is not liable for any damage or loss of any kind caused directly or indirectly by the use or availability of the datasets or any derived analyses or applications.

## Sources and extraction dates (clause 3.3(a))

| Code | Dataset | Publisher | Page | Extracted | File in `data/raw/` |
|---|---|---|---|---|---|
| RC | Geographical Locations of Restaurants & Cafes | iGA, GIS Department | https://www.data.gov.bh/explore/dataset/geographical-locations-of-restaurants-cafes/ | 17/10/2026 | `geographical-locations-of-restaurants-cafes.csv` |
| OS | Geographical Locations of Other Shops | iGA, GIS Department | https://www.data.gov.bh/explore/dataset/geographical-locations-of-other-shops/ | 17/10/2026 | `geographical-locations-of-other-shops.csv` |
| SH | Geographical Locations of Supermarket & Hypermarkets | iGA, GIS Department | https://www.data.gov.bh/explore/dataset/geographical-locations-of-supermarket-hypermarkets/ | 17/10/2026 | `geographical-locations-of-supermarket-hypermarkets.csv` |
| POP | Population by Governorate, Nationality & Sex | iGA | https://www.data.gov.bh/explore/dataset/02-population-by-governorate-nationality-sex/ | 17/10/2026 | `02-population-by-governorate-nationality-sex.csv` |
| LU | Land Use Monthly Statistics by Land Use Category and Governorate | UPDA | https://www.data.gov.bh/explore/dataset/01-land-use-statistics/ | 17/10/2026 | `01-land-use-statistics.csv` |
| AR | Area by Governorate | SLRB | https://www.data.gov.bh/explore/dataset/02-area-by-governorate-2023/ | 16/11/2026 | `02-area-by-governorate-2023.csv` |

The raw files are stored unchanged, exactly as exported. Full details (licence terms, portal update dates, documents) are in `data/sources.csv`.

## Our own work (clause 3.3(b))

All cleaning, transformations, calculations, charts and answers produced by this app are the work of IT8413 Group G3 (Bahrain Polytechnic). They are **not** attributed to iGA, UPDA, SLRB or any other government entity. The preparation steps are listed in `app/data_prep.py` and on the app's data page.

## Re-use (clause 3.3(d)) and removal (clause 3.3(e))

Anyone who re-uses these datasets from this repository must follow the same licence conditions above.
If iGA or a publishing entity asks, G3 will stop using the datasets and remove them from this repository.

## Documents

The legal and guidance documents (D1–D6, with the amendments D1a and D3a) are the official English PDFs published by MOIC and MOH. They are stored **unchanged** in `documents/`, so the tool runs as submitted, on a computer and online, with exactly the files it was built and evaluated on:

- `documents/`: the 8 PDFs. Their official URLs and SHA-256 checksums are in `data/documents_manifest.json`; a test checks every file against them, and `python scripts/setup_sources.py --check` compares them with the publishers' current files.
- `documents/ocr/`: G3's OCR text of the two scanned PDFs (D1a, D3a).
- `documents/index/`: the search index built from them.

Bahraini legislation and official documents are not protected by copyright (Law No. 22 of 2006, Article 4), but the MOIC and MOH website terms restrict reproducing their content (MOIC asks for prior written permission: https://www.moic.gov.bh/en/node/2671). The documents are kept here only for this course project, credited to their publishers with their publishing pages in `data/sources.csv`, and G3 will remove them from this repository if MOIC, MOH or the course asks.
