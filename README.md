# BizLocate BH – Business Location and Licensing Assistant

IT8413 Generative AI for Data Insights · Bahrain Polytechnic · Group Project, Brief D · **Group G3**

BizLocate BH helps advisors at a business support centre answer the questions of people who want to open a small business in Bahrain: **where** similar businesses already operate, **what each area is like** (residents, land use, area), and **which registration and licensing rules apply**. Every number is computed in code from data.gov.bh datasets, every rule is cited to its passage in the official documents, and the tool says so when the sources cannot answer.

## Team

| Member | Leads |
|---|---|
| Sayed Fadhul Hashem | F6–F8 (combined questions, refusal, follow-ups), F10 (query log, settings, credentials), evaluation, test set, repository and report |
| Mohamed Alradhi | F5 retrieval and citations, F2–F3 dashboard, interventions and enhancements, Responsible AI |
| Ali Haji | F1 data preparation, F4 data questions (function calling), F9 report export, vendor benchmark |

Each member commits their own work from their own GitHub account.

## Setup (Windows)

1. **Install Python 3.10 or newer** from python.org. Tick *Add Python to PATH*.
2. **Get the code.** Clone this repository to a folder *outside* OneDrive (for example `C:\Users\<your name>\Projects\IT8413_BizLocate`), because OneDrive syncing can damage the `.git` folder.
   ```
   cd C:\Users\<your name>\Projects
   git clone https://github.com/SayedFadhul/IT8413_BizLocate.git
   cd IT8413_BizLocate
   ```
3. **Create a virtual environment and install the libraries.**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Add your own Gemini API key** (free, from https://aistudio.google.com/apikey).
   Copy `.env.example` to a new file named `.env` in the same folder and paste your key:
   ```
   GEMINI_API_KEY=your-key-here
   ```
   `.env` is in `.gitignore`, so it is never committed. Never paste a key into any other file.
   (Alternatives: an environment variable, `.streamlit/secrets.toml` (also ignored), or the key box in the app's sidebar, which keeps it only for that browser session.)
5. **Download the documents** (once):
   ```
   python scripts/setup_sources.py --ocr-dir "<folder with the group's OCR text>"
   ```
   Every PDF should show `OK`. `CHANGED` means the publisher has updated it since G3 checked it (18/11/2026): tell the group before using it. Run `python scripts/setup_sources.py --check` to re-download everything and compare.
   Two documents (D1a, D3a) are scans, so the tool reads their OCR text from `documents/ocr/`. Group members copy the group's checked OCR text with `--ocr-dir`; anyone else can create a transcription with Gemini instead: `python scripts/setup_sources.py --transcribe` (it is then marked as a model transcription).
6. **Build the document search index** (once; about 9 embedding requests):
   ```
   python scripts/build_index.py
   ```
7. **Run the tests:**
   ```
   python -m pytest -q
   ```
8. **Start the app:**
   ```
   streamlit run streamlit_app.py
   ```
   It opens at http://localhost:8501.

On macOS or Linux use `python3`, `source .venv/bin/activate`, and forward slashes.

## Using the app

| Tab | What it does | Feature |
|---|---|---|
| Sidebar | Version (v1/v2), the settings in use and the one setting v2 changes; API key status; filters by governorate, business group and type, population years, nationality, sex, land-use months and categories | F2, F10 |
| 📊 Dashboard | Summary figures and charts for the current filters: businesses by governorate, residents per business, residents over time, mix of business types, land use by category and over time, a map and the busiest blocks. Each chart has a *Show the numbers* table | F3 |
| 💬 Ask | Questions in plain English about the data, the documents, or both. Answers cite computed results `[T1]` and passages `[P12]`; the *Sources* panel shows every function call and every retrieved passage in full. Follow-up questions can refer to earlier ones. Questions the sources cannot answer start with “This is not available in the sources.” | F4–F8 |
| 📄 Report | Downloads an HTML report for the current filters: figures, three charts, tables, the session's questions with their cited passages, and the licensing passages for the selected business groups | F9 |
| 🧾 Query log | Every question with its answer, citations, time, tokens and cost (`logs/query_log.jsonl`), downloadable as JSON Lines or CSV | F10 |
| 🗂️ Data & sources | Datasets, every preparation step, sources and the licence statement | F1 |

## How a question is answered

1. **Retrieval (F5):** the question is embedded with `gemini-embedding-2` and the 5 most similar passages are found by cosine similarity (Labs 3.1 and 3.3). For a follow-up, the previous question is added to the search text.
2. **Prompting:** a system instruction sets the rules: use only the function results and passages, cite their ids, never calculate a number, and start with “This is not available in the sources.” when the sources do not answer (including questions about success, rents, footfall or the future).
3. **Tool use (F4):** the model can call 7 functions over the prepared data (`count_businesses`, `find_businesses`, `get_population`, `get_land_use`, `get_area`, `compare_governorates`, `area_profile`). Our code runs them and returns the figures with their source; the model only writes the explanation. At most 3 generation calls per question.
4. **Checks:** citations are matched with what the model received; unknown ids and refusals are flagged and logged.

## Evaluation runs

Only **development** questions are run during the build; the held-out questions are locked until the final evaluation.
```
python scripts/run_eval.py --run control  --test-set "<path to IT8413_G3_Test_Set_and_Results.xlsx>"
python scripts/run_eval.py --run baseline --test-set "..."
python scripts/run_eval.py --run v1       --test-set "..."
python scripts/run_eval.py --run v2       --test-set "..."
```
- **control**: the question alone, with no data, documents, retrieval or tools.
- **baseline**: all sources pasted into the prompt as text (prepared datasets and full documents); no retrieval or tools.
- **v1 / v2**: the tool; v2 differs from v1 in exactly one setting (`V2_CHANGE` in `app/config.py`).

Each run writes `results/<run>_development_<date>.csv` with the spreadsheet's columns (response, tokens of all calls, latency without rate-limit waits, run date) and the full records to `logs/`. The group scores each answer in the results spreadsheet. The final evaluation adds `--final` and asks for confirmation.

## Repository layout

```
IT8413_BizLocate/
├── streamlit_app.py           the web app: sidebar, tabs
├── app/
│   ├── config.py              every setting (model, temperature, k, chunk size, v1/v2 change), prices; reads the API key
│   ├── data_prep.py           F1: loads and prepares the six datasets, records every preparation step
│   ├── filters.py             F2: the selection and how each dataset is filtered
│   ├── dashboard.py           F3: summary figures and the tables behind the charts
│   ├── data_tools.py          F4: the functions the model can call, and their declarations
│   ├── documents.py           F5: reads the PDFs and OCR text, splits them into passages
│   ├── retrieval.py           F5: embeddings index, cosine search, keyword search
│   ├── gemini.py              Gemini client: retries, rate limits, token counts
│   ├── assistant.py           F6–F8: answers a question (retrieval + prompting + tool use), refusal, follow-ups
│   ├── report.py              F9: the HTML report
│   ├── query_log.py           F10: the structured query log
│   ├── evaluation.py          control / baseline / v1 / v2 runs, held-out protection
│   └── ui_*.py                the screen of each tab
├── data/
│   ├── raw/                   the six data.gov.bh exports, unchanged
│   ├── sources.csv            every source: publisher, URL, licence or terms, retrieval date, version
│   └── documents_manifest.json  official URL and SHA-256 of each document (and of the OCR text of the scans)
├── documents/                 (not in Git) PDFs, OCR text and the search index
├── logs/                      (not in Git) query logs (F10)
├── results/                   evaluation run outputs
├── scripts/
│   ├── setup_sources.py       downloads the documents, checks them, adds the OCR text
│   ├── build_index.py         builds the document search index
│   └── run_eval.py            runs control / baseline / v1 / v2 on the development questions
├── tests/                     pytest tests (no API key needed; no test-set question is used)
├── ATTRIBUTION.md             data licence statement and attribution
├── CHANGES.md                 changes from the approved proposal
└── requirements.txt
```

## Data and documents

- **Datasets (6, 5,330 rows):** restaurants and cafes, other shops, supermarkets and hypermarkets (iGA), population (iGA), land use (UPDA), area (SLRB). Shared dimension: **governorate**. Licence: Bahrain Open Government Data License v1.1; see [ATTRIBUTION.md](ATTRIBUTION.md).
- **Documents (D1–D6, plus amendments D1a and D3a):** eight official English PDFs from MOIC and MOH (99 pages, 161 passages of up to 200 words), downloaded by the setup script and not stored here, because the MOIC and MOH website terms restrict republishing. D1a and D3a are scanned, so their text is read from OCR text.

### How the data are prepared (F1)

| Issue | What we do |
|---|---|
| Governorate written `CAPITAL` in some files, `Capital` in others | Converted to title case so all datasets join on the same labels |
| Block numbers stored as `301.0` | Converted to whole-number codes |
| Land-use area stored as text `"16398662.17 m2"` | Unit removed, converted to m² and km² |
| One land-use value is only `m2` (Southern, Other, Sep 2025) | Treated as **missing**, not zero |
| Population 2010–2011 includes *Central* and *Not Stated* | Kept but flagged; per-governorate figures use the four current governorates |
| Population has mid-year and year-end estimates | Labelled; trends use mid-year only |
| Area file gained yearly *Total* rows (portal update 04/11/2026) | Dropped, so nothing is counted twice |
| One exact duplicate record (Baskin Robbins, block 346) | Kept but flagged; same name in the same block at different coordinates = separate branches |
| Land-use `n` is not unique across months | Records identified by period, governorate and category |

The app's *Data & sources* tab lists every step with the number of rows affected.

## Model

`gemini-3.1-flash-lite` (generation and function calling), fallback `gemini-3.5-flash-lite`, embeddings `gemini-embedding-2` (the model used in Labs 3.1 and 3.3), temperature 1.0. All settings are in `app/config.py` and shown in the app sidebar and in every query-log record. Changes from the approved proposal are listed in [CHANGES.md](CHANGES.md).

## Feature status

| # | Feature | Status |
|---|---|---|
| F1 | Data loading and preparation | ✅ done, tested |
| F2 | Filters (governorate, business group and type, years, nationality, sex, land-use months and categories) | ✅ done, tested |
| F3 | Dashboard (6 charts, map, summary figures) | ✅ done, tested |
| F4 | Questions over the data (7 functions, numbers computed in code) | ✅ done, tested; checked live on the development questions |
| F5 | Questions over the documents, with citations and passage viewer | ✅ done, tested; checked live on the development questions |
| F6 | Combined questions | ✅ done, tested; checked live on the development questions |
| F7 | Refusal when the sources lack the answer | ✅ done, tested; checked live on the development questions |
| F8 | Follow-up questions | ✅ done, tested; checked live on the development questions |
| F9 | Report download (HTML, CSV) | ✅ done, tested |
| F10 | Query log, configuration, v1/v2 setting | ✅ done, tested |

## Rules we follow

- No API key or other credential in the repository or its history.
- Held-out test questions are never used to build or tune the tool before the final evaluation (not even in tests).
