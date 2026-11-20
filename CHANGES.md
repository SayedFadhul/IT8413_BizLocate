# Changes from the approved proposal

Every change to the design after the revised proposal (18/11/2026) is recorded here, with the reason,
so the report can list it. Newest first.

| Date | What changed | Proposal said | Now | Why | Effect on the evaluation |
|---|---|---|---|---|---|
| 19/11/2026 | Embedding model for document retrieval (F5) | `gemini-embedding-001` | `gemini-embedding-2` | It is the embedding model used in the course labs (Lab 3.1 semantic search, Lab 3.3 RAG pipeline), with the same task prefixes (`task: search result \| query: …` for questions, `title: … \| text: …` for passages). Using it keeps our retrieval method the same as the method we studied and can explain. | Decided before any evaluation run, so all four runs (control, baseline, v1, v2) use the same embedding model. Not the v1 → v2 change. |

## Fixes made during development (development questions only, before the v1 run)

The development questions may be used to improve the tool (brief 7.1). These fixes came from running them;
the outputs are in `results/v1_development_*.csv`. No held-out question was used.

| Date | Problem seen | Cause | Fix |
|---|---|---|---|
| 19/11/2026 | Embedding a batch of passages returned one vector instead of one per passage | With `gemini-embedding-2`, texts sent together in one input give one combined embedding (Week 8 lecture) | Each passage is sent as its own input in the batch request (`app/gemini.py`); checked: identical to one-by-one requests |
| 19/11/2026 | A dataset question (area change 2013–2014) was declined without calling a function | The model answered from the passages only | System instruction: call the functions that could hold the answer before saying it is not available |
| 19/11/2026 | A missing land-use value was reported without the refusal sentence and without saying it is not zero | Instruction covered missing values only loosely | System instruction: a missing value starts with the refusal sentence and says the record has no value, which is not zero |
| 19/11/2026 | Answers left out the figures behind a claim (e.g. the years the population fell) and cited ids that were never given | Instruction did not ask for supporting figures; citation rule not strict enough | System instruction: give the values behind each part; cite only ids from this conversation; no citation for a sentence that uses no source |
| 19/11/2026 | One answer came back empty: on the last allowed call the model still asked for a function that does not exist | The last call still carried the function list (mode NONE) | The last generation call is sent without the function list, so it always writes text (`app/assistant.py`) |
| 19/11/2026 | The ratio function was first called without the business type (all businesses counted) | Function description did not stress the filter | `compare_governorates` description: always set the business type or group |
| 20/11/2026 | In the app, a follow-up ("And in Muharraq?") got a made-up count (7; the data says 11) cited to the earlier answer's result [T1] | Earlier answers were sent back with their citations, so the model reused an old id instead of calling a function | Earlier answers are sent back without citation markers; new rule: a follow-up calls the functions again; a citation is accepted only if it belongs to the current answer (`app/assistant.py`). Re-tested: 11 [T2]. (Found with a new question, not a test-set question.) |

Still seen after these fixes (left for the v1 failure analysis): at temperature 1.0 the model sometimes declines the
2013–2014 area question without calling a function, and on some refusals it cites an id it was never given.
