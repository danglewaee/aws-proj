# LeakGuard

`LeakGuard` is an AWS-first internal tool that detects leaked AWS access keys in GitHub push events, stores a redacted finding, and lets one operator disable the exposed key from a small response console.

## Why this project exists

Engineering teams do not struggle because they lack secret scanning vendors. They struggle because one leaked key in one commit can still turn into a live incident before anyone sees it.

This project treats that as a very small response workflow:

- receive a GitHub push webhook
- fetch or accept the changed diff
- detect high-confidence leaked AWS access key IDs
- store one redacted finding in `DynamoDB`
- archive evidence in `S3`
- let one operator inspect and disable the key

## AWS-first stack

- `API Gateway HTTP API` for webhook ingress and operator APIs
- `AWS Lambda (Python)` for ingest, listing, detail lookup, and disable actions
- `DynamoDB` for finding metadata and status tracking
- `S3` for raw webhook evidence and action artifacts
- `CloudWatch Logs` for operational traceability
- `AWS SAM` for infrastructure and deployment
- `Static frontend` for the operator console

## MVP scope

- receive GitHub push webhooks at `POST /github/webhook`
- verify `X-Hub-Signature-256` if a webhook secret is configured
- detect `AWS_ACCESS_KEY_ID` patterns in diff text
- persist findings to `DynamoDB`
- expose:
  - `GET /findings`
  - `GET /findings/{findingId}`
  - `POST /findings/{findingId}/action`
- support finding statuses:
  - `OPEN`
  - `DISMISSED`
  - `KEY_DISABLED`
- provide a small operator console in `frontend/`

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

Then post a sample GitHub push payload:

```bash
curl -X POST http://127.0.0.1:3000/github/webhook \
  -H "content-type: application/json" \
  -d @events/sample-github-push.json
```

### 4. Open the operator console

The static console is in `frontend/`. For a quick local view, serve it with any static file server and point it at your local or deployed API base URL.

### 5. Publish the frontend to S3 website hosting

```powershell
$api = aws cloudformation describe-stacks `
  --stack-name leakguard `
  --region us-east-1 `
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" `
  --output text

powershell -ExecutionPolicy Bypass -File .\scripts\publish-frontend.ps1 `
  -BucketName leakguard-frontend-873014949989 `
  -ApiBaseUrl $api `
  -Region us-east-1
```

## Finding model

Each finding tracks:

- `findingId`
- `status`
- `repoFullName`
- `branch`
- `secretType`
- `matchedKeyIdRedacted`
- `iamUserName`
- `compareUrl`
- `receivedAt`
- `payloadS3Key`
- `disableCount`
- `lastActionNote`

## Current implementation notes

- `inlineDiff` can be provided in the payload to demo the flow without calling GitHub
- if `GITHUB_TOKEN` is configured, the ingest function can fetch compare diffs from GitHub
- disable is manual and opt-in through the console
- the current detector intentionally focuses on one high-confidence pattern: long-term AWS access key IDs

## Next high-value steps

1. Add delivery idempotency keyed by `X-GitHub-Delivery`
2. Add `GetAccessKeyLastUsed` enrichment to the UI as a stronger triage signal
3. Add allowlists so auto-disable can be enabled safely for specific IAM users
4. Add SNS or digest notifications after the core response loop is stable
