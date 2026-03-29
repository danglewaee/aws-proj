param(
    [Parameter(Mandatory = $true)]
    [string]$BucketName,

    [Parameter(Mandatory = $true)]
    [string]$ApiBaseUrl,

    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

function Invoke-AwsCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$IgnoreErrors,
        [switch]$ReturnOutput
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()

    try {
        $process = Start-Process `
            -FilePath "aws" `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $stdout = Get-Content -Path $stdoutPath -Raw
        $stderr = Get-Content -Path $stderrPath -Raw

        if (-not $IgnoreErrors -and $process.ExitCode -ne 0) {
            $message = if ([string]::IsNullOrWhiteSpace($stderr)) {
                "aws command failed: aws $($Arguments -join ' ')"
            } else {
                $stderr.Trim()
            }

            throw $message
        }

        if ($ReturnOutput) {
            return [PSCustomObject]@{
                ExitCode = $process.ExitCode
                StdOut   = $stdout
                StdErr   = $stderr
            }
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrPath -ErrorAction SilentlyContinue
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendPath = Join-Path $projectRoot "frontend"
$configPath = Join-Path $frontendPath "config.js"
$policyPath = Join-Path $projectRoot "bucket-policy.json"

$configContent = @"
window.LEAK_GUARD_CONFIG = {
    apiBaseUrl: "$ApiBaseUrl"
};
"@

Set-Content -Path $configPath -Value $configContent -Encoding ascii

$policy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BucketName/*"
    }
  ]
}
"@

Set-Content -Path $policyPath -Value $policy -Encoding ascii

$headBucket = Invoke-AwsCli -Arguments @("s3api", "head-bucket", "--bucket", $BucketName) -IgnoreErrors -ReturnOutput
if ($headBucket.ExitCode -ne 0) {
    Invoke-AwsCli -Arguments @("s3", "mb", "s3://$BucketName", "--region", $Region)
}

Invoke-AwsCli -Arguments @(
    "s3api", "put-public-access-block",
    "--bucket", $BucketName,
    "--public-access-block-configuration", "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
)

Invoke-AwsCli -Arguments @(
    "s3api", "put-bucket-policy",
    "--bucket", $BucketName,
    "--policy", "file://$policyPath"
)

Invoke-AwsCli -Arguments @(
    "s3", "website", "s3://$BucketName/",
    "--index-document", "index.html",
    "--error-document", "index.html"
)

Invoke-AwsCli -Arguments @(
    "s3", "sync", $frontendPath, "s3://$BucketName",
    "--delete"
)

Remove-Item -LiteralPath $policyPath

$websiteUrl = "http://{0}.s3-website-{1}.amazonaws.com" -f $BucketName, $Region
Write-Host ""
Write-Host "Frontend published to: $websiteUrl"
