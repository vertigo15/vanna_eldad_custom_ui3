#!/usr/bin/env pwsh
# Vanna Training Data Validation Test Runner

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Vanna 2.0 Training Data Validation Test Runner            ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check if services are running
Write-Host "🔍 Checking if services are running..." -ForegroundColor Yellow
$dockerStatus = docker-compose ps --format json 2>$null | ConvertFrom-Json

if (-not $dockerStatus) {
    Write-Host "❌ Docker services are not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the services first:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d" -ForegroundColor White
    Write-Host ""
    exit 1
}

$vannaAppRunning = $false
foreach ($service in $dockerStatus) {
    if ($service.Service -eq "vanna-app" -and $service.State -eq "running") {
        $vannaAppRunning = $true
        break
    }
}

if (-not $vannaAppRunning) {
    Write-Host "❌ vanna-app service is not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the services first:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✅ Services are running" -ForegroundColor Green
Write-Host ""

# Check if API is accessible
Write-Host "🔍 Checking API connectivity..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ API is accessible" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Cannot connect to API at http://localhost:8000" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure vanna-app is healthy:" -ForegroundColor Yellow
    Write-Host "  docker-compose logs vanna-app" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host ""

# Check if requests library is installed
Write-Host "🔍 Checking Python dependencies..." -ForegroundColor Yellow
$pipList = pip list 2>&1
if ($pipList -match "requests") {
    Write-Host "✅ Python requests library is installed" -ForegroundColor Green
} else {
    Write-Host "⚠️  requests library not found, installing..." -ForegroundColor Yellow
    pip install requests
}

Write-Host ""

# Ask user if they want to load training data first
Write-Host "❓ Have you loaded the training data?" -ForegroundColor Yellow
Write-Host "   If not, tests may fail." -ForegroundColor Gray
Write-Host ""
$loadData = Read-Host "Load training data now? (y/N)"

if ($loadData -eq "y" -or $loadData -eq "Y") {
    Write-Host ""
    Write-Host "📚 Loading training data..." -ForegroundColor Cyan
    docker exec -it vanna-app python scripts/load_training_data.py
    Write-Host ""
    Write-Host "✅ Training data loaded" -ForegroundColor Green
    Write-Host ""
    Start-Sleep -Seconds 2
}

# Run tests
Write-Host ""
Write-Host "🚀 Running tests..." -ForegroundColor Cyan
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host ""

python tests/test_training_data_usage.py

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host ""

# Check results
if (Test-Path "tests/test_results.json") {
    Write-Host "📄 Detailed results saved to: tests/test_results.json" -ForegroundColor Cyan
    
    # Parse and display summary
    try {
        $results = Get-Content "tests/test_results.json" | ConvertFrom-Json
        $passRate = ($results.passed_tests / $results.total_tests) * 100
        
        Write-Host ""
        Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
        Write-Host "║                      FINAL SUMMARY                             ║" -ForegroundColor Cyan
        Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  Total Tests:  $($results.total_tests)" -ForegroundColor White
        Write-Host "  Passed:       $($results.passed_tests) ✅" -ForegroundColor Green
        Write-Host "  Failed:       $($results.total_tests - $results.passed_tests) ❌" -ForegroundColor Red
        Write-Host "  Success Rate: $([math]::Round($passRate, 1))%" -ForegroundColor $(if ($passRate -eq 100) { "Green" } elseif ($passRate -ge 80) { "Yellow" } else { "Red" })
        Write-Host ""
        
        if ($results.passed_tests -eq $results.total_tests) {
            Write-Host "🎉 All tests passed! Training data is working perfectly." -ForegroundColor Green
        } elseif ($passRate -ge 80) {
            Write-Host "⚠️  Most tests passed. Review failed tests in test_results.json" -ForegroundColor Yellow
        } else {
            Write-Host "❌ Many tests failed. Check:" -ForegroundColor Red
            Write-Host "   1. Is training data loaded?" -ForegroundColor Yellow
            Write-Host "   2. Is the database connected?" -ForegroundColor Yellow
            Write-Host "   3. Review logs: docker-compose logs vanna-app" -ForegroundColor Yellow
        }
        
    } catch {
        Write-Host "⚠️  Could not parse results file" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  No results file generated" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host ""

exit $exitCode
