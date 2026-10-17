"""Build samples/example_run.json: one real run with the default settings, shown by "See an example brief".

Usage (from the app folder, with OPENAI_API_KEY set):
    python tools/make_example.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from madison.config import BRANDS, SAMPLES_DIR, SOURCES  # noqa: E402
from madison.pipeline import Settings, run  # noqa: E402


def main():
    s = Settings(company="Databricks", competitors=[b for b in BRANDS if b != "Databricks"], sources=list(SOURCES))
    result = run(s, progress=lambda f, msg: print(f"{f:4.0%}  {msg}"))
    out = SAMPLES_DIR / "example_run.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    qa = result["qa"]
    print(f"saved {out.name}: {result['status']}, {qa['claims_verified']}/{qa['claims_total']} claims, "
          f"attempt {qa['attempt']}, {result['seconds']}s, tokens {result['usage']}")


if __name__ == "__main__":
    main()
