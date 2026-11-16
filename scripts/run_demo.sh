#!/usr/bin/env bash
# =============================================================================
# AADS (Agentic Architecture Design & Simulation) Demo Startup Script
# Phase 5.0 End-to-End Product Demonstration
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${WORKSPACE_ROOT}"

# Locate Python environment
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    UVICORN=".venv/bin/uvicorn"
    STREAMLIT=".venv/bin/streamlit"
else
    PYTHON="$(which python3)"
    UVICORN="$(which uvicorn 2>/dev/null || echo "$PYTHON -m uvicorn")"
    STREAMLIT="$(which streamlit 2>/dev/null || echo "$PYTHON -m streamlit")"
fi

export PYTHONPATH="${WORKSPACE_ROOT}:${PYTHONPATH}"

# Default hosts and ports
API_HOST="${AADS_API_HOST:-127.0.0.1}"
API_PORT="${AADS_API_PORT:-8000}"
REACT_PORT="${AADS_REACT_PORT:-3000}"
STREAMLIT_PORT="${AADS_STREAMLIT_PORT:-8501}"

echo "======================================================================"
echo "⚡ AADS: Agentic Architecture Design & Simulation — Demo Launcher"
echo "======================================================================"
echo "Workspace Root:  ${WORKSPACE_ROOT}"
echo "Python Binary:   ${PYTHON}"
echo "API Endpoint:    http://${API_HOST}:${API_PORT}"
echo "React Frontend:  http://${API_HOST}:${REACT_PORT}"
echo "======================================================================"

# Handle command-line arguments
MODE="${1:-all}"

if [ "${MODE}" = "--scenarios" ] || [ "${MODE}" = "scenarios" ]; then
    echo "Running 3 reproducible demonstration scenarios..."
    "${PYTHON}" scripts/run_demo_scenarios.py
    exit $?
fi

if [ "${MODE}" = "--api-only" ] || [ "${MODE}" = "api" ]; then
    echo "Starting FastAPI backend on http://${API_HOST}:${API_PORT}..."
    exec "${PYTHON}" -m uvicorn aads.api.app:app --host "${API_HOST}" --port "${API_PORT}" --reload
fi

if [ "${MODE}" = "--react-only" ] || [ "${MODE}" = "react" ]; then
    echo "Starting React Vite frontend on http://${API_HOST}:${REACT_PORT}..."
    cd "${WORKSPACE_ROOT}/frontend"
    exec yarn dev
fi

if [ "${MODE}" = "--streamlit" ] || [ "${MODE}" = "streamlit" ]; then
    echo "Starting legacy Streamlit UI on http://${API_HOST}:${STREAMLIT_PORT}..."
    exec "${STREAMLIT}" run aads/ui/streamlit_app.py --server.port "${STREAMLIT_PORT}" --server.address "${API_HOST}"
fi

# Default: Start both FastAPI backend and React frontend
API_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down AADS demo services..."
    if [ -n "${FRONTEND_PID}" ] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
        kill "${FRONTEND_PID}" 2>/dev/null || true
    fi
    if [ -n "${API_PID}" ] && kill -0 "${API_PID}" 2>/dev/null; then
        kill "${API_PID}" 2>/dev/null || true
    fi
    echo "Demo stopped gracefully."
    exit 0
}

trap cleanup INT TERM

echo "1. Starting FastAPI backend in background..."
"${PYTHON}" -m uvicorn aads.api.app:app --host "${API_HOST}" --port "${API_PORT}" > /tmp/aads_api.log 2>&1 &
API_PID=$!
echo "   Backend PID: ${API_PID} (Logs: /tmp/aads_api.log)"

# Wait for API health check
echo -n "2. Polling API health check on http://${API_HOST}:${API_PORT}/ ... "
for i in {1..30}; do
    if "${PYTHON}" -c "import urllib.request; urllib.request.urlopen('http://${API_HOST}:${API_PORT}/')" >/dev/null 2>&1; then
        echo "HEALTHY!"
        break
    fi
    sleep 0.5
    echo -n "."
done

echo ""
echo "3. Starting React frontend on http://${API_HOST}:${REACT_PORT}..."
echo "   Press Ctrl+C to terminate both backend and frontend."
echo "======================================================================"

cd "${WORKSPACE_ROOT}/frontend"
exec yarn dev
