# Quick script to check Docker status
Write-Host "Checking Docker status..." -ForegroundColor Yellow

# Test Docker daemon connection
Write-Host "`n1. Testing Docker connection..." -ForegroundColor Cyan
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Docker is running!" -ForegroundColor Green
        Write-Host "   Docker version:" -ForegroundColor Gray
        docker version --format "   Client: {{.Client.Version}}, Server: {{.Server.Version}}"
    } else {
        Write-Host "   ❌ Docker is not responding" -ForegroundColor Red
        Write-Host "   Error: $dockerInfo" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Cannot connect to Docker" -ForegroundColor Red
}

# Check if Docker Desktop process is running
Write-Host "`n2. Checking Docker Desktop process..." -ForegroundColor Cyan
$dockerProcesses = Get-Process -Name "*docker*" -ErrorAction SilentlyContinue
if ($dockerProcesses) {
    Write-Host "   ✅ Docker processes found:" -ForegroundColor Green
    $dockerProcesses | ForEach-Object {
        Write-Host "      - $($_.Name) (PID: $($_.Id))" -ForegroundColor Gray
    }
} else {
    Write-Host "   ❌ No Docker processes found" -ForegroundColor Red
    Write-Host "   Docker Desktop is not running!" -ForegroundColor Yellow
}

# Check Docker Desktop service
Write-Host "`n3. Checking Docker Desktop service..." -ForegroundColor Cyan
try {
    $service = Get-Service -Name "*docker*" -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "   Services found:" -ForegroundColor Gray
        $service | ForEach-Object {
            $status = if ($_.Status -eq "Running") { "✅" } else { "❌" }
            Write-Host "      $status $($_.Name): $($_.Status)" -ForegroundColor $(if ($_.Status -eq "Running") { "Green" } else { "Red" })
        }
    } else {
        Write-Host "   ⚠️  No Docker services found (may be running as user process)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠️  Could not check services" -ForegroundColor Yellow
}

Write-Host "`n---" -ForegroundColor Gray
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Make sure Docker Desktop is fully started (wait for the whale icon in system tray)" -ForegroundColor White
Write-Host "2. Try: docker ps" -ForegroundColor White
Write-Host "3. If still failing, restart Docker Desktop" -ForegroundColor White





