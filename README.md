# AWS Spend Inbox

`AWS Spend Inbox` is an AWS-first internal tool for catching unexpected cost alerts, turning them into review cases, and helping one engineer decide what to inspect first.

## Why this project exists

Small engineering teams do not struggle because AWS lacks billing data. They struggle because the signal is scattered across budgets, anomaly alerts, and optimization recommendations, and nobody knows what to review first when the bill jumps.

This project treats that as an inbox problem:

- ingest AWS spend alerts through a small API
- persist review cases in `DynamoDB`
- archive raw alert payloads in `S3`
- expose a small operator console for triage
- let one operator acknowledge or resolve a case with an explicit note

## AWS-first stack

- `API Gateway HTTP API` for alert ingress and operator APIs
- `AWS Lambda (Python)` for ingest, listing, detail lookup, and case review
- `DynamoDB` for case metadata and status tracking
- `S3` for raw alert archival and review artifacts
- `CloudWatch Logs` for operational traceability
- `AWS SAM` for infrastructure and deployment
- `Static frontend` for the operator console

## Why AWS fits

This is not a generic analytics dashboard. It is a narrow AWS operations workflow:

- `API Gateway` receives alerts from budgets, anomaly monitors, or manual intake
- `Lambda` normalizes those alerts into small review cases
- `DynamoDB` stores action status cheaply
- `S3` provides forensic storage for the original alert payload

That gives the project a clean single-vendor story instead of a mixed deployment narrative.

## MVP scope

- receive alerts at `POST /alerts/{source}`
- write raw alert payloads to `S3`
- write review cases to `DynamoDB`
- expose:
  - `GET /cases`
  - `GET /cases/{caseId}`
  - `POST /cases/{caseId}/review`
- support case statuses:
  - `NEW`
  - `ACKNOWLEDGED`
  - `RESOLVED`
- provide a small operator console in `frontend/`

## Repository layout

```text
aws-webhook-replay-console/
  docs/
  events/
  frontend/
  src/
    handlers/
    shared/
  template.yaml
```

## Quick start

### 1. Prerequisites

- AWS account
- AWS CLI configured
- AWS SAM CLI installed
- Python 3.12 available locally if you want to run without containers

### 2. Build and deploy

```bash
sam build
sam deploy --guided
```

### 3. Run locally

```bash
sam local start-api
```

Then post a sample alert:

```bash
curl -X POST http://127.0.0.1:3000/alerts/anomaly-detection \
  -H "content-type: application/json" \
  -d @events/sample-cost-alert.json
```

### 4. Open the operator console

The static console is in `frontend/`. For a quick local view, serve it with any static file server and point it at your local or deployed API base URL.

### 5. Publish the frontend to S3 website hosting

You can host the operator console on AWS with a public S3 website endpoint:

```powershell
$api = aws cloudformation describe-stacks `
  --stack-name webhook-replay-console `
  --region us-east-1 `
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" `
  --output text

powershell -ExecutionPolicy Bypass -File .\scripts\publish-frontend.ps1 `
  -BucketName webhook-replay-console-frontend-873014949989 `
  -ApiBaseUrl $api `
  -Region us-east-1
```

This script:

- writes the API base URL into `frontend/config.js`
- creates the bucket if needed
- enables S3 website hosting
- applies a public read bucket policy
- uploads the static files

## Case model

Each case record tracks:

- `caseId`
- `title`
- `source`
- `service`
- `severity`
- `estimatedImpactUsd`
- `status`
- `receivedAt`
- `lastUpdatedAt`
- `payloadS3Key`
- `reviewCount`
- `lastReviewNote`
- `owner`

## Current implementation notes

- alerts can come from `budgets`, `anomaly-detection`, `compute-optimizer`, or `manual`
- review currently means `ACKNOWLEDGED` or `RESOLVED`
- automated enrichment from real AWS Cost APIs is intentionally left for a later iteration

## Next high-value steps

1. Add direct ingestion from AWS Budgets and Cost Anomaly Detection
2. Add owner assignment and saved views
3. Replace list-case `scan` behavior with stricter indexed access patterns
4. Add CloudWatch dashboards and cost review notifications
