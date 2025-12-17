# Video Demo Checklist

**Durasi Target:** < 25 menit  
**Link YouTube:** [Isi setelah upload]

---

## Pre-Recording Checklist

- [ ] Clean Docker environment: `docker system prune -a`
- [ ] Remove volumes: `docker volume rm $(docker volume ls -q | grep uas)`
- [ ] Close unnecessary applications
- [ ] Open terminals dan browser
- [ ] Prepare screen recording software (OBS, Loom, dll)
- [ ] Test microphone
- [ ] Prepare slide/notes

---

## Script & Timeline

### 1. Introduction & Arsitektur (0:00 - 2:00)

**Show:**
- [ ] Slide dengan nama, NIM, judul project
- [ ] Diagram arsitektur (bisa gambar atau compose file)

**Explain:**
- [ ] Tujuan sistem: Pub-Sub log aggregator
- [ ] Komponen: Aggregator, Publisher, Redis, PostgreSQL
- [ ] Fitur kunci: Idempotency, Deduplication, Transactions, Concurrency

**Script:**
```
"Selamat pagi/siang, nama saya [Nama], NIM [NIM].
Ini adalah demo untuk UAS Sistem Terdistribusi: Pub-Sub Log Aggregator.

Sistem ini terdiri dari 4 komponen utama:
1. Aggregator - FastAPI service dengan consumer workers
2. Publisher - Event generator dengan duplikasi
3. Redis - Message broker untuk queue
4. PostgreSQL - Database untuk deduplication dan persistence

Fitur utama yang diimplementasi:
- Idempotent consumer untuk at-least-once delivery
- Deduplication berbasis database constraint
- ACID transactions untuk data consistency
- Concurrent processing dengan 4 workers
- Named volumes untuk persistence"
```

---

### 2. Build & Run (2:00 - 5:00)

**Terminal Commands:**
```bash
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"

# Show project structure
dir

# Build and run
docker compose up --build
```

**Show:**
- [ ] Build process (image creation)
- [ ] Service startup sequence (storage → broker → aggregator → publisher)
- [ ] Health checks passing

**Explain:**
- [ ] Docker Compose orchestration
- [ ] Dependency management (depends_on)
- [ ] Health check mechanism

**Script:**
```
"Saya akan build dan run semua services menggunakan Docker Compose.
Perhatikan startup sequence:
1. PostgreSQL dan Redis start dulu
2. Health checks memastikan mereka ready
3. Aggregator start setelah dependencies healthy
4. Publisher start terakhir

Ini memastikan no race conditions saat startup."
```

---

### 3. Idempotency Demo (5:00 - 9:00)

**Terminal Commands:**
```bash
# Open new terminal
# Get initial stats
curl http://localhost:8080/stats | jq

# Send same event twice
EVENT='{"events":[{"topic":"demo.test","event_id":"duplicate-test-1","timestamp":"2025-12-17T10:00:00Z","source":"demo","payload":{"test":"data"}}]}'

curl -X POST http://localhost:8080/publish -H "Content-Type: application/json" -d "$EVENT"
sleep 2
curl -X POST http://localhost:8080/publish -H "Content-Type: application/json" -d "$EVENT"
sleep 2

# Check stats again
curl http://localhost:8080/stats | jq
```

**Show:**
- [ ] Initial stats
- [ ] Send duplicate event
- [ ] Final stats showing: unique_processed +1, duplicate_dropped +1
- [ ] Query specific event

**Explain:**
- [ ] Event structure (topic, event_id, timestamp, source, payload)
- [ ] Deduplication key: (topic, event_id)
- [ ] Database constraint enforcement

**Script:**
```
"Sekarang demo idempotency dan deduplication.
Saya akan send event yang sama dua kali.

[Show initial stats]
Initial stats: unique_processed = X, duplicate_dropped = Y

[Send first event]
Event pertama diterima dan diproses.

[Send duplicate]
Event kedua adalah duplicate - same topic dan event_id.

[Show final stats]
Final stats: unique_processed = X+1, duplicate_dropped = Y+1

Notice bahwa event hanya diproses sekali (unique +1),
dan duplicate terdeteksi dan di-drop (duplicate +1).

Ini dijamin oleh UNIQUE constraint di database pada (topic, event_id)."
```

---

### 4. Concurrency Demo (9:00 - 12:00)

**Show logs:**
```bash
# Show consumer workers
docker compose logs aggregator | grep "Consumer worker"

# Send multiple parallel requests
for i in {1..10}; do
  curl -X POST http://localhost:8080/publish \
    -H "Content-Type: application/json" \
    -d "{\"events\":[{\"topic\":\"concurrent.test\",\"event_id\":\"concurrent-$i\",\"timestamp\":\"2025-12-17T10:00:00Z\",\"source\":\"test\",\"payload\":{}}]}" &
done
wait

# Check processing in logs
docker compose logs aggregator | grep "Processed"
```

**Show:**
- [ ] Multiple workers processing (Worker 0, 1, 2, 3)
- [ ] Concurrent processing logs
- [ ] Stats consistency

**Explain:**
- [ ] 4 consumer workers
- [ ] Redis queue distribution
- [ ] Database transaction guarantees no race conditions

**Script:**
```
"Sistem menjalankan 4 consumer workers secara paralel.
[Show logs]
Lihat di logs: Worker 0, 1, 2, 3 all processing events.

Saya akan send 10 concurrent requests sekaligus.
[Run for loop]

[Show logs]
Notice bahwa multiple workers process different events.
Database transaction dan unique constraint menjamin
tidak ada duplicate processing walau concurrent.

[Show stats]
Stats tetap consistent."
```

---

### 5. Transaction Demo (12:00 - 15:00)

**Show code:**
```bash
# Open aggregator/main.py
code aggregator/main.py
```

**Navigate to `process_event_with_transaction` function**

**Show:**
- [ ] Transaction boundary (BEGIN - COMMIT/ROLLBACK)
- [ ] ON CONFLICT DO NOTHING pattern
- [ ] Atomic counter updates

**Explain:**
- [ ] ACID properties
- [ ] Isolation level: READ COMMITTED
- [ ] Atomic operations (UPDATE count = count + 1)

**Script:**
```
"Mari kita lihat implementasi transaction di code.
[Open main.py, scroll to function]

Function process_event_with_transaction:
1. BEGIN transaction (implicit)
2. Increment received counter - atomic SQL
3. INSERT event with ON CONFLICT DO NOTHING
4. Check rowcount untuk tentukan new vs duplicate
5. Update corresponding counter (unique atau duplicate)
6. COMMIT transaction

Semua ini atomic - all or nothing.
Jika ada error, rollback automatic.

Isolation level: READ COMMITTED
- Cukup untuk use case ini
- Lower overhead daripada SERIALIZABLE
- Database constraint handle concurrency

Unique constraint pada (topic, event_id):
- Mencegah duplicate inserts di database level
- No application-level locking needed
- Concurrent workers safe"
```

---

### 6. Persistence Demo (15:00 - 18:00)

**Terminal Commands:**
```bash
# Get current stats
curl http://localhost:8080/stats | jq > stats_before.json
cat stats_before.json

# Stop all containers
docker compose down

# Show volumes still exist
docker volume ls | grep uas

# Inspect volume
docker volume inspect uas_pg_data

# Restart
docker compose up -d aggregator

# Wait for health
sleep 15
curl http://localhost:8080/health

# Get stats again
curl http://localhost:8080/stats | jq > stats_after.json
cat stats_after.json

# Compare
diff stats_before.json stats_after.json
```

**Show:**
- [ ] Stats before shutdown
- [ ] Container removal
- [ ] Volumes persist
- [ ] Stats after restart (same values)

**Explain:**
- [ ] Named volumes
- [ ] PostgreSQL data persistence
- [ ] Redis AOF
- [ ] Container stateless, data in volumes

**Script:**
```
"Sekarang demo persistence dan crash recovery.
[Get stats before]
Current stats: received=20000, unique=14000, duplicate=6000

[docker compose down]
Stopping dan removing semua containers...

[Show volumes]
Containers hilang, tapi volumes tetap ada:
- uas_pg_data: PostgreSQL data
- uas_broker_data: Redis AOF
- uas_aggregator_logs: Application logs

[Restart]
Restarting aggregator...

[Show stats after]
Stats sama persis! Data tidak hilang.
received=20000, unique=14000, duplicate=6000

Ini karena data persist di named volumes.
PostgreSQL dan Redis data survive container deletion.

Deduplication juga tetap work - jika saya send
event lama lagi, akan ke-detect sebagai duplicate
karena sudah ada di database."
```

---

### 7. Testing (18:00 - 22:00)

**Terminal Commands:**
```bash
# Install dependencies
pip install -r tests/requirements.txt

# Run tests
pytest tests/test_aggregator.py -v
```

**Show:**
- [ ] Test execution
- [ ] All 18 tests passing
- [ ] Test categories

**Explain:**
- [ ] Test coverage
- [ ] Key test scenarios

**Optional - show specific test:**
```bash
pytest tests/test_aggregator.py::test_08_duplicate_detection -v -s
```

**Script:**
```
"System telah diuji dengan 18 unit dan integration tests.
[Run pytest]

Test categories:
1. Health & API (3 tests) - basic endpoints
2. Event Validation (4 tests) - schema validation
3. Idempotency & Dedup (4 tests) - duplicate detection
4. Concurrency (3 tests) - parallel processing
5. Query Endpoints (2 tests) - GET /events
6. Persistence & Stress (2 tests) - large batch

[Show results]
All 18 tests passed!

Setiap test memverifikasi aspek berbeda:
- Test 8: Duplicate detection
- Test 12: Concurrent same event (idempotency)
- Test 13: Concurrent different events (all processed)
- Test 14: High load consistency

Tests ini ensure system robust dan reliable."
```

---

### 8. Observability (22:00 - 24:00)

**Show:**
```bash
# Health check
curl http://localhost:8080/health | jq

# Stats
curl http://localhost:8080/stats | jq

# Events
curl http://localhost:8080/events?limit=5 | jq

# Logs
docker compose logs --tail=50 aggregator

# Container stats
docker stats --no-stream
```

**Explain:**
- [ ] Health endpoint monitoring
- [ ] Metrics collection
- [ ] Structured logging
- [ ] Resource monitoring

**Script:**
```
"System memiliki observability yang baik.

[Health check]
Health endpoint untuk monitoring:
- Database connection status
- Redis connection status
- Overall service health

[Stats]
Metrics endpoint:
- received: total events diterima
- unique_processed: events unik diproses
- duplicate_dropped: duplikat yang diabaikan
- topics: jumlah topic unik
- uptime: waktu running

[Logs]
Structured logging:
- Level: INFO, WARNING, ERROR
- Timestamp, service name, message
- Clear symbols: ✓ success, ⊗ duplicate, ✗ error

[Docker stats]
Resource monitoring:
- CPU usage
- Memory usage
- Network I/O

Production bisa ditambah:
- Prometheus metrics export
- Grafana dashboards
- Distributed tracing
- Alerting"
```

---

### 9. Summary & Closing (24:00 - 25:00)

**Show final slide with key points**

**Script:**
```
"Summary implementasi:

✅ Fitur yang Diimplementasi:
1. Idempotent consumer dengan deduplication
2. ACID transactions (READ COMMITTED isolation)
3. Concurrent processing (4 workers)
4. Persistent storage (named volumes)
5. Crash recovery tanpa data loss
6. Comprehensive testing (18 tests)
7. Observability (health, metrics, logs)
8. Docker Compose orchestration

✅ Teori yang Diterapkan (Bab 1-13):
- Bab 1-2: Distributed system characteristics, Pub-Sub architecture
- Bab 3-4: Communication protocols, Naming schemes
- Bab 5: Logical ordering dengan timestamps
- Bab 6: Fault tolerance, retry mechanisms
- Bab 7: Eventual consistency dengan idempotency
- Bab 8-9: ACID transactions, Concurrency control ⭐
- Bab 10-13: Security, Persistence, Orchestration, Observability

✅ Testing:
- 18 unit & integration tests
- Load testing dengan K6
- Persistence verification
- Concurrency stress tests

Repository GitHub: [link]
Laporan lengkap: LAPORAN.md

Terima kasih!"
```

---

## Post-Recording Checklist

- [ ] Review video (audio clear, screen readable)
- [ ] Upload to YouTube (unlisted or public)
- [ ] Add to video description:
  - GitHub repository link
  - Table of contents with timestamps
  - Commands used
- [ ] Copy link to README.md
- [ ] Test link accessibility

---

## Backup Plan

Jika ada technical issue saat recording:

1. **Docker not starting:**
   - Show pre-recorded terminal session
   - Explain from logs

2. **Network issues:**
   - Use localhost commands (already prepared)
   - Demo from saved JSON responses

3. **Time overrun:**
   - Skip load testing section
   - Focus on core features (idempotency, transactions, persistence)

---

**Tips:**
- Speak clearly and not too fast
- Pause after important points
- Use cursor to highlight key code/output
- Zoom in if needed (Ctrl + +)
- Test run once before actual recording
