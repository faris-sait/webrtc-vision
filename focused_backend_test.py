#!/usr/bin/env python3
"""
Focused Backend Testing - Core API functionality only
"""

import asyncio
import aiohttp
import json
import base64
import time
import uuid
from PIL import Image
import io
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BACKEND_URL = "https://live-object-detect.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

class FocusedBackendTester:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_test_image(self, width=300, height=300) -> str:
        """Create a test image and return as base64 encoded string"""
        image = Image.new('RGB', (width, height), color='blue')
        
        # Add some simple shapes
        pixels = image.load()
        for i in range(50, 150):
            for j in range(50, 150):
                pixels[i, j] = (255, 0, 0)  # Red square
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{image_data}"
    
    async def test_core_apis(self) -> dict:
        """Test core API functionality"""
        results = {}
        
        # Test 1: API Root
        logger.info("Testing API Root...")
        try:
            async with self.session.get(f"{API_BASE}/") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✓ API Root: {data}")
                    results["api_root"] = True
                else:
                    logger.error(f"✗ API Root failed: {response.status}")
                    results["api_root"] = False
        except Exception as e:
            logger.error(f"✗ API Root error: {e}")
            results["api_root"] = False
        
        # Test 2: Object Detection with Real ONNX Model
        logger.info("Testing Object Detection with ONNX...")
        try:
            test_image = self.create_test_image()
            detection_request = {
                "image_data": test_image,
                "confidence_threshold": 0.3,  # Lower threshold to catch more detections
                "max_detections": 20
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
                    inference_time = (end_time - start_time) * 1000
                    
                    logger.info(f"✓ Object Detection successful")
                    logger.info(f"  - Response time: {inference_time:.2f}ms")
                    logger.info(f"  - Detections found: {len(data['detections'])}")
                    logger.info(f"  - Frame ID: {data['frame_id']}")
                    
                    # Log detection details
                    for i, det in enumerate(data['detections'][:3]):  # Show first 3
                        logger.info(f"  - Detection {i+1}: {det['class_name']} ({det['confidence']:.2f})")
                    
                    results["object_detection"] = True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Object Detection failed: {response.status} - {error_text}")
                    results["object_detection"] = False
        except Exception as e:
            logger.error(f"✗ Object Detection error: {e}")
            results["object_detection"] = False
        
        # Test 3: Metrics Storage and Retrieval
        logger.info("Testing Metrics System...")
        try:
            # Save test metrics
            test_metrics = {
                "e2e_latency_median": 125.5,
                "e2e_latency_p95": 200.0,
                "server_latency_median": 35.2,
                "network_latency_median": 90.3,
                "processed_fps": 18.5,
                "bandwidth_kbps": 1500.0
            }
            
            async with self.session.post(
                f"{API_BASE}/metrics",
                json=test_metrics,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    save_data = await response.json()
                    logger.info(f"✓ Metrics saved: {save_data['status']}")
                    
                    # Retrieve latest metrics
                    async with self.session.get(f"{API_BASE}/metrics/latest") as get_response:
                        if get_response.status == 200:
                            latest_data = await get_response.json()
                            logger.info(f"✓ Latest metrics retrieved")
                            logger.info(f"  - E2E Latency: {latest_data.get('e2e_latency_median', 'N/A')}ms")
                            logger.info(f"  - Processed FPS: {latest_data.get('processed_fps', 'N/A')}")
                            results["metrics"] = True
                        else:
                            logger.error(f"✗ Metrics retrieval failed: {get_response.status}")
                            results["metrics"] = False
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Metrics save failed: {response.status} - {error_text}")
                    results["metrics"] = False
        except Exception as e:
            logger.error(f"✗ Metrics system error: {e}")
            results["metrics"] = False
        
        # Test 4: Room Management
        logger.info("Testing Room Management...")
        try:
            test_room_id = f"test_room_{uuid.uuid4().hex[:8]}"
            async with self.session.get(f"{API_BASE}/rooms/{test_room_id}/users") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✓ Room Management successful")
                    logger.info(f"  - Room ID: {data['room_id']}")
                    logger.info(f"  - User count: {data['count']}")
                    results["room_management"] = True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Room Management failed: {response.status} - {error_text}")
                    results["room_management"] = False
        except Exception as e:
            logger.error(f"✗ Room Management error: {e}")
            results["room_management"] = False
        
        # Test 5: Performance Test - Multiple Detection Requests
        logger.info("Testing Performance - Multiple Requests...")
        try:
            test_image = self.create_test_image()
            detection_request = {
                "image_data": test_image,
                "confidence_threshold": 0.5,
                "max_detections": 10
            }
            
            num_requests = 5
            start_time = time.time()
            
            tasks = []
            for i in range(num_requests):
                task = self.session.post(
                    f"{API_BASE}/detect",
                    json=detection_request,
                    headers={"Content-Type": "application/json"}
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful_responses = 0
            for response in responses:
                if not isinstance(response, Exception):
                    if response.status == 200:
                        successful_responses += 1
                    response.close()
            
            total_time = (end_time - start_time) * 1000
            avg_time = total_time / num_requests
            
            logger.info(f"✓ Performance test completed")
            logger.info(f"  - Total requests: {num_requests}")
            logger.info(f"  - Successful: {successful_responses}")
            logger.info(f"  - Total time: {total_time:.2f}ms")
            logger.info(f"  - Average time per request: {avg_time:.2f}ms")
            
            results["performance"] = successful_responses >= num_requests * 0.8  # 80% success rate
            
        except Exception as e:
            logger.error(f"✗ Performance test error: {e}")
            results["performance"] = False
        
        return results
    
    async def run_focused_tests(self):
        """Run focused backend tests"""
        logger.info("=" * 60)
        logger.info("FOCUSED BACKEND API TESTING")
        logger.info("=" * 60)
        
        results = await self.test_core_apis()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✓ PASSED" if result else "✗ FAILED"
            logger.info(f"{test_name.replace('_', ' ').title():.<40} {status}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 ALL CORE BACKEND TESTS PASSED!")
        else:
            logger.warning(f"⚠ {total - passed} tests failed")
        
        return results

async def main():
    """Main test execution"""
    async with FocusedBackendTester() as tester:
        results = await tester.run_focused_tests()
        return results

if __name__ == "__main__":
    results = asyncio.run(main())
    all_passed = all(results.values())
    print(f"\nFinal Result: {'SUCCESS' if all_passed else 'PARTIAL SUCCESS'}")
    exit(0 if all_passed else 1)