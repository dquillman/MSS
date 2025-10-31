#!/bin/bash
# Test Docker build locally before deploying to Cloud Run

echo "=== Testing MSS Docker Build ==="
echo ""

# Check if Dockerfile exists
if [ ! -f "Dockerfile.app" ]; then
    echo "ERROR: Dockerfile.app not found!"
    exit 1
fi

echo "1. Building Docker image..."
docker build -f Dockerfile.app -t mss-api-test:latest . || {
    echo "ERROR: Docker build failed!"
    exit 1
}

echo ""
echo "2. Testing container startup..."
docker run -d \
    --name mss-api-test \
    -p 8080:8080 \
    -e PORT=8080 \
    mss-api-test:latest || {
    echo "ERROR: Container failed to start!"
    exit 1
}

echo ""
echo "3. Waiting for container to start (10 seconds)..."
sleep 10

echo ""
echo "4. Testing health endpoint..."
curl -f http://localhost:8080/healthz || {
    echo "ERROR: Health check failed!"
    docker logs mss-api-test
    docker rm -f mss-api-test
    exit 1
}

echo ""
echo "5. Checking container logs..."
docker logs mss-api-test | tail -20

echo ""
echo "=== Test passed! Container is running ==="
echo "Health check: http://localhost:8080/healthz"
echo ""
echo "To stop the test container:"
echo "  docker rm -f mss-api-test"
echo ""
echo "To test manually:"
echo "  curl http://localhost:8080/healthz"
echo "  curl http://localhost:8080/health"

