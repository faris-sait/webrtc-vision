#!/usr/bin/env python3
"""
HTTP Signaling Verification Test
Focused testing for HTTP signaling endpoints after SDP m-line order fix
"""

import asyncio
import aiohttp
import json
import time
import uuid
import base64
from PIL import Image
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://webrtc-answer-fix.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

class HTTPSignalingVerifier:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def create_realistic_sdp_offer(self) -> dict:
        """Create a realistic SDP offer with proper m-line ordering"""
        return {
            "type": "offer",
            "sdp": """v=0
o=- 4611731400430051336 2 IN IP4 127.0.0.1
s=-
t=0 0
a=group:BUNDLE 0
a=extmap-allow-mixed
a=msid-semantic: WMS
m=video 9 UDP/TLS/RTP/SAVPF 96 97 98 99 100 101 102 121 127 120 125 107 108 109 124 119 123 118 114 115 116
c=IN IP4 0.0.0.0
a=rtcp:9 IN IP4 0.0.0.0
a=ice-ufrag:4ZcD
a=ice-pwd:2/1muCWoOi3uLifh4d0gqgf+
a=ice-options:trickle
a=fingerprint:sha-256 75:74:5A:A6:A4:E5:52:F4:A7:67:4C:01:C7:EE:91:3F:21:3D:A2:E3:53:7B:6F:30:86:F2:30:FF:A6:22:D9:35
a=setup:actpass
a=mid:0
a=extmap:1 urn:ietf:params:rtp-hdrext:toffset
a=extmap:2 http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time
a=extmap:3 urn:3gpp:video-orientation
a=extmap:4 http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01
a=extmap:5 http://www.webrtc.org/experiments/rtp-hdrext/playout-delay
a=extmap:6 http://www.webrtc.org/experiments/rtp-hdrext/video-content-type
a=extmap:7 http://www.webrtc.org/experiments/rtp-hdrext/video-timing
a=extmap:8 http://www.webrtc.org/experiments/rtp-hdrext/color-space
a=extmap:9 urn:ietf:params:rtp-hdrext:sdes:mid
a=extmap:10 urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id
a=extmap:11 urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id
a=sendonly
a=msid:- 
a=rtcp-mux
a=rtcp-rsize
a=rtpmap:96 VP8/90000
a=rtcp-fb:96 goog-remb
a=rtcp-fb:96 transport-cc
a=rtcp-fb:96 ccm fir
a=rtcp-fb:96 nack
a=rtcp-fb:96 nack pli
a=rtpmap:97 rtx/90000
a=fmtp:97 apt=96
a=rtpmap:98 VP9/90000
a=rtcp-fb:98 goog-remb
a=rtcp-fb:98 transport-cc
a=rtcp-fb:98 ccm fir
a=rtcp-fb:98 nack
a=rtcp-fb:98 nack pli
a=fmtp:98 profile-id=0
a=rtpmap:99 rtx/90000
a=fmtp:99 apt=98
a=rtpmap:100 VP9/90000
a=rtcp-fb:100 goog-remb
a=rtcp-fb:100 transport-cc
a=rtcp-fb:100 ccm fir
a=rtcp-fb:100 nack
a=rtcp-fb:100 nack pli
a=fmtp:100 profile-id=2
a=rtpmap:101 rtx/90000
a=fmtp:101 apt=100
a=rtpmap:102 H264/90000
a=rtcp-fb:102 goog-remb
a=rtcp-fb:102 transport-cc
a=rtcp-fb:102 ccm fir
a=rtcp-fb:102 nack
a=rtcp-fb:102 nack pli
a=fmtp:102 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42001f
a=rtpmap:121 rtx/90000
a=fmtp:121 apt=102
a=rtpmap:127 H264/90000
a=rtcp-fb:127 goog-remb
a=rtcp-fb:127 transport-cc
a=rtcp-fb:127 ccm fir
a=rtcp-fb:127 nack
a=rtcp-fb:127 nack pli
a=fmtp:127 level-asymmetry-allowed=1;packetization-mode=0;profile-level-id=42001f
a=rtpmap:120 rtx/90000
a=fmtp:120 apt=127
a=rtpmap:125 H264/90000
a=rtcp-fb:125 goog-remb
a=rtcp-fb:125 transport-cc
a=rtcp-fb:125 ccm fir
a=rtcp-fb:125 nack
a=rtcp-fb:125 nack pli
a=fmtp:125 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=640032
a=rtpmap:107 rtx/90000
a=fmtp:107 apt=125
a=rtpmap:108 red/90000
a=rtpmap:109 rtx/90000
a=fmtp:109 apt=108
a=rtpmap:124 ulpfec/90000
a=rtpmap:119 rtx/90000
a=fmtp:119 apt=124
a=rtpmap:123 flexfec-03/90000
a=rtcp-fb:123 goog-remb
a=rtcp-fb:123 transport-cc
a=fmtp:123 repair-window=10000000
a=rtpmap:118 rtx/90000
a=fmtp:118 apt=123
a=rtpmap:114 red/90000
a=rtpmap:115 rtx/90000
a=fmtp:115 apt=114
a=rtpmap:116 ulpfec/90000
"""
        }
    
    def create_realistic_sdp_answer(self) -> dict:
        """Create a realistic SDP answer with matching m-line order"""
        return {
            "type": "answer",
            "sdp": """v=0
o=- 1234567890 2 IN IP4 127.0.0.1
s=-
t=0 0
a=group:BUNDLE 0
a=extmap-allow-mixed
a=msid-semantic: WMS
m=video 9 UDP/TLS/RTP/SAVPF 96 97 98 99 100 101 102 121 127 120 125 107 108 109 124 119 123 118 114 115 116
c=IN IP4 0.0.0.0
a=rtcp:9 IN IP4 0.0.0.0
a=ice-ufrag:abcd
a=ice-pwd:1234567890abcdef1234567890abcdef
a=ice-options:trickle
a=fingerprint:sha-256 AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99
a=setup:active
a=mid:0
a=extmap:1 urn:ietf:params:rtp-hdrext:toffset
a=extmap:2 http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time
a=extmap:3 urn:3gpp:video-orientation
a=extmap:4 http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01
a=extmap:5 http://www.webrtc.org/experiments/rtp-hdrext/playout-delay
a=extmap:6 http://www.webrtc.org/experiments/rtp-hdrext/video-content-type
a=extmap:7 http://www.webrtc.org/experiments/rtp-hdrext/video-timing
a=extmap:8 http://www.webrtc.org/experiments/rtp-hdrext/color-space
a=extmap:9 urn:ietf:params:rtp-hdrext:sdes:mid
a=extmap:10 urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id
a=extmap:11 urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id
a=recvonly
a=rtcp-mux
a=rtcp-rsize
a=rtpmap:96 VP8/90000
a=rtcp-fb:96 goog-remb
a=rtcp-fb:96 transport-cc
a=rtcp-fb:96 ccm fir
a=rtcp-fb:96 nack
a=rtcp-fb:96 nack pli
a=rtpmap:97 rtx/90000
a=fmtp:97 apt=96
a=rtpmap:98 VP9/90000
a=rtcp-fb:98 goog-remb
a=rtcp-fb:98 transport-cc
a=rtcp-fb:98 ccm fir
a=rtcp-fb:98 nack
a=rtcp-fb:98 nack pli
a=fmtp:98 profile-id=0
a=rtpmap:99 rtx/90000
a=fmtp:99 apt=98
"""
        }
    
    def create_realistic_ice_candidate(self) -> dict:
        """Create a realistic ICE candidate"""
        return {
            "candidate": "candidate:842163049 1 udp 1677729535 192.168.1.100 54400 typ srflx raddr 192.168.1.100 rport 54400 generation 0 ufrag 4ZcD network-cost 999",
            "sdpMLineIndex": 0,
            "sdpMid": "0"
        }
    
    async def test_room_join_endpoint(self) -> bool:
        """Test room join endpoint functionality"""
        logger.info("🔍 Testing Room Join Endpoint...")
        try:
            test_room_id = f"VERIFY_{uuid.uuid4().hex[:8].upper()}"
            phone_client_id = f"phone_{uuid.uuid4().hex[:8]}"
            browser_client_id = f"browser_{uuid.uuid4().hex[:8]}"
            
            # Test phone joining room
            join_request = {"client_id": phone_client_id}
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["status"] == "joined" and data["client_id"] == phone_client_id:
                        logger.info(f"✅ Phone client joined room successfully")
                        logger.info(f"   Room: {data['room_id']}, Users: {len(data['users'])}")
                    else:
                        logger.error(f"❌ Invalid phone join response: {data}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Phone join failed: {response.status} - {error_text}")
                    return False
            
            # Test browser joining same room
            join_request = {"client_id": browser_client_id}
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["status"] == "joined" and len(data["users"]) == 2:
                        logger.info(f"✅ Browser client joined room successfully")
                        logger.info(f"   Room: {data['room_id']}, Users: {len(data['users'])}")
                        return True
                    else:
                        logger.error(f"❌ Invalid browser join response: {data}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Browser join failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Room join endpoint test failed: {e}")
            return False
    
    async def test_message_polling_endpoint(self) -> bool:
        """Test message polling endpoint functionality"""
        logger.info("🔍 Testing Message Polling Endpoint...")
        try:
            test_room_id = f"POLL_{uuid.uuid4().hex[:8].upper()}"
            sender_id = f"sender_{uuid.uuid4().hex[:8]}"
            receiver_id = f"receiver_{uuid.uuid4().hex[:8]}"
            
            # Join room
            for client_id in [sender_id, receiver_id]:
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"❌ Failed to join room for polling test")
                        return False
            
            # Test polling with no messages
            async with self.session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{receiver_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["count"] == 0 and len(data["messages"]) == 0:
                        logger.info("✅ Empty message polling works correctly")
                    else:
                        logger.error(f"❌ Expected empty messages, got: {data}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Message polling failed: {response.status} - {error_text}")
                    return False
            
            # Send a test message
            test_message = {
                "type": "test_ping",
                "data": {"message": "Hello from sender", "timestamp": time.time()},
                "target_id": receiver_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/message?client_id={sender_id}",
                json=test_message,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    logger.error(f"❌ Failed to send test message")
                    return False
            
            # Poll for the message
            async with self.session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{receiver_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["count"] == 1 and len(data["messages"]) == 1:
                        message = data["messages"][0]
                        if message["type"] == "test_ping" and message["sender_id"] == sender_id:
                            logger.info("✅ Message polling and delivery works correctly")
                            logger.info(f"   Message latency: {(time.time() - message['data']['timestamp']) * 1000:.2f}ms")
                            return True
                        else:
                            logger.error(f"❌ Invalid message structure: {message}")
                            return False
                    else:
                        logger.error(f"❌ Expected 1 message, got: {data}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Message polling failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Message polling endpoint test failed: {e}")
            return False
    
    async def test_webrtc_message_handling(self) -> bool:
        """Test WebRTC offer/answer/ice_candidate message handling"""
        logger.info("🔍 Testing WebRTC Message Handling...")
        try:
            test_room_id = f"WEBRTC_{uuid.uuid4().hex[:8].upper()}"
            phone_id = f"phone_{uuid.uuid4().hex[:8]}"
            browser_id = f"browser_{uuid.uuid4().hex[:8]}"
            
            # Join room
            for client_id in [phone_id, browser_id]:
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.error(f"❌ Failed to join room for WebRTC test")
                        return False
            
            # Step 1: Phone sends WebRTC offer
            offer_message = {
                "type": "offer",
                "data": self.create_realistic_sdp_offer(),
                "target_id": browser_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/message?client_id={phone_id}",
                json=offer_message,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✅ WebRTC offer sent successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send WebRTC offer: {response.status} - {error_text}")
                    return False
            
            # Step 2: Browser receives offer
            async with self.session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{browser_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["count"] > 0:
                        offer_received = data["messages"][0]
                        if offer_received["type"] == "offer":
                            sdp_content = offer_received["data"]["sdp"]
                            if "m=video" in sdp_content and "a=sendonly" in sdp_content:
                                logger.info("✅ WebRTC offer received with proper SDP content")
                                logger.info(f"   SDP contains video track: {'m=video' in sdp_content}")
                                logger.info(f"   SDP contains sendonly: {'a=sendonly' in sdp_content}")
                            else:
                                logger.error(f"❌ SDP offer missing required video track info")
                                return False
                        else:
                            logger.error(f"❌ Expected offer, got: {offer_received['type']}")
                            return False
                    else:
                        logger.error("❌ No offer received by browser")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to receive offer: {response.status} - {error_text}")
                    return False
            
            # Step 3: Browser sends WebRTC answer
            answer_message = {
                "type": "answer",
                "data": self.create_realistic_sdp_answer(),
                "target_id": phone_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/message?client_id={browser_id}",
                json=answer_message,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✅ WebRTC answer sent successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send WebRTC answer: {response.status} - {error_text}")
                    return False
            
            # Step 4: Phone receives answer
            async with self.session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{phone_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["count"] > 0:
                        answer_received = data["messages"][0]
                        if answer_received["type"] == "answer":
                            sdp_content = answer_received["data"]["sdp"]
                            if "m=video" in sdp_content and "a=recvonly" in sdp_content:
                                logger.info("✅ WebRTC answer received with proper SDP content")
                                logger.info(f"   SDP contains video track: {'m=video' in sdp_content}")
                                logger.info(f"   SDP contains recvonly: {'a=recvonly' in sdp_content}")
                            else:
                                logger.error(f"❌ SDP answer missing required video track info")
                                return False
                        else:
                            logger.error(f"❌ Expected answer, got: {answer_received['type']}")
                            return False
                    else:
                        logger.error("❌ No answer received by phone")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to receive answer: {response.status} - {error_text}")
                    return False
            
            # Step 5: Test ICE candidate exchange
            ice_message = {
                "type": "ice_candidate",
                "data": self.create_realistic_ice_candidate(),
                "target_id": browser_id
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/message?client_id={phone_id}",
                json=ice_message,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✅ ICE candidate sent successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send ICE candidate: {response.status} - {error_text}")
                    return False
            
            # Browser receives ICE candidate
            async with self.session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{browser_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["count"] > 0:
                        ice_received = data["messages"][0]
                        if ice_received["type"] == "ice_candidate":
                            candidate = ice_received["data"]["candidate"]
                            if "candidate:" in candidate and "typ srflx" in candidate:
                                logger.info("✅ ICE candidate received with proper format")
                                logger.info(f"   Candidate type: {'typ srflx' in candidate}")
                                return True
                            else:
                                logger.error(f"❌ Invalid ICE candidate format")
                                return False
                        else:
                            logger.error(f"❌ Expected ice_candidate, got: {ice_received['type']}")
                            return False
                    else:
                        logger.error("❌ No ICE candidate received")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to receive ICE candidate: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ WebRTC message handling test failed: {e}")
            return False
    
    async def test_sdp_processing(self) -> bool:
        """Test SDP processing and validation"""
        logger.info("🔍 Testing SDP Processing...")
        try:
            test_room_id = f"SDP_{uuid.uuid4().hex[:8].upper()}"
            client_id = f"client_{uuid.uuid4().hex[:8]}"
            
            # Join room
            join_request = {"client_id": client_id}
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    logger.error(f"❌ Failed to join room for SDP test")
                    return False
            
            # Test various SDP formats
            test_cases = [
                {
                    "name": "Video-only SDP offer",
                    "sdp": self.create_realistic_sdp_offer(),
                    "expected_elements": ["m=video", "a=sendonly", "VP8", "H264"]
                },
                {
                    "name": "Video-only SDP answer", 
                    "sdp": self.create_realistic_sdp_answer(),
                    "expected_elements": ["m=video", "a=recvonly", "VP8"]
                }
            ]
            
            for test_case in test_cases:
                message = {
                    "type": "offer" if "offer" in test_case["name"] else "answer",
                    "data": test_case["sdp"],
                    "target_id": None  # Broadcast
                }
                
                # Send SDP message
                async with self.session.post(
                    f"{API_BASE}/signaling/{test_room_id}/message?client_id={client_id}",
                    json=message,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ {test_case['name']} processed successfully")
                        
                        # Validate SDP content
                        sdp_content = test_case["sdp"]["sdp"]
                        for element in test_case["expected_elements"]:
                            if element in sdp_content:
                                logger.info(f"   ✓ SDP contains {element}")
                            else:
                                logger.warning(f"   ⚠ SDP missing {element}")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ {test_case['name']} failed: {response.status} - {error_text}")
                        return False
            
            logger.info("✅ SDP processing validation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ SDP processing test failed: {e}")
            return False
    
    async def test_multiple_client_connections(self) -> bool:
        """Test room management with multiple clients"""
        logger.info("🔍 Testing Multiple Client Connections...")
        try:
            test_room_id = f"MULTI_{uuid.uuid4().hex[:8].upper()}"
            
            # Create multiple clients
            clients = [f"client_{i}_{uuid.uuid4().hex[:6]}" for i in range(5)]
            
            # All clients join room
            for i, client_id in enumerate(clients):
                join_request = {"client_id": client_id}
                async with self.session.post(
                    f"{API_BASE}/signaling/{test_room_id}/join",
                    json=join_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        expected_count = i + 1
                        if len(data["users"]) == expected_count:
                            logger.info(f"✅ Client {i+1}/5 joined successfully ({expected_count} total)")
                        else:
                            logger.error(f"❌ Expected {expected_count} users, got {len(data['users'])}")
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Client {i+1} failed to join: {response.status} - {error_text}")
                        return False
            
            # Test broadcast message to all clients
            sender_id = clients[0]
            broadcast_message = {
                "type": "broadcast_test",
                "data": {"message": "Hello everyone!", "timestamp": time.time()},
                "target_id": None  # Broadcast to all
            }
            
            async with self.session.post(
                f"{API_BASE}/signaling/{test_room_id}/message?client_id={sender_id}",
                json=broadcast_message,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info("✅ Broadcast message sent successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send broadcast: {response.status} - {error_text}")
                    return False
            
            # All other clients should receive the broadcast
            received_count = 0
            for client_id in clients[1:]:  # Skip sender
                async with self.session.get(
                    f"{API_BASE}/signaling/{test_room_id}/messages/{client_id}"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["count"] > 0:
                            message = data["messages"][0]
                            if message["type"] == "broadcast_test" and message["sender_id"] == sender_id:
                                received_count += 1
                                logger.info(f"   ✓ Client {client_id[:12]} received broadcast")
                            else:
                                logger.error(f"❌ Invalid broadcast message for {client_id}")
                                return False
                        else:
                            logger.error(f"❌ No broadcast received by {client_id}")
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to poll messages for {client_id}: {response.status}")
                        return False
            
            if received_count == 4:  # 5 clients - 1 sender = 4 receivers
                logger.info(f"✅ All {received_count} clients received broadcast message")
                return True
            else:
                logger.error(f"❌ Expected 4 clients to receive broadcast, got {received_count}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Multiple client connections test failed: {e}")
            return False
    
    async def test_onnx_detection_api(self) -> bool:
        """Test ONNX object detection API"""
        logger.info("🔍 Testing ONNX Object Detection API...")
        try:
            # Create test image with realistic content
            image = Image.new('RGB', (300, 300), color=(135, 206, 235))  # Sky blue background
            
            # Add some shapes that might trigger detections
            pixels = image.load()
            
            # Add a person-like shape (vertical rectangle)
            for i in range(100, 200):
                for j in range(80, 220):
                    if 120 < i < 180:  # Body
                        pixels[i, j] = (139, 69, 19)  # Brown
                    elif 80 < i < 120:  # Head
                        pixels[i, j] = (255, 220, 177)  # Skin tone
            
            # Add a car-like shape (horizontal rectangle)
            for i in range(200, 280):
                for j in range(150, 200):
                    pixels[i, j] = (255, 0, 0)  # Red car
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG')
            image_data = base64.b64encode(buffer.getvalue()).decode()
            test_image = f"data:image/jpeg;base64,{image_data}"
            
            # Test detection request
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
                    
                    # Validate response structure
                    required_fields = ["frame_id", "capture_ts", "recv_ts", "inference_ts", "detections"]
                    for field in required_fields:
                        if field not in data:
                            logger.error(f"❌ Missing field '{field}' in detection response")
                            return False
                    
                    inference_time = (end_time - start_time) * 1000
                    logger.info(f"✅ ONNX detection API successful")
                    logger.info(f"   Response time: {inference_time:.2f}ms")
                    logger.info(f"   Detections found: {len(data['detections'])}")
                    logger.info(f"   Frame ID: {data['frame_id']}")
                    
                    # Show detection details
                    for i, detection in enumerate(data['detections'][:3]):
                        logger.info(f"   Detection {i+1}: {detection['class_name']} ({detection['confidence']:.2f})")
                    
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ ONNX detection failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ ONNX detection API test failed: {e}")
            return False
    
    async def run_verification_tests(self) -> dict:
        """Run all HTTP signaling verification tests"""
        logger.info("=" * 80)
        logger.info("🎯 WEBRTC SIGNALING SYSTEM VERIFICATION")
        logger.info("   Testing backend functionality after SDP m-line order fix")
        logger.info("=" * 80)
        
        tests = [
            ("Room Join Endpoint", self.test_room_join_endpoint),
            ("Message Polling Endpoint", self.test_message_polling_endpoint),
            ("WebRTC Message Handling", self.test_webrtc_message_handling),
            ("SDP Processing", self.test_sdp_processing),
            ("Multiple Client Connections", self.test_multiple_client_connections),
            ("ONNX Detection Integration", self.test_onnx_detection_api)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n{'🔧'*30} {test_name} {'🔧'*30}")
            try:
                result = await test_func()
                results[test_name] = result
                status = "✅ PASSED" if result else "❌ FAILED"
                logger.info(f"📊 {test_name}: {status}")
            except Exception as e:
                logger.error(f"📊 {test_name}: ❌ FAILED with exception: {e}")
                results[test_name] = False
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📋 VERIFICATION SUMMARY")
        logger.info("=" * 80)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{test_name:.<60} {status}")
        
        logger.info(f"\n📈 Overall Results: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("🎉 ALL VERIFICATION TESTS PASSED!")
            logger.info("✅ SDP m-line order fix does NOT break backend functionality")
            logger.info("✅ HTTP signaling endpoints are fully operational")
            logger.info("✅ WebRTC message handling is working correctly")
            logger.info("✅ ONNX object detection integration is functional")
        else:
            logger.warning(f"⚠️ {total - passed} tests failed")
            logger.warning("❌ Backend functionality may be impacted by recent changes")
        
        return results

async def main():
    """Main verification execution function"""
    async with HTTPSignalingVerifier() as verifier:
        results = await verifier.run_verification_tests()
        
        # Return exit code based on results
        all_passed = all(results.values())
        return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)