# Quick Start Guide

## Prerequisites Check
```bash
docker --version
docker compose version
python --version
```

## 1. First Time Setup

```bash
# Navigate to project
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"

# Build and start all services
docker compose up --build
```

**Expected Output:**
```
[+] Running 5/5
 ✔ Network uas-network       Created
 ✔ Volume "uas_pg_data"      Created
 ✔ Volume "uas_broker_data"  Created
 ✔ Container uas-storage     Healthy
 ✔ Container uas-broker      Healthy
 ✔ Container uas-aggregator  Healthy
 ✔ Container uas-publisher   Started
```

## 2. Verify System

Open new terminal:

```bash
# Health check
curl http://localhost:8080/health

# Expected: {"status":"healthy","database":"connected","redis":"connected",...}

# Wait for publisher to complete (~ 2 minutes)
docker compose logs -f publisher

# Check stats
curl http://localhost:8080/stats
```

**Expected Stats:**
```json
{
  "received": 20000,
  "unique_processed": 14000,
  "duplicate_dropped": 6000,
  "topics": 10,
  "uptime_seconds": 120.5,
  "status": "healthy"
}
```

## 3. Explore API

```bash
# Get recent events
curl "http://localhost:8080/events?limit=5"

# Filter by topic
curl "http://localhost:8080/events?topic=user.login"

# Manual publish
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "events": [{
      "topic": "test.manual",
      "event_id": "manual-123",
      "timestamp": "2025-12-17T10:00:00Z",
      "source": "curl",
      "payload": {"message": "Hello from curl"}
    }]
  }'
```

## 4. Test Persistence

```bash
# Get current stats
curl http://localhost:8080/stats > before.json

# Stop containers
docker compose down

# Verify volumes still exist
docker volume ls | grep uas

# Restart
docker compose up -d aggregator

# Wait for ready
sleep 10

# Check stats (should be same)
curl http://localhost:8080/stats > after.json

# Compare
cat before.json
cat after.json
```

## 5. Run Tests

```bash
# Ensure aggregator running
docker compose up -d aggregator

# Install test dependencies
pip install -r tests/requirements.txt

# Run tests
pytest tests/test_aggregator.py -v
```

**Expected:**
```
==================== 18 passed in 45.67s ====================
```

## 6. Load Testing (Optional)

```bash
# Install K6 (Windows with Chocolatey)
choco install k6

# Run load test
k6 run tests/load_test.js
```

## 7. Cleanup

```bash
# Stop containers (keep data)
docker compose down

# Stop and remove all data
docker compose down -v

# Remove images
docker compose down --rmi all
```

## Common Commands

```bash
# View logs
docker compose logs -f                    # All services
docker compose logs -f aggregator         # Specific service
docker compose logs --tail=100 publisher  # Last 100 lines

# Restart service
docker compose restart aggregator

# Check status
docker compose ps

# Check resources
docker stats

# Execute command in container
docker compose exec aggregator sh
docker compose exec storage psql -U loguser -d logdb

# View volumes
docker volume ls
docker volume inspect uas_pg_data
```

## Troubleshooting

### Issue: Port already in use
```bash
# Find process using port 8080
netstat -ano | findstr :8080

# Kill process (replace PID)
taskkill /PID <PID> /F
```

### Issue: Database connection failed
```bash
# Check database status
docker compose ps storage

# Restart database
docker compose restart storage

# Wait and retry
docker compose restart aggregator
```

### Issue: Out of disk space
```bash
# Clean Docker system
docker system prune -a

# Remove unused volumes
docker volume prune
```

## Next Steps

1. ✅ Complete bagian teori di [LAPORAN.md](../LAPORAN.md)
2. ✅ Record video demo (< 25 menit)
3. ✅ Upload ke GitHub
4. ✅ Submit laporan PDF

---

**Need Help?** Check [README.md](../README.md) for detailed documentation.
