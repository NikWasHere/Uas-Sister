# PowerShell Helper Scripts
# Untuk Windows users yang tidak bisa gunakan Makefile

# Build and start services
function Start-Services {
    Write-Host "Building and starting services..." -ForegroundColor Green
    docker compose up --build -d
    Write-Host "Services started!" -ForegroundColor Green
}

# Stop services
function Stop-Services {
    Write-Host "Stopping services..." -ForegroundColor Yellow
    docker compose down
    Write-Host "Services stopped!" -ForegroundColor Green
}

# Stop and remove all data
function Stop-ServicesClean {
    Write-Host "Stopping services and removing volumes..." -ForegroundColor Red
    docker compose down -v
    Write-Host "Services stopped and data removed!" -ForegroundColor Green
}

# View logs
function Show-Logs {
    param(
        [string]$Service = ""
    )
    if ($Service) {
        docker compose logs -f $Service
    } else {
        docker compose logs -f
    }
}

# Check health
function Test-Health {
    Write-Host "Checking aggregator health..." -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

# Get stats
function Get-Stats {
    Write-Host "Getting aggregator statistics..." -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri "http://localhost:8080/stats" -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

# Get events
function Get-Events {
    param(
        [int]$Limit = 10,
        [string]$Topic = ""
    )
    
    $uri = "http://localhost:8080/events?limit=$Limit"
    if ($Topic) {
        $uri += "&topic=$Topic"
    }
    
    Write-Host "Getting events..." -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri $uri -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

# Run tests
function Invoke-Tests {
    Write-Host "Installing test dependencies..." -ForegroundColor Cyan
    pip install -r tests/requirements.txt
    
    Write-Host "Running tests..." -ForegroundColor Cyan
    pytest tests/test_aggregator.py -v
}

# Publish test event
function Publish-TestEvent {
    param(
        [string]$Topic = "test.manual",
        [string]$EventId = "test-$(Get-Random)",
        [string]$Message = "Test message"
    )
    
    $event = @{
        events = @(
            @{
                topic = $Topic
                event_id = $EventId
                timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                source = "powershell"
                payload = @{
                    message = $Message
                }
            }
        )
    } | ConvertTo-Json -Depth 10
    
    Write-Host "Publishing event..." -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri "http://localhost:8080/publish" `
        -Method POST `
        -ContentType "application/json" `
        -Body $event `
        -UseBasicParsing
    
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

# Demo persistence
function Test-Persistence {
    Write-Host "=== Testing Persistence ===" -ForegroundColor Magenta
    
    Write-Host "`n1. Getting current stats..." -ForegroundColor Cyan
    $statsBefore = Invoke-WebRequest -Uri "http://localhost:8080/stats" -UseBasicParsing | ConvertFrom-Json
    Write-Host "Stats before: $($statsBefore | ConvertTo-Json -Compress)" -ForegroundColor White
    
    Write-Host "`n2. Stopping containers..." -ForegroundColor Yellow
    docker compose down
    Start-Sleep -Seconds 2
    
    Write-Host "`n3. Verifying volumes exist..." -ForegroundColor Cyan
    docker volume ls | Select-String "uas"
    
    Write-Host "`n4. Restarting aggregator..." -ForegroundColor Green
    docker compose up -d aggregator
    Write-Host "Waiting for service to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
    
    Write-Host "`n5. Getting stats after restart..." -ForegroundColor Cyan
    $statsAfter = Invoke-WebRequest -Uri "http://localhost:8080/stats" -UseBasicParsing | ConvertFrom-Json
    Write-Host "Stats after: $($statsAfter | ConvertTo-Json -Compress)" -ForegroundColor White
    
    Write-Host "`n6. Verification:" -ForegroundColor Magenta
    if ($statsBefore.received -eq $statsAfter.received) {
        Write-Host "✓ Received count matches!" -ForegroundColor Green
    } else {
        Write-Host "✗ Received count mismatch!" -ForegroundColor Red
    }
    
    if ($statsBefore.unique_processed -eq $statsAfter.unique_processed) {
        Write-Host "✓ Unique processed count matches!" -ForegroundColor Green
    } else {
        Write-Host "✗ Unique processed count mismatch!" -ForegroundColor Red
    }
    
    Write-Host "`n=== Persistence Test Complete ===" -ForegroundColor Magenta
}

# Demo duplicate detection
function Test-Deduplication {
    Write-Host "=== Testing Deduplication ===" -ForegroundColor Magenta
    
    $eventId = "dedup-test-$(Get-Random)"
    $event = @{
        events = @(
            @{
                topic = "test.dedup"
                event_id = $eventId
                timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                source = "powershell"
                payload = @{ test = "deduplication" }
            }
        )
    } | ConvertTo-Json -Depth 10
    
    Write-Host "`n1. Getting initial stats..." -ForegroundColor Cyan
    $statsBefore = Invoke-WebRequest -Uri "http://localhost:8080/stats" -UseBasicParsing | ConvertFrom-Json
    Write-Host "Unique: $($statsBefore.unique_processed), Duplicate: $($statsBefore.duplicate_dropped)" -ForegroundColor White
    
    Write-Host "`n2. Sending event first time..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $event -UseBasicParsing | Out-Null
    Start-Sleep -Seconds 2
    
    Write-Host "`n3. Sending same event again (duplicate)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "http://localhost:8080/publish" -Method POST -ContentType "application/json" -Body $event -UseBasicParsing | Out-Null
    Start-Sleep -Seconds 2
    
    Write-Host "`n4. Getting final stats..." -ForegroundColor Cyan
    $statsAfter = Invoke-WebRequest -Uri "http://localhost:8080/stats" -UseBasicParsing | ConvertFrom-Json
    Write-Host "Unique: $($statsAfter.unique_processed), Duplicate: $($statsAfter.duplicate_dropped)" -ForegroundColor White
    
    Write-Host "`n5. Verification:" -ForegroundColor Magenta
    $uniqueDelta = $statsAfter.unique_processed - $statsBefore.unique_processed
    $dupDelta = $statsAfter.duplicate_dropped - $statsBefore.duplicate_dropped
    
    Write-Host "Unique delta: $uniqueDelta (expected: 1)" -ForegroundColor White
    Write-Host "Duplicate delta: $dupDelta (expected: 1)" -ForegroundColor White
    
    if ($uniqueDelta -eq 1 -and $dupDelta -eq 1) {
        Write-Host "✓ Deduplication working correctly!" -ForegroundColor Green
    } else {
        Write-Host "✗ Deduplication test failed!" -ForegroundColor Red
    }
    
    Write-Host "`n=== Deduplication Test Complete ===" -ForegroundColor Magenta
}

# Quick start
function Start-QuickDemo {
    Write-Host "=== Quick Demo Sequence ===" -ForegroundColor Magenta
    
    Write-Host "`n1. Building and starting services..." -ForegroundColor Cyan
    docker compose up --build -d
    
    Write-Host "`n2. Waiting for services to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
    
    Write-Host "`n3. Checking health..." -ForegroundColor Cyan
    Test-Health
    
    Write-Host "`n4. Showing stats..." -ForegroundColor Cyan
    Get-Stats
    
    Write-Host "`n5. Showing recent events..." -ForegroundColor Cyan
    Get-Events -Limit 5
    
    Write-Host "`n=== Quick Demo Complete ===" -ForegroundColor Magenta
    Write-Host "Use Get-Stats, Get-Events, Publish-TestEvent for more interactions" -ForegroundColor Yellow
}

# Export functions
Export-ModuleMember -Function *

# Display available functions
Write-Host "`nAvailable commands:" -ForegroundColor Green
Write-Host "  Start-Services          - Build and start all services" -ForegroundColor Cyan
Write-Host "  Stop-Services           - Stop all services (keep data)" -ForegroundColor Cyan
Write-Host "  Stop-ServicesClean      - Stop services and remove data" -ForegroundColor Cyan
Write-Host "  Show-Logs [service]     - View logs" -ForegroundColor Cyan
Write-Host "  Test-Health             - Check aggregator health" -ForegroundColor Cyan
Write-Host "  Get-Stats               - Get statistics" -ForegroundColor Cyan
Write-Host "  Get-Events              - Get recent events" -ForegroundColor Cyan
Write-Host "  Invoke-Tests            - Run pytest suite" -ForegroundColor Cyan
Write-Host "  Publish-TestEvent       - Send test event" -ForegroundColor Cyan
Write-Host "  Test-Persistence        - Demo persistence" -ForegroundColor Cyan
Write-Host "  Test-Deduplication      - Demo deduplication" -ForegroundColor Cyan
Write-Host "  Start-QuickDemo         - Run quick demo" -ForegroundColor Cyan
Write-Host "`nExample: Start-Services" -ForegroundColor Yellow
