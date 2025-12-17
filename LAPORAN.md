# Laporan UAS Sistem Terdistribusi
## Pub-Sub Log Aggregator dengan Idempotency, Deduplication, dan Transaksi

**Nama:** [Nama Lengkap Anda]  
**NIM:** [NIM Anda]  
**Mata Kuliah:** Sistem Terdistribusi  
**Dosen:** [Nama Dosen]  
**Tanggal:** 17 Desember 2025

---

## Daftar Isi

1. [Bagian Teori](#bagian-teori)
   - [T1: Karakteristik Sistem Terdistribusi](#t1-karakteristik-sistem-terdistribusi)
   - [T2: Arsitektur Publish-Subscribe](#t2-arsitektur-publish-subscribe)
   - [T3: At-least-once vs Exactly-once Delivery](#t3-at-least-once-vs-exactly-once-delivery)
   - [T4: Skema Penamaan](#t4-skema-penamaan)
   - [T5: Ordering dan Timestamp](#t5-ordering-dan-timestamp)
   - [T6: Failure Modes dan Mitigasi](#t6-failure-modes-dan-mitigasi)
   - [T7: Eventual Consistency](#t7-eventual-consistency)
   - [T8: Desain Transaksi (ACID)](#t8-desain-transaksi-acid)
   - [T9: Kontrol Konkurensi](#t9-kontrol-konkurensi)
   - [T10: Orkestrasi dan Observability](#t10-orkestrasi-dan-observability)
2. [Bagian Implementasi](#bagian-implementasi)
3. [Hasil dan Analisis](#hasil-dan-analisis)
4. [Referensi](#referensi)

---

## Bagian Teori

### T1: Karakteristik Sistem Terdistribusi

**Pertanyaan:** Jelaskan karakteristik sistem terdistribusi dan trade-off desain pada Pub-Sub log aggregator.

**Jawaban:**

Sistem terdistribusi memiliki beberapa karakteristik utama yang relevan dengan implementasi log aggregator:

1. **Concurrency (Konkurensi)**: Sistem kami menjalankan multiple consumer workers (4 workers) secara paralel untuk memproses events dari queue. Ini meningkatkan throughput namun memerlukan mekanisme sinkronisasi untuk mencegah race conditions.

2. **Lack of Global Clock**: Tidak ada clock global yang sempurna antar komponen (publisher, broker, aggregator). Oleh karena itu, kami menggunakan timestamp pada setiap event sebagai logical ordering, dengan pemahaman bahwa clock skew dapat terjadi.

3. **Independent Failures**: Setiap komponen (publisher, aggregator, broker, database) dapat gagal secara independen. Implementasi kami menggunakan health checks, retry logic, dan persistent storage untuk menangani failure.

4. **No Shared Memory**: Komponen berkomunikasi melalui message passing (Redis queue) dan shared database (PostgreSQL), bukan shared memory.

**Trade-offs dalam desain:**

- **Consistency vs Availability**: Kami memilih eventual consistency dengan idempotency guarantee, memungkinkan high availability sambil tetap menjamin konsistensi data akhir.
- **Latency vs Throughput**: Menggunakan batching dan asynchronous processing meningkatkan throughput namun menambah latency minimal.
- **Complexity vs Performance**: Implementasi deduplication dan transaction control menambah kompleksitas namun crucial untuk data integrity.

**Referensi implementasi:** Lihat [aggregator/main.py](aggregator/main.py) pada fungsi `consumer_worker()` yang mengimplementasikan concurrent processing dengan idempotency guarantee.

**Sitasi:**  
[Sesuaikan dengan buku utama Anda, contoh format APA 7th Indonesia:]  
Tanenbaum, A. S., & Van Steen, M. (2017). *Sistem terdistribusi: Prinsip dan paradigma* (Edisi ke-3). Pearson Education.

---

### T2: Arsitektur Publish-Subscribe

**Pertanyaan:** Kapan memilih arsitektur publish-subscribe dibanding client-server? Berikan alasan teknis.

**Jawaban:**

Arsitektur publish-subscribe dipilih untuk log aggregator karena beberapa alasan teknis:

**Keunggulan Pub-Sub untuk Use Case Ini:**

1. **Decoupling**: Publisher dan subscriber (aggregator) tidak perlu mengetahui keberadaan satu sama lain. Publisher hanya perlu tahu topic, bukan endpoint spesifik. Ini memungkinkan:
   - Multiple publishers dapat mengirim ke topic yang sama tanpa koordinasi
   - Multiple consumers dapat memproses events secara paralel
   - Komponen dapat di-scale secara independen

2. **Asynchronous Communication**: Events diproses secara asynchronous melalui message queue (Redis). Ini memberikan:
   - Buffering capability: sistem dapat menangani burst traffic
   - Load leveling: consumer memproses dengan rate yang stabil
   - Non-blocking: publisher tidak menunggu processing selesai

3. **Event Fanout**: Satu event dapat di-consume oleh multiple subscribers dengan topic berbeda (extensible untuk future requirements)

4. **Temporal Decoupling**: Publisher dan consumer tidak perlu online bersamaan. Events dipersist di queue hingga diproses.

**Kapan Client-Server Lebih Cocok:**

- Request-response pattern dengan immediate feedback
- Transactional operations yang memerlukan confirmation instant
- Direct communication dengan routing sederhana

**Implementasi dalam sistem:**
- Publisher mengirim events ke Redis queue via HTTP API
- Multiple consumers (4 workers) mengambil dari queue secara paralel
- Database sebagai persistent store untuk deduplication

**Sitasi:**  
[Sesuaikan dengan buku Anda]  
Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2011). *Distributed systems: Concepts and design* (Edisi ke-5). Addison-Wesley.

---

### T3: At-least-once vs Exactly-once Delivery

**Pertanyaan:** Jelaskan perbedaan at-least-once dan exactly-once delivery, serta peran idempotent consumer.

**Jawaban:**

**At-least-once Delivery:**
- Sistem menjamin setiap message akan dikirim minimal satu kali
- Kemungkinan duplicate delivery (network retry, crash recovery)
- Lebih mudah diimplementasi dan performant
- **Trade-off**: Consumer harus handle duplicates

**Exactly-once Delivery:**
- Setiap message diproses tepat satu kali, tidak lebih tidak kurang
- Sulit/impossible untuk dijamin di distributed systems (Two Generals Problem)
- Memerlukan koordinasi kompleks dan overhead tinggi
- **Trade-off**: Performance dan complexity cost

**Pendekatan Sistem Kami: At-least-once + Idempotent Consumer**

Kami menggunakan at-least-once delivery dengan idempotent consumer pattern:

1. **Publisher** dapat mengirim duplicate (simulasi network retry, intentional duplicates untuk testing)
2. **Broker (Redis)** tidak guarantee exactly-once
3. **Consumer (Aggregator)** mengimplementasi idempotency via:
   - Unique constraint pada (topic, event_id) di database
   - Transaction-based deduplication
   - Setiap event hanya diproses sekali walau diterima berkali-kali

**Implementasi Idempotent Consumer:**

```python
# Lihat aggregator/main.py, fungsi process_event_with_transaction()
# Menggunakan PostgreSQL ON CONFLICT DO NOTHING
stmt = insert(ProcessedEvent).values(...).on_conflict_do_nothing(
    index_elements=['topic', 'event_id']
)
```

Dengan pendekatan ini, sistem mencapai **effectively exactly-once processing** (idempotent semantics) tanpa overhead exactly-once delivery infrastructure.

**Bukti dalam Testing:**  
Test #8-11 (`test_08_duplicate_detection`, dll) memverifikasi bahwa duplicate events tidak diproses ulang.

**Sitasi:**  
[Sesuaikan dengan buku Anda]  
Kleppmann, M. (2017). *Designing data-intensive applications*. O'Reilly Media.

---

### T4: Skema Penamaan

**Pertanyaan:** Jelaskan skema penamaan topic dan event_id untuk deduplication yang collision-resistant.

**Jawaban:**

**Skema Penamaan Topic:**

Format: `<domain>.<entity>.<action>`

Contoh:
- `user.registration` - event user melakukan registrasi
- `order.created` - event order dibuat
- `payment.completed` - event pembayaran selesai

**Keuntungan:**
- Hierarchical dan organized
- Mudah di-filter dan di-route
- Scalable untuk menambah domain baru
- Clear semantic meaning

**Skema Event ID (Collision-Resistant):**

Format: `<timestamp_ms>-<uuid>-<counter>`

Contoh: `1703001234567-a3f5c8b9-12345`

**Komponen:**
1. **Timestamp millisecond**: Memberikan ordering temporal dan uniqueness berbasis waktu
2. **UUID (8 char)**: Random identifier untuk mencegah collision pada timestamp sama
3. **Monotonic counter**: Additional uniqueness guarantee dalam single publisher

**Collision Resistance:**

Probabilitas collision sangat rendah karena:
- Timestamp: 1ms granularity
- UUID: 2^32 possible values (8 hex chars)
- Counter: Monotonically increasing
- **Combined**: P(collision) ≈ 10^-15 untuk rate normal

**Database Schema untuk Deduplication:**

```sql
CREATE TABLE processed_events (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    -- ... other fields
    CONSTRAINT uq_topic_event_id UNIQUE (topic, event_id)
);
CREATE INDEX idx_topic ON processed_events(topic);
```

Unique constraint `(topic, event_id)` menjamin:
- Event dengan ID sama pada topic berbeda dapat coexist
- Event duplicate (topic + event_id sama) akan rejected oleh database
- Atomic operation level database (tidak bisa di-bypass oleh race condition)

**Implementasi:** Lihat `publisher/main.py` fungsi `generate_event_id()` dan `aggregator/main.py` model `ProcessedEvent`.

**Sitasi:**  
[Sesuaikan dengan buku Anda]

---

### T5: Ordering dan Timestamp

**Pertanyaan:** Jelaskan ordering praktis dengan timestamp + monotonic counter, batasan, dan dampaknya.

**Jawaban:**

**Strategi Ordering:**

1. **Physical Timestamp (ISO8601)**:
   - Setiap event memiliki timestamp saat creation
   - Format: `2025-12-17T10:30:45.123456Z` (UTC)
   - Digunakan untuk approximate ordering

2. **Monotonic Counter**:
   - Counter incremental per publisher
   - Guarantee ordering dalam single publisher
   - Digabung dalam event_id: `timestamp-uuid-counter`

**Batasan:**

1. **Clock Skew**: 
   - Berbeda publisher dapat memiliki clock yang berbeda
   - NTP drift dapat menyebabkan timestamp tidak perfectly ordered
   - **Dampak**: Events dapat "out of order" jika dari publisher berbeda

2. **Network Latency Variable**:
   - Event dengan timestamp lebih awal bisa sampai lebih lambat
   - **Dampak**: Processing order ≠ timestamp order

3. **No Total Ordering Guarantee**:
   - Sistem hanya guarantee eventual consistency
   - Tidak ada global ordering across topics

**Mitigasi:**

1. **Logical Timestamps**: Bisa ditambahkan Lamport clock atau vector clock jika total ordering critical
2. **Windowing**: Implementasi time window untuk batch processing
3. **Idempotency**: Karena system idempotent, order tidak affect correctness (hanya performance)

**Implementasi dalam Sistem:**

```python
# Publisher generates timestamp
timestamp = datetime.now(timezone.utc).isoformat()
event_id = f"{int(time.time() * 1000)}-{uuid}-{counter}"
```

Timestamp digunakan untuk:
- Audit trail (kapan event terjadi)
- Query filtering (`GET /events?since=timestamp`)
- Debugging dan observability

**Ordering bukan requirement kritis** untuk use case kami karena:
- Setiap event atomic dan independent
- Idempotency menjamin correctness regardless of order
- Statistik (received, unique, duplicate) eventual consistent

**Sitasi:**  
[Sesuaikan dengan buku Anda, contoh Bab 5: Time and Ordering]

---

### T6: Failure Modes dan Mitigasi

**Pertanyaan:** Jelaskan failure modes dan strategi mitigasi (retry, backoff, durable store, crash recovery).

**Jawaban:**

**Failure Modes:**

1. **Publisher Failure**:
   - **Mode**: Publisher crash sebelum confirm send
   - **Dampak**: Events lost
   - **Mitigasi**: 
     - Retry with exponential backoff (implemented in requests library)
     - Idempotency memungkinkan safe retry
     - Local buffering sebelum send (optional enhancement)

2. **Network Failure**:
   - **Mode**: Request timeout, connection drop
   - **Dampak**: Duplicate sends (retry), lost messages
   - **Mitigasi**:
     - HTTP retry strategy (5 retries, backoff factor 1s)
     - At-least-once semantics + idempotent consumer
     - Health checks sebelum publish

3. **Aggregator Failure**:
   - **Mode**: Aggregator crash saat processing
   - **Dampak**: Events di queue tidak diproses
   - **Mitigasi**:
     - Redis queue persistence (`appendonly yes`)
     - Multiple workers (4) untuk availability
     - Graceful shutdown handling
     - Container restart policy: `unless-stopped`

4. **Database Failure**:
   - **Mode**: Connection lost, database crash
   - **Dampak**: Tidak bisa commit transactions
   - **Mitigasi**:
     - Connection pooling with pre-ping
     - Transaction rollback automatic
     - Persistent volume untuk data durability
     - Health check monitoring

5. **Broker (Redis) Failure**:
   - **Mode**: Redis crash, data loss
   - **Dampak**: Queued events lost
   - **Mitigasi**:
     - AOF (Append Only File) persistence
     - Named volume mount
     - Health checks
     - Consider adding Redis Sentinel/Cluster untuk HA (future work)

**Strategi Retry dan Backoff:**

```python
# Implemented in publisher/main.py
retry_strategy = Retry(
    total=5,
    backoff_factor=1,  # 1s, 2s, 4s, 8s, 16s
    status_forcelist=[429, 500, 502, 503, 504]
)
```

**Crash Recovery:**

1. **Database State Persisten**:
   - PostgreSQL di named volume `uas_pg_data`
   - Setelah container recreate, data tetap ada
   - Deduplication tetap berfungsi

2. **Redis Queue Persisten**:
   - AOF di volume `uas_broker_data`
   - Events di queue tidak hilang saat restart

3. **Stateless Application**:
   - Aggregator dan publisher stateless
   - Semua state di database/redis
   - Mudah di-restart tanpa state loss

**Testing Failure Scenarios:**

Untuk test persistence:
```bash
# Stop containers
docker compose down

# Verify volumes tetap ada
docker volume ls | grep uas

# Restart
docker compose up -d

# Verify data still intact
curl http://localhost:8080/stats
```

**Sitasi:**  
[Sesuaikan dengan buku Anda, Bab 6: Fault Tolerance]

---

### T7: Eventual Consistency

**Pertanyaan:** Jelaskan eventual consistency pada aggregator dan peran idempotency + deduplication.

**Jawaban:**

**Eventual Consistency dalam Log Aggregator:**

Sistem kami mengimplementasi eventual consistency model:

1. **Write Path** (Publisher → Queue → Consumer → Database):
   - Publisher menulis ke queue (fast, async)
   - Consumer memproses dengan rate sendiri
   - **Gap temporal** antara publish dan process
   - **Eventually**: Semua events akan diproses

2. **Read Path** (Query → Database):
   - `GET /events` membaca dari database
   - Hanya menampilkan events yang **sudah diproses**
   - Mungkin ada events di queue belum terlihat
   - **Eventually**: Semua events akan muncul

3. **Statistics** (`GET /stats`):
   - Counter di-update per transaction
   - Concurrent updates dapat menyebabkan slight delay
   - **Eventually**: Angka akan consistent dan accurate

**Peran Idempotency:**

Idempotency critical untuk eventual consistency karena:

1. **Retry-safe**: Publisher dapat retry tanpa khawatir duplicate processing
2. **Order-independent**: Processing order tidak affect final state
3. **Crash-recovery safe**: Reprocessing setelah crash tidak corrupt data

**Implementasi:**
```python
# Every event process is idempotent
# Database constraint + transaction guarantee ini
stmt = insert(ProcessedEvent).values(...).on_conflict_do_nothing()
```

**Peran Deduplication:**

Deduplication menjamin eventual consistency dengan:

1. **Deterministic State**: 
   - Setiap unique (topic, event_id) hanya diproses sekali
   - Tidak peduli berapa kali diterima
   - Final state always sama

2. **Consistent Statistics**:
   - `unique_processed` hanya count distinct events
   - `duplicate_dropped` track redundant messages
   - Sum always consistent: `received = unique + duplicate`

3. **Persistent Dedup Store**:
   - Database menyimpan semua processed events
   - Survive restarts dan crashes
   - Query-able untuk verification

**Contoh Skenario:**

```
t0: Publisher send Event A
t1: Event A masuk queue
t2: Consumer 1 process Event A → DB insert success
t3: Network glitch, Publisher retry Event A
t4: Event A (duplicate) masuk queue
t5: Consumer 2 process Event A → DB insert ignored (conflict)
t6: Statistics: unique_processed +1, duplicate_dropped +1
Final: State consistent, Event A processed exactly once
```

**Testing Eventual Consistency:**

Test #12-14 memverifikasi consistency under:
- Concurrent same events
- High load (50+ events)
- Statistics accumulation

**CAP Theorem Context:**

Sistem kami:
- **Partition Tolerance**: ✓ (dapat handle network partition via retry)
- **Availability**: ✓ (async processing, multiple workers)
- **Consistency**: Eventual (bukan strong consistency)

Trade-off ini cocok untuk log aggregation karena tidak memerlukan immediate consistency.

**Sitasi:**  
[Sesuaikan dengan buku Anda, Bab 7: Consistency and Replication]

---

### T8: Desain Transaksi (ACID)

**Pertanyaan:** Jelaskan desain transaksi dengan ACID, isolation level, dan strategi menghindari lost-update.

**Jawaban:**

**ACID Properties dalam Implementasi:**

1. **Atomicity (Atomisitas)**:
   - Setiap event processing adalah satu transaction
   - Operations: insert event + update stats
   - **All or nothing**: Jika salah satu gagal, semua rollback
   
   ```python
   session.begin()  # Start transaction
   try:
       session.execute(insert_event)
       session.execute(update_stats)
       session.commit()  # Atomic commit
   except:
       session.rollback()  # Atomic rollback
   ```

2. **Consistency (Konsistensi)**:
   - Database constraints enforced:
     - `UNIQUE (topic, event_id)` untuk deduplication
     - `NOT NULL` pada required fields
     - Foreign key integrity (jika ada relasi)
   - Application-level consistency:
     - `received = unique_processed + duplicate_dropped` always true

3. **Isolation (Isolasi)**:
   - **Level: READ COMMITTED** (PostgreSQL default)
   - Setiap transaction hanya lihat committed data
   - Mencegah dirty reads
   - Phantom reads mungkin (tapi tidak masalah untuk use case kami)

4. **Durability (Durabilitas)**:
   - Setelah commit, data persist di disk
   - PostgreSQL WAL (Write-Ahead Logging)
   - Named volume untuk persistence across container restart

**Isolation Level Analysis:**

**Pilihan: READ COMMITTED**

Kenapa bukan SERIALIZABLE?
- SERIALIZABLE lebih strict tapi higher overhead
- Use case kami: independent events, low conflict probability
- READ COMMITTED cukup karena:
  - Unique constraint handle concurrent inserts
  - Counter updates atomic via SQL
  - No complex read-modify-write cycles

**Potensi Anomaly:**
- **Phantom Read**: Query count events bisa berbeda jika ada insert concurrent
  - **Mitigasi**: Tidak critical, eventual consistency acceptable
- **Write Skew**: Dua transaction update based on stale read
  - **Mitigasi**: Tidak ada read-modify-write pattern yang vulnerable

**Strategi Menghindari Lost Update:**

1. **Atomic SQL Operations**:
   ```sql
   -- WRONG: Read-modify-write (vulnerable)
   SELECT count FROM stats WHERE id = 1;
   UPDATE stats SET count = <calculated> WHERE id = 1;
   
   -- CORRECT: Atomic increment (safe)
   UPDATE stats SET count = count + 1 WHERE id = 1;
   ```
   
   Implementation: [aggregator/main.py](aggregator/main.py) line ~250

2. **Database Constraints sebagai Guards**:
   ```sql
   CONSTRAINT uq_topic_event_id UNIQUE (topic, event_id)
   ```
   Concurrent inserts dengan same key:
   - First: success
   - Others: IntegrityError → handled as duplicate
   - **No lost update possible**

3. **Optimistic Locking Alternative** (not implemented, but possible):
   ```sql
   UPDATE events SET status = 'processed', version = version + 1
   WHERE id = ? AND version = ?
   ```
   If version mismatch → retry

4. **Pessimistic Locking Alternative** (not implemented):
   ```sql
   SELECT ... FOR UPDATE  -- Row-level lock
   ```
   More overhead, not needed karena conflict rendah

**Transaction Boundary Example:**

```python
def process_event_with_transaction(event):
    session = Session()
    try:
        # BEGIN (implicit)
        
        # 1. Increment received counter (atomic)
        session.execute(
            "UPDATE event_stats SET received_count = received_count + 1"
        )
        
        # 2. Insert event (with conflict handling)
        stmt = insert(ProcessedEvent).values(...).on_conflict_do_nothing()
        result = session.execute(stmt)
        
        # 3. Conditional update based on result
        if result.rowcount > 0:
            session.execute(
                "UPDATE event_stats SET unique_processed = unique_processed + 1"
            )
        else:
            session.execute(
                "UPDATE event_stats SET duplicate_dropped = duplicate_dropped + 1"
            )
        
        session.commit()  # COMMIT
        return True
        
    except Exception as e:
        session.rollback()  # ROLLBACK
        return False
    finally:
        session.close()
```

**Testing Transaction Correctness:**

Test #12: Concurrent same event → only one processed
Test #13: Concurrent different events → all processed
Test #14: High load consistency check

**Performance Considerations:**

- Short transaction duration (minimize lock time)
- No network calls inside transaction
- Batch operations when possible (future enhancement)

**Sitasi:**  
[Sesuaikan dengan buku Anda, Bab 8: Transactions]  
Garcia-Molina, H., Ullman, J. D., & Widom, J. (2008). *Database systems: The complete book* (Edisi ke-2). Pearson.

---

### T9: Kontrol Konkurensi

**Pertanyaan:** Jelaskan mekanisme kontrol konkurensi: locking, unique constraints, upsert, dan idempotent write pattern.

**Jawaban:**

**Kontrol Konkurensi dalam Multi-Worker Environment:**

Sistem kami menjalankan 4 consumer workers secara paralel. Tanpa kontrol konkurensi yang tepat, ini dapat menyebabkan:
- Race conditions
- Lost updates
- Duplicate processing
- Inconsistent statistics

**Strategi yang Diimplementasi:**

**1. Unique Constraints (Database-Level)**

Primary mechanism untuk deduplication:

```sql
CREATE TABLE processed_events (
    ...
    CONSTRAINT uq_topic_event_id UNIQUE (topic, event_id)
);
```

**Cara Kerja:**
- Worker 1 dan Worker 2 process event A bersamaan
- Keduanya mencoba insert ke database
- Database hanya allow one insert succeed
- Yang kedua dapat IntegrityError
- No application-level locking needed

**Keuntungan:**
- Atomic operation level database engine
- Tidak ada deadlock possibility
- Scalable (no distributed locking)
- Persist across restarts

**2. Idempotent Upsert Pattern (ON CONFLICT)**

PostgreSQL specific feature:

```python
stmt = insert(ProcessedEvent).values(
    topic=event.topic,
    event_id=event.event_id,
    ...
).on_conflict_do_nothing(
    index_elements=['topic', 'event_id']
)

result = session.execute(stmt)
if result.rowcount > 0:
    # Successfully inserted (new event)
    update_unique_counter()
else:
    # Conflict occurred (duplicate)
    update_duplicate_counter()
```

**Cara Kerja:**
- Attempt insert
- If conflict with unique constraint → do nothing (no error)
- Check rowcount untuk determine apakah insert succeed
- Update counter accordingly

**Keuntungan:**
- Single SQL statement (atomic)
- No exception handling overhead
- Cleaner code
- Idempotent by design

**3. Atomic Counter Updates (SQL-Level)**

Menghindari lost update pada statistics:

```sql
-- UNSAFE (lost update possible):
count = SELECT received_count FROM stats WHERE id = 1;
UPDATE stats SET received_count = count + 1 WHERE id = 1;

-- SAFE (atomic):
UPDATE stats SET received_count = received_count + 1 WHERE id = 1;
```

**Cara Kerja:**
- Database evaluate `count + 1` at execution time
- Atomic read-modify-write
- Multiple concurrent updates safely handled

**4. Transaction Isolation**

Setiap event processing wrapped in transaction:

```python
session.begin()
try:
    # All operations in single transaction
    atomic_counter_update()
    idempotent_insert()
    conditional_counter_update()
    session.commit()
except:
    session.rollback()
```

**Isolation Level: READ COMMITTED**
- Prevent dirty reads
- Allow concurrent transactions
- Sufficient untuk use case dengan low conflict rate

**5. No Shared State Pattern**

Application-level best practice:
- Each worker completely stateless
- No shared variables between workers
- All state in database or Redis
- Workers can crash/restart independently

**Alternatif yang TIDAK Digunakan (dan Alasan):**

**Pessimistic Locking (SELECT FOR UPDATE):**
```sql
SELECT * FROM processed_events WHERE ... FOR UPDATE;
```
- ❌ Higher latency
- ❌ Potential deadlocks
- ❌ Reduced concurrency
- ✓ Stronger guarantee (not needed for our use case)

**Optimistic Locking (Version Field):**
```sql
UPDATE events SET ..., version = version + 1 WHERE id = ? AND version = ?;
```
- ❌ Requires retry logic
- ❌ More complex code
- ❌ Not needed karena unique constraint sufficient

**Distributed Locks (Redis/Zookeeper):**
```python
with redis_lock.acquire("event:{event_id}"):
    process_event()
```
- ❌ Additional dependency
- ❌ Network overhead
- ❌ Potential lock timeout issues
- ❌ Not needed karena database constraint sufficient

**Concurrency Testing:**

Test #12: Concurrent same event
```python
# 10 workers try to process same event simultaneously
tasks = [publish_event(same_event) for _ in range(10)]
await asyncio.gather(*tasks)

# Verify: unique_processed increment by 1 only
assert unique_processed_delta == 1
```

Test #13: Concurrent different events
```python
# 10 workers process different events simultaneously
tasks = [publish_event(unique_event[i]) for i in range(10)]
await asyncio.gather(*tasks)

# Verify: all 10 processed
assert unique_processed_delta == 10
```

**Performance Impact:**

| Mechanism | Overhead | Scalability | Safety |
|-----------|----------|-------------|--------|
| Unique Constraint | Low | High | High |
| Upsert Pattern | Low | High | High |
| Atomic SQL | Very Low | High | High |
| Pessimistic Lock | High | Low | Very High |
| Optimistic Lock | Medium | Medium | High |

**Sitasi:**  
[Sesuaikan dengan buku Anda, Bab 9: Concurrency Control]  
Bernstein, P. A., Hadzilacos, V., & Goodman, N. (1987). *Concurrency control and recovery in database systems*. Addison-Wesley.

---

### T10: Orkestrasi dan Observability

**Pertanyaan:** Jelaskan orkestrasi Docker Compose, keamanan jaringan lokal, persistensi volume, dan observability.

**Jawaban:**

**Orkestrasi dengan Docker Compose:**

**Service Dependencies:**
```yaml
services:
  storage:
    # No dependencies
    healthcheck: pg_isready
  
  broker:
    # No dependencies
    healthcheck: redis-cli ping
  
  aggregator:
    depends_on:
      storage:
        condition: service_healthy
      broker:
        condition: service_healthy
  
  publisher:
    depends_on:
      aggregator:
        condition: service_healthy
```

**Startup Sequence:**
1. `storage` dan `broker` start first (parallel)
2. Wait untuk health checks pass
3. `aggregator` start setelah dependencies healthy
4. `publisher` start terakhir

**Benefits:**
- Automatic ordering
- Graceful startup
- Failure handling (restart unhealthy services)

**Keamanan Jaringan Lokal:**

**1. Internal Network Isolation:**
```yaml
networks:
  uas-network:
    driver: bridge
    name: uas-network
```

Semua services dalam satu network:
- Internal DNS resolution (by service name)
- No external network access required
- Isolated dari host network (kecuali exposed ports)

**2. Minimal Port Exposure:**
```yaml
aggregator:
  ports:
    - "8080:8080"  # Only HTTP API exposed

storage:
  ports:
    - "5432:5432"  # Optional, untuk debugging only

broker:
  ports:
    - "6379:6379"  # Optional, untuk debugging only
```

Untuk production, hapus expose storage dan broker ports.

**3. Non-Root User dalam Container:**
```dockerfile
# aggregator/Dockerfile
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser
```

Security benefits:
- Limit container capabilities
- Prevent privilege escalation
- Follow least privilege principle

**4. No External Dependencies:**
- Tidak ada calls ke public APIs
- Tidak ada outbound internet traffic
- Semua dependencies self-contained
- Reproducible environment

**Persistensi dengan Named Volumes:**

**Volume Definitions:**
```yaml
volumes:
  uas_pg_data:
    name: uas_pg_data
    driver: local
  
  uas_broker_data:
    name: uas_broker_data
    driver: local
  
  uas_aggregator_logs:
    name: uas_aggregator_logs
    driver: local
```

**Service Mounts:**
```yaml
storage:
  volumes:
    - pg_data:/var/lib/postgresql/data

broker:
  volumes:
    - broker_data:/data

aggregator:
  volumes:
    - aggregator_logs:/app/logs
```

**Persistence Verification:**

```bash
# Stop dan remove containers
docker compose down

# Verify volumes masih ada
docker volume ls | grep uas
# Output:
# uas_pg_data
# uas_broker_data
# uas_aggregator_logs

# Restart containers
docker compose up -d

# Data masih intact
curl http://localhost:8080/stats
# Previous statistics still available
```

**Observability:**

**1. Health Checks:**

Semua services memiliki health checks:

```yaml
aggregator:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
```

Check health status:
```bash
docker compose ps
# Shows health: starting, healthy, unhealthy
```

**2. Logging:**

Structured logging di semua services:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger.info("✓ Processed event: topic=%s, event_id=%s", topic, event_id)
logger.warning("⊗ Dropped duplicate: topic=%s, event_id=%s", topic, event_id)
logger.error("✗ Processing failed: %s", error, exc_info=True)
```

View logs:
```bash
docker compose logs -f aggregator
docker compose logs -f publisher
docker compose logs --tail=100 storage
```

**3. Metrics Endpoint:**

`GET /stats` provides observability:
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

**4. Query Endpoint:**

`GET /events?topic=X` untuk audit:
- Verify events processed
- Check timestamps
- Validate payloads

**5. Container Statistics:**

```bash
docker stats
# Shows CPU, memory, network, I/O
```

**Monitoring Best Practices:**

**Readiness vs Liveness (Implementasi):**

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  # Health check acts as both readiness and liveness
  # healthy = ready to accept traffic
  # unhealthy (3 retries) = container restarted
```

**Health Check Logic:**
```python
@app.get("/health")
async def health_check():
    # Check database connection
    # Check Redis connection
    # Return 200 if both OK, 503 if not
```

**Restart Policies:**
```yaml
aggregator:
  restart: unless-stopped  # Auto-restart on failure

publisher:
  restart: "no"  # Run once, don't restart
```

**Future Enhancements (Optional):**

- **Prometheus metrics export**: Add `/metrics` endpoint
- **Grafana dashboards**: Visualize throughput, latency, error rate
- **Distributed tracing**: OpenTelemetry untuk trace request flow
- **Alerting**: Alert on health check failures, high error rate

**Documentation:**

Semua configuration documented dalam:
- `docker-compose.yml` (inline comments)
- `README.md` (setup instructions)
- `LAPORAN.md` (architecture explanation)

**Sitasi:**  
[Sesuaikan dengan buku Anda, Bab 12-13: Web-based Systems and Coordination]  
Bass, L., Clements, P., & Kazman, R. (2021). *Software architecture in practice* (Edisi ke-4). Addison-Wesley.

---

## Bagian Implementasi

[Isi dengan analisis implementasi Anda]

### Arsitektur Sistem

[Diagram dan penjelasan]

### Komponen-Komponen

#### 1. Aggregator Service
[Penjelasan detail]

#### 2. Publisher Service
[Penjelasan detail]

#### 3. Storage (PostgreSQL)
[Penjelasan detail]

#### 4. Broker (Redis)
[Penjelasan detail]

### Keputusan Desain Kunci

[Penjelasan keputusan teknis]

---

## Hasil dan Analisis

### Hasil Testing

[Screenshot test results, statistics, dll]

### Analisis Performa

[Throughput, latency, resource usage]

### Verifikasi Fitur

- ✅ Idempotency
- ✅ Deduplication
- ✅ Transaction/Concurrency
- ✅ Persistence
- ✅ Health monitoring

---

## Referensi

[Daftar referensi dalam format APA 7th edisi Bahasa Indonesia]

### Buku Utama

Tanenbaum, A. S., & Van Steen, M. (2017). *Sistem terdistribusi: Prinsip dan paradigma* (Edisi ke-3). Pearson Education.

[Sesuaikan dengan buku utama Anda dari docs/buku-utama.pdf]

### Referensi Tambahan

Kleppmann, M. (2017). *Designing data-intensive applications: The big ideas behind reliable, scalable, and maintainable systems*. O'Reilly Media.

Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2011). *Distributed systems: Concepts and design* (Edisi ke-5). Addison-Wesley.

PostgreSQL Global Development Group. (2024). *PostgreSQL 16 documentation*. https://www.postgresql.org/docs/16/

Redis Ltd. (2024). *Redis documentation*. https://redis.io/docs/

Docker Inc. (2024). *Docker Compose documentation*. https://docs.docker.com/compose/

---

**Catatan Penggunaan Template:**

1. Ganti semua `[...]` dengan informasi Anda
2. Sesuaikan sitasi dengan buku utama Anda (docs/buku-utama.pdf)
3. Tambahkan screenshot dan diagram di bagian implementasi
4. Isi hasil testing dengan data aktual dari run
5. Review dan expand penjelasan sesuai kebutuhan (target 150-250 kata per poin teori)
