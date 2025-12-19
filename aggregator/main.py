"""
Aggregator Service - Pub-Sub Log Aggregator dengan Idempotency & Deduplication
Mendukung transaksi ACID dan kontrol konkurensi untuk mencegah race conditions
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import redis.asyncio as redis
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, UniqueConstraint, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
import psycopg2

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@storage:5432/db")
REDIS_URL = os.getenv("REDIS_URL", "redis://broker:6379")
WORKER_COUNT = int(os.getenv("WORKER_COUNT", "4"))

# Database setup
Base = declarative_base()

class ProcessedEvent(Base):
    """
    Tabel untuk menyimpan event yang telah diproses (deduplication store)
    Menggunakan UNIQUE constraint pada (topic, event_id) untuk idempotency
    """
    __tablename__ = 'processed_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(255), nullable=False, index=True)
    event_id = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(255), nullable=False)
    payload = Column(Text, nullable=False)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        UniqueConstraint('topic', 'event_id', name='uq_topic_event_id'),
        Index('idx_topic', 'topic'),
        Index('idx_timestamp', 'timestamp'),
    )

class EventStats(Base):
    """
    Tabel untuk menyimpan statistik dengan kontrol konkurensi
    Menggunakan UPDATE ... SET count = count + 1 untuk atomic increment
    """
    __tablename__ = 'event_stats'
    
    id = Column(Integer, primary_key=True)
    received_count = Column(Integer, default=0)
    unique_processed = Column(Integer, default=0)
    duplicate_dropped = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

# Pydantic models
class EventPayload(BaseModel):
    """Model untuk payload event yang fleksibel"""
    data: Dict[str, Any] = Field(default_factory=dict)

class Event(BaseModel):
    """
    Model event dengan validasi ketat
    event_id harus unik per topic untuk deduplication
    """
    topic: str = Field(..., min_length=1, max_length=255, description="Event topic name")
    event_id: str = Field(..., min_length=1, max_length=255, description="Unique event identifier")
    timestamp: str = Field(..., description="ISO8601 timestamp")
    source: str = Field(..., min_length=1, max_length=255, description="Event source identifier")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload data")
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validasi format timestamp ISO8601"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('timestamp must be valid ISO8601 format')
        return v

class EventBatch(BaseModel):
    """Model untuk batch events"""
    events: List[Event] = Field(..., min_length=1, description="List of events")

class EventResponse(BaseModel):
    """Response model untuk event"""
    topic: str
    event_id: str
    timestamp: str
    source: str
    payload: Dict[str, Any]
    processed_at: str

class StatsResponse(BaseModel):
    """Response model untuk statistik"""
    received: int
    unique_processed: int
    duplicate_dropped: int
    topics: int
    uptime_seconds: float
    status: str = "healthy"

# Global state
app_state = {
    "engine": None,
    "Session": None,
    "redis_client": None,
    "start_time": datetime.now(timezone.utc),
    "consumer_task": None
}

def init_database():
    """
    Inisialisasi database dengan retry logic
    Membuat tabel dan entry statistik awal
    """
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                isolation_level="READ COMMITTED"  # Isolation level untuk consistency
            )
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Create tables
            Base.metadata.create_all(engine)
            
            # Initialize stats if not exists
            Session = sessionmaker(bind=engine)
            session = Session()
            try:
                if not session.query(EventStats).filter_by(id=1).first():
                    stats = EventStats(
                        id=1,
                        received_count=0,
                        unique_processed=0,
                        duplicate_dropped=0
                    )
                    session.add(stats)
                    session.commit()
                    logger.info("Initialized event statistics")
            finally:
                session.close()
            
            logger.info("Database initialized successfully")
            return engine, Session
            
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager untuk FastAPI
    Mengelola koneksi database dan Redis, serta consumer workers
    """
    # Startup
    logger.info("Starting aggregator service...")
    
    # Initialize database
    app_state["engine"], app_state["Session"] = init_database()
    
    # Initialize Redis
    app_state["redis_client"] = await redis.from_url(REDIS_URL)
    logger.info("Redis connection established")
    
    # Start consumer workers
    app_state["consumer_task"] = asyncio.create_task(start_consumers())
    logger.info(f"Started {WORKER_COUNT} consumer workers")
    
    yield
    
    # Shutdown
    logger.info("Shutting down aggregator service...")
    
    # Stop consumer
    if app_state["consumer_task"]:
        app_state["consumer_task"].cancel()
        try:
            await app_state["consumer_task"]
        except asyncio.CancelledError:
            pass
    
    # Close connections
    if app_state["redis_client"]:
        await app_state["redis_client"].close()
    
    if app_state["engine"]:
        app_state["engine"].dispose()
    
    logger.info("Shutdown complete")

app = FastAPI(
    title="Log Aggregator Service",
    description="Pub-Sub Log Aggregator with Idempotency, Deduplication, and Transaction Control",
    version="1.0.0",
    lifespan=lifespan
)

def process_event_with_transaction(event: Event) -> tuple[bool, str]:
    """
    Memproses single event dengan transaksi ACID
    
    Menggunakan INSERT ... ON CONFLICT DO NOTHING untuk idempotent upsert
    Mencegah race condition dengan UNIQUE constraint
    
    Returns:
        tuple: (success: bool, message: str)
    """
    Session = app_state["Session"]
    session = Session()
    
    try:
        # BEGIN TRANSACTION (implicit dengan session)
        # Isolation level: READ COMMITTED (default, cukup untuk kasus ini)
        
        # Increment received counter (atomic)
        session.execute(
            text("UPDATE event_stats SET received_count = received_count + 1, updated_at = NOW() WHERE id = 1")
        )
        
        # Attempt to insert event (idempotent operation)
        # Jika (topic, event_id) sudah ada, constraint akan mencegah insert
        stmt = insert(ProcessedEvent).values(
            topic=event.topic,
            event_id=event.event_id,
            timestamp=datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')),
            source=event.source,
            payload=str(event.payload),
            processed_at=datetime.now(timezone.utc)
        )
        
        # PostgreSQL specific: ON CONFLICT DO NOTHING
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['topic', 'event_id']
        )
        
        result = session.execute(stmt)
        
        # Check if row was actually inserted
        if result.rowcount > 0:
            # New event, update unique processed counter
            session.execute(
                text("UPDATE event_stats SET unique_processed = unique_processed + 1, updated_at = NOW() WHERE id = 1")
            )
            session.commit()
            logger.info(f"✓ Processed new event: topic={event.topic}, event_id={event.event_id}")
            return True, "processed"
        else:
            # Duplicate event, update duplicate counter
            session.execute(
                text("UPDATE event_stats SET duplicate_dropped = duplicate_dropped + 1, updated_at = NOW() WHERE id = 1")
            )
            session.commit()
            logger.info(f"⊗ Dropped duplicate event: topic={event.topic}, event_id={event.event_id}")
            return True, "duplicate"
            
    except IntegrityError as e:
        session.rollback()
        logger.warning(f"Integrity error (duplicate): {e}")
        # Update duplicate counter
        try:
            session.execute(
                text("UPDATE event_stats SET duplicate_dropped = duplicate_dropped + 1, updated_at = NOW() WHERE id = 1")
            )
            session.commit()
        except:
            session.rollback()
        return True, "duplicate"
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing event: {e}", exc_info=True)
        return False, f"error: {str(e)}"
        
    finally:
        session.close()

async def consumer_worker(worker_id: int):
    """
    Worker untuk mengkonsumsi events dari Redis queue
    
    Mendukung konkurensi: multiple workers dapat berjalan paralel
    Idempotency dijamin oleh database constraint
    """
    redis_client = app_state["redis_client"]
    logger.info(f"Consumer worker {worker_id} started")
    
    while True:
        try:
            # BLPOP: blocking pop dari Redis list (queue)
            # Timeout 1 detik untuk graceful shutdown
            result = await redis_client.blpop("event_queue", timeout=1)
            
            if result is None:
                continue
            
            _, event_json = result
            
            # Parse event
            import json
            event_data = json.loads(event_json)
            event = Event(**event_data)
            
            # Process with transaction
            success, message = process_event_with_transaction(event)
            
            if not success:
                logger.error(f"Worker {worker_id} failed to process event: {message}")
                
        except asyncio.CancelledError:
            logger.info(f"Consumer worker {worker_id} cancelled")
            break
        except Exception as e:
            logger.error(f"Consumer worker {worker_id} error: {e}", exc_info=True)
            await asyncio.sleep(1)  # Backoff on error

async def start_consumers():
    """
    Memulai multiple consumer workers untuk konkurensi
    """
    workers = [
        asyncio.create_task(consumer_worker(i))
        for i in range(WORKER_COUNT)
    ]
    
    await asyncio.gather(*workers, return_exceptions=True)

@app.post("/publish", status_code=202)
async def publish_events(batch: EventBatch) -> JSONResponse:
    """
    Endpoint untuk publish batch events
    
    Events dipush ke Redis queue untuk asynchronous processing
    Mendukung at-least-once delivery
    
    Returns:
        JSONResponse dengan status dan jumlah events yang diterima
    """
    redis_client = app_state["redis_client"]
    
    try:
        import json
        
        # Push semua events ke queue
        pipeline = redis_client.pipeline()
        for event in batch.events:
            event_json = json.dumps(event.model_dump())
            pipeline.rpush("event_queue", event_json)
        
        await pipeline.execute()
        
        logger.info(f"Queued {len(batch.events)} events for processing")
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "queued": len(batch.events),
                "message": "Events queued for processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Error publishing events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to publish events: {str(e)}")

@app.get("/events", response_model=List[EventResponse])
async def get_events(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return")
) -> List[EventResponse]:
    """
    Endpoint untuk mengambil daftar events yang telah diproses
    
    Mendukung filtering by topic dan pagination
    """
    Session = app_state["Session"]
    session = Session()
    
    try:
        query = session.query(ProcessedEvent)
        
        if topic:
            query = query.filter(ProcessedEvent.topic == topic)
        
        query = query.order_by(ProcessedEvent.processed_at.desc()).limit(limit)
        
        events = query.all()
        
        return [
            EventResponse(
                topic=e.topic,
                event_id=e.event_id,
                timestamp=e.timestamp.isoformat(),
                source=e.source,
                payload=eval(e.payload) if e.payload else {},
                processed_at=e.processed_at.isoformat()
            )
            for e in events
        ]
        
    except Exception as e:
        logger.error(f"Error fetching events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")
    finally:
        session.close()

@app.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Endpoint untuk mengambil statistik sistem
    
    Menampilkan:
    - received: total events diterima
    - unique_processed: total events unik yang diproses
    - duplicate_dropped: total duplikat yang diabaikan
    - topics: jumlah topic unik
    - uptime_seconds: waktu berjalan sistem
    """
    Session = app_state["Session"]
    session = Session()
    
    try:
        # Get stats dengan read lock
        stats = session.query(EventStats).filter_by(id=1).first()
        
        # Count unique topics
        topic_count = session.query(ProcessedEvent.topic).distinct().count()
        
        uptime = (datetime.now(timezone.utc) - app_state["start_time"]).total_seconds()
        
        return StatsResponse(
            received=stats.received_count if stats else 0,
            unique_processed=stats.unique_processed if stats else 0,
            duplicate_dropped=stats.duplicate_dropped if stats else 0,
            topics=topic_count,
            uptime_seconds=uptime
        )
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")
    finally:
        session.close()

@app.get("/health")
async def health_check():
    """
    Health check endpoint untuk monitoring
    Memeriksa koneksi ke database dan Redis
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Check database
    try:
        Session = app_state["Session"]
        session = Session()
        session.execute(text("SELECT 1"))
        session.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Redis
    try:
        await app_state["redis_client"].ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(status_code=status_code, content=health_status)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Log Aggregator",
        "version": "1.0.0",
        "endpoints": {
            "publish": "POST /publish",
            "events": "GET /events",
            "stats": "GET /stats",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
