#!/usr/bin/env python3
"""
Simple WebSocket connectivity test
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_simple():
    """Test basic WebSocket connectivity"""
    try:
        # Try external URL first
        external_url = "wss://live-object-detect.preview.emergentagent.com/ws/test_room"
        logger.info(f"Testing WebSocket connection to: {external_url}")
        
        async with websockets.connect(external_url, timeout=5) as websocket:
            logger.info("✓ WebSocket connected successfully")
            
            # Send a simple message
            await websocket.send(json.dumps({"type": "get_room_users"}))
            
            # Try to receive response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            logger.info(f"✓ Received response: {response}")
            return True
            
    except Exception as e:
        logger.error(f"✗ External WebSocket failed: {e}")
        
        # Try internal URL as fallback
        try:
            internal_url = "ws://localhost:8001/ws/test_room"
            logger.info(f"Testing internal WebSocket: {internal_url}")
            
            async with websockets.connect(internal_url, timeout=5) as websocket:
                logger.info("✓ Internal WebSocket connected successfully")
                
                await websocket.send(json.dumps({"type": "get_room_users"}))
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                logger.info(f"✓ Received response: {response}")
                return True
                
        except Exception as e2:
            logger.error(f"✗ Internal WebSocket also failed: {e2}")
            return False

async def test_error_details():
    """Test error handling with detailed response"""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        try:
            invalid_request = {
                "image_data": "invalid_base64_data",
                "confidence_threshold": 0.5
            }
            
            async with session.post(
                "https://media-track-issue.preview.emergentagent.com/api/detect",
                json=invalid_request,
                headers={"Content-Type": "application/json"}
            ) as response:
                status = response.status
                text = await response.text()
                logger.info(f"Error test - Status: {status}, Response: {text}")
                
        except Exception as e:
            logger.error(f"Error test failed: {e}")

async def main():
    logger.info("=== Simple WebSocket Test ===")
    ws_result = await test_websocket_simple()
    
    logger.info("\n=== Error Handling Test ===")
    await test_error_details()
    
    return ws_result

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"WebSocket test result: {result}")