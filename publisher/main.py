"""
Publisher Service - Event Generator dengan Duplicate Simulation
Mengirim events ke aggregator termasuk duplikasi untuk testing idempotency
"""
import os
import time
import random
import logging
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AGGREGATOR_URL = os.getenv("AGGREGATOR_URL", "http://aggregator:8080")
PUBLISH_ENDPOINT = f"{AGGREGATOR_URL}/publish"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DUPLICATE_RATE = float(os.getenv("DUPLICATE_RATE", "0.3"))  # 30% duplikasi
TOTAL_EVENTS = int(os.getenv("TOTAL_EVENTS", "20000"))
DELAY_BETWEEN_BATCHES = float(os.getenv("DELAY_BETWEEN_BATCHES", "0.5"))

# Topics untuk simulasi
TOPICS = [
    "user.registration",
    "user.login",
    "user.logout",
    "order.created",
    "order.completed",
    "order.cancelled",
    "payment.initiated",
    "payment.completed",
    "payment.failed",
    "inventory.updated"
]

# Sources untuk simulasi
SOURCES = [
    "web-app-1",
    "web-app-2",
    "mobile-app-1",
    "mobile-app-2",
    "api-gateway-1",
    "api-gateway-2"
]

class EventGenerator:
    """Generator untuk membuat events realistik"""
    
    def __init__(self):
        self.event_cache: List[Dict[str, Any]] = []  # Cache untuk duplikasi
        self.event_counter = 0
    
    def generate_event_id(self) -> str:
        """
        Generate unique event ID dengan format:
        <timestamp>-<uuid>-<counter>
        """
        timestamp = int(time.time() * 1000)
        uid = str(uuid.uuid4())[:8]
        self.event_counter += 1
        return f"{timestamp}-{uid}-{self.event_counter}"
    
    def generate_payload(self, topic: str) -> Dict[str, Any]:
        """Generate realistic payload berdasarkan topic"""
        
        if topic.startswith("user."):
            return {
                "user_id": f"user_{random.randint(1000, 9999)}",
                "email": f"user{random.randint(1000, 9999)}@example.com",
                "ip_address": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                "user_agent": random.choice(["Mozilla/5.0", "Chrome/90.0", "Safari/14.0"])
            }
        
        elif topic.startswith("order."):
            return {
                "order_id": f"ORD-{random.randint(10000, 99999)}",
                "customer_id": f"user_{random.randint(1000, 9999)}",
                "amount": round(random.uniform(10.0, 1000.0), 2),
                "items": random.randint(1, 10),
                "currency": "USD"
            }
        
        elif topic.startswith("payment."):
            return {
                "payment_id": f"PAY-{random.randint(10000, 99999)}",
                "order_id": f"ORD-{random.randint(10000, 99999)}",
                "amount": round(random.uniform(10.0, 1000.0), 2),
                "method": random.choice(["credit_card", "debit_card", "paypal", "bank_transfer"]),
                "status": random.choice(["pending", "completed", "failed"])
            }
        
        elif topic.startswith("inventory."):
            return {
                "product_id": f"PROD-{random.randint(1000, 9999)}",
                "quantity": random.randint(0, 1000),
                "warehouse": f"WH-{random.randint(1, 5)}",
                "action": random.choice(["restock", "sold", "reserved", "returned"])
            }
        
        return {"data": "generic_event"}
    
    def generate_event(self) -> Dict[str, Any]:
        """Generate single event"""
        topic = random.choice(TOPICS)
        source = random.choice(SOURCES)
        
        event = {
            "topic": topic,
            "event_id": self.generate_event_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "payload": self.generate_payload(topic)
        }
        
        return event
    
    def generate_batch(self, size: int, duplicate_rate: float = 0.0) -> List[Dict[str, Any]]:
        """
        Generate batch events dengan kontrol duplikasi
        
        Args:
            size: jumlah events dalam batch
            duplicate_rate: proporsi duplikasi (0.0 - 1.0)
        
        Returns:
            List of events (termasuk duplikat)
        """
        events = []
        num_duplicates = int(size * duplicate_rate)
        num_new = size - num_duplicates
        
        # Generate new events
        for _ in range(num_new):
            event = self.generate_event()
            events.append(event)
            # Cache untuk kemungkinan duplikasi di masa depan
            if len(self.event_cache) < 1000:
                self.event_cache.append(event)
        
        # Add duplicates from cache
        if num_duplicates > 0 and self.event_cache:
            for _ in range(num_duplicates):
                # Pilih event dari cache dan kirim lagi (duplikasi)
                duplicate_event = random.choice(self.event_cache).copy()
                # Update timestamp untuk simulasi "late duplicate"
                duplicate_event["timestamp"] = datetime.now(timezone.utc).isoformat()
                events.append(duplicate_event)
        
        # Shuffle untuk distribusi acak duplikat
        random.shuffle(events)
        
        return events

class Publisher:
    """Publisher untuk mengirim events ke aggregator"""
    
    def __init__(self, aggregator_url: str):
        self.aggregator_url = aggregator_url
        self.session = self._create_session()
        self.generator = EventGenerator()
        
        self.stats = {
            "sent": 0,
            "batches": 0,
            "errors": 0,
            "duplicates_sent": 0
        }
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session dengan retry strategy
        Untuk reliability pada network issues
        """
        session = requests.Session()
        
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def wait_for_aggregator(self, timeout: int = 60):
        """
        Wait untuk aggregator service siap
        Health check dengan retry
        """
        logger.info(f"Waiting for aggregator at {self.aggregator_url}...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.session.get(f"{self.aggregator_url}/health", timeout=5)
                if response.status_code == 200:
                    logger.info("✓ Aggregator is ready")
                    return True
            except Exception as e:
                logger.debug(f"Aggregator not ready yet: {e}")
            
            time.sleep(2)
        
        logger.error(f"✗ Aggregator did not become ready within {timeout}s")
        return False
    
    def publish_batch(self, events: List[Dict[str, Any]]) -> bool:
        """
        Publish batch events ke aggregator
        
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            payload = {"events": events}
            
            response = self.session.post(
                PUBLISH_ENDPOINT,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            
            self.stats["sent"] += len(events)
            self.stats["batches"] += 1
            
            logger.info(
                f"✓ Sent batch {self.stats['batches']}: "
                f"{len(events)} events, "
                f"total sent: {self.stats['sent']}"
            )
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.stats["errors"] += 1
            logger.error(f"✗ Failed to send batch: {e}")
            return False
    
    def run_simulation(
        self,
        total_events: int,
        batch_size: int,
        duplicate_rate: float,
        delay: float = 0.5
    ):
        """
        Run simulation untuk mengirim events
        
        Args:
            total_events: total events yang akan dikirim
            batch_size: ukuran batch per request
            duplicate_rate: proporsi duplikasi (0.0 - 1.0)
            delay: delay antar batch (seconds)
        """
        logger.info("=" * 60)
        logger.info("Starting event publishing simulation")
        logger.info(f"Total events: {total_events}")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Duplicate rate: {duplicate_rate * 100:.1f}%")
        logger.info(f"Delay between batches: {delay}s")
        logger.info("=" * 60)
        
        num_batches = (total_events + batch_size - 1) // batch_size
        events_remaining = total_events
        
        start_time = time.time()
        
        for batch_num in range(num_batches):
            # Calculate batch size for this iteration
            current_batch_size = min(batch_size, events_remaining)
            
            # Generate batch
            events = self.generator.generate_batch(
                current_batch_size,
                duplicate_rate
            )
            
            # Track duplicates
            duplicates_in_batch = sum(
                1 for e in events
                if e in self.generator.event_cache
            )
            self.stats["duplicates_sent"] += duplicates_in_batch
            
            # Publish
            success = self.publish_batch(events)
            
            if not success:
                logger.warning(f"Batch {batch_num + 1} failed, continuing...")
            
            events_remaining -= current_batch_size
            
            # Progress log setiap 10 batch
            if (batch_num + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = self.stats["sent"] / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Progress: {self.stats['sent']}/{total_events} events "
                    f"({rate:.1f} events/s), "
                    f"{self.stats['errors']} errors"
                )
            
            # Delay antar batch
            if events_remaining > 0:
                time.sleep(delay)
        
        # Final statistics
        elapsed = time.time() - start_time
        self._print_final_stats(elapsed)
    
    def _print_final_stats(self, elapsed: float):
        """Print final statistics"""
        logger.info("=" * 60)
        logger.info("Publishing simulation completed")
        logger.info(f"Total events sent: {self.stats['sent']}")
        logger.info(f"Total batches: {self.stats['batches']}")
        logger.info(f"Duplicates sent: {self.stats['duplicates_sent']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Elapsed time: {elapsed:.2f}s")
        logger.info(f"Average rate: {self.stats['sent'] / elapsed:.1f} events/s")
        logger.info("=" * 60)
    
    def fetch_aggregator_stats(self):
        """Fetch dan tampilkan statistik dari aggregator"""
        try:
            response = self.session.get(f"{AGGREGATOR_URL}/stats", timeout=10)
            response.raise_for_status()
            
            stats = response.json()
            
            logger.info("=" * 60)
            logger.info("Aggregator Statistics:")
            logger.info(f"  Received: {stats.get('received', 0)}")
            logger.info(f"  Unique processed: {stats.get('unique_processed', 0)}")
            logger.info(f"  Duplicate dropped: {stats.get('duplicate_dropped', 0)}")
            logger.info(f"  Topics: {stats.get('topics', 0)}")
            logger.info(f"  Uptime: {stats.get('uptime_seconds', 0):.2f}s")
            logger.info("=" * 60)
            
            # Verification
            if stats.get('received', 0) > 0:
                actual_duplicate_rate = stats.get('duplicate_dropped', 0) / stats.get('received', 1)
                logger.info(f"Actual duplicate rate: {actual_duplicate_rate * 100:.1f}%")
                logger.info(f"Expected duplicate rate: {DUPLICATE_RATE * 100:.1f}%")
            
        except Exception as e:
            logger.error(f"Failed to fetch aggregator stats: {e}")

def main():
    """Main function"""
    logger.info("Publisher service starting...")
    
    # Create publisher
    publisher = Publisher(AGGREGATOR_URL)
    
    # Wait for aggregator
    if not publisher.wait_for_aggregator():
        logger.error("Aggregator not available, exiting")
        return 1
    
    # Wait additional time untuk database initialization
    time.sleep(5)
    
    # Run simulation
    try:
        publisher.run_simulation(
            total_events=TOTAL_EVENTS,
            batch_size=BATCH_SIZE,
            duplicate_rate=DUPLICATE_RATE,
            delay=DELAY_BETWEEN_BATCHES
        )
        
        # Wait untuk processing
        logger.info("Waiting 10 seconds for event processing...")
        time.sleep(10)
        
        # Fetch final stats
        publisher.fetch_aggregator_stats()
        
        logger.info("Publisher service completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Publisher interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Publisher failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())
