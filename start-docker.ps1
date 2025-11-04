# Script to start Docker Desktop on Windows

Write-Host "=== Starting Docker Desktop ===" -ForegroundColor Cyan

# Check if Docker Desktop process exists
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if ($dockerProcess) {
    Write-Host "✅ Docker Desktop is already running!" -ForegroundColor Green
    exit 0
}

Write-Host "`n1. Starting Docker Desktop service..." -ForegroundColor Yellow
try {
    # Try to start the Docker service
    Start-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    Write-Host "   Service start command sent" -ForegroundColor Gray
} catch {
    Write-Host "   Service start failed (may need admin rights)" -ForegroundColor Yellow
}

Write-Host "`n2. Launching Docker Desktop application..." -ForegroundColor Yellow

# Find Docker Desktop executable
$dockerPaths = @(
    "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
    "${env:LOCALAPPDATA}\Programs\Docker\Docker\Docker Desktop.exe"
)

$dockerFound = $false
foreach ($path in $dockerPaths) {
    if (Test-Path $path) {
        Write-Host "   Found Docker Desktop at: $path" -ForegroundColor Gray
        Start-Process -FilePath $path
        $dockerFound = $true
        break
    }
}

if (-not $dockerFound) {
    Write-Host "❌ Could not find Docker Desktop executable" -ForegroundColor Red
    Write-Host "Please start Docker Desktop manually from:" -ForegroundColor Yellow
    Write-Host "   Start Menu → Docker Desktop" -ForegroundColor White
    exit 1
}

Write-Host "   ✅ Docker Desktop launch command sent" -ForegroundColor Green

Write-Host "`n3. Waiting for Docker Desktop to start..." -ForegroundColor Yellow
Write-Host "   (This can take 30-60 seconds)" -ForegroundColor Gray

$maxWait = 60
$waited = 0
$interval = 3

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds $interval
    $waited += $interval
    
    # Test if Docker is responding
    $dockerTest = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker Desktop is ready!" -ForegroundColor Green
        Write-Host "`n✅ Docker is now running. You can proceed with deployment!" -ForegroundColor Green
        exit 0
    }
    
    Write-Host "   Still waiting... ($waited/$maxWait seconds)" -ForegroundColor Gray
}

Write-Host "`n⚠️  Docker Desktop may still be starting" -ForegroundColor Yellow
Write-Host "Please wait a bit longer, then run:" -ForegroundColor Yellow
Write-Host "   docker ps" -ForegroundColor White
Write-Host "If that works, Docker is ready!" -ForegroundColor Yellow





