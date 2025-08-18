#!/bin/bash

set -e

# WebRTC Multi-Object Detection System Startup Script
echo "🚀 Starting WebRTC Multi-Object Detection System..."

# Default configuration
MODE=${MODE:-"server"}
NGROK=${NGROK:-false}
PORT=${PORT:-3000}
BACKEND_PORT=${BACKEND_PORT:-8001}
DB_NAME=${DB_NAME:-"webrtc_detection"}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  WebRTC Object Detection Demo  ${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --ngrok)
            NGROK=true
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --backend-port)
            BACKEND_PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --mode MODE          Detection mode: server or wasm (default: server)"
            echo "  --ngrok              Enable ngrok for external access"
            echo "  --port PORT          Frontend port (default: 3000)"
            echo "  --backend-port PORT  Backend port (default: 8001)"
            echo "  --help               Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  MODE                 Detection mode (server/wasm)"
            echo "  NGROK                Enable ngrok (true/false)"
            echo "  DB_NAME              MongoDB database name"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start with server mode"
            echo "  $0 --mode wasm               # Start with WASM mode"
            echo "  $0 --ngrok                   # Start with ngrok tunneling"
            echo "  $0 --mode server --ngrok     # Server mode with ngrok"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

print_header

# Validate mode
if [[ "$MODE" != "server" && "$MODE" != "wasm" ]]; then
    print_error "Invalid mode: $MODE. Must be 'server' or 'wasm'"
    exit 1
fi

print_status "Detection mode: $MODE"

# Check Docker availability
if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
    print_status "Docker detected - using containerized deployment"
    USE_DOCKER=true
else
    print_warning "Docker not found - using local development mode"
    USE_DOCKER=false
fi

# Function to check if port is available
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1
    else
        return 0
    fi
}

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local url=$2
    local timeout=${3:-30}
    local count=0

    echo -n "Waiting for $service_name to be ready"
    while [ $count -lt $timeout ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo ""
            print_status "$service_name is ready"
            return 0
        fi
        echo -n "."
        sleep 1
        count=$((count + 1))
    done
    echo ""
    print_error "$service_name failed to start within ${timeout}s"
    return 1
}

# Function to setup ngrok
setup_ngrok() {
    if ! command -v ngrok >/dev/null 2>&1; then
        print_error "ngrok not found. Please install ngrok from https://ngrok.com/download"
        return 1
    fi

    print_status "Starting ngrok tunnel..."
    
    # Kill existing ngrok processes
    pkill -f ngrok >/dev/null 2>&1 || true
    
    # Start ngrok in background
    ngrok http $PORT --log=stdout > ngrok.log 2>&1 &
    NGROK_PID=$!
    
    # Wait for ngrok to start
    sleep 3
    
    # Get ngrok URL
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnel = data['tunnels'][0] if data['tunnels'] else None
    print(tunnel['public_url'] if tunnel else '')
except:
    print('')
    ")
    
    if [ -n "$NGROK_URL" ]; then
        print_status "Ngrok tunnel active: $NGROK_URL"
        echo "📱 Phone access URL: $NGROK_URL"
        echo "🔗 Share this URL for remote access"
        export PUBLIC_URL="$NGROK_URL"
    else
        print_error "Failed to get ngrok URL"
        return 1
    fi
}

# Function to start with Docker
start_docker() {
    print_status "Starting services with Docker Compose..."
    
    # Set environment variables
    export MODE
    export DB_NAME
    export CORS_ORIGINS="*"
    
    # Build and start services
    docker-compose down >/dev/null 2>&1 || true
    docker-compose up -d --build
    
    # Wait for services
    wait_for_service "MongoDB" "http://localhost:27017" 30
    wait_for_service "Backend" "http://localhost:$BACKEND_PORT/api/" 60
    wait_for_service "Frontend" "http://localhost:$PORT" 30
}

# Function to start local development
start_local() {
    print_status "Starting services in local development mode..."
    
    # Check MongoDB
    if ! pgrep mongod >/dev/null 2>&1; then
        print_warning "MongoDB not running. Attempting to start..."
        if command -v mongod >/dev/null 2>&1; then
            mongod --fork --logpath /tmp/mongodb.log --dbpath /tmp/mongodb
            sleep 2
        else
            print_error "MongoDB not found. Please install MongoDB or use Docker mode."
            exit 1
        fi
    fi
    
    # Start backend
    cd backend
    export MONGO_URL="mongodb://localhost:27017"
    export DB_NAME
    python -m uvicorn server:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
    BACKEND_PID=$!
    cd ..
    
    # Start frontend
    cd frontend
    export REACT_APP_DETECTION_MODE=$MODE
    if [ "$NGROK" = true ]; then
        export REACT_APP_BACKEND_URL="$PUBLIC_URL"
    else
        export REACT_APP_BACKEND_URL="http://localhost:$BACKEND_PORT"
    fi
    
    if command -v yarn >/dev/null 2>&1; then
        yarn start &
    else
        npm start &
    fi
    FRONTEND_PID=$!
    cd ..
    
    # Wait for services
    wait_for_service "Backend" "http://localhost:$BACKEND_PORT/api/" 30
    wait_for_service "Frontend" "http://localhost:$PORT" 30
}

# Cleanup function
cleanup() {
    print_status "Shutting down services..."
    
    if [ "$USE_DOCKER" = true ]; then
        docker-compose down
    else
        [ -n "$BACKEND_PID" ] && kill $BACKEND_PID >/dev/null 2>&1 || true
        [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID >/dev/null 2>&1 || true
    fi
    
    [ -n "$NGROK_PID" ] && kill $NGROK_PID >/dev/null 2>&1 || true
    
    print_status "Services stopped"
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Check ports
if ! check_port $PORT; then
    print_error "Port $PORT is already in use"
    exit 1
fi

if ! check_port $BACKEND_PORT; then
    print_error "Port $BACKEND_PORT is already in use"  
    exit 1
fi

# Setup ngrok if requested
if [ "$NGROK" = true ]; then
    setup_ngrok
fi

# Start services
if [ "$USE_DOCKER" = true ]; then
    start_docker
else
    start_local
fi

# Print summary
echo ""
echo -e "${GREEN}🎉 WebRTC Object Detection System Started Successfully!${NC}"
echo ""
echo -e "${BLUE}📊 System Information:${NC}"
echo "   Detection Mode: $MODE"
echo "   Frontend:       http://localhost:$PORT"
echo "   Backend API:    http://localhost:$BACKEND_PORT/api/"

if [ "$NGROK" = true ] && [ -n "$NGROK_URL" ]; then
    echo "   Public URL:     $NGROK_URL"
    echo ""
    echo -e "${YELLOW}📱 Mobile Access:${NC}"
    echo "   1. Open $NGROK_URL on your phone"
    echo "   2. Scan the QR code to connect camera"
    echo "   3. Allow camera permissions"
fi

echo ""
echo -e "${BLUE}🔧 Usage:${NC}"
echo "   • Open the frontend URL in a desktop browser"
echo "   • Click 'Start Detection Session'"  
echo "   • Scan QR code with phone camera"
echo "   • Allow camera access on phone"
echo "   • Watch real-time object detection!"

echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Keep script running
wait