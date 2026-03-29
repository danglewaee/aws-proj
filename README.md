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
- publish one SNS alert if an email subscriber is configured
- let one operator inspect and disable the key
- keep a tiny action history for every finding

## AWS-first stack

- `API Gateway HTTP API` for webhook ingress and operator APIs
- `AWS Lambda (Python)` for ingest, listing, detail lookup, and disable actions
- `DynamoDB` for finding metadata and status tracking
- `S3` for raw webhook evidence and action artifacts
- `SNS` for optional finding alerts
- `CloudWatch Logs` for operational traceability
- `AWS SAM` for infrastructure and deployment
- `Static frontend` for the operator console

## MVP scope

- receive GitHub push webhooks at `POST /github/webhook`
- verify `X-Hub-Signature-256` if a webhook secret is configured
- detect `AWS_ACCESS_KEY_ID` patterns in diff text
- persist findings to `DynamoDB`
- assign a simple `severity` and `confidence`
- enforce a disable allowlist if the team configures one
- publish an optional SNS email alert for each new finding
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

If `sam deploy --guided` asks for `AlertEmailEndpoint`, enter an email address to receive one alert email per new finding. Leave it blank to keep alerting disabled. If you do enter an email, AWS SNS will send a subscription confirmation message that must be accepted before alerts are delivered.

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
- `severity`
- `confidence`
- `compareUrl`
- `receivedAt`
- `payloadS3Key`
- `disableCount`
- `lastActionNote`
- `actionHistory`
- `disableEligible`
- `alertStatus`
- `alertChannel`

## Current implementation notes

- `inlineDiff` can be provided in the payload to demo the flow without calling GitHub
- if `GITHUB_TOKEN` is configured, the ingest function can fetch compare diffs from GitHub
- disable is manual, opt-in, and requires explicit confirmation in the console
- `DISABLE_ALLOWLIST_USERS` can restrict which IAM users are eligible for key disable
- `AlertEmailEndpoint` creates an SNS email subscription and enables per-finding alert publishing
- the current detector intentionally focuses on one high-confidence pattern: long-term AWS access key IDs

## Next high-value steps

1. Add a stricter duplicate model for repeated pushes touching the same key across separate deliveries
2. Add delivery-level audit search so one operator can review what the same GitHub webhook triggered over time
3. Add a second notification channel only after SNS email stays low-noise
4. Add a second detector for short-lived cloud credentials only after the AWS key flow is rock solid
