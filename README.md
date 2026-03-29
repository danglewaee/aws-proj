# LeakGuard

`LeakGuard` is an AWS-first internal tool that detects leaked AWS access keys in GitHub push events, stores a redacted finding, and lets one operator disable the exposed key from a small response console.

## Why this project exists

Engineering teams do not struggle because they lack secret scanning vendors. They struggle because one leaked key in one commit can still turn into a live incident before anyone sees it.

This project treats that as a very small response workflow:

- receive a GitHub push webhook
- verify the delivery and queue it for scan
- fetch the changed diff in a worker
- detect high-confidence leaked AWS access key IDs
- store one redacted finding in `DynamoDB`
- archive evidence in `S3`
- publish one SNS alert if an email subscriber is configured
- let one operator inspect and disable the key
- keep a tiny action history for every finding

## AWS-first stack

- `API Gateway HTTP API` for webhook ingress and operator APIs
- `AWS Lambda (Python)` for ingest, queue workers, listing, detail lookup, and disable actions
- `SQS` to decouple webhook acknowledgement from diff scanning
- `DynamoDB` for finding metadata and status tracking
- `DynamoDB` delivery dedupe table with TTL for GitHub webhook replay protection
- `S3` for raw webhook evidence and action artifacts
- `SNS` for optional finding alerts
- `CloudWatch Logs` for operational traceability
- `AWS SAM` for infrastructure and deployment
- `Static frontend` for the operator console

## MVP scope

- receive GitHub push webhooks at `POST /github/webhook`
- require `X-GitHub-Delivery` so each GitHub delivery can be deduplicated
- acknowledge the webhook quickly and enqueue a scan job
- verify `X-Hub-Signature-256` if a webhook secret is configured
- detect `AWS_ACCESS_KEY_ID` patterns in diff text
- persist findings to `DynamoDB`
- assign a simple `severity` and `confidence`
- enforce a disable allowlist if the team configures one
- publish an optional SNS email alert for each new finding
- optionally auto-disable verified leaked keys under an allowlist-based containment policy
- expose:
  - `GET /findings`
  - `GET /findings/{findingId}`
  - `GET /deliveries`
  - `GET /deliveries/{deliveryId}`
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

If `sam deploy --guided` asks for `GitHubWebhookSecret`, enter the webhook secret configured in your GitHub repository or organization. If it asks for `GitHubToken`, enter a GitHub token with permission to call the compare API for the target repository. With a token configured, LeakGuard treats the GitHub compare API as the primary diff source and only falls back to `inlineDiff` when the compare request fails.

If `sam deploy --guided` asks for `AutoDisableMode`, leave it as `OFF` for a detect-only deployment. Set it to `ALLOWLIST_HIGH_CONFIDENCE` only when you want LeakGuard to auto-disable verified leaked keys for IAM users that also pass the configured disable allowlist.

### 3. Run locally

```bash
sam local start-api
```

Then post a sample GitHub push payload:

```bash
curl -X POST http://127.0.0.1:3000/github/webhook \
  -H "content-type: application/json" \
  -H "x-github-event: push" \
  -H "x-github-delivery: sample-delivery-001" \
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
- `deliveryId`
- `payloadS3Key`
- `disableCount`
- `lastActionNote`
- `actionHistory`
- `disableEligible`
- `alertStatus`
- `alertChannel`
- `autoDisableMode`
- `autoDisableStatus`
- `autoDisableReason`

## Current implementation notes

- `GitHub compare API` is the primary diff source when `GITHUB_TOKEN` is configured
- `inlineDiff` is only a demo and fallback path if the compare request fails or the token is intentionally omitted
- GitHub deliveries are deduplicated in a separate DynamoDB table with TTL
- webhook ingress now only validates and enqueues; the SQS worker performs diff scanning and finding creation
- findings record `diffSource` so operators can see whether a case came from a real compare API fetch or a demo fallback
- containment is opt-in: `AutoDisableMode=ALLOWLIST_HIGH_CONFIDENCE` only auto-disables verified keys that also pass the current disable allowlist
- disable is manual, opt-in, and requires explicit confirmation in the console
- `DISABLE_ALLOWLIST_USERS` can restrict which IAM users are eligible for key disable
- `AlertEmailEndpoint` creates an SNS email subscription and enables per-finding alert publishing
- the operator console now includes a delivery audit view so the same GitHub delivery can be inspected before or after finding creation
- the current detector intentionally focuses on one high-confidence pattern: long-term AWS access key IDs

## Next high-value steps

1. Add a dead-letter queue and replay path for failed scans
2. Complete the real GitHub webhook loop with a configured webhook secret and compare API token
3. Add a second notification channel only after SNS email stays low-noise
4. Add a second detector for short-lived cloud credentials only after the AWS key flow is rock solid
