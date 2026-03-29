param(
    [string]$StackName = "leakguard",
    [string]$Region = "us-east-1"
)

$api = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --region $Region `
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" `
  --output text

if (-not $api -or $api -eq "None") {
    throw "Could not resolve ApiBaseUrl for stack '$StackName' in region '$Region'."
}

$payloadUrl = "$($api.TrimEnd('/'))/github/webhook"

Write-Host ""
Write-Host "LeakGuard GitHub webhook configuration" -ForegroundColor Cyan
Write-Host "------------------------------------" -ForegroundColor Cyan
Write-Host "Stack:        $StackName"
Write-Host "Region:       $Region"
Write-Host "API base URL: $api"
Write-Host "Payload URL:  $payloadUrl"
Write-Host ""
Write-Host "GitHub webhook settings" -ForegroundColor Yellow
Write-Host "- Content type: application/json"
Write-Host "- Secret: use the same value you deployed as GitHubWebhookSecret"
Write-Host "- Events: Just the push event"
Write-Host ""
Write-Host "GitHub token requirements" -ForegroundColor Yellow
Write-Host "- Fine-grained personal access token"
Write-Host "- Repository access: only the repo you are testing"
Write-Host "- Permissions: Contents = Read-only"
Write-Host ""
Write-Host "Expected result after a real push" -ForegroundColor Yellow
Write-Host "- A new delivery appears in the Deliveries panel"
Write-Host "- A new finding shows Diff source = GITHUB_COMPARE_API"
Write-Host "- Delivery ID is no longer sample-*"
Write-Host ""
