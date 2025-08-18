#!/usr/bin/env python3
"""
Test WebSocket connection through tunnel
"""

import asyncio
import websockets
import json

async def test_tunnel_websocket():
    uri = "wss://732980370df48a.lhr.life/ws/test123"
    print(f"Attempting to connect to: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Tunnel WebSocket connected successfully!")
            
            # Send a test message
            await websocket.send(json.dumps({"type": "get_room_users"}))
            print("✓ Message sent")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"✓ Response received: {response}")
            
            # Test WebRTC signaling
            await websocket.send(json.dumps({
                "type": "offer", 
                "data": {"sdp": "test-sdp", "type": "offer"}
            }))
            print("✓ WebRTC offer sent")
            
    except Exception as e:
        print(f"✗ Tunnel WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_tunnel_websocket())