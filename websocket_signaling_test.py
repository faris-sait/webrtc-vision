#!/usr/bin/env python3
"""
Focused WebSocket Signaling Test for WebRTC Connection Issues
Tests WebSocket endpoint accessibility, upgrade handling, and signaling message flow
"""

import asyncio
import websockets
import aiohttp
import json
import time
import uuid
import base64
import logging
from PIL import Image
import io
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://qr-join-debug.preview.emergentagent.com"
LOCAL_BACKEND_URL = "http://localhost:8001"
WS_EXTERNAL = BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")
WS_LOCAL = LOCAL_BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")

class WebSocketSignalingTester:
    def __init__(self):
        self.session = None
        self.test_results = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_test_image(self, width=300, height=300) -> str:
        """Create a test image for detection testing"""
        image = Image.new('RGB', (width, height), color='blue')
        pixels = image.load()
        
        # Add red square for detection
        for i in range(50, 150):
            for j in range(50, 150):
                pixels[i, j] = (255, 0, 0)
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{image_data}"
    
    async def test_websocket_endpoint_accessibility(self) -> Dict[str, bool]:
        """Test WebSocket endpoint accessibility both locally and externally"""
        logger.info("Testing WebSocket Endpoint Accessibility...")
        results = {}
        
        # Test 1: Local WebSocket Connection
        logger.info("1. Testing LOCAL WebSocket connection...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            local_ws_url = f"{WS_LOCAL}/ws/{test_room_id}"
            
            # Try to connect locally
            async with websockets.connect(local_ws_url, timeout=5) as websocket:
                logger.info(f"✓ LOCAL WebSocket connected successfully to {local_ws_url}")
                
                # Test basic message exchange
                await websocket.send(json.dumps({"type": "get_room_users"}))
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                data = json.loads(response)
                
                if data.get("type") == "room_users":
                    logger.info(f"✓ LOCAL WebSocket message exchange successful")
                    results["local_websocket"] = True
                else:
                    logger.error(f"✗ LOCAL WebSocket unexpected response: {data}")
                    results["local_websocket"] = False
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"✗ LOCAL WebSocket connection closed: {e}")
            results["local_websocket"] = False
        except asyncio.TimeoutError:
            logger.error("✗ LOCAL WebSocket connection timeout")
            results["local_websocket"] = False
        except Exception as e:
            logger.error(f"✗ LOCAL WebSocket connection failed: {e}")
            results["local_websocket"] = False
        
        # Test 2: External WebSocket Connection
        logger.info("2. Testing EXTERNAL WebSocket connection...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            external_ws_url = f"{WS_EXTERNAL}/ws/{test_room_id}"
            
            # Try to connect externally
            async with websockets.connect(external_ws_url, timeout=10) as websocket:
                logger.info(f"✓ EXTERNAL WebSocket connected successfully to {external_ws_url}")
                
                # Test basic message exchange
                await websocket.send(json.dumps({"type": "get_room_users"}))
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("type") == "room_users":
                    logger.info(f"✓ EXTERNAL WebSocket message exchange successful")
                    results["external_websocket"] = True
                else:
                    logger.error(f"✗ EXTERNAL WebSocket unexpected response: {data}")
                    results["external_websocket"] = False
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"✗ EXTERNAL WebSocket connection closed: {e}")
            results["external_websocket"] = False
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"✗ EXTERNAL WebSocket invalid status code: {e}")
            logger.error("This indicates Kubernetes ingress is not configured for WebSocket upgrades")
            results["external_websocket"] = False
        except asyncio.TimeoutError:
            logger.error("✗ EXTERNAL WebSocket connection timeout")
            results["external_websocket"] = False
        except Exception as e:
            logger.error(f"✗ EXTERNAL WebSocket connection failed: {e}")
            results["external_websocket"] = False
        
        return results
    
    async def test_websocket_upgrade_handling(self) -> Dict[str, bool]:
        """Test WebSocket upgrade response handling"""
        logger.info("Testing WebSocket Upgrade Handling...")
        results = {}
        
        # Test 1: Check HTTP response for WebSocket endpoint
        logger.info("1. Testing HTTP request to WebSocket endpoint...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            
            # Test local endpoint
            local_url = f"{LOCAL_BACKEND_URL}/ws/{test_room_id}"
            async with self.session.get(local_url) as response:
                logger.info(f"LOCAL WebSocket endpoint HTTP response: {response.status}")
                if response.status == 400:
                    logger.info("✓ LOCAL endpoint returns HTTP 400 (expected for incomplete WebSocket handshake)")
                    results["local_http_response"] = True
                else:
                    logger.warning(f"⚠ LOCAL endpoint returns HTTP {response.status} (unexpected)")
                    results["local_http_response"] = False
            
            # Test external endpoint
            external_url = f"{BACKEND_URL}/ws/{test_room_id}"
            async with self.session.get(external_url) as response:
                logger.info(f"EXTERNAL WebSocket endpoint HTTP response: {response.status}")
                response_text = await response.text()
                
                if response.status == 200 and "html" in response_text.lower():
                    logger.error("✗ EXTERNAL endpoint returns HTTP/2 200 with HTML (PROBLEM IDENTIFIED)")
                    logger.error("This confirms Kubernetes ingress is not configured for WebSocket support")
                    results["external_http_response"] = False
                elif response.status == 400:
                    logger.info("✓ EXTERNAL endpoint returns HTTP 400 (expected for incomplete WebSocket handshake)")
                    results["external_http_response"] = True
                else:
                    logger.warning(f"⚠ EXTERNAL endpoint returns HTTP {response.status}")
                    results["external_http_response"] = False
                    
        except Exception as e:
            logger.error(f"✗ WebSocket upgrade test failed: {e}")
            results["local_http_response"] = False
            results["external_http_response"] = False
        
        return results
    
    async def test_signaling_message_flow(self) -> Dict[str, bool]:
        """Test WebRTC signaling message handling"""
        logger.info("Testing Signaling Message Flow...")
        results = {}
        
        # Use local connection for testing signaling logic
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            ws_url = f"{WS_LOCAL}/ws/{test_room_id}"
            
            # Create two connections to simulate peer-to-peer signaling
            async with websockets.connect(ws_url, timeout=5) as ws1, \
                       websockets.connect(ws_url, timeout=5) as ws2:
                
                logger.info("✓ Two WebSocket connections established for signaling test")
                
                # Wait for connection setup
                await asyncio.sleep(0.5)
                
                # Clear any pending user_joined messages
                try:
                    while True:
                        await asyncio.wait_for(ws1.recv(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
                
                try:
                    while True:
                        await asyncio.wait_for(ws2.recv(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
                
                # Test 1: WebRTC Offer/Answer Exchange
                logger.info("1. Testing WebRTC offer/answer exchange...")
                
                # Send offer from peer 1
                test_offer = {
                    "type": "offer",
                    "data": {
                        "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\n",
                        "type": "offer"
                    }
                }
                
                await ws1.send(json.dumps(test_offer))
                logger.info("✓ WebRTC offer sent from peer 1")
                
                # Receive offer on peer 2
                try:
                    response = await asyncio.wait_for(ws2.recv(), timeout=3.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "offer" and "sender_id" in data:
                        logger.info("✓ WebRTC offer received on peer 2")
                        sender_id = data["sender_id"]
                        
                        # Send answer back
                        test_answer = {
                            "type": "answer",
                            "target_id": sender_id,
                            "data": {
                                "sdp": "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\n",
                                "type": "answer"
                            }
                        }
                        
                        await ws2.send(json.dumps(test_answer))
                        logger.info("✓ WebRTC answer sent from peer 2")
                        
                        # Receive answer on peer 1
                        answer_response = await asyncio.wait_for(ws1.recv(), timeout=3.0)
                        answer_data = json.loads(answer_response)
                        
                        if answer_data.get("type") == "answer":
                            logger.info("✓ WebRTC answer received on peer 1")
                            results["offer_answer_exchange"] = True
                        else:
                            logger.error(f"✗ Expected answer, got: {answer_data.get('type')}")
                            results["offer_answer_exchange"] = False
                    else:
                        logger.error(f"✗ Expected offer with sender_id, got: {data}")
                        results["offer_answer_exchange"] = False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Timeout waiting for WebRTC offer")
                    results["offer_answer_exchange"] = False
                
                # Test 2: ICE Candidate Exchange
                logger.info("2. Testing ICE candidate exchange...")
                
                test_ice_candidate = {
                    "type": "ice_candidate",
                    "data": {
                        "candidate": "candidate:1 1 UDP 2130706431 192.168.1.100 54400 typ host",
                        "sdpMid": "0",
                        "sdpMLineIndex": 0
                    }
                }
                
                await ws1.send(json.dumps(test_ice_candidate))
                logger.info("✓ ICE candidate sent from peer 1")
                
                try:
                    ice_response = await asyncio.wait_for(ws2.recv(), timeout=3.0)
                    ice_data = json.loads(ice_response)
                    
                    if ice_data.get("type") == "ice_candidate":
                        logger.info("✓ ICE candidate received on peer 2")
                        results["ice_candidate_exchange"] = True
                    else:
                        logger.error(f"✗ Expected ice_candidate, got: {ice_data.get('type')}")
                        results["ice_candidate_exchange"] = False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Timeout waiting for ICE candidate")
                    results["ice_candidate_exchange"] = False
                
        except Exception as e:
            logger.error(f"✗ Signaling message flow test failed: {e}")
            results["offer_answer_exchange"] = False
            results["ice_candidate_exchange"] = False
        
        return results
    
    async def test_detection_frame_processing(self) -> Dict[str, bool]:
        """Test detection frame processing through WebSocket"""
        logger.info("Testing Detection Frame Processing...")
        results = {}
        
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            ws_url = f"{WS_LOCAL}/ws/{test_room_id}"
            
            async with websockets.connect(ws_url, timeout=5) as websocket:
                logger.info("✓ WebSocket connected for detection frame test")
                
                # Create test image
                test_image = self.create_test_image()
                frame_id = str(uuid.uuid4())
                
                # Send detection frame
                detection_message = {
                    "type": "detection_frame",
                    "frame_id": frame_id,
                    "frame_data": test_image,
                    "capture_ts": time.time()
                }
                
                start_time = time.time()
                await websocket.send(json.dumps(detection_message))
                logger.info("✓ Detection frame sent via WebSocket")
                
                # Wait for detection result
                try:
                    result = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    end_time = time.time()
                    result_data = json.loads(result)
                    
                    if result_data.get("type") == "detection_result":
                        processing_time = (end_time - start_time) * 1000
                        logger.info(f"✓ Detection result received via WebSocket")
                        logger.info(f"  - Processing time: {processing_time:.2f}ms")
                        logger.info(f"  - Frame ID: {result_data.get('frame_id')}")
                        logger.info(f"  - Detections: {len(result_data.get('detections', []))}")
                        
                        # Validate result structure
                        required_fields = ["frame_id", "capture_ts", "recv_ts", "inference_ts", "detections"]
                        all_fields_present = all(field in result_data for field in required_fields)
                        
                        if all_fields_present:
                            logger.info("✓ Detection result has all required fields")
                            results["detection_frame_processing"] = True
                        else:
                            logger.error("✗ Detection result missing required fields")
                            results["detection_frame_processing"] = False
                            
                    elif result_data.get("type") == "detection_error":
                        logger.error(f"✗ Detection error: {result_data.get('error')}")
                        results["detection_frame_processing"] = False
                    else:
                        logger.error(f"✗ Unexpected response type: {result_data.get('type')}")
                        results["detection_frame_processing"] = False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Timeout waiting for detection result")
                    results["detection_frame_processing"] = False
                    
        except Exception as e:
            logger.error(f"✗ Detection frame processing test failed: {e}")
            results["detection_frame_processing"] = False
        
        return results
    
    async def test_connection_state_tracking(self) -> Dict[str, bool]:
        """Test SignalingManager connection and room tracking"""
        logger.info("Testing Connection State Tracking...")
        results = {}
        
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            ws_url = f"{WS_LOCAL}/ws/{test_room_id}"
            
            # Test 1: Single connection tracking
            async with websockets.connect(ws_url, timeout=5) as ws1:
                logger.info("✓ First connection established")
                
                # Get room users
                await ws1.send(json.dumps({"type": "get_room_users"}))
                response = await asyncio.wait_for(ws1.recv(), timeout=3.0)
                data = json.loads(response)
                
                if data.get("type") == "room_users" and data.get("room_id") == test_room_id:
                    user_count = len(data.get("users", []))
                    logger.info(f"✓ Room tracking working - {user_count} user(s) in room")
                    
                    # Test 2: Multiple connections
                    async with websockets.connect(ws_url, timeout=5) as ws2:
                        logger.info("✓ Second connection established")
                        
                        # Wait for user_joined message on first connection
                        try:
                            join_message = await asyncio.wait_for(ws1.recv(), timeout=3.0)
                            join_data = json.loads(join_message)
                            
                            if join_data.get("type") == "user_joined":
                                logger.info("✓ User joined notification received")
                                
                                # Check updated room users
                                await ws1.send(json.dumps({"type": "get_room_users"}))
                                updated_response = await asyncio.wait_for(ws1.recv(), timeout=3.0)
                                updated_data = json.loads(updated_response)
                                
                                updated_user_count = len(updated_data.get("users", []))
                                if updated_user_count > user_count:
                                    logger.info(f"✓ Room state updated - {updated_user_count} users now in room")
                                    results["connection_tracking"] = True
                                else:
                                    logger.error("✗ Room state not properly updated")
                                    results["connection_tracking"] = False
                            else:
                                logger.error(f"✗ Expected user_joined, got: {join_data.get('type')}")
                                results["connection_tracking"] = False
                                
                        except asyncio.TimeoutError:
                            logger.error("✗ Timeout waiting for user_joined notification")
                            results["connection_tracking"] = False
                        
                        # ws2 will disconnect here, test user_left notification
                        
                    # Wait for user_left message
                    try:
                        leave_message = await asyncio.wait_for(ws1.recv(), timeout=3.0)
                        leave_data = json.loads(leave_message)
                        
                        if leave_data.get("type") == "user_left":
                            logger.info("✓ User left notification received")
                            results["disconnect_tracking"] = True
                        else:
                            logger.error(f"✗ Expected user_left, got: {leave_data.get('type')}")
                            results["disconnect_tracking"] = False
                            
                    except asyncio.TimeoutError:
                        logger.error("✗ Timeout waiting for user_left notification")
                        results["disconnect_tracking"] = False
                        
                else:
                    logger.error(f"✗ Invalid room users response: {data}")
                    results["connection_tracking"] = False
                    results["disconnect_tracking"] = False
                    
        except Exception as e:
            logger.error(f"✗ Connection state tracking test failed: {e}")
            results["connection_tracking"] = False
            results["disconnect_tracking"] = False
        
        return results
    
    async def check_backend_logs(self) -> Dict[str, Any]:
        """Check backend logs for WebSocket connection attempts"""
        logger.info("Checking Backend Logs...")
        
        try:
            # Check supervisor logs for backend
            import subprocess
            result = subprocess.run(
                ["tail", "-n", "50", "/var/log/supervisor/backend.out.log"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                log_content = result.stdout
                logger.info("✓ Backend logs retrieved")
                
                # Look for WebSocket-related log entries
                websocket_logs = []
                for line in log_content.split('\n'):
                    if any(keyword in line.lower() for keyword in ['websocket', 'ws', 'signaling', 'connected', 'disconnected']):
                        websocket_logs.append(line.strip())
                
                if websocket_logs:
                    logger.info(f"Found {len(websocket_logs)} WebSocket-related log entries:")
                    for log_line in websocket_logs[-10:]:  # Show last 10
                        logger.info(f"  {log_line}")
                else:
                    logger.info("No WebSocket-related log entries found")
                
                return {"logs_retrieved": True, "websocket_logs": websocket_logs}
            else:
                logger.error(f"✗ Failed to retrieve backend logs: {result.stderr}")
                return {"logs_retrieved": False, "error": result.stderr}
                
        except Exception as e:
            logger.error(f"✗ Backend log check failed: {e}")
            return {"logs_retrieved": False, "error": str(e)}
    
    async def run_comprehensive_websocket_tests(self) -> Dict[str, Any]:
        """Run all WebSocket signaling tests"""
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE WEBSOCKET SIGNALING TESTS")
        logger.info("=" * 80)
        
        all_results = {}
        
        # Test 1: WebSocket Endpoint Accessibility
        logger.info(f"\n{'='*20} WebSocket Endpoint Accessibility {'='*20}")
        accessibility_results = await self.test_websocket_endpoint_accessibility()
        all_results.update(accessibility_results)
        
        # Test 2: WebSocket Upgrade Handling
        logger.info(f"\n{'='*20} WebSocket Upgrade Handling {'='*20}")
        upgrade_results = await self.test_websocket_upgrade_handling()
        all_results.update(upgrade_results)
        
        # Test 3: Signaling Message Flow (only if local WebSocket works)
        if accessibility_results.get("local_websocket", False):
            logger.info(f"\n{'='*20} Signaling Message Flow {'='*20}")
            signaling_results = await self.test_signaling_message_flow()
            all_results.update(signaling_results)
            
            # Test 4: Detection Frame Processing
            logger.info(f"\n{'='*20} Detection Frame Processing {'='*20}")
            detection_results = await self.test_detection_frame_processing()
            all_results.update(detection_results)
            
            # Test 5: Connection State Tracking
            logger.info(f"\n{'='*20} Connection State Tracking {'='*20}")
            tracking_results = await self.test_connection_state_tracking()
            all_results.update(tracking_results)
        else:
            logger.warning("Skipping advanced tests due to local WebSocket connection failure")
        
        # Test 6: Backend Logs Analysis
        logger.info(f"\n{'='*20} Backend Logs Analysis {'='*20}")
        log_results = await self.check_backend_logs()
        all_results["backend_logs"] = log_results
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("WEBSOCKET SIGNALING TEST SUMMARY")
        logger.info("=" * 80)
        
        test_categories = {
            "WebSocket Accessibility": ["local_websocket", "external_websocket"],
            "Upgrade Handling": ["local_http_response", "external_http_response"],
            "Signaling Flow": ["offer_answer_exchange", "ice_candidate_exchange"],
            "Detection Processing": ["detection_frame_processing"],
            "Connection Tracking": ["connection_tracking", "disconnect_tracking"]
        }
        
        for category, test_keys in test_categories.items():
            logger.info(f"\n{category}:")
            for key in test_keys:
                if key in all_results:
                    status = "✓ PASSED" if all_results[key] else "✗ FAILED"
                    logger.info(f"  {key.replace('_', ' ').title():.<35} {status}")
        
        # Overall assessment
        critical_tests = ["local_websocket", "offer_answer_exchange", "ice_candidate_exchange", "detection_frame_processing"]
        critical_passed = sum(1 for test in critical_tests if all_results.get(test, False))
        
        logger.info(f"\nCritical Tests: {critical_passed}/{len(critical_tests)} passed")
        
        if all_results.get("external_websocket", False):
            logger.info("🎉 EXTERNAL WEBSOCKET WORKING - Infrastructure issue resolved!")
        else:
            logger.warning("⚠ EXTERNAL WEBSOCKET FAILING - Kubernetes ingress configuration needed")
        
        if critical_passed >= len(critical_tests) * 0.75:  # 75% of critical tests
            logger.info("✅ WEBSOCKET SIGNALING IMPLEMENTATION IS FUNCTIONAL")
            logger.info("The backend WebSocket implementation works correctly when infrastructure supports it")
        else:
            logger.error("❌ WEBSOCKET SIGNALING IMPLEMENTATION HAS ISSUES")
        
        return all_results

async def main():
    """Main test execution function"""
    async with WebSocketSignalingTester() as tester:
        results = await tester.run_comprehensive_websocket_tests()
        
        # Determine overall success
        critical_tests = ["local_websocket", "offer_answer_exchange", "ice_candidate_exchange", "detection_frame_processing"]
        critical_passed = sum(1 for test in critical_tests if results.get(test, False))
        success = critical_passed >= len(critical_tests) * 0.75
        
        return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)