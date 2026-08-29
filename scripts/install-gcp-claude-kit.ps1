$ErrorActionPreference = "Stop"

Write-Host "RevenueFlow AI - GCP + Claude Code Dev Kit"

function Need-Cmd($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "[MISSING] $name"
        return $false
    }
    Write-Host "[OK] $name"
    return $true
}

$gcloudOk = Need-Cmd "gcloud"
$claudeOk = Need-Cmd "claude"

if (-not $gcloudOk) {
    Write-Host "Install Google Cloud CLI from the official Google Cloud documentation, then rerun this script."
}
if (-not $claudeOk) {
    Write-Host "Install Claude Code from Anthropic's official installation instructions, then rerun this script."
}
if (-not ($gcloudOk -and $claudeOk)) { exit 1 }

Write-Host ""
Write-Host "Authenticate interactively:"
gcloud auth login

$adc = Read-Host "Configure Application Default Credentials too? (y/N)"
if ($adc -match '^[Yy]$') {
    gcloud auth application-default login
}

$project = Read-Host "GCP PROJECT_ID"
if ([string]::IsNullOrWhiteSpace($project)) {
    throw "PROJECT_ID is required"
}

gcloud config set project $project

Write-Host ""
Write-Host "Active account:"
gcloud config get-value account

Write-Host "Active project:"
gcloud config get-value project

Write-Host ""
Write-Host "Project .mcp.json is already configured for Google Cloud CLI remote MCP."
Write-Host "Open Claude Code from the repository root and verify MCP connectivity."
Write-Host ""
Write-Host "No APIs were enabled and no infrastructure was deployed by this installer."
