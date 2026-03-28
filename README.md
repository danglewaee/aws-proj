# Webhook Replay Console

`Webhook Replay Console` is an AWS-first internal platform for ingesting webhooks, storing payload history, inspecting failures, and manually replaying events with a clean audit trail.

## Why this project exists

Teams that depend on webhooks usually do not fail at the "receive HTTP" part. They fail when delivery becomes unreliable, payloads drift, downstream handlers break, or retries happen outside any visible control surface.

This project treats that as a platform problem:

- ingest webhook events through a public endpoint
- persist event summaries in `DynamoDB`
- archive raw payloads in `S3`
- expose a small operator console for inspection
- support controlled replay with explicit state changes

## AWS-first stack

- `API Gateway HTTP API` for webhook ingress and operator APIs
- `AWS Lambda (Python)` for ingest, listing, detail lookup, and replay
- `DynamoDB` for event metadata and status tracking
- `S3` for raw payload archival and replay artifacts
- `CloudWatch Logs` for operational traceability
- `AWS SAM` for infrastructure and deployment
- `Static frontend` for the operator console

## Why AWS fits

This is not a CRUD app looking for a cloud host. It is a naturally event-driven workflow:

- `API Gateway` receives untrusted external traffic
- `Lambda` normalizes and processes short-lived requests
- `DynamoDB` stores replayable event state cheaply
- `S3` provides forensic storage for raw payloads

That gives the project a clean single-vendor story instead of a mixed deployment narrative.

## MVP scope

- receive webhook requests at `POST /webhooks/{source}`
- write raw payloads to `S3`
- write event summaries to `DynamoDB`
- expose:
  - `GET /events`
  - `GET /events/{eventId}`
  - `POST /events/{eventId}/replay`
- support event statuses:
  - `PROCESSED`
  - `FAILED`
  - `REPLAYED`
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

Then post a sample webhook:

```bash
curl -X POST http://127.0.0.1:3000/webhooks/shopify \
  -H "content-type: application/json" \
  -d @events/sample-webhook.json
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

## Event model

Each event record tracks:

- `eventId`
- `source`
- `eventType`
- `status`
- `receivedAt`
- `correlationId`
- `payloadS3Key`
- `replayCount`
- `lastReplayReason`
- `lastErrorCode`
- `lastErrorMessage`

## Current implementation notes

- ingest can simulate failure when the body includes `"simulateFailure": true`
- replay currently updates event state and writes a replay artifact
- production-grade downstream forwarding is intentionally left for a later iteration

## Next high-value steps

1. Add request authentication per source
2. Add a replay target and signed delivery attempts
3. Replace list-event `scan` behavior with stricter indexed access patterns
4. Add CloudWatch dashboards and alarms
