#!/bin/bash
echo "Starting Orbis..."
echo ""

echo "Step 1: Starting Database..."
if docker-compose ps | grep -q "Up"; then
    echo "✓ Database already running"
else
    docker-compose up -d
    echo "✓ Database started"
fi
echo ""

echo "⚙️  Step 2: Starting API..."
if lsof -i :8000 > /dev/null 2>&1; then
    echo "✓ API already running on port 8000"
else
    cd api
    ./run.sh &
    API_PID=$!
    cd ..
    echo "✓ API started on port 8000"
fi
echo ""

echo "Step 3: Starting Web..."
if lsof -i :5173 > /dev/null 2>&1; then
    echo "✓ Web already running on port 5173"
else
    cd web
    ./run.sh &
    WEB_PID=$!
    cd ..
    echo "✓ Web started on port 5173"
fi
echo ""

echo "All services are running!"
echo ""
echo "  Web:      http://localhost:5173"
echo "  API:      http://localhost:8000"
echo "  Database: localhost:5432"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

trap "echo ''; echo 'Stopping services...'; kill $API_PID $WEB_PID 2>/dev/null; docker-compose down; echo 'Done!'; exit" INT
wait
