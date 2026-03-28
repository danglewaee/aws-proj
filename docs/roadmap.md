# Roadmap

## Week 1

- deploy `API Gateway`, `Lambda`, `DynamoDB`, and `S3`
- accept webhook payloads through `POST /webhooks/{source}`
- persist raw payload and summary metadata

## Week 2

- finish operator console event list
- add event detail page behavior
- filter by `status`, `source`, and `eventType`

## Week 3

- implement replay state changes
- store replay artifacts in `S3`
- improve logs and correlation tracing

## Week 4

- polish demo flow
- add screenshots and architecture diagrams
- prepare interview pitch and demo script

## Explicit non-goals for V1

- multi-tenant support
- provider-specific cryptographic signature verification
- Slack or email alerting
- dead-letter queue orchestration
- long-running workflow engines
