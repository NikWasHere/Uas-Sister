#!/bin/bash
# Script untuk menjalankan tests
# Pastikan aggregator service sudah running

echo "=================================="
echo "Running Aggregator Tests"
echo "=================================="

# Check if aggregator is running
echo "Checking aggregator availability..."
curl -s http://localhost:8080/health > /dev/null

if [ $? -ne 0 ]; then
    echo "ERROR: Aggregator service tidak tersedia di http://localhost:8080"
    echo "Jalankan terlebih dahulu: docker compose up -d aggregator"
    exit 1
fi

echo "✓ Aggregator is running"
echo ""

# Install test dependencies
echo "Installing test dependencies..."
pip install -q -r tests/requirements.txt

# Run tests
echo ""
echo "Running tests..."
pytest tests/test_aggregator.py -v --tb=short

# Capture exit code
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "=================================="
    echo "✓ All tests passed!"
    echo "=================================="
else
    echo "=================================="
    echo "✗ Some tests failed"
    echo "=================================="
fi

exit $EXIT_CODE
