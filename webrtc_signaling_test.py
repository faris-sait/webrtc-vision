#!/usr/bin/env python3
"""
WebRTC Video Streaming Flow Testing
Comprehensive testing of HTTP signaling API endpoints and WebRTC flow
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
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration - Using the correct backend URL from frontend/.env
BACKEND_URL = "https://rtc-troubleshoot.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

class WebRTCSignalingTester:
    def __init__(self):
        self.session = None
        self.test_room_id = "QH5AMV"  # Using the specific room from the request
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_test_image(self, width=300, height=300) -> str:
        """Create a test image for detection frame testing"""
        image = Image.new('RGB', (width, height), color='lightblue')
        
        # Add some recognizable shapes for object detection
        pixels = image.load()
        # Red rectangle (simulating a person)
        for i in range(80, 180):
            for j in range(50, 200):
                pixels[i, j] = (255, 100, 100)
                
        # Green square (simulating a car)
        for i in range(200, 280):
            for j in range(150, 230):
                pixels[i, j] = (100, 255, 100)
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{image_data}"
    
    async def test_http_signaling_join(self) -> bool:
        """Test HTTP signaling room join endpoint"""
        logger.info("Testing HTTP Signaling - Room Join...")
        try:
            client_id = f"phone_client_{uuid.uuid4().hex[:8]}"
            
            join_request = {
                "client_id": client_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{self.test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    required_fields = ["status", "room_id", "client_id", "users"]
                    for field in required_fields:
                        if field not in data:
                            logger.error(f"✗ Missing field '{field}' in join response")
                            return False
                    
                    logger.info(f"✓ HTTP Signaling Join successful")
                    logger.info(f"  - Status: {data['status']}")
                    logger.info(f"  - Room ID: {data['room_id']}")
                    logger.info(f"  - Client ID: {data['client_id']}")
                    logger.info(f"  - Users in room: {len(data['users'])}")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ HTTP Signaling Join failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ HTTP Signaling Join test failed: {e}")
            return False
    
    async def test_http_signaling_messages(self) -> bool:
        """Test HTTP signaling message polling endpoint"""
        logger.info("Testing HTTP Signaling - Message Polling...")
        try:
            client_id = f"browser_client_{uuid.uuid4().hex[:8]}"
            
            # First join the room
            join_request = {"client_id": client_id}
            async with self.session.post(
                f"{API_BASE}/signaling/{self.test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    logger.error("Failed to join room for message polling test")
                    return False
            
            # Poll for messages
            async with self.session.get(
                f"{API_BASE}/signaling/{self.test_room_id}/messages/{client_id}"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    required_fields = ["messages", "client_id", "room_id", "count"]
                    for field in required_fields:
                        if field not in data:
                            logger.error(f"✗ Missing field '{field}' in messages response")
                            return False
                    
                    logger.info(f"✓ HTTP Signaling Message Polling successful")
                    logger.info(f"  - Client ID: {data['client_id']}")
                    logger.info(f"  - Room ID: {data['room_id']}")
                    logger.info(f"  - Message count: {data['count']}")
                    logger.info(f"  - Messages: {data['messages']}")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ HTTP Signaling Message Polling failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ HTTP Signaling Message Polling test failed: {e}")
            return False
    
    async def test_webrtc_offer_answer_flow(self) -> bool:
        """Test complete WebRTC offer/answer signaling flow"""
        logger.info("Testing WebRTC Offer/Answer Flow...")
        try:
            phone_client_id = f"phone_{uuid.uuid4().hex[:8]}"
            browser_client_id = f"browser_{uuid.uuid4().hex[:8]}"
            
            # Step 1: Both clients join the room
            for client_id, client_type in [(phone_client_id, "phone"), (browser_client_id, "browser")]:
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{self.test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to join room for {client_type}")
                        return False
                    logger.info(f"✓ {client_type} client joined room")
            
            # Step 2: Phone sends SDP offer to browser
            sdp_offer = {
                "type": "offer",
                "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96 97 98 99 100 101 102 121 127 120 125 107 108 109 124 119 123 118 114 115 116\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:4ZcD\r\na=ice-pwd:2/1muCWoOi3uLifh4d2u6QgbvJRs\r\na=ice-options:trickle\r\na=fingerprint:sha-256 75:74:5A:A6:A4:E5:52:F4:A7:67:4C:01:C7:EE:91:3F:21:3D:A2:E3:53:7B:6F:30:86:F2:30:FF:A6:22:D2:04\r\na=setup:actpass\r\na=mid:0\r\na=extmap:1 urn:ietf:params:rtp-hdrext:toffset\r\na=extmap:2 http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time\r\na=extmap:3 urn:3gpp:video-orientation\r\na=extmap:4 http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01\r\na=extmap:5 http://www.webrtc.org/experiments/rtp-hdrext/playout-delay\r\na=extmap:6 http://www.webrtc.org/experiments/rtp-hdrext/video-content-type\r\na=extmap:7 http://www.webrtc.org/experiments/rtp-hdrext/video-timing\r\na=extmap:8 http://www.webrtc.org/experiments/rtp-hdrext/color-space\r\na=extmap:9 urn:ietf:params:rtp-hdrext:sdes:mid\r\na=extmap:10 urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id\r\na=extmap:11 urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id\r\na=sendrecv\r\na=msid:- {uuid.uuid4()}\r\na=rtcp-mux\r\na=rtcp-rsize\r\na=rtpmap:96 VP8/90000\r\na=rtcp-fb:96 goog-remb\r\na=rtcp-fb:96 transport-cc\r\na=rtcp-fb:96 ccm fir\r\na=rtcp-fb:96 nack\r\na=rtcp-fb:96 nack pli\r\na=ssrc:1001 cname:4TOk42mSjMCkjqMp\r\n"
            }
            
            offer_message = {
                "type": "offer",
                "data": sdp_offer,
                "target_id": browser_client_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{self.test_room_id}/message",
                json=offer_message,
                params={"client_id": phone_client_id},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✓ SDP offer sent from phone to browser")
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to send SDP offer: {response.status} - {error_text}")
                    return False
            
            # Step 3: Browser polls for messages and should receive the offer
            await asyncio.sleep(0.5)  # Small delay to ensure message is queued
            
            async with self.session.get(
                f"{API_BASE}/signaling/{self.test_room_id}/messages/{browser_client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['count'] > 0:
                        offer_received = False
                        for message in data['messages']:
                            if message.get('type') == 'offer':
                                offer_received = True
                                logger.info("✓ SDP offer received by browser")
                                logger.info(f"  - Sender ID: {message.get('sender_id')}")
                                break
                        
                        if not offer_received:
                            logger.error("✗ SDP offer not found in browser messages")
                            return False
                    else:
                        logger.error("✗ No messages received by browser")
                        return False
                else:
                    logger.error("✗ Failed to poll messages for browser")
                    return False
            
            # Step 4: Browser sends SDP answer back to phone
            sdp_answer = {
                "type": "answer",
                "sdp": "v=0\r\no=- 1234567890123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:abcd\r\na=ice-pwd:1234567890123456789012\r\na=ice-options:trickle\r\na=fingerprint:sha-256 AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99\r\na=setup:active\r\na=mid:0\r\na=recvonly\r\na=rtcp-mux\r\na=rtcp-rsize\r\na=rtpmap:96 VP8/90000\r\n"
            }
            
            answer_message = {
                "type": "answer",
                "data": sdp_answer,
                "target_id": phone_client_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{self.test_room_id}/message",
                json=answer_message,
                params={"client_id": browser_client_id},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✓ SDP answer sent from browser to phone")
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to send SDP answer: {response.status} - {error_text}")
                    return False
            
            # Step 5: Phone polls for messages and should receive the answer
            await asyncio.sleep(0.5)
            
            async with self.session.get(
                f"{API_BASE}/signaling/{self.test_room_id}/messages/{phone_client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['count'] > 0:
                        answer_received = False
                        for message in data['messages']:
                            if message.get('type') == 'answer':
                                answer_received = True
                                logger.info("✓ SDP answer received by phone")
                                logger.info(f"  - Sender ID: {message.get('sender_id')}")
                                break
                        
                        if not answer_received:
                            logger.error("✗ SDP answer not found in phone messages")
                            return False
                    else:
                        logger.error("✗ No messages received by phone")
                        return False
                else:
                    logger.error("✗ Failed to poll messages for phone")
                    return False
            
            logger.info("✓ Complete WebRTC Offer/Answer flow successful")
            return True
            
        except Exception as e:
            logger.error(f"✗ WebRTC Offer/Answer flow test failed: {e}")
            return False
    
    async def test_ice_candidate_exchange(self) -> bool:
        """Test ICE candidate exchange"""
        logger.info("Testing ICE Candidate Exchange...")
        try:
            phone_client_id = f"phone_{uuid.uuid4().hex[:8]}"
            browser_client_id = f"browser_{uuid.uuid4().hex[:8]}"
            
            # Join room
            for client_id in [phone_client_id, browser_client_id]:
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{self.test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to join room for ICE test")
                        return False
            
            # Phone sends ICE candidate to browser
            ice_candidate = {
                "candidate": "candidate:842163049 1 udp 1677729535 192.168.1.100 54400 typ srflx raddr 192.168.1.100 rport 54400 generation 0 ufrag 4ZcD network-cost 999",
                "sdpMLineIndex": 0,
                "sdpMid": "0"
            }
            
            ice_message = {
                "type": "ice_candidate",
                "data": ice_candidate,
                "target_id": browser_client_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{self.test_room_id}/message",
                json=ice_message,
                params={"client_id": phone_client_id},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✓ ICE candidate sent from phone to browser")
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to send ICE candidate: {response.status} - {error_text}")
                    return False
            
            # Browser polls and receives ICE candidate
            await asyncio.sleep(0.5)
            
            async with self.session.get(
                f"{API_BASE}/signaling/{self.test_room_id}/messages/{browser_client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    ice_received = False
                    for message in data['messages']:
                        if message.get('type') == 'ice_candidate':
                            ice_received = True
                            logger.info("✓ ICE candidate received by browser")
                            logger.info(f"  - Candidate: {message['data']['candidate'][:50]}...")
                            break
                    
                    if not ice_received:
                        logger.error("✗ ICE candidate not received by browser")
                        return False
                else:
                    logger.error("✗ Failed to poll ICE candidate")
                    return False
            
            # Browser sends ICE candidate back to phone
            browser_ice_candidate = {
                "candidate": "candidate:842163050 1 udp 1677729535 10.0.0.1 45678 typ host generation 0 ufrag abcd network-cost 10",
                "sdpMLineIndex": 0,
                "sdpMid": "0"
            }
            
            browser_ice_message = {
                "type": "ice_candidate",
                "data": browser_ice_candidate,
                "target_id": phone_client_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{self.test_room_id}/message",
                json=browser_ice_message,
                params={"client_id": browser_client_id},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✓ ICE candidate sent from browser to phone")
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to send browser ICE candidate: {response.status} - {error_text}")
                    return False
            
            # Phone receives ICE candidate
            await asyncio.sleep(0.5)
            
            async with self.session.get(
                f"{API_BASE}/signaling/{self.test_room_id}/messages/{phone_client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    ice_received = False
                    for message in data['messages']:
                        if message.get('type') == 'ice_candidate':
                            ice_received = True
                            logger.info("✓ ICE candidate received by phone")
                            break
                    
                    if not ice_received:
                        logger.error("✗ ICE candidate not received by phone")
                        return False
                else:
                    logger.error("✗ Failed to poll ICE candidate for phone")
                    return False
            
            logger.info("✓ Bidirectional ICE candidate exchange successful")
            return True
            
        except Exception as e:
            logger.error(f"✗ ICE candidate exchange test failed: {e}")
            return False
    
    async def test_detection_frame_processing(self) -> bool:
        """Test object detection integration through signaling"""
        logger.info("Testing Object Detection Integration...")
        try:
            # Create test image with recognizable objects
            test_image = self.create_test_image()
            
            # Test detection through regular API first to ensure it works
            detection_request = {
                "image_data": test_image,
                "confidence_threshold": 0.3,
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
                    processing_time = (end_time - start_time) * 1000
                    
                    logger.info("✓ Object Detection API working")
                    logger.info(f"  - Processing time: {processing_time:.2f}ms")
                    logger.info(f"  - Detections found: {len(data['detections'])}")
                    
                    # Log detection details
                    for i, det in enumerate(data['detections'][:3]):
                        logger.info(f"  - Detection {i+1}: {det['class_name']} ({det['confidence']:.2f})")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Object Detection API failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Object Detection integration test failed: {e}")
            return False
    
    async def test_room_management_performance(self) -> bool:
        """Test room management with multiple clients"""
        logger.info("Testing Room Management Performance...")
        try:
            # Create multiple clients
            client_ids = [f"client_{i}_{uuid.uuid4().hex[:6]}" for i in range(5)]
            
            # All clients join the room
            for client_id in client_ids:
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{self.test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to join room for client {client_id}")
                        return False
            
            logger.info(f"✓ {len(client_ids)} clients joined room")
            
            # Check room users via HTTP signaling
            async with self.session.get(
                f"{API_BASE}/signaling/{self.test_room_id}/users"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✓ Room users retrieved via HTTP signaling")
                    logger.info(f"  - Room ID: {data['room_id']}")
                    logger.info(f"  - User count: {data['count']}")
                    logger.info(f"  - Users: {data['users'][:3]}...")  # Show first 3
                    
                    if data['count'] >= len(client_ids):
                        logger.info("✓ All clients properly tracked in room")
                        return True
                    else:
                        logger.error(f"✗ Expected {len(client_ids)} users, found {data['count']}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"✗ Failed to get room users: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Room management performance test failed: {e}")
            return False
    
    async def test_message_delivery_latency(self) -> bool:
        """Test signaling message delivery latency"""
        logger.info("Testing Message Delivery Latency...")
        try:
            sender_id = f"sender_{uuid.uuid4().hex[:8]}"
            receiver_id = f"receiver_{uuid.uuid4().hex[:8]}"
            
            # Both join room
            for client_id in [sender_id, receiver_id]:
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{self.test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to join room for latency test")
                        return False
            
            # Send multiple messages and measure latency
            num_messages = 5
            latencies = []
            
            for i in range(num_messages):
                # Send message with timestamp
                send_time = time.time()
                test_message = {
                    "type": "test_message",
                    "data": {"message_id": i, "send_time": send_time},
                    "target_id": receiver_id
                }
                
                async with self.session.post(
                    f"{API_BASE}/signaling/{self.test_room_id}/message",
                    json=test_message,
                    params={"client_id": sender_id},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send test message {i}")
                        continue
                
                # Small delay between messages
                await asyncio.sleep(0.1)
                
                # Poll for message
                async with self.session.get(
                    f"{API_BASE}/signaling/{self.test_room_id}/messages/{receiver_id}"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        recv_time = time.time()
                        
                        # Find our message
                        for message in data['messages']:
                            if (message.get('type') == 'test_message' and 
                                message.get('data', {}).get('message_id') == i):
                                latency = (recv_time - send_time) * 1000
                                latencies.append(latency)
                                break
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                min_latency = min(latencies)
                
                logger.info("✓ Message delivery latency test completed")
                logger.info(f"  - Messages tested: {len(latencies)}")
                logger.info(f"  - Average latency: {avg_latency:.2f}ms")
                logger.info(f"  - Min latency: {min_latency:.2f}ms")
                logger.info(f"  - Max latency: {max_latency:.2f}ms")
                
                # Consider successful if average latency is reasonable
                return avg_latency < 1000  # Less than 1 second
            else:
                logger.error("✗ No latency measurements collected")
                return False
                
        except Exception as e:
            logger.error(f"✗ Message delivery latency test failed: {e}")
            return False
    
    async def run_webrtc_signaling_tests(self) -> Dict[str, bool]:
        """Run all WebRTC signaling tests"""
        logger.info("=" * 80)
        logger.info("WEBRTC VIDEO STREAMING FLOW TESTING")
        logger.info(f"Testing Room: {self.test_room_id}")
        logger.info(f"Backend URL: {BACKEND_URL}")
        logger.info("=" * 80)
        
        tests = [
            ("HTTP Signaling Join", self.test_http_signaling_join),
            ("HTTP Signaling Messages", self.test_http_signaling_messages),
            ("WebRTC Offer/Answer Flow", self.test_webrtc_offer_answer_flow),
            ("ICE Candidate Exchange", self.test_ice_candidate_exchange),
            ("Object Detection Integration", self.test_detection_frame_processing),
            ("Room Management Performance", self.test_room_management_performance),
            ("Message Delivery Latency", self.test_message_delivery_latency)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*25} {test_name} {'='*25}")
            try:
                result = await test_func()
                results[test_name] = result
                status = "✓ PASSED" if result else "✗ FAILED"
                logger.info(f"{test_name}: {status}")
            except Exception as e:
                logger.error(f"{test_name}: ✗ FAILED with exception: {e}")
                results[test_name] = False
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("WEBRTC SIGNALING TEST SUMMARY")
        logger.info("=" * 80)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✓ PASSED" if result else "✗ FAILED"
            logger.info(f"{test_name:.<50} {status}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 ALL WEBRTC SIGNALING TESTS PASSED!")
        elif passed >= total * 0.8:
            logger.info("✅ MOST WEBRTC SIGNALING TESTS PASSED!")
        else:
            logger.warning(f"⚠ {total - passed} critical tests failed")
        
        return results

async def main():
    """Main test execution function"""
    async with WebRTCSignalingTester() as tester:
        results = await tester.run_webrtc_signaling_tests()
        
        # Return results for analysis
        all_passed = all(results.values())
        critical_passed = sum(1 for k, v in results.items() if v and k in [
            "HTTP Signaling Join", "HTTP Signaling Messages", 
            "WebRTC Offer/Answer Flow", "ICE Candidate Exchange"
        ])
        
        logger.info(f"\nFinal Analysis:")
        logger.info(f"- All tests passed: {all_passed}")
        logger.info(f"- Critical signaling tests passed: {critical_passed}/4")
        
        return results

if __name__ == "__main__":
    results = asyncio.run(main())
    all_passed = all(results.values())
    exit(0 if all_passed else 1)