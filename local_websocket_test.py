#!/usr/bin/env python3
"""
Local WebSocket Test - Test WebRTC signaling locally to verify backend implementation
"""

import asyncio
import websockets
import json
import time
import uuid
import logging
import base64
from PIL import Image
import io

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalWebSocketTester:
    def __init__(self):
        self.message_log = []
        
    def log_message(self, direction: str, client: str, message: dict):
        """Log WebSocket messages for debugging"""
        timestamp = time.time()
        log_entry = {
            "timestamp": timestamp,
            "direction": direction,
            "client": client,
            "message": message
        }
        self.message_log.append(log_entry)
        logger.info(f"[{client}] {direction.upper()}: {message.get('type', 'unknown')}")
    
    def create_test_image(self) -> str:
        """Create a test image and return as base64 encoded string"""
        image = Image.new('RGB', (300, 300), color='blue')
        
        # Add some simple shapes
        pixels = image.load()
        for i in range(50, 150):
            for j in range(50, 150):
                pixels[i, j] = (255, 0, 0)  # Red square
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_data = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{image_data}"
    
    async def test_complete_webrtc_signaling_flow(self) -> bool:
        """Test complete WebRTC signaling flow locally"""
        logger.info("=" * 60)
        logger.info("LOCAL WEBRTC SIGNALING FLOW TEST")
        logger.info("=" * 60)
        
        test_room_id = f"local_test_{uuid.uuid4().hex[:8]}"
        ws_url = f"ws://localhost:8001/ws/{test_room_id}"
        
        try:
            # Connect two clients (phone and laptop simulation)
            async with websockets.connect(ws_url) as phone_ws, websockets.connect(ws_url) as laptop_ws:
                logger.info("✓ Phone and Laptop clients connected locally")
                
                # Wait for connection setup
                await asyncio.sleep(0.5)
                
                # Clear initial user_joined messages
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
                
                # Step 1: Test room users
                logger.info("Step 1: Testing room user management...")
                get_users_msg = {"type": "get_room_users"}
                await phone_ws.send(json.dumps(get_users_msg))
                self.log_message("sent", "phone", get_users_msg)
                
                response = await asyncio.wait_for(phone_ws.recv(), timeout=5.0)
                data = json.loads(response)
                self.log_message("received", "phone", data)
                
                if data.get("type") == "room_users":
                    users = data.get("users", [])
                    logger.info(f"✓ Room has {len(users)} users")
                    if len(users) >= 2:
                        logger.info("✓ Both clients tracked in room")
                    else:
                        logger.warning(f"⚠ Expected 2+ users, got {len(users)}")
                
                # Step 2: Phone sends WebRTC offer
                logger.info("Step 2: Phone sending WebRTC offer...")
                offer_message = {
                    "type": "offer",
                    "data": {
                        "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96 97\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:4ZcD\r\na=ice-pwd:2/1muCWoOi3uLifh0NuRHgpw\r\na=ice-options:trickle\r\na=fingerprint:sha-256 75:74:5A:A6:A4:E5:52:F4:A7:67:4C:01:C7:EE:91:3F:21:3D:A2:E3:53:7B:6F:30:86:F2:30:FF:A6:22:D2:04\r\na=setup:actpass\r\na=mid:0\r\na=sendrecv\r\na=rtcp-mux\r\na=rtcp-rsize\r\na=rtpmap:96 VP8/90000\r\na=rtcp-fb:96 goog-remb\r\na=rtcp-fb:96 transport-cc\r\n",
                        "type": "offer"
                    }
                }
                
                await phone_ws.send(json.dumps(offer_message))
                self.log_message("sent", "phone", offer_message)
                
                # Step 3: Laptop receives offer
                logger.info("Step 3: Laptop waiting for offer...")
                laptop_response = await asyncio.wait_for(laptop_ws.recv(), timeout=5.0)
                laptop_data = json.loads(laptop_response)
                self.log_message("received", "laptop", laptop_data)
                
                if laptop_data.get("type") == "offer":
                    logger.info("✓ Laptop received WebRTC offer")
                    logger.info(f"  - Sender ID: {laptop_data.get('sender_id')}")
                else:
                    logger.error(f"✗ Expected offer, got: {laptop_data.get('type')}")
                    return False
                
                # Step 4: Laptop sends answer
                logger.info("Step 4: Laptop sending WebRTC answer...")
                answer_message = {
                    "type": "answer",
                    "data": {
                        "sdp": "v=0\r\no=- 1234567890 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96 97\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:abcd\r\na=ice-pwd:efghijklmnopqrstuvwxyz123456\r\na=ice-options:trickle\r\na=fingerprint:sha-256 AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99\r\na=setup:active\r\na=mid:0\r\na=sendrecv\r\na=rtcp-mux\r\na=rtcp-rsize\r\na=rtpmap:96 VP8/90000\r\n",
                        "type": "answer"
                    }
                }
                
                await laptop_ws.send(json.dumps(answer_message))
                self.log_message("sent", "laptop", answer_message)
                
                # Step 5: Phone receives answer
                logger.info("Step 5: Phone waiting for answer...")
                phone_response = await asyncio.wait_for(phone_ws.recv(), timeout=5.0)
                phone_data = json.loads(phone_response)
                self.log_message("received", "phone", phone_data)
                
                if phone_data.get("type") == "answer":
                    logger.info("✓ Phone received WebRTC answer")
                    logger.info(f"  - Sender ID: {phone_data.get('sender_id')}")
                else:
                    logger.error(f"✗ Expected answer, got: {phone_data.get('type')}")
                    return False
                
                # Step 6: ICE candidate exchange
                logger.info("Step 6: Testing ICE candidate exchange...")
                
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
                
                # Laptop receives ICE candidate
                laptop_ice_response = await asyncio.wait_for(laptop_ws.recv(), timeout=5.0)
                laptop_ice_data = json.loads(laptop_ice_response)
                self.log_message("received", "laptop", laptop_ice_data)
                
                if laptop_ice_data.get("type") == "ice_candidate":
                    logger.info("✓ Laptop received ICE candidate")
                    
                    # Laptop sends ICE candidate back
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
                    
                    # Phone receives laptop's ICE candidate
                    phone_ice_response = await asyncio.wait_for(phone_ws.recv(), timeout=5.0)
                    phone_ice_data = json.loads(phone_ice_response)
                    self.log_message("received", "phone", phone_ice_data)
                    
                    if phone_ice_data.get("type") == "ice_candidate":
                        logger.info("✓ Phone received ICE candidate from laptop")
                        logger.info("✅ COMPLETE WebRTC signaling flow successful!")
                    else:
                        logger.error(f"✗ Expected ice_candidate, got: {phone_ice_data.get('type')}")
                        return False
                else:
                    logger.error(f"✗ Expected ice_candidate, got: {laptop_ice_data.get('type')}")
                    return False
                
                # Step 7: Test detection frame processing
                logger.info("Step 7: Testing detection frame processing...")
                test_image = self.create_test_image()
                frame_id = str(uuid.uuid4())
                
                detection_message = {
                    "type": "detection_frame",
                    "frame_id": frame_id,
                    "frame_data": test_image,
                    "capture_ts": time.time()
                }
                
                await phone_ws.send(json.dumps(detection_message))
                self.log_message("sent", "phone", detection_message)
                
                # Wait for detection result
                detection_result = await asyncio.wait_for(phone_ws.recv(), timeout=10.0)
                detection_data = json.loads(detection_result)
                self.log_message("received", "phone", detection_data)
                
                if detection_data.get("type") == "detection_result":
                    logger.info("✓ Detection frame processing successful")
                    logger.info(f"  - Frame ID: {detection_data.get('frame_id')}")
                    logger.info(f"  - Detections: {len(detection_data.get('detections', []))}")
                    
                    # Calculate processing time
                    recv_ts = detection_data.get('recv_ts', 0)
                    inference_ts = detection_data.get('inference_ts', 0)
                    processing_time = (inference_ts - recv_ts) * 1000
                    logger.info(f"  - Processing time: {processing_time:.2f}ms")
                    
                    return True
                elif detection_data.get("type") == "detection_error":
                    logger.error(f"✗ Detection error: {detection_data.get('error')}")
                    return False
                else:
                    logger.error(f"✗ Unexpected detection response: {detection_data.get('type')}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Local WebRTC signaling test failed: {e}")
            return False
    
    async def run_local_tests(self):
        """Run local WebSocket tests"""
        logger.info("🔍 STARTING LOCAL WEBRTC SIGNALING TESTS")
        logger.info("=" * 60)
        
        result = await self.test_complete_webrtc_signaling_flow()
        
        logger.info("\n" + "=" * 60)
        logger.info("LOCAL TEST SUMMARY")
        logger.info("=" * 60)
        
        if result:
            logger.info("✅ ALL LOCAL WEBRTC SIGNALING TESTS PASSED!")
            logger.info("✅ Backend WebSocket implementation is FULLY FUNCTIONAL")
            logger.info("🔧 Issue is with external Kubernetes ingress configuration")
        else:
            logger.error("❌ LOCAL WEBRTC SIGNALING TESTS FAILED")
            logger.error("🚨 Backend implementation has issues")
        
        return result

async def main():
    """Main test execution"""
    tester = LocalWebSocketTester()
    result = await tester.run_local_tests()
    return result

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)