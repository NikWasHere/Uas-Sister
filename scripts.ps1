# PowerShell Helper Scripts

function Start-Services {
    Write-Host 'Building and starting services...' -ForegroundColor Green
    docker compose up --build -d
    Write-Host 'Services started!' -ForegroundColor Green
}

function Stop-Services {
    Write-Host 'Stopping services...' -ForegroundColor Yellow
    docker compose down
    Write-Host 'Services stopped!' -ForegroundColor Green
}

function Stop-ServicesClean {
    Write-Host 'Stopping services and removing volumes...' -ForegroundColor Red
    docker compose down -v
    Write-Host 'Services stopped and data removed!' -ForegroundColor Green
}

function Show-Logs {
    param([string]$Service = '')
    if ($Service) {
        docker compose logs -f $Service
    } else {
        docker compose logs -f
    }
}

function Test-Health {
    Write-Host 'Checking health...' -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri 'http://localhost:8080/health' -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

function Get-Stats {
    Write-Host 'Getting stats...' -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri 'http://localhost:8080/stats' -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

function Get-Events {
    param([int]$Limit = 10, [string]$Topic = '')
    $uri = 'http://localhost:8080/events?limit=' + $Limit
    if ($Topic) { $uri += '&topic=' + $Topic }
    Write-Host 'Getting events...' -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri $uri -UseBasicParsing
    $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10
}

function Invoke-Tests {
    Write-Host 'Running tests...' -ForegroundColor Cyan
    pip install -q -r tests/requirements.txt
    pytest tests/test_aggregator.py -v
}

function Publish-TestEvent {
    param([string]$Topic = 'test.manual', [string]$EventId = 'test-' + (Get-Random), [string]$Message = 'Test')
    $event = @{
        events = @(@{
            topic = $Topic
            event_id = $EventId
            timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
            source = 'powershell'
            payload = @{ message = $Message }
        })
    } | ConvertTo-Json -Depth 10
    Write-Host 'Publishing event...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri 'http://localhost:8080/publish' -Method POST -ContentType 'application/json' -Body $event -UseBasicParsing | Out-Null
}

function Test-Deduplication {
    Write-Host '=== Testing Deduplication ===' -ForegroundColor Magenta
    $eventId = 'dedup-test-' + (Get-Random)
    $event = @{ events = @(@{ topic = 'test.dedup'; event_id = $eventId; timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ'); source = 'powershell'; payload = @{ test = 'dedup' } }) } | ConvertTo-Json -Depth 10
    
    Write-Host '1. Getting initial stats...' -ForegroundColor Cyan
    $before = Invoke-WebRequest -Uri 'http://localhost:8080/stats' -UseBasicParsing | ConvertFrom-Json
    Write-Host ('Unique: {0}, Duplicate: {1}' -f $before.unique_processed, $before.duplicate_dropped) -ForegroundColor White
    
    Write-Host '2. Sending event first time...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri 'http://localhost:8080/publish' -Method POST -ContentType 'application/json' -Body $event -UseBasicParsing | Out-Null
    Start-Sleep -Seconds 2
    
    Write-Host '3. Sending same event again (duplicate)...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri 'http://localhost:8080/publish' -Method POST -ContentType 'application/json' -Body $event -UseBasicParsing | Out-Null
    Start-Sleep -Seconds 2
    
    Write-Host '4. Getting final stats...' -ForegroundColor Cyan
    $after = Invoke-WebRequest -Uri 'http://localhost:8080/stats' -UseBasicParsing | ConvertFrom-Json
    Write-Host ('Unique: {0}, Duplicate: {1}' -f $after.unique_processed, $after.duplicate_dropped) -ForegroundColor White
    
    Write-Host '5. Verification:' -ForegroundColor Magenta
    $uDelta = $after.unique_processed - $before.unique_processed
    $dDelta = $after.duplicate_dropped - $before.duplicate_dropped
    Write-Host ('Unique delta: {0} (expected: 1)' -f $uDelta) -ForegroundColor White
    Write-Host ('Duplicate delta: {0} (expected: 1)' -f $dDelta) -ForegroundColor White
    
    if ($uDelta -eq 1 -and $dDelta -eq 1) {
        Write-Host 'PASS: Deduplication working!' -ForegroundColor Green
    } else {
        Write-Host 'FAIL: Deduplication test failed!' -ForegroundColor Red
    }
    Write-Host '=== Deduplication Test Complete ===' -ForegroundColor Magenta
}

function Test-Persistence {
    Write-Host '=== Testing Persistence ===' -ForegroundColor Magenta
    Write-Host '1. Getting current stats...' -ForegroundColor Cyan
    $before = Invoke-WebRequest -Uri 'http://localhost:8080/stats' -UseBasicParsing | ConvertFrom-Json
    Write-Host ('Before: Received={0}, Unique={1}' -f $before.received, $before.unique_processed) -ForegroundColor White
    
    Write-Host '2. Stopping containers...' -ForegroundColor Yellow
    docker compose down
    Start-Sleep -Seconds 2
    
    Write-Host '3. Verifying volumes exist...' -ForegroundColor Cyan
    docker volume ls | Select-String 'uas'
    
    Write-Host '4. Restarting aggregator...' -ForegroundColor Green
    docker compose up -d storage broker aggregator
    Write-Host 'Waiting for ready...' -ForegroundColor Yellow
    Start-Sleep -Seconds 20
    
    Write-Host '5. Getting stats after restart...' -ForegroundColor Cyan
    $after = Invoke-WebRequest -Uri 'http://localhost:8080/stats' -UseBasicParsing | ConvertFrom-Json
    Write-Host ('After: Received={0}, Unique={1}' -f $after.received, $after.unique_processed) -ForegroundColor White
    
    Write-Host '6. Verification:' -ForegroundColor Magenta
    if ($before.received -eq $after.received -and $before.unique_processed -eq $after.unique_processed) {
        Write-Host 'PASS: Data persisted!' -ForegroundColor Green
    } else {
        Write-Host 'FAIL: Data mismatch!' -ForegroundColor Red
    }
    Write-Host '=== Persistence Test Complete ===' -ForegroundColor Magenta
}

function Start-QuickDemo {
    Write-Host '=== Quick Demo ===' -ForegroundColor Magenta
    docker compose up --build -d
    Start-Sleep -Seconds 30
    Test-Health
    Get-Stats
    Get-Events -Limit 5
    Write-Host '=== Demo Complete ===' -ForegroundColor Magenta
}

Write-Host ''
Write-Host 'PowerShell Helper Scripts Loaded!' -ForegroundColor Green
Write-Host 'Commands: Start-Services, Stop-Services, Stop-ServicesClean' -ForegroundColor Cyan
Write-Host '          Test-Health, Get-Stats, Get-Events, Invoke-Tests' -ForegroundColor Cyan
Write-Host '          Publish-TestEvent, Test-Deduplication, Test-Persistence' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Example: Start-Services' -ForegroundColor Yellow
Write-Host ''
