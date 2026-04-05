# Evaluation

`LeakGuard` is still intentionally narrow, so its first evaluation target is simple:

- detect added long-term AWS access key IDs
- avoid triggering on removed lines, context lines, and obvious near-misses

## Detector corpus

The repository includes a small detector corpus in [evaluation-cases.json](D:/CODE/Projects/Project-cloud-used/aws-webhook-replay-console/events/evaluation-cases.json).

Run it with:

```powershell
python .\scripts\evaluate-detector.py
```

The script prints:

- number of evaluation cases
- exact-match count
- exact-match rate
- expected vs detected findings per case

This is not meant to be a benchmark suite for all secret types. It is a narrow regression harness for the first supported detector.

## Metrics that matter most

For `LeakGuard`, the strongest operational signals are:

- `timeToFindingMs.p50` and `timeToFindingMs.p95`
- scan delivery retry/DLQ counts
- `alertsPublished`
- `autoDisabled`
- diff source mix:
  - `GITHUB_COMPARE_API`
  - `INLINE_DIFF`
  - `UNKNOWN`

These now come from the `GET /metrics/summary` endpoint and the hosted `System snapshot` panel.
