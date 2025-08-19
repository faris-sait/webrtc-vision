#!/usr/bin/env python3
"""
WebRTC Signaling Debug Test - Focused on debugging signaling issues
Tests the specific WebRTC signaling flow: offer→answer→ice candidate exchange
"""

import asyncio
import websockets
import json
import time
import uuid
import logging
from typing import Dict, List, Any

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://streamlink-2.preview.emergentagent.com"
WS_BASE = BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")

class WebRTCSignalingDebugger:
    def __init__(self):
        self.test_results = {}
        self.message_log = []
        
    def log_message(self, direction: str, client: str, message: dict):
        """Log WebSocket messages for debugging"""
        timestamp = time.time()
        log_entry = {
            "timestamp": timestamp,
            "direction": direction,  # "sent" or "received"
            "client": client,
            "message": message
        }
        self.message_log.append(log_entry)
        logger.info(f"[{client}] {direction.upper()}: {message.get('type', 'unknown')} - {message}")
    
    async def test_websocket_connection(self) -> bool:
        """Test basic WebSocket connection to signaling server"""
        logger.info("=" * 60)
        logger.info("TEST 1: WebSocket Connection")
        logger.info("=" * 60)
        
        test_room_id = f"debug_room_{uuid.uuid4().hex[:8]}"
        ws_url = f"{WS_BASE}/ws/{test_room_id}"
        
        try:
            logger.info(f"Attempting WebSocket connection to: {ws_url}")
            
            async with websockets.connect(ws_url, timeout=10) as websocket:
                logger.info("✓ WebSocket connection established successfully")
                
                # Test basic ping-pong
                await websocket.ping()
                logger.info("✓ WebSocket ping successful")
                
                # Wait for any initial messages (user_joined)
                try:
                    initial_message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(initial_message)
                    self.log_message("received", "client1", data)
                    
                    if data.get("type") == "user_joined":
                        logger.info("✓ Received user_joined notification")
                    else:
                        logger.warning(f"⚠ Unexpected initial message: {data.get('type')}")
                        
                except asyncio.TimeoutError:
                    logger.info("ℹ No initial messages received (this is okay)")
                
                return True
                
        except Exception as e:
            logger.error(f"✗ WebSocket connection failed: {e}")
            return False
    
    async def test_room_management(self) -> bool:
        """Test room management and user tracking"""
        logger.info("=" * 60)
        logger.info("TEST 2: Room Management & User Tracking")
        logger.info("=" * 60)
        
        test_room_id = f"debug_room_{uuid.uuid4().hex[:8]}"
        ws_url = f"{WS_BASE}/ws/{test_room_id}"
        
        try:
            # Connect two clients to the same room
            async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
                logger.info("✓ Two clients connected to the same room")
                
                # Clear initial messages
                await asyncio.sleep(1)
                
                # Client 1 requests room users
                get_users_msg = {"type": "get_room_users"}
                await ws1.send(json.dumps(get_users_msg))
                self.log_message("sent", "client1", get_users_msg)
                
                # Wait for room users response
                response = await asyncio.wait_for(ws1.recv(), timeout=5.0)
                data = json.loads(response)
                self.log_message("received", "client1", data)
                
                if data.get("type") == "room_users":
                    users = data.get("users", [])
                    logger.info(f"✓ Room users response received: {len(users)} users")
                    logger.info(f"  - Users: {users}")
                    
                    if len(users) >= 2:
                        logger.info("✓ Both clients are tracked in the room")
                        return True
                    else:
                        logger.warning(f"⚠ Expected 2+ users, got {len(users)}")
                        return False
                else:
                    logger.error(f"✗ Expected room_users, got: {data.get('type')}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Room management test failed: {e}")
            return False
    
    async def test_webrtc_offer_answer_flow(self) -> bool:
        """Test the complete WebRTC offer→answer→ice candidate flow"""
        logger.info("=" * 60)
        logger.info("TEST 3: WebRTC Offer→Answer→ICE Candidate Flow")
        logger.info("=" * 60)
        
        test_room_id = f"debug_room_{uuid.uuid4().hex[:8]}"
        ws_url = f"{WS_BASE}/ws/{test_room_id}"
        
        try:
            # Connect two clients (phone and laptop simulation)
            async with websockets.connect(ws_url) as phone_ws, websockets.connect(ws_url) as laptop_ws:
                logger.info("✓ Phone and Laptop clients connected")
                
                # Wait for connection setup and clear initial messages
                await asyncio.sleep(1)
                try:
                    while True:
                        await asyncio.wait_for(phone_ws.recv(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
                try:
                    while True:
                        await asyncio.wait_for(laptop_ws.recv(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
                
                # Step 1: Phone sends WebRTC offer
                logger.info("Step 1: Phone sending WebRTC offer...")
                offer_message = {
                    "type": "offer",
                    "data": {
                        "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96 97 98 99 100 101 102 121 127 120 125 107 108 109 124 119 123 118 114 115 116\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:4ZcD\r\na=ice-pwd:2/1muCWoOi3uLifh0NuRHgpw\r\na=ice-options:trickle\r\na=fingerprint:sha-256 75:74:5A:A6:A4:E5:52:F4:A7:67:4C:01:C7:EE:91:3F:21:3D:A2:E3:53:7B:6F:30:86:F2:30:FF:A6:22:D2:04\r\na=setup:actpass\r\na=mid:0\r\na=extmap:1 urn:ietf:params:rtp-hdrext:toffset\r\na=extmap:2 http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time\r\na=extmap:3 urn:3gpp:video-orientation\r\na=extmap:4 http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01\r\na=extmap:5 http://www.webrtc.org/experiments/rtp-hdrext/playout-delay\r\na=extmap:6 http://www.webrtc.org/experiments/rtp-hdrext/video-content-type\r\na=extmap:7 http://www.webrtc.org/experiments/rtp-hdrext/video-timing\r\na=extmap:8 http://www.webrtc.org/experiments/rtp-hdrext/color-space\r\na=extmap:9 urn:ietf:params:rtp-hdrext:sdes:mid\r\na=extmap:10 urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id\r\na=extmap:11 urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id\r\na=sendrecv\r\na=msid:- \r\na=rtcp-mux\r\na=rtcp-rsize\r\na=rtpmap:96 VP8/90000\r\na=rtcp-fb:96 goog-remb\r\na=rtcp-fb:96 transport-cc\r\na=rtcp-fb:96 ccm fir\r\na=rtcp-fb:96 nack\r\na=rtcp-fb:96 nack pli\r\na=rtpmap:97 rtx/90000\r\na=fmtp:97 apt=96\r\n",
                        "type": "offer"
                    }
                }
                
                await phone_ws.send(json.dumps(offer_message))
                self.log_message("sent", "phone", offer_message)
                
                # Step 2: Laptop should receive the offer
                logger.info("Step 2: Waiting for laptop to receive offer...")
                try:
                    laptop_response = await asyncio.wait_for(laptop_ws.recv(), timeout=10.0)
                    laptop_data = json.loads(laptop_response)
                    self.log_message("received", "laptop", laptop_data)
                    
                    if laptop_data.get("type") == "offer":
                        logger.info("✓ Laptop received WebRTC offer successfully")
                        logger.info(f"  - Sender ID: {laptop_data.get('sender_id')}")
                        logger.info(f"  - SDP Type: {laptop_data.get('data', {}).get('type')}")
                    else:
                        logger.error(f"✗ Expected offer, got: {laptop_data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ CRITICAL: Laptop did not receive offer within 10 seconds")
                    logger.error("  This indicates signaling is not working properly")
                    return False
                
                # Step 3: Laptop sends answer back
                logger.info("Step 3: Laptop sending WebRTC answer...")
                answer_message = {
                    "type": "answer",
                    "data": {
                        "sdp": "v=0\r\no=- 1234567890 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96 97 98 99 100 101 102 121 127 120 125 107 108 109 124 119 123 118 114 115 116\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:abcd\r\na=ice-pwd:efghijklmnopqrstuvwxyz123456\r\na=ice-options:trickle\r\na=fingerprint:sha-256 AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99\r\na=setup:active\r\na=mid:0\r\na=sendrecv\r\na=rtcp-mux\r\na=rtcp-rsize\r\na=rtpmap:96 VP8/90000\r\n",
                        "type": "answer"
                    }
                }
                
                await laptop_ws.send(json.dumps(answer_message))
                self.log_message("sent", "laptop", answer_message)
                
                # Step 4: Phone should receive the answer
                logger.info("Step 4: Waiting for phone to receive answer...")
                try:
                    phone_response = await asyncio.wait_for(phone_ws.recv(), timeout=10.0)
                    phone_data = json.loads(phone_response)
                    self.log_message("received", "phone", phone_data)
                    
                    if phone_data.get("type") == "answer":
                        logger.info("✓ Phone received WebRTC answer successfully")
                        logger.info(f"  - Sender ID: {phone_data.get('sender_id')}")
                        logger.info(f"  - SDP Type: {phone_data.get('data', {}).get('type')}")
                    else:
                        logger.error(f"✗ Expected answer, got: {phone_data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ CRITICAL: Phone did not receive answer within 10 seconds")
                    return False
                
                # Step 5: Test ICE candidate exchange
                logger.info("Step 5: Testing ICE candidate exchange...")
                
                # Phone sends ICE candidate
                ice_candidate_message = {
                    "type": "ice_candidate",
                    "data": {
                        "candidate": "candidate:842163049 1 udp 1677729535 192.168.1.100 54400 typ srflx raddr 192.168.1.100 rport 54400 generation 0 ufrag 4ZcD network-cost 999",
                        "sdpMLineIndex": 0,
                        "sdpMid": "0"
                    }
                }
                
                await phone_ws.send(json.dumps(ice_candidate_message))
                self.log_message("sent", "phone", ice_candidate_message)
                
                # Laptop should receive ICE candidate
                try:
                    laptop_ice_response = await asyncio.wait_for(laptop_ws.recv(), timeout=5.0)
                    laptop_ice_data = json.loads(laptop_ice_response)
                    self.log_message("received", "laptop", laptop_ice_data)
                    
                    if laptop_ice_data.get("type") == "ice_candidate":
                        logger.info("✓ Laptop received ICE candidate successfully")
                        logger.info(f"  - Candidate: {laptop_ice_data.get('data', {}).get('candidate', '')[:50]}...")
                        
                        # Send ICE candidate back from laptop
                        laptop_ice_message = {
                            "type": "ice_candidate",
                            "data": {
                                "candidate": "candidate:987654321 1 udp 1677729535 10.0.0.50 45678 typ host generation 0 ufrag abcd network-cost 50",
                                "sdpMLineIndex": 0,
                                "sdpMid": "0"
                            }
                        }
                        
                        await laptop_ws.send(json.dumps(laptop_ice_message))
                        self.log_message("sent", "laptop", laptop_ice_message)
                        
                        # Phone should receive laptop's ICE candidate
                        try:
                            phone_ice_response = await asyncio.wait_for(phone_ws.recv(), timeout=5.0)
                            phone_ice_data = json.loads(phone_ice_response)
                            self.log_message("received", "phone", phone_ice_data)
                            
                            if phone_ice_data.get("type") == "ice_candidate":
                                logger.info("✓ Phone received ICE candidate from laptop")
                                logger.info("✅ COMPLETE WebRTC signaling flow successful!")
                                return True
                            else:
                                logger.error(f"✗ Expected ice_candidate, got: {phone_ice_data.get('type')}")
                                return False
                                
                        except asyncio.TimeoutError:
                            logger.error("✗ Phone did not receive ICE candidate from laptop")
                            return False
                            
                    else:
                        logger.error(f"✗ Expected ice_candidate, got: {laptop_ice_data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Laptop did not receive ICE candidate")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ WebRTC signaling flow test failed: {e}")
            return False
    
    async def test_detection_frame_processing(self) -> bool:
        """Test detection frame processing through WebSocket"""
        logger.info("=" * 60)
        logger.info("TEST 4: Detection Frame Processing via WebSocket")
        logger.info("=" * 60)
        
        test_room_id = f"debug_room_{uuid.uuid4().hex[:8]}"
        ws_url = f"{WS_BASE}/ws/{test_room_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                logger.info("✓ Connected for detection frame testing")
                
                # Create a simple test image (base64 encoded)
                import base64
                from PIL import Image
                import io
                
                # Create test image
                image = Image.new('RGB', (300, 300), color='blue')
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG')
                image_data = base64.b64encode(buffer.getvalue()).decode()
                test_image_b64 = f"data:image/jpeg;base64,{image_data}"
                
                # Send detection frame
                frame_id = str(uuid.uuid4())
                detection_message = {
                    "type": "detection_frame",
                    "frame_id": frame_id,
                    "frame_data": test_image_b64,
                    "capture_ts": time.time()
                }
                
                logger.info("Sending detection frame...")
                await websocket.send(json.dumps(detection_message))
                self.log_message("sent", "client", detection_message)
                
                # Wait for detection result
                try:
                    result = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                    result_data = json.loads(result)
                    self.log_message("received", "client", result_data)
                    
                    if result_data.get("type") == "detection_result":
                        logger.info("✓ Detection result received successfully")
                        logger.info(f"  - Frame ID: {result_data.get('frame_id')}")
                        logger.info(f"  - Detections: {len(result_data.get('detections', []))}")
                        
                        # Calculate processing time
                        recv_ts = result_data.get('recv_ts', 0)
                        inference_ts = result_data.get('inference_ts', 0)
                        processing_time = (inference_ts - recv_ts) * 1000
                        logger.info(f"  - Processing time: {processing_time:.2f}ms")
                        
                        return True
                    elif result_data.get("type") == "detection_error":
                        logger.error(f"✗ Detection error: {result_data.get('error')}")
                        return False
                    else:
                        logger.error(f"✗ Unexpected response type: {result_data.get('type')}")
                        return False
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Timeout waiting for detection result")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Detection frame processing test failed: {e}")
            return False
    
    async def test_multiple_clients_signaling(self) -> bool:
        """Test signaling with multiple clients in the same room"""
        logger.info("=" * 60)
        logger.info("TEST 5: Multiple Clients Signaling")
        logger.info("=" * 60)
        
        test_room_id = f"debug_room_{uuid.uuid4().hex[:8]}"
        ws_url = f"{WS_BASE}/ws/{test_room_id}"
        
        try:
            # Connect 3 clients to simulate a multi-user scenario
            async with websockets.connect(ws_url) as ws1, \
                       websockets.connect(ws_url) as ws2, \
                       websockets.connect(ws_url) as ws3:
                
                logger.info("✓ Three clients connected to the same room")
                
                # Wait for connections to stabilize
                await asyncio.sleep(1)
                
                # Clear initial messages
                for ws in [ws1, ws2, ws3]:
                    try:
                        while True:
                            await asyncio.wait_for(ws.recv(), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass
                
                # Client 1 broadcasts an offer
                broadcast_offer = {
                    "type": "offer",
                    "data": {
                        "sdp": "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
                        "type": "offer"
                    }
                }
                
                await ws1.send(json.dumps(broadcast_offer))
                self.log_message("sent", "client1", broadcast_offer)
                logger.info("Client 1 sent broadcast offer")
                
                # Both client 2 and client 3 should receive the offer
                received_count = 0
                
                # Check client 2
                try:
                    response2 = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                    data2 = json.loads(response2)
                    self.log_message("received", "client2", data2)
                    
                    if data2.get("type") == "offer":
                        logger.info("✓ Client 2 received broadcast offer")
                        received_count += 1
                    else:
                        logger.warning(f"⚠ Client 2 got unexpected message: {data2.get('type')}")
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Client 2 did not receive broadcast offer")
                
                # Check client 3
                try:
                    response3 = await asyncio.wait_for(ws3.recv(), timeout=5.0)
                    data3 = json.loads(response3)
                    self.log_message("received", "client3", data3)
                    
                    if data3.get("type") == "offer":
                        logger.info("✓ Client 3 received broadcast offer")
                        received_count += 1
                    else:
                        logger.warning(f"⚠ Client 3 got unexpected message: {data3.get('type')}")
                        
                except asyncio.TimeoutError:
                    logger.error("✗ Client 3 did not receive broadcast offer")
                
                if received_count >= 2:
                    logger.info("✅ Multiple clients signaling working correctly")
                    return True
                else:
                    logger.error(f"✗ Only {received_count}/2 clients received the broadcast")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Multiple clients signaling test failed: {e}")
            return False
    
    def print_message_log(self):
        """Print detailed message log for debugging"""
        logger.info("=" * 60)
        logger.info("DETAILED MESSAGE LOG")
        logger.info("=" * 60)
        
        for i, entry in enumerate(self.message_log):
            timestamp = entry["timestamp"]
            direction = entry["direction"]
            client = entry["client"]
            message = entry["message"]
            
            logger.info(f"[{i+1:02d}] {timestamp:.3f} | {client:>8} | {direction:>8} | {message.get('type', 'unknown'):>15} | {str(message)[:100]}...")
    
    async def run_comprehensive_debug_tests(self) -> Dict[str, bool]:
        """Run all WebRTC signaling debug tests"""
        logger.info("🔍 STARTING COMPREHENSIVE WEBRTC SIGNALING DEBUG TESTS")
        logger.info("=" * 80)
        
        tests = [
            ("WebSocket Connection", self.test_websocket_connection),
            ("Room Management", self.test_room_management),
            ("WebRTC Offer→Answer→ICE Flow", self.test_webrtc_offer_answer_flow),
            ("Detection Frame Processing", self.test_detection_frame_processing),
            ("Multiple Clients Signaling", self.test_multiple_clients_signaling)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                logger.info(f"\n🧪 Running: {test_name}")
                result = await test_func()
                results[test_name] = result
                
                status = "✅ PASSED" if result else "❌ FAILED"
                logger.info(f"Result: {status}")
                
                if not result:
                    logger.error(f"❌ CRITICAL ISSUE DETECTED in {test_name}")
                    
            except Exception as e:
                logger.error(f"❌ {test_name} failed with exception: {e}")
                results[test_name] = False
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("🔍 WEBRTC SIGNALING DEBUG TEST SUMMARY")
        logger.info("=" * 80)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name:.<50} {status}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 ALL WEBRTC SIGNALING TESTS PASSED!")
            logger.info("✅ WebRTC signaling is working correctly")
        else:
            logger.error(f"❌ {total - passed} critical signaling issues detected")
            logger.error("🚨 WebRTC connections may fail due to signaling problems")
        
        # Print detailed message log for debugging
        if self.message_log:
            self.print_message_log()
        
        return results

async def main():
    """Main debug test execution"""
    debugger = WebRTCSignalingDebugger()
    results = await debugger.run_comprehensive_debug_tests()
    
    # Return results for further analysis
    return results

if __name__ == "__main__":
    results = asyncio.run(main())
    
    # Determine exit code
    all_passed = all(results.values())
    critical_failures = [name for name, passed in results.items() if not passed]
    
    if all_passed:
        print("\n✅ SUCCESS: All WebRTC signaling tests passed")
        exit(0)
    else:
        print(f"\n❌ FAILURE: Critical issues in: {', '.join(critical_failures)}")
        print("🔧 These issues need to be resolved for WebRTC to work properly")
        exit(1)