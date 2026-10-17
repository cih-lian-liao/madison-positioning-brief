"""Build data/classified/focus_<company>.csv: AI labels for all 217 snapshot records, scored from each
company's point of view, so a brief only needs one AI call when someone presses "Build my brief".

Databricks reuses the A4 full-run labels (run 20261008T021228, hand-checked 20/20 on theme in A5).
The other three companies are labelled with the same prompt (gpt-4.1-mini, temperature 0).

Usage (from the app folder, with OPENAI_API_KEY set):
    python tools/build_labels.py --a4 ../../A4/outputs/20261008T021228_scored_records.csv
"""
import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from madison.classify import classify  # noqa: E402
from madison.config import BRANDS, CLASSIFIER_MODEL  # noqa: E402
from madison.data import load_snapshot, save_labels  # noqa: E402


def from_a4(path):
    labels = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("threat_to_databricks") or "").strip()
            labels[r["record_id"]] = {
                "record_id": r["record_id"], "sentiment": r["sentiment"], "theme": r["theme"],
                "threat": int(float(t)) if t else "", "positioning_signal": r["positioning_signal"],
                "insight": r["insight"], "ai_status": r["ai_status"], "ai_issue": r["ai_issue"],
            }
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a4", help="A4 scored_records.csv to reuse for Databricks")
    ap.add_argument("--brands", nargs="*", default=BRANDS)
    args = ap.parse_args()
    records = list(load_snapshot())
    for brand in args.brands:
        t = time.time()
        if brand == "Databricks" and args.a4:
            labels = from_a4(args.a4)
            source = "A4 labels"
        else:
            labels, usage = classify(records, brand)
            source = f"{CLASSIFIER_MODEL}, {usage[0]} in / {usage[1]} out tokens"
        missing = {r["record_id"] for r in records} - set(labels)
        review = sum(1 for x in labels.values() if x["ai_status"] != "ok")
        save_labels(brand, labels)
        print(f"{brand}: {len(labels)} labels ({review} needs_review, {len(missing)} missing) from {source} "
              f"in {time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
