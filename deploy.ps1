# deploy.ps1 — package Lambda code and run the infrastructure setup
# Prerequisites: AWS CLI configured, Python 3.12+, pip

param(
    [string]$Region = "us-east-1"
)

$env:AWS_REGION = $Region

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet

Write-Host "Running AWS setup..." -ForegroundColor Cyan
python infrastructure/setup_aws.py

Write-Host "`nDeploy complete." -ForegroundColor Green
