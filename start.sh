#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Iniciando backend..."
source "$SCRIPT_DIR/venv/bin/activate"
cd "$SCRIPT_DIR/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Esperando a que el backend esté listo..."
for i in {1..30}; do
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        echo "Backend listo!"
        break
    fi
    sleep 1
done

echo "Iniciando frontend..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "PIDs: backend=$BACKEND_PID, frontend=$FRONTEND_PID"
echo ""
echo "Presiona Ctrl+C para detener..."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
