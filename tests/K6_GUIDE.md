# K6 Load Testing Guide

## Prerequisites

Install K6:

**Windows (Chocolatey):**
```powershell
choco install k6
```

**macOS (Homebrew):**
```bash
brew install k6
```

**Linux:**
```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

## Running Tests

### Basic Run
```bash
k6 run tests/load_test.js
```

### Custom Configuration
```bash
# Adjust virtual users and duration
k6 run tests/load_test.js --vus 20 --duration 120s

# Set environment variables
k6 run tests/load_test.js \
  -e BASE_URL=http://localhost:8080 \
  -e TOTAL_EVENTS=50000 \
  -e DUPLICATE_RATE=0.4 \
  -e BATCH_SIZE=200
```

### Output to File
```bash
k6 run tests/load_test.js --out json=results.json
```

## Understanding Results

### Key Metrics

- **http_req_duration**: Request latency
  - p(95) should be < 500ms
  
- **http_req_failed**: Error rate
  - Should be < 10%
  
- **http_reqs**: Total requests
  - Rate = requests/second
  
- **iteration_duration**: Time per iteration
  
- **checks**: Validation pass rate
  - Should be 100%

### Example Output
```
scenarios: (100.00%) 1 scenario, 10 max VUs, 1m30s max duration
load_test: 10 looping VUs for 1m (gracefulStop: 30s)

     ✓ status is 202
     ✓ has queued field
     ✓ response time < 500ms

     checks.........................: 100.00% ✓ 3000  ✗ 0
     data_received..................: 2.3 MB  38 kB/s
     data_sent......................: 45 MB   750 kB/s
     errors.........................: 0.00%   ✓ 0     ✗ 1000
     http_req_blocked...............: avg=125µs   min=0s   med=0s     max=15ms
     http_req_duration..............: avg=45ms    min=10ms med=40ms   max=200ms
       { expected_response:true }...: avg=45ms    min=10ms med=40ms   max=200ms
     http_req_failed................: 0.00%   ✓ 0     ✗ 1000
     http_reqs......................: 1000    16.67/s
     iteration_duration.............: avg=600ms   min=550ms med=600ms max=750ms
     iterations.....................: 1000    16.67/s
     vus............................: 10      min=10  max=10
     vus_max........................: 10      min=10  max=10
```

### Teardown Stats
```
==================================================================
K6 Load Test Completed
==================================================================
Waiting 10 seconds for event processing...
Final Stats:
  Received: 100000 (+100000)
  Unique: 70000 (+70000)
  Duplicates: 30000 (+30000)
  Topics: 8
==================================================================
Verification:
  Total Received: 100000
  Unique + Duplicates: 100000
  Match: ✓
  Expected Duplicate Rate: 30.0%
  Actual Duplicate Rate: 30.0%
==================================================================
```

## Troubleshooting

### High Error Rate

If error rate > 10%:

1. Check aggregator health:
```bash
curl http://localhost:8080/health
```

2. Check logs:
```bash
docker compose logs aggregator
```

3. Reduce load:
```bash
k6 run tests/load_test.js --vus 5 --duration 30s
```

### High Latency

If p(95) > 500ms:

1. Check system resources:
```bash
docker stats
```

2. Increase worker count:
```yaml
# docker-compose.yml
aggregator:
  environment:
    - WORKER_COUNT=8  # Default 4
```

3. Optimize batch size:
```bash
k6 run tests/load_test.js -e BATCH_SIZE=50
```

### Connection Refused

1. Verify aggregator is running:
```bash
docker compose ps
```

2. Check port mapping:
```bash
docker compose port aggregator 8080
```

3. Wait for service ready:
```bash
# Wait for health check
while ! curl -s http://localhost:8080/health > /dev/null; do
  echo "Waiting for aggregator..."
  sleep 2
done
echo "Aggregator is ready"
```

## Performance Tuning

### Database

```sql
-- Check connection pool
SELECT count(*) FROM pg_stat_activity;

-- Check slow queries
SELECT query, calls, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
```

### Redis

```bash
# Check memory usage
docker compose exec broker redis-cli INFO memory

# Check queue length
docker compose exec broker redis-cli LLEN event_queue
```

### Application

```bash
# Monitor aggregator CPU/Memory
docker stats uas-aggregator

# Check worker throughput in logs
docker compose logs aggregator | grep "Processed"
```

## Best Practices

1. **Ramp-up gradually**: Start with low VUs, increase slowly
2. **Monitor resources**: Use `docker stats` during test
3. **Multiple runs**: Run test 3 times, take average
4. **Realistic scenarios**: Match production traffic patterns
5. **Verify data**: Always check final stats for consistency

## References

- K6 Documentation: https://k6.io/docs/
- K6 Examples: https://github.com/grafana/k6-examples
