# Pub-Sub Log Aggregator Terdistribusi

**UAS Sistem Terdistribusi - Semester 7**

Sistem log aggregator berbasis publish-subscribe dengan fitur **idempotent consumer**, **deduplication**, **transaction control**, dan **concurrency handling** menggunakan Docker Compose.

---

## 📋 Daftar Isi

- [Deskripsi Sistem](#deskripsi-sistem)
- [Arsitektur](#arsitektur)
- [Fitur Utama](#fitur-utama)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Load Testing dengan K6](#load-testing-dengan-k6)
- [Struktur Project](#struktur-project)
- [Keputusan Desain](#keputusan-desain)
- [Troubleshooting](#troubleshooting)
- [Video Demo](#video-demo)

---

## 🎯 Deskripsi Sistem

Sistem ini adalah implementasi **Pub-Sub Log Aggregator** yang menangani:

- ✅ **At-least-once delivery** dengan idempotent consumer
- ✅ **Deduplication** berbasis database constraint (UNIQUE constraint)
- ✅ **ACID transactions** untuk data consistency
- ✅ **Concurrency control** untuk multiple workers
- ✅ **Persistent storage** dengan named volumes
- ✅ **Crash recovery** tanpa data loss
- ✅ **Observability** dengan metrics dan health checks

---

## 🏗️ Arsitektur

```
┌─────────────┐
│  Publisher  │ (Event Generator + Duplicate Simulator)
└──────┬──────┘
       │ HTTP POST /publish
       ▼
┌─────────────────┐
│   Aggregator    │ (FastAPI + Consumer Workers)
│   - API Layer   │
│   - 4 Workers   │
└────┬────────┬───┘
     │        │
     │        └─────────────┐
     ▼                      ▼
┌──────────┐         ┌──────────┐
│  Redis   │         │ Postgres │
│  Broker  │         │  Storage │
│  (Queue) │         │  (Dedup) │
└──────────┘         └──────────┘
```

### Komponen:

1. **Aggregator Service** (`aggregator/`)
   - FastAPI application
   - HTTP API: `/publish`, `/events`, `/stats`, `/health`
   - 4 consumer workers (concurrent processing)
   - Transaction-based deduplication

2. **Publisher Service** (`publisher/`)
   - Event generator
   - Simulates 30% duplicate events
   - Configurable batch size dan rate

3. **Redis Broker**
   - Message queue (`event_queue`)
   - AOF persistence enabled

4. **PostgreSQL Storage**
   - Deduplication store (`processed_events` table)
   - Statistics tracking (`event_stats` table)
   - UNIQUE constraint on `(topic, event_id)`

---

## ⚡ Fitur Utama

### 1. Idempotency & Deduplication

```python
# Database constraint menjamin idempotency
CONSTRAINT uq_topic_event_id UNIQUE (topic, event_id)

# Upsert pattern dengan ON CONFLICT
INSERT INTO processed_events (...) 
ON CONFLICT (topic, event_id) DO NOTHING
```

**Hasil:** Event dengan `(topic, event_id)` yang sama hanya diproses **sekali**, walau diterima berkali-kali.

### 2. Transaction Control (ACID)

```python
# Setiap event processing dalam 1 transaction
BEGIN TRANSACTION
  UPDATE stats SET received = received + 1;
  INSERT INTO events (...) ON CONFLICT DO NOTHING;
  IF inserted THEN
    UPDATE stats SET unique = unique + 1;
  ELSE
    UPDATE stats SET duplicate = duplicate + 1;
  END IF;
COMMIT
```

**Isolation Level:** `READ COMMITTED` (balance antara consistency dan performance)

### 3. Concurrency Control

- **4 consumer workers** berjalan paralel
- **Database constraint** sebagai synchronization mechanism
- **Atomic SQL operations** untuk counter updates
- **No application-level locking** needed

### 4. Persistence

Semua data persist di **named volumes**:

```yaml
volumes:
  uas_pg_data:      # PostgreSQL data
  uas_broker_data:  # Redis AOF
  uas_aggregator_logs: # Application logs
```

**Test persistence:**
```bash
docker compose down
docker compose up -d
# Data tetap ada!
```

---

## 📦 Requirements

- **Docker** >= 24.0
- **Docker Compose** >= 2.20
- **Python** >= 3.11 (untuk local development/testing)
- **curl** (untuk health checks)

---

## 🚀 Quick Start

### 1. Clone & Navigate

```bash
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"
```

### 2. Build & Run

```bash
# Build images dan start semua services
docker compose up --build

# Atau detached mode:
docker compose up --build -d
```

**Startup Sequence:**
1. PostgreSQL dan Redis start first
2. Aggregator start setelah DB ready
3. Publisher start terakhir dan send 20,000 events

### 3. Monitor Logs

```bash
# Follow all logs
docker compose logs -f

# Aggregator only
docker compose logs -f aggregator

# Publisher only
docker compose logs -f publisher
```

### 4. Check Status

```bash
# Health check
curl http://localhost:8080/health

# Statistics
curl http://localhost:8080/stats

# List events
curl http://localhost:8080/events?limit=10
```

### 5. Cleanup

```bash
# Stop containers (keep volumes)
docker compose down

# Stop dan remove volumes (data loss)
docker compose down -v
```

---

## 📡 API Endpoints

Base URL: `http://localhost:8080`

### POST `/publish`

Publish batch events ke aggregator.

**Request:**
```json
{
  "events": [
    {
      "topic": "user.login",
      "event_id": "unique-id-123",
      "timestamp": "2025-12-17T10:30:00.000Z",
      "source": "web-app-1",
      "payload": {
        "user_id": "user_123",
        "ip": "192.168.1.1"
      }
    }
  ]
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "queued": 1,
  "message": "Events queued for processing"
}
```

**Example:**
```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "events": [{
      "topic": "test.event",
      "event_id": "test-123",
      "timestamp": "2025-12-17T10:00:00Z",
      "source": "curl",
      "payload": {"message": "Hello World"}
    }]
  }'
```

### GET `/events`

Retrieve processed events.

**Query Parameters:**
- `topic` (optional): Filter by topic
- `limit` (optional): Max results (default: 100, max: 1000)

**Response:**
```json
[
  {
    "topic": "user.login",
    "event_id": "unique-id-123",
    "timestamp": "2025-12-17T10:30:00.000Z",
    "source": "web-app-1",
    "payload": {"user_id": "user_123"},
    "processed_at": "2025-12-17T10:30:01.234Z"
  }
]
```

**Example:**
```bash
# All events
curl http://localhost:8080/events

# Filter by topic
curl http://localhost:8080/events?topic=user.login

# Limit results
curl http://localhost:8080/events?limit=50
```

### GET `/stats`

Get aggregator statistics.

**Response:**
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

**Verification:**
```
received = unique_processed + duplicate_dropped
20000 = 14000 + 6000 ✓
```

**Example:**
```bash
curl http://localhost:8080/stats
```

### GET `/health`

Health check endpoint.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2025-12-17T10:30:00.000Z"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "database": "error: connection refused",
  "redis": "connected"
}
```

---

## 🧪 Testing

### Unit & Integration Tests (18 tests)

**Prerequisites:**
```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Start aggregator (without publisher)
docker compose up -d aggregator
```

**Run Tests:**
```bash
# All tests
pytest tests/test_aggregator.py -v

# Specific test
pytest tests/test_aggregator.py::test_08_duplicate_detection -v

# With coverage
pytest tests/test_aggregator.py --cov=aggregator --cov-report=html
```

**Test Coverage:**

| Category | Tests | Description |
|----------|-------|-------------|
| Health & API | 3 | Basic endpoints, health check |
| Event Validation | 4 | Schema validation, invalid inputs |
| Idempotency & Dedup | 4 | Duplicate detection, batch dedup |
| Concurrency | 3 | Concurrent same/different events, high load |
| Query Endpoints | 2 | GET /events with filters |
| Persistence & Stress | 2 | Stats accumulation, large batch |

**Expected Output:**
```
=================== test session starts ===================
tests/test_aggregator.py::test_01_health_endpoint PASSED
tests/test_aggregator.py::test_02_root_endpoint PASSED
...
tests/test_aggregator.py::test_18_large_batch_processing PASSED
=================== 18 passed in 45.67s ===================
```

### Manual Testing Scenarios

**Scenario 1: Duplicate Detection**
```bash
# Send same event twice
EVENT='{"events":[{"topic":"test","event_id":"dup-test-1","timestamp":"2025-12-17T10:00:00Z","source":"test","payload":{}}]}'

curl -X POST http://localhost:8080/publish -H "Content-Type: application/json" -d "$EVENT"
sleep 2
curl -X POST http://localhost:8080/publish -H "Content-Type: application/json" -d "$EVENT"
sleep 2

# Check stats
curl http://localhost:8080/stats
# Expected: unique_processed +1, duplicate_dropped +1
```

**Scenario 2: Concurrent Processing**
```bash
# Send 10 parallel requests
for i in {1..10}; do
  curl -X POST http://localhost:8080/publish \
    -H "Content-Type: application/json" \
    -d "{\"events\":[{\"topic\":\"concurrent.test\",\"event_id\":\"concurrent-$i\",\"timestamp\":\"2025-12-17T10:00:00Z\",\"source\":\"test\",\"payload\":{}}]}" &
done
wait

# Check stats
curl http://localhost:8080/stats
# Expected: unique_processed +10 (all different events)
```

**Scenario 3: Persistence Test**
```bash
# Get current stats
curl http://localhost:8080/stats > before.json

# Stop containers
docker compose down

# Verify volumes exist
docker volume ls | grep uas

# Restart
docker compose up -d aggregator

# Wait for health
sleep 10

# Check stats again
curl http://localhost:8080/stats > after.json

# Compare
diff before.json after.json
# Expected: Same stats (data persisted)
```

---

## 📊 Load Testing dengan K6

### Setup K6

**Install K6:**
```bash
# Windows (Chocolatey)
choco install k6

# macOS (Homebrew)
brew install k6

# Linux
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

### Run Load Test

```bash
# Start aggregator
docker compose up -d aggregator

# Run K6 test
k6 run tests/load_test.js

# Or with custom config
k6 run tests/load_test.js \
  --vus 10 \
  --duration 30s
```

### K6 Test Script

File: [`tests/load_test.js`](tests/load_test.js)

**Features:**
- 20,000 events total
- 30% duplicate rate
- Configurable VUs (Virtual Users)
- Metrics: throughput, latency, error rate

**Expected Results:**
```
scenarios: (100.00%) 1 scenario, 10 max VUs, 1m30s max duration
default: 10 looping VUs for 1m (gracefulStop: 30s)

     ✓ status is 202
     ✓ has queued field

     checks.........................: 100.00% ✓ 400  ✗ 0
     data_received..................: 156 kB  2.6 kB/s
     data_sent......................: 2.8 MB  47 kB/s
     http_req_blocked...............: avg=50µs    min=0s   med=0s     max=10ms
     http_req_duration..............: avg=12.5ms  min=5ms  med=11ms   max=50ms
     http_reqs......................: 200     3.33/s
     iteration_duration.............: avg=3s      min=2.9s med=3s     max=3.2s
     iterations.....................: 200     3.33/s
```

---

## 📁 Struktur Project

```
Uas Sister/
├── aggregator/                 # Aggregator service
│   ├── main.py                # FastAPI app + consumer workers
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile             # Container image
│
├── publisher/                 # Publisher service
│   ├── main.py               # Event generator
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile            # Container image
│
├── tests/                     # Test suite
│   ├── test_aggregator.py    # 18 unit & integration tests
│   ├── requirements.txt      # Test dependencies
│   ├── run_tests.sh          # Test runner script
│   └── load_test.js          # K6 load test
│
├── docker-compose.yml         # Service orchestration
├── pytest.ini                 # Pytest configuration
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
└── LAPORAN.md                 # Theoretical report (T1-T10)
```

---

## 🛠️ Keputusan Desain

### 1. Mengapa Python?

- ✅ FastAPI untuk async HTTP server (high performance)
- ✅ SQLAlchemy untuk database ORM (transaction support)
- ✅ Rich ecosystem untuk testing (pytest, httpx)
- ✅ Readable code untuk educational purpose

### 2. Mengapa PostgreSQL?

- ✅ ACID transactions out-of-the-box
- ✅ UNIQUE constraints untuk idempotency
- ✅ `ON CONFLICT` clause untuk upsert
- ✅ Excellent concurrency control
- ✅ Persistence dan reliability

### 3. Mengapa Redis?

- ✅ Fast in-memory queue
- ✅ AOF persistence untuk durability
- ✅ Simple pub-sub semantics
- ✅ Lightweight dan proven

### 4. Mengapa Docker Compose?

- ✅ Easy orchestration untuk multi-service
- ✅ Dependency management (`depends_on`)
- ✅ Named volumes untuk persistence
- ✅ Network isolation
- ✅ Reproducible environment

### 5. Isolation Level: READ COMMITTED

**Mengapa bukan SERIALIZABLE?**

- Event processing independent (low conflict rate)
- Database constraints handle concurrency
- Performance trade-off acceptable
- READ COMMITTED cukup untuk use case ini

**Anomaly yang diterima:**
- Phantom reads (tidak masalah untuk stats query)

**Mitigasi:**
- Unique constraint mencegah duplicate inserts
- Atomic SQL operations untuk counter updates

### 6. No Distributed Locking

**Mengapa tidak pakai Redis Lock atau Zookeeper?**

- ✅ Database constraint lebih simple
- ✅ No additional dependency
- ✅ No network overhead
- ✅ Atomic di database level
- ✅ Persist across failures

### 7. At-least-once + Idempotent Consumer

**Mengapa bukan exactly-once?**

- Exactly-once extremely difficult di distributed system
- At-least-once + idempotency gives same result
- Much simpler implementation
- Better performance
- Industry-standard pattern (Kafka, RabbitMQ, etc.)

---

## 🐛 Troubleshooting

### Issue: Aggregator tidak start

**Symptom:**
```
aggregator  | Error: connection refused
```

**Solution:**
```bash
# Check database health
docker compose ps storage

# Check logs
docker compose logs storage

# Restart
docker compose restart storage
docker compose restart aggregator
```

### Issue: Publisher send duplicates tapi tidak terdeteksi

**Symptom:**
```
duplicate_dropped = 0
```

**Possible Causes:**
1. Different `event_id` setiap request
2. Database constraint belum dibuat

**Solution:**
```bash
# Verify event_id
docker compose logs publisher | grep event_id

# Check constraint
docker compose exec storage psql -U loguser -d logdb -c "\d processed_events"
# Should show: uq_topic_event_id UNIQUE CONSTRAINT
```

### Issue: Tests gagal dengan connection refused

**Solution:**
```bash
# Pastikan aggregator running
docker compose ps aggregator

# Check port forwarding
curl http://localhost:8080/health

# Restart aggregator
docker compose restart aggregator
```

### Issue: Volume tidak persist setelah `down`

**Symptom:**
```
Stats reset to 0 after restart
```

**Solution:**
```bash
# JANGAN gunakan -v flag
docker compose down     # ✓ Keep volumes
docker compose down -v  # ✗ Remove volumes

# Verify volumes
docker volume ls | grep uas
```

### Issue: High memory usage

**Solution:**
```bash
# Check stats
docker stats

# Reduce batch size
# Edit docker-compose.yml:
publisher:
  environment:
    - BATCH_SIZE=50  # Default 100
    - DELAY_BETWEEN_BATCHES=1  # Default 0.5

# Restart
docker compose up -d publisher
```

### Issue: Test timeout

**Solution:**
```bash
# Increase timeout di tests/test_aggregator.py
TIMEOUT = 60.0  # Default 30.0

# Atau increase sleep duration
await asyncio.sleep(5)  # Default 2
```

---

## 📹 Video Demo

**Link YouTube:** [Akan diisi setelah recording]

**Durasi:** < 25 menit

**Konten yang harus ditampilkan:**

1. **Arsitektur Overview** (2 menit)
   - Diagram sistem
   - Penjelasan komponen
   - Alasan desain

2. **Build & Run** (3 menit)
   - `docker compose up --build`
   - Health checks
   - Log monitoring

3. **Idempotency Demo** (4 menit)
   - Send duplicate events
   - Show stats (duplicate_dropped)
   - Query events (verify single processing)

4. **Concurrency Demo** (3 menit)
   - Parallel requests
   - Show 4 workers processing
   - Stats consistency check

5. **Persistence Demo** (3 menit)
   - Show current stats
   - `docker compose down`
   - Verify volumes exist
   - `docker compose up`
   - Show same stats

6. **Transaction Demo** (3 menit)
   - Explain transaction boundary
   - Show database schema (constraint)
   - Demonstrate atomic updates

7. **Testing** (4 menit)
   - Run pytest suite
   - Show coverage report
   - Explain key tests

8. **Observability** (2 menit)
   - Health check endpoint
   - Metrics endpoint
   - Log aggregation

9. **Q&A / Keputusan Desain** (1 menit)
   - Summary keputusan teknis
   - Trade-offs

---

## 📚 Referensi

Lihat [LAPORAN.md](LAPORAN.md) untuk:
- Teori lengkap (T1-T10)
- Analisis Bab 1-13
- Sitasi APA 7th
- Penjelasan implementasi detail

---

## 🤝 Kontribusi

Project ini adalah tugas individual UAS. Namun, feedback dan saran sangat diterima.

**Contact:**
- Nama: [Nama Anda]
- NIM: [NIM Anda]
- Email: [Email Anda]

---

## 📄 License

Educational purpose only - ITK Sistem Terdistribusi 2025

---

## ✅ Checklist Pengerjaan

- [x] Implementasi Aggregator Service
- [x] Implementasi Publisher Service
- [x] Docker Compose setup
- [x] Dockerfile untuk semua services
- [x] Named volumes untuk persistence
- [x] Health checks
- [x] Idempotency & Deduplication
- [x] Transaction control
- [x] Concurrency handling (4 workers)
- [x] Unit & Integration Tests (18 tests)
- [x] README.md comprehensive
- [x] LAPORAN.md dengan teori (T1-T10)
- [ ] Load testing dengan K6
- [ ] Video demo (< 25 menit)
- [ ] Submit GitHub + Laporan PDF

---

**Last Updated:** 17 Desember 2025
