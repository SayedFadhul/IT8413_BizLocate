"""Run one evaluation configuration on the test set and save the results.

Examples (from the repository folder):
    python scripts/run_eval.py --run control  --test-set "<path to IT8413_G3_Test_Set_and_Results.xlsx>"
    python scripts/run_eval.py --run baseline --test-set "..."
    python scripts/run_eval.py --run v1       --test-set "..." --questions 9,10,11
    python scripts/run_eval.py --run v2       --test-set "..."

Only DEVELOPMENT questions are run. The held-out questions are reserved for the final evaluation
(brief 7.1); running them needs --final and typing FINAL EVALUATION when asked.
The test-set path can also be set once in the environment variable BIZLOCATE_TEST_SET.

Output: results/<run>_<set>_<date>.csv (columns as in the results spreadsheet: paste the Response,
token, latency and date columns into the run's sheet, then score each answer) and logs/eval_*.jsonl.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_api_key, get_settings  # noqa: E402
from app.data_prep import load_all  # noqa: E402
from app.evaluation import RUNS, Runner, baseline_sources, load_test_set, run_questions, with_parents  # noqa: E402
from app.gemini import Gemini  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, choices=RUNS)
    ap.add_argument("--test-set", default=os.environ.get("BIZLOCATE_TEST_SET"), help="path to the test-set .xlsx")
    ap.add_argument("--questions", help="comma-separated question numbers (default: all development questions)")
    ap.add_argument("--pause", type=float, default=None,
                    help="seconds between questions (default: 5, or 60 for the baseline's large requests)")
    ap.add_argument("--final", action="store_true", help="FINAL EVALUATION ONLY: also run the held-out questions")
    args = ap.parse_args()

    if not args.test_set or not Path(args.test_set).exists():
        print("Give the test-set spreadsheet with --test-set (or set BIZLOCATE_TEST_SET).")
        return 1
    if args.final:
        typed = input("The held-out questions must only be run once, in the final evaluation, after v2 is fixed.\n"
                      "Type FINAL EVALUATION to continue: ")
        if typed.strip() != "FINAL EVALUATION":
            print("Stopped. No question was run.")
            return 1
    key = get_api_key()
    if not key:
        print("No GEMINI_API_KEY found. Create a .env file first (README, step 4).")
        return 1

    questions = load_test_set(Path(args.test_set), allow_held_out=args.final)
    if args.questions:
        wanted = {int(x) for x in args.questions.split(",")}
        missing = wanted - {q.number for q in questions}
        if missing:
            print(f"Not run (held-out or unknown): {sorted(missing)}")
        questions = with_parents([q for q in questions if q.number in wanted], questions)
    if not questions:
        print("No questions to run.")
        return 1

    version = args.run if args.run in ("v1", "v2") else "v1"
    settings = get_settings(version)
    gemini = Gemini(key, settings)
    ds = load_all()
    assistant = sources = None
    if args.run in ("v1", "v2"):
        from app.assistant import Assistant
        from app.data_tools import DataTools
        from app.retrieval import load_index
        index = load_index(settings)
        if index is None:
            print("The document index is missing. Run: python scripts/build_index.py" +
                  (" --version v2" if version == "v2" else ""))
            return 1
        assistant = Assistant(gemini, settings, tools=DataTools(ds), index=index)
    elif args.run == "baseline":
        sources = baseline_sources(ds)
        print(f"Baseline request text: {len(sources.split()):,} words")
    pause = args.pause if args.pause is not None else (60.0 if args.run == "baseline" else settings.pause_seconds)

    print(f"Run {args.run}: {len(questions)} question(s) "
          f"({', '.join(sorted({q.set for q in questions}))}), model {settings.model}, pause {pause:g} s")
    runner = Runner(args.run, gemini, settings, ds, assistant=assistant, sources_text=sources)
    csv_path, log_path = run_questions(runner, questions, pause)
    print(f"\nSaved {csv_path}\nFull records: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
