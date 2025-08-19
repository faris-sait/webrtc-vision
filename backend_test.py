#!/usr/bin/env python3
"""
Comprehensive Backend Testing for WebRTC Multi-Object Detection System
Tests all backend APIs and WebSocket functionality
"""

import asyncio
import aiohttp
import websockets
import json
import base64
import time
import uuid
from PIL import Image
import io
import numpy as np
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://streamlink-2.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"
WS_BASE = BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")

class BackendTester:
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
        """Create a test image and return as base64 encoded string"""
        # Create a simple test image with some patterns
        image = Image.new('RGB', (width, height), color='blue')
        
        # Add some simple shapes for detection testing
        pixels = image.load()
        for i in range(50, 150):
            for j in range(50, 150):
                pixels[i, j] = (255, 0, 0)  # Red square
                
        for i in range(200, 250):
            for j in range(100, 200):
                pixels[i, j] = (0, 255, 0)  # Green rectangle
        
        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{image_data}"
    
    async def test_api_root(self) -> bool:
        """Test the root API endpoint"""
        logger.info("Testing API root endpoint...")
        try:
            async with self.session.get(f"{API_BASE}/") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✓ API root response: {data}")
                    return True
                else:
                    logger.error(f"✗ API root failed with status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"✗ API root test failed: {e}")
            return False
    
    async def test_object_detection_api(self) -> bool:
        """Test the object detection API endpoint"""
        logger.info("Testing Object Detection API...")
        try:
            # Create test image
            test_image = self.create_test_image()
            
            # Test detection request
            detection_request = {
                "image_data": test_image,
                "confidence_threshold": 0.5,
                "max_detections": 10
            }
            
            start_time = time.time()
            async with self.session.post(
                f"{API_BASE}/detect",
                json=detection_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                end_time = time.time()
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    required_fields = ["frame_id", "capture_ts", "recv_ts", "inference_ts", "detections"]
                    for field in required_fields:
                        if field not in data:
                            logger.error(f"✗ Missing field '{field}' in detection response")
                            return False
                    
                    # Validate detections structure
                    for detection in data["detections"]:
                        detection_fields = ["class_id", "class_name", "confidence", "bbox"]
                        for field in detection_fields:
                            if field not in detection:
                                logger.error(f"✗ Missing field '{field}' in detection")
                                return False
                        
                        # Validate bbox structure
                        bbox_fields = ["x1", "y1", "x2", "y2", "width", "height"]
                        for field in bbox_fields:
                            if field not in detection["bbox"]:
                                logger.error(f"✗ Missing field '{field}' in bbox")
                                return False
                    
                    inference_time = (end_time - start_time) * 1000
                    logger.info(f"✓ Object Detection API successful")
                    logger.info(f"  - Response time: {inference_time:.2f}ms")
                    logger.info(f"  - Detections found: {len(data['detections'])}")
                    logger.info(f"  - Frame ID: {data['frame_id']}")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Object Detection API failed with status {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Object Detection API test failed: {e}")
            return False
    
    async def test_metrics_api(self) -> bool:
        """Test the metrics storage and retrieval APIs"""
        logger.info("Testing Metrics API...")
        try:
            # Test metrics storage
            test_metrics = {
                "e2e_latency_median": 150.5,
                "e2e_latency_p95": 250.0,
                "server_latency_median": 45.2,
                "network_latency_median": 105.3,
                "processed_fps": 15.8,
                "bandwidth_kbps": 1250.0
            }
            
            # Save metrics
            async with self.session.post(
                f"{API_BASE}/metrics",
                json=test_metrics,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    save_data = await response.json()
                    logger.info(f"✓ Metrics saved successfully: {save_data}")
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Metrics save failed with status {response.status}: {error_text}")
                    return False
            
            # Retrieve latest metrics
            async with self.session.get(f"{API_BASE}/metrics/latest") as response:
                if response.status == 200:
                    latest_data = await response.json()
                    logger.info(f"✓ Latest metrics retrieved successfully")
                    
                    # Validate that our saved metrics are present
                    if "e2e_latency_median" in latest_data:
                        logger.info(f"  - E2E Latency: {latest_data['e2e_latency_median']}ms")
                        logger.info(f"  - Processed FPS: {latest_data['processed_fps']}")
                        return True
                    else:
                        logger.error("✗ Saved metrics not found in latest metrics")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Latest metrics retrieval failed with status {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Metrics API test failed: {e}")
            return False
    
    async def test_room_management_api(self) -> bool:
        """Test the room management API"""
        logger.info("Testing Room Management API...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            
            # Get room users (should be empty initially)
            async with self.session.get(f"{API_BASE}/rooms/{test_room_id}/users") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    required_fields = ["room_id", "users", "count"]
                    for field in required_fields:
                        if field not in data:
                            logger.error(f"✗ Missing field '{field}' in room users response")
                            return False
                    
                    logger.info(f"✓ Room Management API successful")
                    logger.info(f"  - Room ID: {data['room_id']}")
                    logger.info(f"  - User count: {data['count']}")
                    logger.info(f"  - Users: {data['users']}")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Room Management API failed with status {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Room Management API test failed: {e}")
            return False
    
    async def test_websocket_signaling(self) -> bool:
        """Test WebSocket signaling functionality"""
        logger.info("Testing WebSocket Signaling...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            ws_url = f"{WS_BASE}/ws/{test_room_id}"
            
            # Test WebSocket connection and basic signaling
            async with websockets.connect(ws_url) as websocket:
                logger.info(f"✓ WebSocket connected to room {test_room_id}")
                
                # Test getting room users
                await websocket.send(json.dumps({
                    "type": "get_room_users"
                }))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("type") == "room_users":
                    logger.info(f"✓ Room users response received: {data}")
                else:
                    logger.error(f"✗ Unexpected response type: {data.get('type')}")
                    return False
                
                # Test detection frame processing
                test_image = self.create_test_image()
                frame_id = str(uuid.uuid4())
                
                detection_message = {
                    "type": "detection_frame",
                    "frame_id": frame_id,
                    "frame_data": test_image,
                    "capture_ts": time.time()
                }
                
                await websocket.send(json.dumps(detection_message))
                logger.info("✓ Detection frame sent via WebSocket")
                
                # Wait for detection result
                try:
                    result = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    result_data = json.loads(result)
                    
                    if result_data.get("type") == "detection_result":
                        logger.info(f"✓ Detection result received via WebSocket")
                        logger.info(f"  - Frame ID: {result_data.get('frame_id')}")
                        logger.info(f"  - Detections: {len(result_data.get('detections', []))}")
                        
                        # Validate detection result structure
                        required_fields = ["frame_id", "capture_ts", "recv_ts", "inference_ts", "detections"]
                        for field in required_fields:
                            if field not in result_data:
                                logger.error(f"✗ Missing field '{field}' in WebSocket detection result")
                                return False
                        
                        return True
                    elif result_data.get("type") == "detection_error":
                        logger.error(f"✗ Detection error via WebSocket: {result_data.get('error')}")
                        return False
                    else:
                        logger.error(f"✗ Unexpected WebSocket response type: {result_data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Timeout waiting for WebSocket detection result")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ WebSocket signaling test failed: {e}")
            return False
    
    async def test_webrtc_signaling_messages(self) -> bool:
        """Test WebRTC signaling message forwarding"""
        logger.info("Testing WebRTC Signaling Messages...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            ws_url = f"{WS_BASE}/ws/{test_room_id}"
            
            # Create two WebSocket connections to simulate peer-to-peer signaling
            async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
                logger.info("✓ Two WebSocket connections established")
                
                # Wait for user_joined messages
                await asyncio.sleep(0.5)
                
                # Clear any pending messages
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
                
                # Test offer/answer signaling
                test_offer = {
                    "type": "offer",
                    "data": {
                        "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
                        "type": "offer"
                    }
                }
                
                # Send offer from ws1
                await ws1.send(json.dumps(test_offer))
                logger.info("✓ WebRTC offer sent")
                
                # Receive offer on ws2
                try:
                    response = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "offer":
                        logger.info("✓ WebRTC offer received on peer connection")
                        logger.info(f"  - Sender ID: {data.get('sender_id')}")
                        return True
                    else:
                        logger.error(f"✗ Expected offer, got: {data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Timeout waiting for WebRTC offer")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ WebRTC signaling messages test failed: {e}")
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling scenarios"""
        logger.info("Testing Error Handling...")
        try:
            # Test invalid image data
            invalid_request = {
                "image_data": "invalid_base64_data",
                "confidence_threshold": 0.5
            }
            
            async with self.session.post(
                f"{API_BASE}/detect",
                json=invalid_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 400:
                    logger.info("✓ Invalid image data properly rejected with 400 status")
                else:
                    logger.error(f"✗ Expected 400 for invalid image, got {response.status}")
                    return False
            
            # Test invalid confidence threshold
            test_image = self.create_test_image()
            invalid_threshold_request = {
                "image_data": test_image,
                "confidence_threshold": 1.5  # Invalid threshold > 1.0
            }
            
            async with self.session.post(
                f"{API_BASE}/detect",
                json=invalid_threshold_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                # Should still work but clamp the threshold
                if response.status == 200:
                    logger.info("✓ Invalid confidence threshold handled gracefully")
                else:
                    logger.warning(f"⚠ Confidence threshold validation: status {response.status}")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Error handling test failed: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all backend tests"""
        logger.info("=" * 60)
        logger.info("STARTING COMPREHENSIVE BACKEND TESTING")
        logger.info("=" * 60)
        
        tests = [
            ("API Root", self.test_api_root),
            ("Object Detection API", self.test_object_detection_api),
            ("Metrics API", self.test_metrics_api),
            ("Room Management API", self.test_room_management_api),
            ("WebSocket Signaling", self.test_websocket_signaling),
            ("WebRTC Signaling Messages", self.test_webrtc_signaling_messages),
            ("Error Handling", self.test_error_handling)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = await test_func()
                results[test_name] = result
                status = "✓ PASSED" if result else "✗ FAILED"
                logger.info(f"{test_name}: {status}")
            except Exception as e:
                logger.error(f"{test_name}: ✗ FAILED with exception: {e}")
                results[test_name] = False
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✓ PASSED" if result else "✗ FAILED"
            logger.info(f"{test_name:.<40} {status}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.warning(f"⚠ {total - passed} tests failed")
        
        return results

async def main():
    """Main test execution function"""
    async with BackendTester() as tester:
        results = await tester.run_all_tests()
        
        # Return exit code based on results
        all_passed = all(results.values())
        return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)