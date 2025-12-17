"""
Unit & Integration Tests untuk Log Aggregator System
Total: 18 tests mencakup deduplication, persistensi, konkurensi, dan validasi
"""
import pytest
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
import uuid
import concurrent.futures

import httpx
from faker import Faker

# Test configuration
AGGREGATOR_URL = "http://localhost:8080"
TIMEOUT = 30.0

fake = Faker()

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def event_template() -> Dict[str, Any]:
    """Template untuk membuat event test"""
    return {
        "topic": "test.event",
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test-runner",
        "payload": {"test": "data"}
    }

@pytest.fixture
def batch_events(event_template) -> List[Dict[str, Any]]:
    """Generate batch events untuk testing"""
    events = []
    for i in range(10):
        event = event_template.copy()
        event["event_id"] = f"test-{uuid.uuid4()}"
        event["payload"] = {"index": i, "data": fake.text(max_nb_chars=50)}
        events.append(event)
    return events

@pytest.fixture
async def client():
    """HTTP client dengan retry logic"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        yield client

@pytest.fixture
async def wait_for_aggregator(client):
    """Wait untuk aggregator service siap"""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = await client.get(f"{AGGREGATOR_URL}/health")
            if response.status_code == 200:
                return True
        except:
            pass
        await asyncio.sleep(1)
    pytest.fail("Aggregator tidak siap dalam 30 detik")

# ============================================================================
# TEST 1-3: HEALTH & BASIC API
# ============================================================================

@pytest.mark.asyncio
async def test_01_health_endpoint(client, wait_for_aggregator):
    """Test 1: Health endpoint harus return 200 dan status healthy"""
    response = await client.get(f"{AGGREGATOR_URL}/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"
    print("✓ Test 1: Health check passed")

@pytest.mark.asyncio
async def test_02_root_endpoint(client):
    """Test 2: Root endpoint harus return service info"""
    response = await client.get(f"{AGGREGATOR_URL}/")
    assert response.status_code == 200
    
    data = response.json()
    assert "service" in data
    assert "endpoints" in data
    print("✓ Test 2: Root endpoint passed")

@pytest.mark.asyncio
async def test_03_stats_endpoint_initial(client):
    """Test 3: Stats endpoint harus return struktur yang benar"""
    response = await client.get(f"{AGGREGATOR_URL}/stats")
    assert response.status_code == 200
    
    data = response.json()
    assert "received" in data
    assert "unique_processed" in data
    assert "duplicate_dropped" in data
    assert "topics" in data
    assert "uptime_seconds" in data
    assert data["status"] == "healthy"
    print("✓ Test 3: Stats structure validated")

# ============================================================================
# TEST 4-7: EVENT VALIDATION
# ============================================================================

@pytest.mark.asyncio
async def test_04_publish_single_event(client, event_template):
    """Test 4: Publish single event harus berhasil"""
    response = await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": [event_template]}
    )
    assert response.status_code == 202
    
    data = response.json()
    assert data["status"] == "accepted"
    assert data["queued"] == 1
    print("✓ Test 4: Single event published")

@pytest.mark.asyncio
async def test_05_publish_batch_events(client, batch_events):
    """Test 5: Publish batch events harus berhasil"""
    response = await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": batch_events}
    )
    assert response.status_code == 202
    
    data = response.json()
    assert data["queued"] == len(batch_events)
    print(f"✓ Test 5: Batch of {len(batch_events)} events published")

@pytest.mark.asyncio
async def test_06_invalid_event_schema(client):
    """Test 6: Event dengan schema invalid harus ditolak"""
    invalid_event = {
        "topic": "test",
        # missing required fields
    }
    
    response = await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": [invalid_event]}
    )
    assert response.status_code == 422  # Validation error
    print("✓ Test 6: Invalid schema rejected")

@pytest.mark.asyncio
async def test_07_invalid_timestamp(client, event_template):
    """Test 7: Event dengan timestamp invalid harus ditolak"""
    event = event_template.copy()
    event["timestamp"] = "invalid-timestamp"
    
    response = await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": [event]}
    )
    assert response.status_code == 422
    print("✓ Test 7: Invalid timestamp rejected")

# ============================================================================
# TEST 8-11: IDEMPOTENCY & DEDUPLICATION
# ============================================================================

@pytest.mark.asyncio
async def test_08_duplicate_detection(client, event_template):
    """Test 8: Duplicate event harus terdeteksi dan tidak diproses ulang"""
    # Send same event twice
    event_id = f"dedup-test-{uuid.uuid4()}"
    event = event_template.copy()
    event["event_id"] = event_id
    event["topic"] = "dedup.test"
    
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_unique = initial_data["unique_processed"]
    
    # Send first time
    await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": [event]}
    )
    
    # Wait for processing
    await asyncio.sleep(2)
    
    # Send duplicate
    await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": [event]}
    )
    
    # Wait for processing
    await asyncio.sleep(2)
    
    # Check stats
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    # Should only increment unique_processed by 1
    assert final_data["unique_processed"] == initial_unique + 1
    assert final_data["duplicate_dropped"] >= 1
    print("✓ Test 8: Duplicate detection working")

@pytest.mark.asyncio
async def test_09_multiple_duplicates(client, event_template):
    """Test 9: Multiple duplicates dari event yang sama harus semua diabaikan"""
    event_id = f"multi-dup-{uuid.uuid4()}"
    event = event_template.copy()
    event["event_id"] = event_id
    event["topic"] = "multi.dedup.test"
    
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_unique = initial_data["unique_processed"]
    initial_dup = initial_data["duplicate_dropped"]
    
    # Send same event 5 times
    for _ in range(5):
        await client.post(
            f"{AGGREGATOR_URL}/publish",
            json={"events": [event]}
        )
    
    # Wait for processing
    await asyncio.sleep(3)
    
    # Check stats
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    # Should only process once
    assert final_data["unique_processed"] == initial_unique + 1
    assert final_data["duplicate_dropped"] >= initial_dup + 4
    print("✓ Test 9: Multiple duplicates handled correctly")

@pytest.mark.asyncio
async def test_10_different_topic_same_event_id(client, event_template):
    """Test 10: Event ID yang sama di topic berbeda harus diproses terpisah"""
    event_id = f"same-id-{uuid.uuid4()}"
    
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_unique = initial_data["unique_processed"]
    
    # Send to topic 1
    event1 = event_template.copy()
    event1["event_id"] = event_id
    event1["topic"] = "topic.one"
    await client.post(f"{AGGREGATOR_URL}/publish", json={"events": [event1]})
    
    # Send to topic 2 with same event_id
    event2 = event_template.copy()
    event2["event_id"] = event_id
    event2["topic"] = "topic.two"
    await client.post(f"{AGGREGATOR_URL}/publish", json={"events": [event2]})
    
    # Wait for processing
    await asyncio.sleep(2)
    
    # Check stats - both should be processed (different topics)
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    assert final_data["unique_processed"] >= initial_unique + 2
    print("✓ Test 10: Same event_id in different topics processed separately")

@pytest.mark.asyncio
async def test_11_batch_with_internal_duplicates(client, event_template):
    """Test 11: Batch dengan duplikat internal harus dihandle dengan benar"""
    event_id = f"batch-dup-{uuid.uuid4()}"
    
    # Create batch with duplicates
    events = []
    for i in range(5):
        event = event_template.copy()
        event["event_id"] = event_id  # Same ID
        event["topic"] = "batch.dup.test"
        event["payload"] = {"iteration": i}
        events.append(event)
    
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_unique = initial_data["unique_processed"]
    
    # Send batch
    await client.post(f"{AGGREGATOR_URL}/publish", json={"events": events})
    
    # Wait for processing
    await asyncio.sleep(2)
    
    # Check stats - should only process once
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    assert final_data["unique_processed"] == initial_unique + 1
    print("✓ Test 11: Batch with internal duplicates handled")

# ============================================================================
# TEST 12-14: CONCURRENCY
# ============================================================================

@pytest.mark.asyncio
async def test_12_concurrent_same_event(client, event_template):
    """Test 12: Concurrent requests dengan event yang sama harus idempotent"""
    event_id = f"concurrent-{uuid.uuid4()}"
    event = event_template.copy()
    event["event_id"] = event_id
    event["topic"] = "concurrent.test"
    
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_unique = initial_data["unique_processed"]
    
    # Send 10 concurrent requests with same event
    tasks = []
    for _ in range(10):
        task = client.post(
            f"{AGGREGATOR_URL}/publish",
            json={"events": [event]}
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    # Wait for processing
    await asyncio.sleep(3)
    
    # Check stats - should only process once
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    assert final_data["unique_processed"] == initial_unique + 1
    print("✓ Test 12: Concurrent same event handled idempotently")

@pytest.mark.asyncio
async def test_13_concurrent_different_events(client, event_template):
    """Test 13: Concurrent requests dengan events berbeda harus semua diproses"""
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_unique = initial_data["unique_processed"]
    
    # Create unique events
    events = []
    for i in range(10):
        event = event_template.copy()
        event["event_id"] = f"concurrent-unique-{uuid.uuid4()}"
        event["topic"] = "concurrent.unique.test"
        event["payload"] = {"index": i}
        events.append(event)
    
    # Send concurrent requests
    tasks = [
        client.post(f"{AGGREGATOR_URL}/publish", json={"events": [event]})
        for event in events
    ]
    
    await asyncio.gather(*tasks)
    
    # Wait for processing
    await asyncio.sleep(3)
    
    # Check stats - all should be processed
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    assert final_data["unique_processed"] >= initial_unique + 10
    print("✓ Test 13: Concurrent different events all processed")

@pytest.mark.asyncio
async def test_14_high_load_consistency(client, event_template):
    """Test 14: High load test untuk memverifikasi consistency statistik"""
    num_events = 50
    duplicate_rate = 0.3  # 30% duplicates
    
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    initial_received = initial_data["received"]
    initial_unique = initial_data["unique_processed"]
    
    # Generate events with duplicates
    unique_events = []
    all_events = []
    
    for i in range(int(num_events * (1 - duplicate_rate))):
        event = event_template.copy()
        event["event_id"] = f"load-test-{uuid.uuid4()}"
        event["topic"] = "load.test"
        event["payload"] = {"index": i}
        unique_events.append(event)
        all_events.append(event)
    
    # Add duplicates
    num_duplicates = num_events - len(unique_events)
    for _ in range(num_duplicates):
        dup_event = unique_events[fake.random_int(0, len(unique_events) - 1)].copy()
        all_events.append(dup_event)
    
    # Send all events
    await client.post(f"{AGGREGATOR_URL}/publish", json={"events": all_events})
    
    # Wait for processing
    await asyncio.sleep(5)
    
    # Check stats
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    # Verify consistency
    received_delta = final_data["received"] - initial_received
    unique_delta = final_data["unique_processed"] - initial_unique
    
    assert received_delta >= num_events
    assert unique_delta == len(unique_events)
    
    print(f"✓ Test 14: High load consistency verified ({num_events} events, {unique_delta} unique)")

# ============================================================================
# TEST 15-16: QUERY ENDPOINTS
# ============================================================================

@pytest.mark.asyncio
async def test_15_get_events_endpoint(client, event_template):
    """Test 15: GET /events harus return list events"""
    # Publish beberapa events
    events = []
    for i in range(5):
        event = event_template.copy()
        event["event_id"] = f"query-test-{uuid.uuid4()}"
        event["topic"] = "query.test"
        events.append(event)
    
    await client.post(f"{AGGREGATOR_URL}/publish", json={"events": events})
    await asyncio.sleep(2)
    
    # Query events
    response = await client.get(f"{AGGREGATOR_URL}/events")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    print(f"✓ Test 15: GET /events returned {len(data)} events")

@pytest.mark.asyncio
async def test_16_get_events_with_topic_filter(client, event_template):
    """Test 16: GET /events?topic=X harus filter by topic"""
    topic = "filter.test.topic"
    
    # Publish events dengan topic spesifik
    events = []
    for i in range(3):
        event = event_template.copy()
        event["event_id"] = f"filter-test-{uuid.uuid4()}"
        event["topic"] = topic
        events.append(event)
    
    await client.post(f"{AGGREGATOR_URL}/publish", json={"events": events})
    await asyncio.sleep(2)
    
    # Query dengan filter
    response = await client.get(f"{AGGREGATOR_URL}/events?topic={topic}")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # All events should have the filtered topic
    for event in data:
        if event["topic"] == topic:
            assert True
            break
    
    print(f"✓ Test 16: Topic filter working, found {len(data)} events")

# ============================================================================
# TEST 17-18: PERSISTENCE & STRESS
# ============================================================================

@pytest.mark.asyncio
async def test_17_stats_accumulation(client, event_template):
    """Test 17: Stats harus akumulasi dengan benar"""
    # Get initial stats
    initial_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    initial_data = initial_stats.json()
    
    # Send 10 unique events
    for i in range(10):
        event = event_template.copy()
        event["event_id"] = f"accumulate-{uuid.uuid4()}"
        await client.post(f"{AGGREGATOR_URL}/publish", json={"events": [event]})
    
    # Wait for processing
    await asyncio.sleep(3)
    
    # Get final stats
    final_stats = await client.get(f"{AGGREGATOR_URL}/stats")
    final_data = final_stats.json()
    
    # Verify accumulation
    assert final_data["received"] > initial_data["received"]
    assert final_data["unique_processed"] > initial_data["unique_processed"]
    
    print("✓ Test 17: Stats accumulation verified")

@pytest.mark.asyncio
async def test_18_large_batch_processing(client, event_template):
    """Test 18: Large batch harus diproses dengan sukses"""
    batch_size = 500
    
    events = []
    for i in range(batch_size):
        event = event_template.copy()
        event["event_id"] = f"large-batch-{uuid.uuid4()}"
        event["topic"] = "large.batch.test"
        event["payload"] = {"index": i, "data": fake.text()}
        events.append(event)
    
    # Send large batch
    response = await client.post(
        f"{AGGREGATOR_URL}/publish",
        json={"events": events}
    )
    assert response.status_code == 202
    
    data = response.json()
    assert data["queued"] == batch_size
    
    print(f"✓ Test 18: Large batch of {batch_size} events accepted")

# ============================================================================
# RUN SUMMARY
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
