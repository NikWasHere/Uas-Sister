/**
 * K6 Load Testing Script untuk Log Aggregator
 * 
 * Test scenario:
 * - 20,000 events total
 * - 30% duplicate rate
 * - Multiple topics
 * - Batch publishing
 * 
 * Run:
 *   k6 run tests/load_test.js
 * 
 * Custom config:
 *   k6 run tests/load_test.js --vus 10 --duration 60s
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const TOTAL_EVENTS = parseInt(__ENV.TOTAL_EVENTS || '20000');
const DUPLICATE_RATE = parseFloat(__ENV.DUPLICATE_RATE || '0.3');
const BATCH_SIZE = parseInt(__ENV.BATCH_SIZE || '100');

// Topics untuk distribusi
const TOPICS = [
    'user.registration',
    'user.login',
    'user.logout',
    'order.created',
    'order.completed',
    'payment.initiated',
    'payment.completed',
    'inventory.updated',
];

const SOURCES = [
    'k6-test-1',
    'k6-test-2',
    'k6-test-3',
];

// Event cache untuk duplicates
let eventCache = [];
let eventCounter = 0;

// Test configuration
export const options = {
    scenarios: {
        load_test: {
            executor: 'constant-vus',
            vus: 10,
            duration: '60s',
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<500'], // 95% of requests should be below 500ms
        http_req_failed: ['rate<0.1'],    // Error rate should be below 10%
        errors: ['rate<0.1'],
    },
};

/**
 * Generate unique event ID
 */
function generateEventId() {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 10);
    eventCounter++;
    return `k6-${timestamp}-${random}-${eventCounter}`;
}

/**
 * Generate event payload based on topic
 */
function generatePayload(topic) {
    if (topic.startsWith('user.')) {
        return {
            user_id: `user_${Math.floor(Math.random() * 10000)}`,
            email: `user${Math.floor(Math.random() * 10000)}@example.com`,
            ip_address: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
        };
    } else if (topic.startsWith('order.')) {
        return {
            order_id: `ORD-${Math.floor(Math.random() * 90000 + 10000)}`,
            customer_id: `user_${Math.floor(Math.random() * 10000)}`,
            amount: Math.floor(Math.random() * 1000 * 100) / 100,
            items: Math.floor(Math.random() * 10) + 1,
        };
    } else if (topic.startsWith('payment.')) {
        return {
            payment_id: `PAY-${Math.floor(Math.random() * 90000 + 10000)}`,
            order_id: `ORD-${Math.floor(Math.random() * 90000 + 10000)}`,
            amount: Math.floor(Math.random() * 1000 * 100) / 100,
            method: ['credit_card', 'debit_card', 'paypal'][Math.floor(Math.random() * 3)],
        };
    } else {
        return {
            product_id: `PROD-${Math.floor(Math.random() * 9000 + 1000)}`,
            quantity: Math.floor(Math.random() * 1000),
            warehouse: `WH-${Math.floor(Math.random() * 5) + 1}`,
        };
    }
}

/**
 * Generate single event
 */
function generateEvent() {
    const topic = TOPICS[Math.floor(Math.random() * TOPICS.length)];
    const source = SOURCES[Math.floor(Math.random() * SOURCES.length)];
    
    return {
        topic: topic,
        event_id: generateEventId(),
        timestamp: new Date().toISOString(),
        source: source,
        payload: generatePayload(topic),
    };
}

/**
 * Generate batch with duplicates
 */
function generateBatch(size, duplicateRate) {
    const events = [];
    const numDuplicates = Math.floor(size * duplicateRate);
    const numNew = size - numDuplicates;
    
    // Generate new events
    for (let i = 0; i < numNew; i++) {
        const event = generateEvent();
        events.push(event);
        
        // Add to cache for future duplicates
        if (eventCache.length < 1000) {
            eventCache.push(event);
        }
    }
    
    // Add duplicates from cache
    if (numDuplicates > 0 && eventCache.length > 0) {
        for (let i = 0; i < numDuplicates; i++) {
            const duplicate = eventCache[Math.floor(Math.random() * eventCache.length)];
            // Update timestamp to simulate "late duplicate"
            const dupEvent = {
                ...duplicate,
                timestamp: new Date().toISOString(),
            };
            events.push(dupEvent);
        }
    }
    
    // Shuffle for random distribution
    return events.sort(() => Math.random() - 0.5);
}

/**
 * Setup function - runs once
 */
export function setup() {
    console.log('='.repeat(60));
    console.log('K6 Load Test Starting');
    console.log(`Target: ${BASE_URL}`);
    console.log(`Total Events: ${TOTAL_EVENTS}`);
    console.log(`Duplicate Rate: ${DUPLICATE_RATE * 100}%`);
    console.log(`Batch Size: ${BATCH_SIZE}`);
    console.log('='.repeat(60));
    
    // Health check
    const healthResponse = http.get(`${BASE_URL}/health`);
    if (healthResponse.status !== 200) {
        throw new Error(`Aggregator not healthy: ${healthResponse.status}`);
    }
    
    console.log('✓ Aggregator is healthy');
    
    // Get initial stats
    const statsResponse = http.get(`${BASE_URL}/stats`);
    const initialStats = JSON.parse(statsResponse.body);
    
    console.log(`Initial Stats:`);
    console.log(`  Received: ${initialStats.received}`);
    console.log(`  Unique: ${initialStats.unique_processed}`);
    console.log(`  Duplicates: ${initialStats.duplicate_dropped}`);
    console.log('='.repeat(60));
    
    return { initialStats };
}

/**
 * Main test function - runs repeatedly
 */
export default function(data) {
    // Generate batch
    const batch = generateBatch(BATCH_SIZE, DUPLICATE_RATE);
    
    // Publish batch
    const payload = JSON.stringify({ events: batch });
    const params = {
        headers: { 'Content-Type': 'application/json' },
    };
    
    const response = http.post(`${BASE_URL}/publish`, payload, params);
    
    // Checks
    const success = check(response, {
        'status is 202': (r) => r.status === 202,
        'has queued field': (r) => {
            try {
                const body = JSON.parse(r.body);
                return body.queued !== undefined;
            } catch {
                return false;
            }
        },
        'response time < 500ms': (r) => r.timings.duration < 500,
    });
    
    if (!success) {
        errorRate.add(1);
        console.error(`Request failed: ${response.status} - ${response.body}`);
    } else {
        errorRate.add(0);
    }
    
    // Small delay between batches
    sleep(0.1);
}

/**
 * Teardown function - runs once at end
 */
export function teardown(data) {
    console.log('='.repeat(60));
    console.log('K6 Load Test Completed');
    console.log('='.repeat(60));
    
    // Wait for processing
    console.log('Waiting 10 seconds for event processing...');
    sleep(10);
    
    // Get final stats
    const statsResponse = http.get(`${BASE_URL}/stats`);
    const finalStats = JSON.parse(statsResponse.body);
    
    console.log('Final Stats:');
    console.log(`  Received: ${finalStats.received} (+${finalStats.received - data.initialStats.received})`);
    console.log(`  Unique: ${finalStats.unique_processed} (+${finalStats.unique_processed - data.initialStats.unique_processed})`);
    console.log(`  Duplicates: ${finalStats.duplicate_dropped} (+${finalStats.duplicate_dropped - data.initialStats.duplicate_dropped})`);
    console.log(`  Topics: ${finalStats.topics}`);
    
    // Verification
    const totalReceived = finalStats.received - data.initialStats.received;
    const totalUnique = finalStats.unique_processed - data.initialStats.unique_processed;
    const totalDuplicates = finalStats.duplicate_dropped - data.initialStats.duplicate_dropped;
    
    console.log('='.repeat(60));
    console.log('Verification:');
    console.log(`  Total Received: ${totalReceived}`);
    console.log(`  Unique + Duplicates: ${totalUnique + totalDuplicates}`);
    console.log(`  Match: ${totalReceived === totalUnique + totalDuplicates ? '✓' : '✗'}`);
    
    const actualDuplicateRate = totalDuplicates / totalReceived;
    console.log(`  Expected Duplicate Rate: ${DUPLICATE_RATE * 100}%`);
    console.log(`  Actual Duplicate Rate: ${(actualDuplicateRate * 100).toFixed(1)}%`);
    
    console.log('='.repeat(60));
}
