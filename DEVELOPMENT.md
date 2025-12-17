# Development Guide

## Setup Development Environment

### Prerequisites
```bash
# Required
- Docker Desktop >= 24.0
- Docker Compose >= 2.20
- Python >= 3.11
- Git

# Optional
- VSCode with Python extension
- K6 for load testing
- PostgreSQL client (psql)
- Redis client (redis-cli)
```

### Clone dan Setup

```bash
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"

# Install Python dependencies
pip install -r aggregator/requirements.txt
pip install -r publisher/requirements.txt
pip install -r tests/requirements.txt

# Build containers
docker compose build
```

## Development Workflow

### 1. Start Services for Development

```bash
# Start only database and broker
docker compose up -d storage broker

# Run aggregator locally for development
cd aggregator
python main.py

# Or run in container with code mount
docker compose up -d aggregator
```

### 2. Code Changes

**Aggregator Service:**
```bash
# Edit code
code aggregator/main.py

# Restart container to apply changes
docker compose restart aggregator

# Or rebuild if Dockerfile changed
docker compose up --build aggregator
```

**Publisher Service:**
```bash
# Edit code
code publisher/main.py

# Run once
docker compose up publisher
```

### 3. Database Operations

**Connect to PostgreSQL:**
```bash
# Using docker
docker compose exec storage psql -U loguser -d logdb

# Or using local psql
psql -h localhost -p 5432 -U loguser -d logdb
```

**Useful queries:**
```sql
-- Check processed events
SELECT * FROM processed_events ORDER BY processed_at DESC LIMIT 10;

-- Count by topic
SELECT topic, COUNT(*) FROM processed_events GROUP BY topic;

-- Check stats
SELECT * FROM event_stats WHERE id = 1;

-- Verify constraint
\d processed_events

-- Clear data (for testing)
TRUNCATE processed_events;
UPDATE event_stats SET received_count = 0, unique_processed = 0, duplicate_dropped = 0 WHERE id = 1;
```

### 4. Redis Operations

**Connect to Redis:**
```bash
docker compose exec broker redis-cli
```

**Useful commands:**
```redis
# Check queue length
LLEN event_queue

# Peek at queue
LRANGE event_queue 0 10

# Clear queue
DEL event_queue

# Monitor commands
MONITOR

# Check memory
INFO memory
```

### 5. Testing

**Run all tests:**
```bash
pytest tests/test_aggregator.py -v
```

**Run specific test:**
```bash
pytest tests/test_aggregator.py::test_08_duplicate_detection -v
```

**Run with coverage:**
```bash
pytest tests/test_aggregator.py --cov=aggregator --cov-report=html
# Open htmlcov/index.html
```

**Run with debug output:**
```bash
pytest tests/test_aggregator.py -v -s
```

### 6. Debugging

**View logs:**
```bash
# Real-time
docker compose logs -f aggregator

# Last 100 lines
docker compose logs --tail=100 aggregator

# Search logs
docker compose logs aggregator | grep "ERROR"
```

**Execute in container:**
```bash
# Shell access
docker compose exec aggregator sh

# Run Python interpreter
docker compose exec aggregator python

# Check environment
docker compose exec aggregator env
```

**Database debugging:**
```sql
-- Check active connections
SELECT * FROM pg_stat_activity;

-- Check locks
SELECT * FROM pg_locks;

-- Check table size
SELECT pg_size_pretty(pg_total_relation_size('processed_events'));
```

## Code Style & Standards

### Python Code

**Follow PEP 8:**
```bash
# Install tools
pip install black flake8 mypy

# Format code
black aggregator/main.py

# Lint
flake8 aggregator/main.py

# Type checking
mypy aggregator/main.py
```

**Docstrings:**
```python
def process_event(event: Event) -> bool:
    """
    Process single event dengan transaction.
    
    Args:
        event: Event object to process
        
    Returns:
        bool: True if successful, False otherwise
        
    Raises:
        DatabaseError: If transaction fails
    """
    pass
```

**Type hints:**
```python
from typing import List, Optional, Dict, Any

def fetch_events(
    topic: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    pass
```

### Git Workflow

**Branch naming:**
```bash
git checkout -b feature/add-metrics
git checkout -b fix/duplicate-detection
git checkout -b docs/update-readme
```

**Commit messages:**
```
feat: Add Prometheus metrics endpoint
fix: Fix race condition in event processing
docs: Update API documentation
test: Add test for concurrent processing
refactor: Simplify transaction logic
```

**Before commit:**
```bash
# Format code
black .

# Run tests
pytest tests/

# Check logs
docker compose logs aggregator | grep ERROR
```

## Performance Optimization

### Database

**Add indexes:**
```sql
CREATE INDEX idx_topic_timestamp ON processed_events(topic, timestamp);
CREATE INDEX idx_source ON processed_events(source);
```

**Analyze queries:**
```sql
EXPLAIN ANALYZE SELECT * FROM processed_events WHERE topic = 'user.login';
```

**Tune PostgreSQL:**
```yaml
# docker-compose.yml
storage:
  command: postgres -c shared_buffers=256MB -c max_connections=200
```

### Application

**Increase workers:**
```yaml
aggregator:
  environment:
    - WORKER_COUNT=8  # Default 4
```

**Batch processing:**
```python
# Process events in batches
batch = []
for event in events:
    batch.append(event)
    if len(batch) >= BATCH_SIZE:
        process_batch(batch)
        batch = []
```

**Connection pooling:**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,      # Default 5
    max_overflow=40,   # Default 10
)
```

## Monitoring & Debugging

### Health Monitoring

```bash
# Continuous health check
watch -n 5 curl http://localhost:8080/health

# Stats monitoring
watch -n 5 curl http://localhost:8080/stats
```

### Resource Monitoring

```bash
# Container stats
docker stats

# Database size
docker compose exec storage du -sh /var/lib/postgresql/data

# Redis memory
docker compose exec broker redis-cli INFO memory
```

### Log Analysis

```bash
# Error rate
docker compose logs aggregator | grep ERROR | wc -l

# Processing rate
docker compose logs aggregator | grep "Processed new event" | wc -l

# Duplicate rate
docker compose logs aggregator | grep "Dropped duplicate" | wc -l
```

## Common Issues & Solutions

### Issue: Database connection pool exhausted

**Symptoms:**
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached
```

**Solution:**
```python
# Increase pool size
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40
)
```

### Issue: Redis queue growing unbounded

**Symptoms:**
```bash
redis-cli LLEN event_queue
# Output: 100000+
```

**Solution:**
```bash
# Increase workers
# Edit docker-compose.yml
aggregator:
  environment:
    - WORKER_COUNT=8

# Or manual drain
docker compose exec broker redis-cli DEL event_queue
```

### Issue: Slow event processing

**Debug:**
```sql
-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check table bloat
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public';
```

**Solution:**
```sql
-- Add missing index
CREATE INDEX idx_topic_event_id ON processed_events(topic, event_id);

-- Vacuum
VACUUM ANALYZE processed_events;
```

## Adding New Features

### Example: Add new endpoint

1. **Add route:**
```python
@app.get("/events/count")
async def count_events(topic: Optional[str] = None):
    Session = app_state["Session"]
    session = Session()
    
    try:
        query = session.query(ProcessedEvent)
        if topic:
            query = query.filter(ProcessedEvent.topic == topic)
        count = query.count()
        return {"count": count}
    finally:
        session.close()
```

2. **Add test:**
```python
@pytest.mark.asyncio
async def test_count_endpoint(client):
    response = await client.get("/events/count")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
```

3. **Update docs:**
```markdown
### GET `/events/count`
Get total count of processed events.
```

4. **Test:**
```bash
pytest tests/test_aggregator.py::test_count_endpoint -v
curl http://localhost:8080/events/count
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/docs/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Pytest Documentation](https://docs.pytest.org/)

## Getting Help

Jika ada masalah:

1. Check logs: `docker compose logs -f`
2. Check health: `curl http://localhost:8080/health`
3. Check database: `docker compose exec storage psql -U loguser -d logdb`
4. Review README.md dan TROUBLESHOOTING section
5. Search GitHub issues (jika applicable)

---

**Happy Coding! 🚀**
