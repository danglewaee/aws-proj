import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from shared.detectors import extract_aws_access_key_findings  # noqa: E402


def main():
    corpus_path = REPO_ROOT / "events" / "evaluation-cases.json"
    cases = json.loads(corpus_path.read_text(encoding="utf-8"))

    results = []
    exact_matches = 0
    total_expected = 0
    total_detected = 0

    for case in cases:
        expected = int(case["expectedFindingCount"])
        detected = len(extract_aws_access_key_findings(case["diffText"]))
        exact = expected == detected
        if exact:
            exact_matches += 1
        total_expected += expected
        total_detected += detected
        results.append(
            {
                "name": case["name"],
                "expectedFindingCount": expected,
                "detectedFindingCount": detected,
                "exactMatch": exact,
            }
        )

    summary = {
        "cases": len(cases),
        "exactMatches": exact_matches,
        "exactMatchRate": round(exact_matches / len(cases), 4) if cases else 0.0,
        "totalExpectedFindings": total_expected,
        "totalDetectedFindings": total_detected,
        "results": results,
    }

    print(json.dumps(summary, indent=2))
    return 0 if exact_matches == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
