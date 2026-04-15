#!/bin/bash
# Multica Launch Script - Boots both the API server and the AutoGen agent daemon

echo "🚀 Starting Multica AutoGen Swarm Platform..."

# Start agent.py as a background process
echo "🤖 Launching AutoGen Agent daemon..."
python3 agent.py &
AGENT_PID=$!
echo "✅ Agent daemon started (PID: $AGENT_PID)"

# Start the single unified FastAPI server
echo "🌐 Starting FastAPI server on port $PORT..."
python3 -m uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
