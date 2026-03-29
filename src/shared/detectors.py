import re


AWS_ACCESS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")


def redact_secret(value):
    if len(value) <= 8:
        return value[0:2] + "***"
    return value[:4] + "..." + value[-4:]


def extract_aws_access_key_findings(diff_text):
    findings = []
    if not diff_text:
        return findings

    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue

        matches = AWS_ACCESS_KEY_PATTERN.findall(line)
        for match in matches:
            findings.append(
                {
                    "secretType": "AWS_ACCESS_KEY_ID",
                    "matchedKeyId": match,
                    "matchedKeyIdRedacted": redact_secret(match),
                    "evidenceSnippet": line[:500],
                    "severity": "HIGH",
                    "confidence": "HIGH",
                }
            )

    return findings
