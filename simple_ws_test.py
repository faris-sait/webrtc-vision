#!/usr/bin/env python3
"""
Simple WebSocket connection test
"""

import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8001/ws/test123"
    print(f"Attempting to connect to: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket connected successfully!")
            
            # Send a test message
            await websocket.send(json.dumps({"type": "get_room_users"}))
            print("✓ Message sent")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"✓ Response received: {response}")
            
    except Exception as e:
        print(f"✗ WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())