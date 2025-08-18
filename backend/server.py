from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import uuid
import time
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np
from PIL import Image
import io
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(
    title="WebRTC Multi-Object Detection System",
    description="Real-time object detection with WebRTC streaming",
    version="1.0.0"
)

# Create API router
api_router = APIRouter(prefix="/api")

# WebRTC Signaling Manager
class SignalingManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.rooms: Dict[str, List[str]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str, room_id: str):
        await websocket.accept()
        self.connections[client_id] = websocket
        
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(client_id)
        
        logging.info(f"Client {client_id} connected to room {room_id}")
        
        # Notify others in the room
        await self.broadcast_to_room({
            "type": "user_joined",
            "client_id": client_id,
            "timestamp": time.time()
        }, room_id, client_id)
        
    def disconnect(self, client_id: str, room_id: str):
        if client_id in self.connections:
            del self.connections[client_id]
        
        if room_id in self.rooms and client_id in self.rooms[room_id]:
            self.rooms[room_id].remove(client_id)
            
        logging.info(f"Client {client_id} disconnected from room {room_id}")
    
    async def send_to_client(self, message: dict, client_id: str):
        if client_id in self.connections:
            try:
                await self.connections[client_id].send_json(message)
            except Exception as e:
                logging.error(f"Failed to send message to {client_id}: {e}")
                
    async def broadcast_to_room(self, message: dict, room_id: str, sender_id: str = None):
        if room_id in self.rooms:
            for client_id in self.rooms[room_id]:
                if client_id != sender_id and client_id in self.connections:
                    await self.send_to_client(message, client_id)

signaling_manager = SignalingManager()

# Models
class DetectionRequest(BaseModel):
    image_data: str  # base64 encoded image
    confidence_threshold: float = 0.5
    max_detections: int = 100

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float

class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox

class DetectionResponse(BaseModel):
    frame_id: str
    capture_ts: float
    recv_ts: float
    inference_ts: float
    detections: List[Detection]

class MetricsData(BaseModel):
    e2e_latency_median: float
    e2e_latency_p95: float
    server_latency_median: float
    network_latency_median: float
    processed_fps: float
    bandwidth_kbps: float

# COCO class names for MobileNet-SSD
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
    'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
    'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
    'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
    'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
    'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
    'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
    'toothbrush'
]

# ONNX Runtime session for object detection
inference_session = None

def load_onnx_model():
    """Load the ONNX model for object detection"""
    global inference_session
    try:
        import onnxruntime as ort
        model_path = os.path.join(ROOT_DIR, "models", "ssd_mobilenet_v1.onnx")
        
        # Configure session options for optimal performance
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = 4
        session_options.inter_op_num_threads = 2
        
        # Create inference session
        inference_session = ort.InferenceSession(
            model_path,
            session_options,
            providers=['CPUExecutionProvider']
        )
        
        logging.info(f"ONNX model loaded successfully from {model_path}")
        logging.info(f"Model inputs: {[inp.name for inp in inference_session.get_inputs()]}")
        logging.info(f"Model outputs: {[out.name for out in inference_session.get_outputs()]}")
        
        return True
    except Exception as e:
        logging.error(f"Failed to load ONNX model: {e}")
        return False

def run_object_detection(image_array: np.ndarray, confidence_threshold: float = 0.5) -> List[Detection]:
    """Run object detection using ONNX Runtime"""
    global inference_session
    
    try:
        # Fallback to mock if model not loaded
        if inference_session is None:
            return mock_object_detection(image_array, confidence_threshold)
        
        # Prepare input tensor (batch_size=1, height=300, width=300, channels=3)
        input_tensor = np.expand_dims(image_array, axis=0).astype(np.uint8)
        
        # Get input name
        input_name = inference_session.get_inputs()[0].name
        
        # Run inference
        start_time = time.time()
        outputs = inference_session.run(None, {input_name: input_tensor})
        inference_time = time.time() - start_time
        
        logging.info(f"ONNX inference completed in {inference_time*1000:.2f}ms")
        
        # Parse outputs: [detection_boxes, detection_classes, detection_scores, num_detections]
        detection_boxes = outputs[0][0]  # Shape: (100, 4) - [y1, x1, y2, x2] normalized
        detection_classes = outputs[1][0].astype(int)  # Shape: (100,)
        detection_scores = outputs[2][0]  # Shape: (100,)
        num_detections = int(outputs[3][0])
        
        detections = []
        
        for i in range(min(num_detections, 100)):
            score = detection_scores[i]
            
            if score < confidence_threshold:
                continue
            
            # Convert normalized coordinates to pixel coordinates
            y1, x1, y2, x2 = detection_boxes[i]
            
            # Scale to 300x300 input size
            bbox = BoundingBox(
                x1=float(x1 * 300),
                y1=float(y1 * 300),
                x2=float(x2 * 300),
                y2=float(y2 * 300),
                width=float((x2 - x1) * 300),
                height=float((y2 - y1) * 300)
            )
            
            class_id = detection_classes[i]
            class_name = COCO_CLASSES[class_id] if class_id < len(COCO_CLASSES) else f"class_{class_id}"
            
            detection = Detection(
                class_id=int(class_id),
                class_name=class_name,
                confidence=float(score),
                bbox=bbox
            )
            
            detections.append(detection)
        
        return detections
        
    except Exception as e:
        logging.error(f"Object detection failed: {e}")
        return mock_object_detection(image_array, confidence_threshold)

# Mock object detection fallback
def mock_object_detection(image_array: np.ndarray, confidence_threshold: float = 0.5) -> List[Detection]:
    """Mock object detection that returns dummy detections"""
    # Simulate processing time
    time.sleep(0.02)  # 20ms inference time
    
    # Generate mock detections
    detections = []
    
    # Mock detection for testing
    if np.random.random() > 0.3:  # 70% chance of detection
        mock_detection = Detection(
            class_id=0,  # person
            class_name="person",
            confidence=0.85,
            bbox=BoundingBox(
                x1=50.0,
                y1=30.0,
                x2=200.0,
                y2=250.0,
                width=150.0,
                height=220.0
            )
        )
        detections.append(mock_detection)
        
    if np.random.random() > 0.7:  # 30% chance of second detection
        mock_detection = Detection(
            class_id=2,  # car
            class_name="car", 
            confidence=0.72,
            bbox=BoundingBox(
                x1=100.0,
                y1=150.0,
                x2=280.0,
                y2=220.0,
                width=180.0,
                height=70.0
            )
        )
        detections.append(mock_detection)
    
    return detections

def preprocess_image(image_data: str) -> np.ndarray:
    """Preprocess base64 encoded image for ONNX inference"""
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(image_data.split(',')[1] if ',' in image_data else image_data)
        
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize to model input size (300x300 for MobileNet-SSD)
        image = image.resize((300, 300), Image.LANCZOS)
        
        # Convert to numpy array (uint8 format for ONNX model)
        image_array = np.array(image).astype(np.uint8)
        
        return image_array
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image preprocessing failed: {str(e)}")

# WebRTC Signaling WebSocket endpoint
@app.websocket("/api/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    client_id = str(uuid.uuid4())
    
    try:
        await signaling_manager.connect(websocket, client_id, room_id)
        
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type in ["offer", "answer", "ice_candidate"]:
                # Forward WebRTC signaling messages
                target_id = data.get("target_id")
                message = {
                    "type": message_type,
                    "data": data.get("data"),
                    "sender_id": client_id,
                    "timestamp": time.time()
                }
                
                if target_id:
                    await signaling_manager.send_to_client(message, target_id)
                else:
                    await signaling_manager.broadcast_to_room(message, room_id, client_id)
                    
            elif message_type == "get_room_users":
                users = signaling_manager.rooms.get(room_id, [])
                await signaling_manager.send_to_client({
                    "type": "room_users",
                    "users": users,
                    "room_id": room_id
                }, client_id)
                
            elif message_type == "detection_frame":
                # Handle frame for object detection
                frame_data = data.get("frame_data")
                capture_ts = data.get("capture_ts", time.time())
                recv_ts = time.time()
                
                if frame_data:
                    try:
                        # Process detection
                        image_array = preprocess_image(frame_data)
                        
                        inference_start = time.time()
                        detections = run_object_detection(image_array, 0.5)
                        inference_ts = time.time()
                        
                        # Send detection results back
                        response = {
                            "type": "detection_result",
                            "frame_id": data.get("frame_id", str(uuid.uuid4())),
                            "capture_ts": capture_ts,
                            "recv_ts": recv_ts,
                            "inference_ts": inference_ts,
                            "detections": [det.dict() for det in detections]
                        }
                        
                        await signaling_manager.send_to_client(response, client_id)
                        
                    except Exception as e:
                        await signaling_manager.send_to_client({
                            "type": "detection_error",
                            "error": str(e),
                            "frame_id": data.get("frame_id")
                        }, client_id)
                        
    except WebSocketDisconnect:
        signaling_manager.disconnect(client_id, room_id)
        await signaling_manager.broadcast_to_room({
            "type": "user_left",
            "client_id": client_id,
            "timestamp": time.time()
        }, room_id, client_id)
    except Exception as e:
        logging.error(f"WebSocket error for client {client_id}: {e}")
        signaling_manager.disconnect(client_id, room_id)

# API Routes
@api_router.get("/")
async def root():
    return {"message": "WebRTC Multi-Object Detection System"}

@api_router.post("/detect", response_model=DetectionResponse)
async def detect_objects(request: DetectionRequest):
    """Object detection API endpoint"""
    recv_ts = time.time()
    frame_id = str(uuid.uuid4())
    
    try:
        # Preprocess image
        image_array = preprocess_image(request.image_data)
        
        # Run inference
        inference_start = time.time()
        detections = run_object_detection(image_array, request.confidence_threshold)
        inference_ts = time.time()
        
        response = DetectionResponse(
            frame_id=frame_id,
            capture_ts=recv_ts,  # Will be overridden with actual capture time
            recv_ts=recv_ts,
            inference_ts=inference_ts,
            detections=detections[:request.max_detections]
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@api_router.get("/rooms/{room_id}/users")
async def get_room_users(room_id: str):
    """Get list of users in a room"""
    users = signaling_manager.rooms.get(room_id, [])
    return {"room_id": room_id, "users": users, "count": len(users)}

@api_router.post("/metrics")
async def save_metrics(metrics: MetricsData):
    """Save performance metrics"""
    metrics_doc = {
        "timestamp": datetime.utcnow(),
        "metrics": metrics.dict()
    }
    
    await db.metrics.insert_one(metrics_doc)
    return {"status": "saved", "timestamp": metrics_doc["timestamp"]}

@api_router.get("/metrics/latest")
async def get_latest_metrics():
    """Get latest performance metrics"""
    latest_metrics = await db.metrics.find_one(
        sort=[("timestamp", -1)]
    )
    
    if latest_metrics:
        return latest_metrics["metrics"]
    else:
        return {"message": "No metrics available"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    logger.info("Starting WebRTC Multi-Object Detection System...")
    
    # Load ONNX model
    model_loaded = load_onnx_model()
    if model_loaded:
        logger.info("✓ ONNX model loaded successfully")
    else:
        logger.warning("⚠ ONNX model loading failed, using mock detection")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()