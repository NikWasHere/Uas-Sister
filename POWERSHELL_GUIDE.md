# Cara Menggunakan PowerShell Scripts

File `scripts.ps1` berisi helper functions untuk memudahkan development dan testing di Windows.

## 🚀 Setup (Satu kali saja)

### 1. Buka PowerShell sebagai Administrator

```powershell
# Cek execution policy
Get-ExecutionPolicy

# Jika Restricted, ubah menjadi RemoteSigned
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2. Load Scripts

```powershell
# Navigate ke project directory
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"

# Load scripts
. .\scripts.ps1
```

**Output:**
```
Available commands:
  Start-Services          - Build and start all services
  Stop-Services           - Stop all services (keep data)
  Stop-ServicesClean      - Stop services and remove data
  ...
```

---

## 📚 Available Commands

### Basic Operations

#### `Start-Services`
Build dan start semua services.

```powershell
Start-Services
```

**Output:**
```
Building and starting services...
[+] Running 5/5
 ✔ Container uas-storage     Healthy
 ✔ Container uas-broker      Healthy
 ✔ Container uas-aggregator  Healthy
 ✔ Container uas-publisher   Started
Services started!
```

#### `Stop-Services`
Stop semua services tapi keep volumes (data tidak hilang).

```powershell
Stop-Services
```

#### `Stop-ServicesClean`
Stop services DAN remove volumes (data hilang).

```powershell
Stop-ServicesClean
```

**⚠️ Warning:** Data akan hilang! Gunakan hanya untuk cleanup.

---

### Monitoring

#### `Test-Health`
Check aggregator health status.

```powershell
Test-Health
```

**Output:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2025-12-17T10:30:00.000Z"
}
```

#### `Get-Stats`
Get aggregator statistics.

```powershell
Get-Stats
```

**Output:**
```json
{
  "received": 20000,
  "unique_processed": 14000,
  "duplicate_dropped": 6000,
  "topics": 10,
  "uptime_seconds": 123.45,
  "status": "healthy"
}
```

#### `Get-Events`
Get recent events.

```powershell
# Default: 10 events
Get-Events

# Custom limit
Get-Events -Limit 5

# Filter by topic
Get-Events -Topic "user.login"

# Both
Get-Events -Limit 20 -Topic "order.created"
```

#### `Show-Logs`
View service logs.

```powershell
# All services
Show-Logs

# Specific service
Show-Logs -Service aggregator
Show-Logs -Service publisher
Show-Logs -Service storage
```

---

### Publishing Events

#### `Publish-TestEvent`
Publish single test event.

```powershell
# Default event
Publish-TestEvent

# Custom topic
Publish-TestEvent -Topic "test.custom"

# Custom event ID
Publish-TestEvent -EventId "custom-123"

# Custom message
Publish-TestEvent -Message "Hello from PowerShell"

# All together
Publish-TestEvent -Topic "demo.test" -EventId "demo-1" -Message "Demo event"
```

**Output:**
```json
{
  "status": "accepted",
  "queued": 1,
  "message": "Events queued for processing"
}
```

---

### Testing & Demos

#### `Invoke-Tests`
Run full test suite.

```powershell
Invoke-Tests
```

**Output:**
```
Installing test dependencies...
Running tests...
==================== 18 passed in 45.67s ====================
```

#### `Test-Deduplication`
Automated demo of deduplication feature.

```powershell
Test-Deduplication
```

**What it does:**
1. Get initial stats
2. Send event first time
3. Send same event again (duplicate)
4. Verify: unique +1, duplicate +1

**Output:**
```
=== Testing Deduplication ===

1. Getting initial stats...
Unique: 100, Duplicate: 50

2. Sending event first time...

3. Sending same event again (duplicate)...

4. Getting final stats...
Unique: 101, Duplicate: 51

5. Verification:
Unique delta: 1 (expected: 1)
Duplicate delta: 1 (expected: 1)
✓ Deduplication working correctly!

=== Deduplication Test Complete ===
```

#### `Test-Persistence`
Automated demo of persistence feature.

```powershell
Test-Persistence
```

**What it does:**
1. Get current stats
2. Stop all containers
3. Verify volumes still exist
4. Restart aggregator
5. Verify stats unchanged

**Output:**
```
=== Testing Persistence ===

1. Getting current stats...
Stats before: {"received":20000,"unique_processed":14000,...}

2. Stopping containers...

3. Verifying volumes exist...
uas_pg_data
uas_broker_data
uas_aggregator_logs

4. Restarting aggregator...
Waiting for service to be ready...

5. Getting stats after restart...
Stats after: {"received":20000,"unique_processed":14000,...}

6. Verification:
✓ Received count matches!
✓ Unique processed count matches!

=== Persistence Test Complete ===
```

#### `Start-QuickDemo`
Run complete demo sequence.

```powershell
Start-QuickDemo
```

**What it does:**
1. Build and start all services
2. Wait for ready
3. Check health
4. Show stats
5. Show recent events

---

## 💡 Typical Workflows

### Workflow 1: First Time Setup

```powershell
# Load scripts
. .\scripts.ps1

# Start everything
Start-Services

# Wait a bit for publisher to finish
Start-Sleep -Seconds 120

# Check results
Get-Stats
Get-Events -Limit 5
```

### Workflow 2: Development

```powershell
# Start services
Start-Services

# ... make code changes ...

# Restart aggregator
docker compose restart aggregator

# Check logs
Show-Logs -Service aggregator

# Test changes
Publish-TestEvent -Topic "dev.test"
Start-Sleep -Seconds 2
Get-Events -Topic "dev.test"
```

### Workflow 3: Testing

```powershell
# Ensure services running
Start-Services

# Run automated tests
Invoke-Tests

# Manual testing
Test-Deduplication
Test-Persistence

# Check final state
Get-Stats
```

### Workflow 4: Demo Preparation

```powershell
# Clean start
Stop-ServicesClean
Start-Services

# Wait for publisher
Start-Sleep -Seconds 120

# Verify system state
Test-Health
Get-Stats

# Demo features
Test-Deduplication
Test-Persistence

# Show monitoring
Show-Logs -Service aggregator
```

### Workflow 5: Cleanup

```powershell
# Stop (keep data for later)
Stop-Services

# Or full cleanup
Stop-ServicesClean

# Verify cleanup
docker ps -a
docker volume ls
```

---

## 🔧 Troubleshooting

### Issue: Scripts not loading

**Error:**
```
. : File C:\...\scripts.ps1 cannot be loaded because running scripts is disabled
```

**Solution:**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Docker commands fail

**Error:**
```
error during connect: This error may indicate that the docker daemon is not running
```

**Solution:**
1. Start Docker Desktop
2. Wait for it to be ready
3. Try again

### Issue: Port 8080 already in use

**Error:**
```
Error: bind: address already in use
```

**Solution:**
```powershell
# Find process using port 8080
netstat -ano | findstr :8080

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change port in docker-compose.yml
```

### Issue: Function not recognized

**Error:**
```
Test-Health : The term 'Test-Health' is not recognized
```

**Solution:**
```powershell
# Reload scripts
. .\scripts.ps1

# Verify loaded
Get-Command Test-Health
```

---

## 📖 Command Reference

| Command | Purpose | Destructive? |
|---------|---------|--------------|
| `Start-Services` | Start all services | No |
| `Stop-Services` | Stop services, keep data | No |
| `Stop-ServicesClean` | Stop and remove data | ⚠️ Yes |
| `Show-Logs` | View logs | No |
| `Test-Health` | Check health | No |
| `Get-Stats` | Get statistics | No |
| `Get-Events` | Query events | No |
| `Publish-TestEvent` | Send test event | No (adds data) |
| `Invoke-Tests` | Run test suite | No |
| `Test-Deduplication` | Demo dedup | No (adds test data) |
| `Test-Persistence` | Demo persistence | No (restarts services) |
| `Start-QuickDemo` | Full demo | No |

---

## 🎯 Pro Tips

1. **Reload after editing scripts:**
   ```powershell
   . .\scripts.ps1
   ```

2. **Combine commands:**
   ```powershell
   Start-Services; Start-Sleep -Seconds 30; Test-Health
   ```

3. **Save output:**
   ```powershell
   Get-Stats | Out-File stats.json
   ```

4. **Pretty print JSON:**
   ```powershell
   Get-Stats | ConvertFrom-Json | ConvertTo-Json -Depth 10
   ```

5. **Quick status check:**
   ```powershell
   docker compose ps
   ```

6. **Watch stats continuously:**
   ```powershell
   while ($true) { Clear-Host; Get-Stats; Start-Sleep -Seconds 5 }
   ```

---

## 🆘 Getting Help

Lihat available functions:
```powershell
Get-Command -Module $null | Where-Object { $_.Name -like "*-*" }
```

Get help for specific function:
```powershell
Get-Help Test-Deduplication -Detailed
```

---

**Happy Testing! 🚀**
