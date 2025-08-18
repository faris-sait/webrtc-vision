#!/usr/bin/env python3
"""
Simulate WebRTC Signaling Flow to Test Complete Connection
"""

import asyncio
import websockets
import json
import uuid
import time

async def simulate_webrtc_peers():
    """Simulate both browser and phone connecting and exchanging WebRTC signaling"""
    room_id = "TESTROOM"
    
    # Connect browser peer
    print("🖥️  Connecting browser peer...")
    browser_ws = await websockets.connect(f"wss://732980370df48a.lhr.life/ws/{room_id}")
    print("✓ Browser connected")
    
    # Connect phone peer  
    print("📱 Connecting phone peer...")
    phone_ws = await websockets.connect(f"wss://732980370df48a.lhr.life/ws/{room_id}")
    print("✓ Phone connected")
    
    async def handle_browser_messages():
        async for message in browser_ws:
            data = json.loads(message)
            print(f"🖥️  Browser received: {data.get('type')}")
            
            if data.get('type') == 'offer':
                # Browser responds with answer
                await browser_ws.send(json.dumps({
                    "type": "answer",
                    "data": {
                        "sdp": "fake-answer-sdp",
                        "type": "answer"
                    },
                    "target_id": data.get('sender_id')
                }))
                print("🖥️  Browser sent answer")
                
    async def handle_phone_messages():
        async for message in phone_ws:
            data = json.loads(message)
            print(f"📱 Phone received: {data.get('type')}")
    
    # Start message handlers
    browser_task = asyncio.create_task(handle_browser_messages())
    phone_task = asyncio.create_task(handle_phone_messages())
    
    # Wait a moment for connections to settle
    await asyncio.sleep(1)
    
    # Phone sends offer
    print("📱 Phone sending offer...")
    await phone_ws.send(json.dumps({
        "type": "offer",
        "data": {
            "sdp": "fake-offer-sdp", 
            "type": "offer"
        }
    }))
    
    # Wait for signaling exchange
    await asyncio.sleep(2)
    
    # Send ICE candidates
    print("📱 Phone sending ICE candidate...")
    await phone_ws.send(json.dumps({
        "type": "ice_candidate",
        "data": {
            "candidate": "candidate:fake-ice-candidate",
            "sdpMid": "0",
            "sdpMLineIndex": 0
        }
    }))
    
    await asyncio.sleep(2)
    
    print("🖥️  Browser sending ICE candidate...")  
    await browser_ws.send(json.dumps({
        "type": "ice_candidate",
        "data": {
            "candidate": "candidate:fake-ice-candidate-browser",
            "sdpMid": "0", 
            "sdpMLineIndex": 0
        }
    }))
    
    # Simulate detection frame processing
    await asyncio.sleep(1)
    print("📱 Phone sending detection frame...")
    await phone_ws.send(json.dumps({
        "type": "detection_frame",
        "frame_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/",  # minimal jpeg
        "frame_id": str(uuid.uuid4()),
        "capture_ts": time.time()
    }))
    
    # Wait for processing
    await asyncio.sleep(3)
    
    # Clean up
    browser_task.cancel()
    phone_task.cancel()
    await browser_ws.close()
    await phone_ws.close()
    
    print("✅ WebRTC signaling flow simulation completed successfully!")

if __name__ == "__main__":
    asyncio.run(simulate_webrtc_peers())