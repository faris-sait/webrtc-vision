#!/bin/bash

# WebRTC Object Detection Benchmark Script
# Measures performance metrics for 30 seconds and outputs metrics.json

set -e

# Default values
DURATION=${DURATION:-30}
MODE=${MODE:-"server"}
OUTPUT_FILE="metrics.json"
BACKEND_URL=${REACT_APP_BACKEND_URL:-"http://localhost:8001"}
FRONTEND_URL=${FRONTEND_URL:-"http://localhost:3000"}

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --backend-url)
            BACKEND_URL="$2"
            shift 2
            ;;
        --frontend-url)
            FRONTEND_URL="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --duration SECONDS    Benchmark duration (default: 30)"
            echo "  --mode MODE          Detection mode: server or wasm (default: server)"
            echo "  --output FILE        Output file (default: metrics.json)"
            echo "  --backend-url URL    Backend URL (default: http://localhost:8001)"
            echo "  --frontend-url URL   Frontend URL (default: http://localhost:3000)"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # 30s benchmark, server mode"
            echo "  $0 --duration 60 --mode wasm         # 60s benchmark, WASM mode"
            echo "  $0 --mode server --output results.json  # Custom output file"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate parameters
if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || [ "$DURATION" -lt 1 ]; then
    print_error "Duration must be a positive integer"
    exit 1
fi

if [[ "$MODE" != "server" && "$MODE" != "wasm" ]]; then
    print_error "Mode must be 'server' or 'wasm'"
    exit 1
fi

echo "🎯 WebRTC Object Detection Benchmark"
echo "=================================="
echo "Duration: ${DURATION}s"
echo "Mode: $MODE"
echo "Output: $OUTPUT_FILE"
echo "Backend: $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"
echo ""

# Check if services are running
print_info "Checking service availability..."

if ! curl -sf "$BACKEND_URL/api/" >/dev/null 2>&1; then
    print_error "Backend not accessible at $BACKEND_URL"
    exit 1
fi
print_status "Backend is accessible"

if ! curl -sf "$FRONTEND_URL" >/dev/null 2>&1; then
    print_error "Frontend not accessible at $FRONTEND_URL"
    exit 1
fi
print_status "Frontend is accessible"

# Check if Node.js is available for the benchmark script
if ! command -v node >/dev/null 2>&1; then
    print_error "Node.js is required for the benchmark script"
    exit 1
fi

# Create the benchmark Node.js script
cat > benchmark_script.js << 'EOF'
const puppeteer = require('puppeteer');
const fs = require('fs');

class BenchmarkRunner {
    constructor(options) {
        this.duration = options.duration * 1000; // Convert to milliseconds
        this.mode = options.mode;
        this.frontendUrl = options.frontendUrl;
        this.backendUrl = options.backendUrl;
        this.outputFile = options.outputFile;
        
        this.metrics = {
            startTime: 0,
            endTime: 0,
            e2eLatencies: [],
            serverLatencies: [],
            networkLatencies: [],
            processedFrames: 0,
            droppedFrames: 0,
            bandwidth: [],
            detectionCounts: [],
            errors: []
        };
    }

    async run() {
        console.log('🚀 Starting benchmark...');
        
        const browser = await puppeteer.launch({
            headless: false,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--use-fake-ui-for-media-stream',
                '--use-fake-device-for-media-stream',
                '--use-file-for-fake-video-capture=/dev/null'
            ]
        });

        try {
            const page = await browser.newPage();
            
            // Set viewport
            await page.setViewport({ width: 1920, height: 1080 });
            
            // Enable permissions for camera
            const context = browser.defaultBrowserContext();
            await context.overridePermissions(this.frontendUrl, ['camera', 'microphone']);
            
            // Navigate to application
            console.log(`📂 Opening ${this.frontendUrl}...`);
            await page.goto(this.frontendUrl, { waitUntil: 'networkidle0' });
            
            // Start detection session
            console.log('🎬 Starting detection session...');
            await page.click('button:has-text("Start Detection Session")');
            await page.waitForTimeout(2000);
            
            // Switch to specified mode
            if (this.mode === 'wasm') {
                console.log('🔧 Switching to WASM mode...');
                await page.selectOption('select', 'wasm');
                await page.waitForTimeout(3000); // Wait for WASM to initialize
            }
            
            // Set up metrics collection
            await this.setupMetricsCollection(page);
            
            // Start benchmark
            this.metrics.startTime = Date.now();
            console.log(`⏱️ Running benchmark for ${this.duration/1000}s in ${this.mode} mode...`);
            
            // Simulate camera input and collect metrics
            await this.runBenchmarkLoop(page);
            
            this.metrics.endTime = Date.now();
            
            // Calculate final metrics
            const results = this.calculateResults();
            
            // Save results
            fs.writeFileSync(this.outputFile, JSON.stringify(results, null, 2));
            console.log(`💾 Results saved to ${this.outputFile}`);
            
            return results;
            
        } finally {
            await browser.close();
        }
    }

    async setupMetricsCollection(page) {
        // Inject metrics collection script
        await page.evaluateOnNewDocument(() => {
            window.benchmarkMetrics = {
                detections: [],
                latencies: [],
                bandwidth: [],
                errors: []
            };
            
            // Override WebSocket to capture messages
            const originalWebSocket = window.WebSocket;
            window.WebSocket = function(url) {
                const ws = new originalWebSocket(url);
                
                const originalSend = ws.send;
                ws.send = function(data) {
                    try {
                        const message = JSON.parse(data);
                        if (message.type === 'detection_frame') {
                            window.benchmarkMetrics.frameSent = Date.now();
                        }
                    } catch (e) {}
                    return originalSend.call(this, data);
                };
                
                ws.addEventListener('message', (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (message.type === 'detection_result') {
                            const now = Date.now();
                            const e2eLatency = now - message.capture_ts;
                            const serverLatency = message.inference_ts - message.recv_ts;
                            const networkLatency = message.recv_ts - message.capture_ts;
                            
                            window.benchmarkMetrics.latencies.push({
                                e2e: e2eLatency,
                                server: serverLatency,
                                network: networkLatency,
                                timestamp: now
                            });
                            
                            window.benchmarkMetrics.detections.push({
                                count: message.detections ? message.detections.length : 0,
                                timestamp: now
                            });
                        }
                    } catch (e) {
                        window.benchmarkMetrics.errors.push({
                            error: e.message,
                            timestamp: Date.now()
                        });
                    }
                });
                
                return ws;
            };
        });
    }

    async runBenchmarkLoop(page) {
        const startTime = Date.now();
        
        // Simulate video streaming for the benchmark duration
        while (Date.now() - startTime < this.duration) {
            try {
                // Get current metrics from page
                const pageMetrics = await page.evaluate(() => {
                    return {
                        detections: window.benchmarkMetrics ? window.benchmarkMetrics.detections.length : 0,
                        latencies: window.benchmarkMetrics ? window.benchmarkMetrics.latencies.length : 0,
                        errors: window.benchmarkMetrics ? window.benchmarkMetrics.errors.length : 0
                    };
                });
                
                // Update progress
                const elapsed = (Date.now() - startTime) / 1000;
                const progress = (elapsed / (this.duration / 1000) * 100).toFixed(1);
                process.stdout.write(`\r📊 Progress: ${progress}% | Detections: ${pageMetrics.detections} | Latencies: ${pageMetrics.latencies} | Errors: ${pageMetrics.errors}`);
                
                await page.waitForTimeout(1000);
                
            } catch (error) {
                this.metrics.errors.push({
                    error: error.message,
                    timestamp: Date.now()
                });
            }
        }
        
        console.log('\n✅ Benchmark completed!');
        
        // Collect final metrics
        const finalMetrics = await page.evaluate(() => {
            return window.benchmarkMetrics || {
                detections: [],
                latencies: [],
                bandwidth: [],
                errors: []
            };
        });
        
        this.metrics.detectionCounts = finalMetrics.detections;
        this.metrics.e2eLatencies = finalMetrics.latencies.map(l => l.e2e);
        this.metrics.serverLatencies = finalMetrics.latencies.map(l => l.server);
        this.metrics.networkLatencies = finalMetrics.latencies.map(l => l.network);
        this.metrics.errors = finalMetrics.errors;
        this.metrics.processedFrames = finalMetrics.latencies.length;
    }

    calculateResults() {
        const duration = (this.metrics.endTime - this.metrics.startTime) / 1000;
        
        // Calculate percentiles
        const calculatePercentile = (arr, percentile) => {
            if (arr.length === 0) return 0;
            const sorted = [...arr].sort((a, b) => a - b);
            const index = Math.ceil((percentile / 100) * sorted.length) - 1;
            return sorted[Math.max(0, index)];
        };
        
        const e2eMedian = calculatePercentile(this.metrics.e2eLatencies, 50);
        const e2eP95 = calculatePercentile(this.metrics.e2eLatencies, 95);
        const serverMedian = calculatePercentile(this.metrics.serverLatencies, 50);
        const networkMedian = calculatePercentile(this.metrics.networkLatencies, 50);
        
        const processedFPS = this.metrics.processedFrames / duration;
        const avgDetections = this.metrics.detectionCounts.length > 0 ? 
            this.metrics.detectionCounts.reduce((sum, d) => sum + d.count, 0) / this.metrics.detectionCounts.length : 0;
        
        // Estimate bandwidth (only for server mode)
        const estimatedBandwidth = this.mode === 'server' ? 
            (this.metrics.processedFrames * 50) : 0; // Rough estimate: 50KB per frame
        
        return {
            benchmark: {
                mode: this.mode,
                duration_seconds: duration,
                start_time: new Date(this.metrics.startTime).toISOString(),
                end_time: new Date(this.metrics.endTime).toISOString()
            },
            performance: {
                e2e_latency_median_ms: Math.round(e2eMedian),
                e2e_latency_p95_ms: Math.round(e2eP95),
                server_latency_median_ms: Math.round(serverMedian),
                network_latency_median_ms: Math.round(networkMedian),
                processed_fps: Math.round(processedFPS * 10) / 10,
                bandwidth_kbps: Math.round(estimatedBandwidth / 1024)
            },
            detections: {
                total_frames: this.metrics.processedFrames,
                dropped_frames: this.metrics.droppedFrames,
                avg_detections_per_frame: Math.round(avgDetections * 10) / 10,
                detection_rate: this.metrics.processedFrames > 0 ? 
                    (this.metrics.detectionCounts.filter(d => d.count > 0).length / this.metrics.processedFrames * 100) : 0
            },
            errors: {
                count: this.metrics.errors.length,
                details: this.metrics.errors.slice(0, 10) // First 10 errors
            },
            raw_data: {
                e2e_latencies: this.metrics.e2eLatencies,
                server_latencies: this.metrics.serverLatencies,
                network_latencies: this.metrics.networkLatencies,
                detection_counts: this.metrics.detectionCounts
            }
        };
    }
}

// Main execution
async function main() {
    const options = {
        duration: parseInt(process.argv[2]) || 30,
        mode: process.argv[3] || 'server',
        frontendUrl: process.argv[4] || 'http://localhost:3000',
        backendUrl: process.argv[5] || 'http://localhost:8001',
        outputFile: process.argv[6] || 'metrics.json'
    };
    
    const runner = new BenchmarkRunner(options);
    
    try {
        const results = await runner.run();
        
        console.log('\n📈 Benchmark Results:');
        console.log(`   Mode: ${results.benchmark.mode}`);
        console.log(`   Duration: ${results.benchmark.duration_seconds}s`);
        console.log(`   E2E Latency (median): ${results.performance.e2e_latency_median_ms}ms`);
        console.log(`   E2E Latency (P95): ${results.performance.e2e_latency_p95_ms}ms`);
        console.log(`   Processed FPS: ${results.performance.processed_fps}`);
        console.log(`   Total Frames: ${results.detections.total_frames}`);
        console.log(`   Errors: ${results.errors.count}`);
        
        process.exit(0);
    } catch (error) {
        console.error('❌ Benchmark failed:', error.message);
        process.exit(1);
    }
}

main();
EOF

# Install Puppeteer if needed
if ! npm list puppeteer >/dev/null 2>&1; then
    print_info "Installing Puppeteer for browser automation..."
    npm install puppeteer
fi

# Run the benchmark
print_info "Starting browser-based benchmark..."
node benchmark_script.js "$DURATION" "$MODE" "$FRONTEND_URL" "$BACKEND_URL" "$OUTPUT_FILE"

# Cleanup
rm -f benchmark_script.js

print_status "Benchmark completed successfully!"
print_info "Results saved to: $OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    print_info "Summary:"
    node -e "
        const fs = require('fs');
        const results = JSON.parse(fs.readFileSync('$OUTPUT_FILE', 'utf8'));
        console.log(\`  Mode: \${results.benchmark.mode}\`);
        console.log(\`  Duration: \${results.benchmark.duration_seconds}s\`);
        console.log(\`  E2E Latency (median): \${results.performance.e2e_latency_median_ms}ms\`);
        console.log(\`  E2E Latency (P95): \${results.performance.e2e_latency_p95_ms}ms\`);
        console.log(\`  Server Latency: \${results.performance.server_latency_median_ms}ms\`);
        console.log(\`  Network Latency: \${results.performance.network_latency_median_ms}ms\`);
        console.log(\`  Processed FPS: \${results.performance.processed_fps}\`);
        console.log(\`  Bandwidth: \${results.performance.bandwidth_kbps} Kbps\`);
    " 2>/dev/null || echo "  (Detailed results in $OUTPUT_FILE)"
fi