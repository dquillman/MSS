#!/usr/bin/env pwsh
<#
.SYNOPSIS
    MSS Cloud Deployment - Streamlined version (no local Docker testing)

.DESCRIPTION
    Validates files, commits to GitHub, and triggers Cloud Run deployment via GitHub Actions.
    Skips local Docker build/test - lets GitHub Actions handle everything.

.PARAMETER Validate
    Only validate files and environment

.PARAMETER Deploy
    Validate, commit, push to GitHub, and trigger deployment

.PARAMETER Monitor
    Monitor the GitHub Actions deployment

.PARAMETER All
    Run complete workflow: validate, deploy, and monitor

.EXAMPLE
    .\Deploy-MSS-Cloud.ps1 -All
    .\Deploy-MSS-Cloud.ps1 -Deploy
    .\Deploy-MSS-Cloud.ps1 -Validate
#>

param(
    [switch]$Validate,
    [switch]$Deploy,
    [switch]$Monitor,
    [switch]$All
)

# Color output functions
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Write-Error { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Warning { param($msg) Write-Host "[WARNING] $msg" -ForegroundColor Yellow }
function Write-Header { param($msg) Write-Host "`n========================================" -ForegroundColor Magenta; Write-Host "   $msg" -ForegroundColor Magenta; Write-Host "========================================`n" -ForegroundColor Magenta }

# Error handling
$ErrorActionPreference = "Continue"

# Validate environment
function Test-Environment {
    Write-Header "MSS Cloud Deployment - Validation"
    
    Write-Info "Validating environment..."
    
    # Check git
    try {
        $gitVersion = git --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Git found: $gitVersion"
        } else {
            Write-Error "Git not found. Please install Git."
            return $false
        }
    } catch {
        Write-Error "Git not found. Please install Git."
        return $false
    }
    
    # Check gcloud (optional but recommended)
    try {
        $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "gcloud found: $gcloudVersion"
        } else {
            Write-Warning "gcloud not found (optional for monitoring)"
        }
    } catch {
        Write-Warning "gcloud not found (optional for monitoring)"
    }
    
    # Check required files
    $requiredFiles = @(
        ".env",
        "Dockerfile.app",
        "entrypoint-app.sh",
        "web\api_server.py",
        "requirements.txt",
        ".github\workflows\gcp-deploy.yml"
    )
    
    foreach ($file in $requiredFiles) {
        if (Test-Path $file) {
            Write-Success "$file exists"
        } else {
            Write-Error "$file is missing!"
            return $false
        }
    }
    
    # Check git repository
    if (Test-Path ".git") {
        Write-Success "Git repository initialized"
        
        # Check remote
        try {
            $remote = git remote get-url origin 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Git remote configured: $remote"
            } else {
                Write-Error "Git remote not configured. Run: git remote add origin <your-repo-url>"
                return $false
            }
        } catch {
            Write-Error "Git remote not configured."
            return $false
        }
    } else {
        Write-Error "Not a git repository. Run: git init"
        return $false
    }
    
    Write-Success "All validations passed!"
    return $true
}

# Deploy to GitHub (triggers Cloud Run deployment)
function Start-Deployment {
    Write-Header "Deploying to Cloud Run via GitHub Actions"
    
    Write-Info "Checking for changes..."
    
    # Check git status
    $status = git status --porcelain 2>&1
    
    if ([string]::IsNullOrWhiteSpace($status)) {
        Write-Info "No changes detected. Checking if we need to push..."
        
        # Check if local is behind remote
        git fetch origin 2>&1 | Out-Null
        $behind = git rev-list HEAD..origin/main --count 2>&1
        $ahead = git rev-list origin/main..HEAD --count 2>&1
        
        if ($ahead -gt 0) {
            Write-Info "Local commits ahead of remote. Pushing..."
        } elseif ($behind -gt 0) {
            Write-Warning "Local branch is behind remote. Pull first: git pull origin main"
            return $false
        } else {
            Write-Info "Already up to date with remote. Triggering re-deployment..."
            Write-Info "Creating empty commit to trigger deployment..."
            git commit --allow-empty -m "Trigger deployment - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" 2>&1 | Out-Null
        }
    } else {
        Write-Info "Changes detected. Staging files..."
        
        # Add all changes
        git add . 2>&1 | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to stage files"
            return $false
        }
        
        Write-Success "Files staged"
        
        # Commit changes
        $commitMsg = "Deploy MSS - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Write-Info "Committing changes: $commitMsg"
        
        git commit -m $commitMsg 2>&1 | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to commit changes"
            return $false
        }
        
        Write-Success "Changes committed"
    }
    
    # Push to GitHub
    Write-Info "Pushing to GitHub..."
    
    $branch = git branch --show-current 2>&1
    Write-Info "Current branch: $branch"
    
    git push origin $branch 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push to GitHub"
        Write-Info "You may need to authenticate. Try: gh auth login"
        return $false
    }
    
    Write-Success "Pushed to GitHub successfully!"
    Write-Success "GitHub Actions will now build and deploy to Cloud Run"
    
    # Get repository info
    $remote = git remote get-url origin 2>&1
    if ($remote -match "github\.com[:/](.+?)(?:\.git)?$") {
        $repoPath = $matches[1]
        $actionsUrl = "https://github.com/$repoPath/actions"
        Write-Info "Monitor deployment at: $actionsUrl"
    }
    
    return $true
}

# Monitor deployment
function Watch-Deployment {
    Write-Header "Monitoring Deployment"
    
    # Get repository info
    $remote = git remote get-url origin 2>&1
    if ($remote -match "github\.com[:/](.+?)(?:\.git)?$") {
        $repoPath = $matches[1]
        $actionsUrl = "https://github.com/$repoPath/actions"
        
        Write-Info "Opening GitHub Actions in browser..."
        Start-Process $actionsUrl
        
        Write-Info "Checking latest workflow run..."
        
        # Try to use gh CLI if available
        try {
            $ghVersion = gh --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Info "Using GitHub CLI to monitor..."
                gh run list --limit 5
                Write-Info "`nTo watch live: gh run watch"
            } else {
                Write-Info "Install GitHub CLI for live monitoring: https://cli.github.com/"
            }
        } catch {
            Write-Info "Install GitHub CLI for live monitoring: https://cli.github.com/"
        }
    } else {
        Write-Warning "Could not parse repository URL"
    }
    
    Write-Info "`nDeployment typically takes 3-5 minutes"
    Write-Info "Check the GitHub Actions page for real-time status"
}

# Main execution
function Main {
    $scriptDir = $PSScriptRoot
    if ($scriptDir) {
        Set-Location $scriptDir
    }
    
    # If no parameters, show help
    if (-not ($Validate -or $Deploy -or $Monitor -or $All)) {
        Write-Header "MSS Cloud Deployment"
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  .\Deploy-MSS-Cloud.ps1 -All        # Complete workflow" -ForegroundColor Cyan
        Write-Host "  .\Deploy-MSS-Cloud.ps1 -Validate   # Only validate" -ForegroundColor Cyan
        Write-Host "  .\Deploy-MSS-Cloud.ps1 -Deploy     # Deploy to cloud" -ForegroundColor Cyan
        Write-Host "  .\Deploy-MSS-Cloud.ps1 -Monitor    # Monitor deployment" -ForegroundColor Cyan
        Write-Host ""
        return
    }
    
    $success = $true
    
    # Validate
    if ($Validate -or $Deploy -or $All) {
        $success = Test-Environment
        if (-not $success) {
            Write-Error "Validation failed. Please fix errors and try again."
            exit 1
        }
    }
    
    # Deploy
    if (($Deploy -or $All) -and $success) {
        $success = Start-Deployment
        if (-not $success) {
            Write-Error "Deployment failed. Check errors above."
            exit 1
        }
    }
    
    # Monitor
    if (($Monitor -or $All) -and $success) {
        Watch-Deployment
    }
    
    if ($success) {
        Write-Header "Deployment Complete!"
        Write-Success "Your app will be live on Cloud Run in a few minutes"
        Write-Info "Next steps:"
        Write-Info "  1. Monitor GitHub Actions for deployment status"
        Write-Info "  2. Check Cloud Run console for the service URL"
        Write-Info "  3. Test your application endpoints"
    }
}

# Run main function
Main