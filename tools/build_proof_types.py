"""Build data/classified/proof_types.csv: what kind of proof each of the 217 snapshot records is
(customer story, launch, partner or acquisition, business news, how-to, discussion).

Added after user testing (19 Oct 2026). Usage, from the app folder with OPENAI_API_KEY set:
    python tools/build_proof_types.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from madison.classify import classify_proof  # noqa: E402
from madison.data import load_snapshot, save_proof_types  # noqa: E402


def main():
    records = list(load_snapshot())
    proofs, usage = classify_proof(records)
    save_proof_types(proofs)
    print(f"{len(proofs)} records labelled ({usage[0]} in / {usage[1]} out tokens)")
    print(Counter(p or "(none)" for p in proofs.values()).most_common())


if __name__ == "__main__":
    main()
