#!/usr/bin/env python3
"""
Debug HTTP Signaling Issues
"""

import asyncio
import aiohttp
import json
import time
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://webrtc-answer-fix.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

async def debug_message_ordering():
    """Debug message ordering issues"""
    logger.info("🔍 Debugging Message Ordering...")
    
    async with aiohttp.ClientSession() as session:
        test_room_id = f"DEBUG_{uuid.uuid4().hex[:8].upper()}"
        phone_id = f"phone_{uuid.uuid4().hex[:8]}"
        browser_id = f"browser_{uuid.uuid4().hex[:8]}"
        
        # Join room
        for client_id, client_type in [(phone_id, "phone"), (browser_id, "browser")]:
            join_request = {"client_id": client_id}
            async with session.post(
                f"{API_BASE}/signaling/{test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ {client_type} joined room")
                else:
                    logger.error(f"❌ {client_type} failed to join")
                    return
        
        # Clear any existing messages
        for client_id in [phone_id, browser_id]:
            async with session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📨 {client_id[:12]} has {data['count']} pending messages")
                    for i, msg in enumerate(data['messages']):
                        logger.info(f"   Message {i+1}: {msg['type']} from {msg.get('sender_id', 'system')[:12]}")
        
        # Send WebRTC answer
        answer_message = {
            "type": "answer",
            "data": {"type": "answer", "sdp": "v=0\no=- 123 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\n"},
            "target_id": phone_id
        }
        
        async with session.post(
            f"{API_BASE}/signaling/{test_room_id}/message?client_id={browser_id}",
            json=answer_message,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                logger.info("✅ Answer sent successfully")
            else:
                logger.error(f"❌ Failed to send answer: {response.status}")
                return
        
        # Check what phone receives
        async with session.get(
            f"{API_BASE}/signaling/{test_room_id}/messages/{phone_id}"
        ) as response:
            if response.status == 200:
                data = await response.json()
                logger.info(f"📨 Phone received {data['count']} messages:")
                for i, msg in enumerate(data['messages']):
                    logger.info(f"   Message {i+1}: {msg['type']} from {msg.get('sender_id', 'system')[:12]}")
                    if msg['type'] == 'answer':
                        logger.info("   ✅ Answer message found!")
                    elif msg['type'] == 'user_joined':
                        logger.info("   ℹ️ User joined notification")
            else:
                logger.error(f"❌ Failed to poll messages: {response.status}")

async def debug_broadcast_messages():
    """Debug broadcast message issues"""
    logger.info("🔍 Debugging Broadcast Messages...")
    
    async with aiohttp.ClientSession() as session:
        test_room_id = f"BROADCAST_{uuid.uuid4().hex[:8].upper()}"
        clients = [f"client_{i}_{uuid.uuid4().hex[:6]}" for i in range(3)]
        
        # All clients join
        for client_id in clients:
            join_request = {"client_id": client_id}
            async with session.post(
                f"{API_BASE}/signaling/{test_room_id}/join",
                json=join_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ {client_id[:12]} joined")
                else:
                    logger.error(f"❌ {client_id[:12]} failed to join")
                    return
        
        # Clear existing messages for all clients
        for client_id in clients:
            async with session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📨 Cleared {data['count']} messages for {client_id[:12]}")
        
        # Send broadcast message from first client
        sender_id = clients[0]
        broadcast_message = {
            "type": "broadcast_test",
            "data": {"message": "Hello everyone!", "timestamp": time.time()},
            "target_id": None  # Broadcast
        }
        
        async with session.post(
            f"{API_BASE}/signaling/{test_room_id}/message?client_id={sender_id}",
            json=broadcast_message,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                logger.info("✅ Broadcast sent successfully")
            else:
                logger.error(f"❌ Failed to send broadcast: {response.status}")
                return
        
        # Check what each client receives
        for client_id in clients:
            async with session.get(
                f"{API_BASE}/signaling/{test_room_id}/messages/{client_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📨 {client_id[:12]} received {data['count']} messages:")
                    for i, msg in enumerate(data['messages']):
                        logger.info(f"   Message {i+1}: {msg['type']} from {msg.get('sender_id', 'system')[:12]}")
                        if msg['type'] == 'broadcast_test':
                            logger.info(f"   ✅ Broadcast received by {client_id[:12]}")
                        elif msg['type'] == 'user_joined':
                            logger.info(f"   ℹ️ User joined notification")
                else:
                    logger.error(f"❌ Failed to poll messages for {client_id[:12]}: {response.status}")

async def main():
    """Main debug function"""
    logger.info("=" * 60)
    logger.info("🐛 HTTP SIGNALING DEBUG SESSION")
    logger.info("=" * 60)
    
    await debug_message_ordering()
    logger.info("\n" + "-" * 60)
    await debug_broadcast_messages()

if __name__ == "__main__":
    asyncio.run(main())