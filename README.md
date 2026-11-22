# BizLocate BH – Business Location and Licensing Assistant

IT8413 Generative AI for Data Insights · Bahrain Polytechnic · Group Project, Brief D · **Group G3**

BizLocate BH helps advisors answer people who want to open a small business in Bahrain: **where** similar businesses are, **what each area is like** (residents, land use, area) and **which registration and licensing rules apply**. Every number is computed in code from published datasets, every rule is cited to its official document, and the tool says so when the sources cannot answer.

**Try it online:** https://bizlocate-bh.streamlit.app

## Team

| Member | Leads |
|---|---|
| Sayed Fadhul Hashem | F6–F8 (combined questions, refusal, follow-ups), F10 (query log, settings), evaluation, test set, repository and report |
| Mohamed Alradhi | F2–F3 (filters, dashboard), F5 (retrieval and citations), interventions, Responsible AI |
| Ali Haji | F1 (data preparation), F4 (data questions), F9 (report export), vendor benchmark |

Each member commits their own work from their own GitHub account.

## Run it on your computer (Windows)

1. Install **Python 3.12** from python.org (tick *Add Python to PATH*).
2. Get the code, in a folder outside OneDrive:
   ```
   cd C:\Users\<your name>\Projects
   git clone https://github.com/SayedFadhul/IT8413_BizLocate.git
   cd IT8413_BizLocate
   ```
3. Install the libraries:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Add your Gemini API key (free at https://aistudio.google.com/apikey): copy `.env.example` to `.env` and write your key after `GEMINI_API_KEY=`. Git ignores `.env`, so the key is never committed. (You can also type the key in the app's sidebar.)
5. Run the tests: `python -m pytest -q`
6. Start the app: `streamlit run streamlit_app.py` (it opens at http://localhost:8501)

The documents and their search index come with the code (in `documents/`), so there is nothing else to download. On macOS or Linux, use `python3` and `source .venv/bin/activate`.

## Using the app

- **Sidebar:** the version (v1 or v2) and the settings in use (F10), and the filters (F2).
- **📊 Dashboard:** summary figures, charts and a map for the filters (F3).
- **💬 Ask:** questions about the data, the documents or both. Answers cite figures as `[T1]` and passages as `[P12]`, and *Sources* shows them in full. Follow-up questions work. When the sources cannot answer, the reply starts with “This is not available in the sources.” (F4–F8)
- **📄 Report:** downloads an HTML report for the filters (F9).
- **🧾 Query log:** every question with its answer, citations, time, tokens and cost (F10).
- **🗂️ Data & sources:** the datasets, every preparation step and the sources (F1).

## How it answers a question

1. It finds the 5 document passages closest to the question (`gemini-embedding-2`, cosine similarity).
2. The model (`gemini-3.1-flash-lite`) can call 7 functions that compute figures from the datasets; it never calculates a number itself.
3. It writes the answer only from those figures and passages, with a citation after each sentence (at most 3 model calls).
4. The citations are checked against what the model received.

All settings are in `app/config.py` and shown in the sidebar.

## Evaluation

```
python scripts/run_eval.py --run v1 --test-set "<path to IT8413_G3_Test_Set_and_Results.xlsx>"
```
`--run` can be `control` (question only), `baseline` (all sources pasted in, no retrieval or tools), `v1` or `v2` (v2 changes one setting: `V2_CHANGE` in `app/config.py`). Runs use the **development** questions and save `results/<run>_development_<date>.csv`. The held-out questions stay locked until the final evaluation (`--final`).

## Online version

The online app runs on Streamlit Community Cloud from the `main` branch (Python 3.12), and every push updates it. Its **Secrets** on share.streamlit.io hold only the key: `GEMINI_API_KEY = "your-key"`. The online query log resets when the app restarts, so evaluation runs are done on a computer.

## Data and documents

- **6 datasets** (5,330 rows) from data.gov.bh, under the Bahrain Open Government Data License v1.1: business locations (restaurants and cafes, other shops, supermarkets), population, land use and area. They are linked by **governorate**.
- **8 official documents** from MOIC and MOH: the Commercial Register law and its regulation, two amendments, two guides, a service notice and a food-safety guideline. They are stored unchanged in `documents/`, with G3's OCR text of the two scanned ones and the search index. A test checks every file against its SHA-256, and `python scripts/setup_sources.py --check` compares them with the publishers' current files. Their terms are explained in [ATTRIBUTION.md](ATTRIBUTION.md).

Details: [data/sources.csv](data/sources.csv) (every source with its licence or terms) and [ATTRIBUTION.md](ATTRIBUTION.md) (licence statement and the documents' terms).

## Files

| Path | What it is |
|---|---|
| `streamlit_app.py` | the app |
| `app/` | the code, one file per feature: `data_prep` (F1), `filters` (F2), `dashboard` (F3), `data_tools` (F4), `documents` and `retrieval` (F5), `assistant` (F6–F8), `report` (F9), `query_log` (F10), plus `config` (all settings) and `gemini` (the API client) |
| `data/` | the six datasets, unchanged, with `sources.csv` and the documents' checksums |
| `documents/` | the 8 official PDFs, unchanged, the OCR text of the two scans and the search index |
| `scripts/` | check the documents against the publishers, rebuild the index, run evaluations |
| `results/` | evaluation outputs |
| `tests/` | tests (no API key needed) |

**Rules we follow:** no API key is ever committed, and the held-out questions are never used before the final evaluation.
