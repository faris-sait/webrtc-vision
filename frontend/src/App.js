import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import { QRCodeSVG } from 'qrcode.react';
import { Camera, Video, Monitor, Smartphone, Zap, BarChart3, Settings, Play, Square, AlertCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WS_URL = BACKEND_URL.replace('https:', 'wss:').replace('http:', 'ws:');

const WebRTCDetectionApp = () => {
  // State management
  const [currentView, setCurrentView] = useState('home');
  const [roomId, setRoomId] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [detectionMode, setDetectionMode] = useState('server'); // 'server' or 'wasm'
  const [isRecording, setIsRecording] = useState(false);
  const [metrics, setMetrics] = useState({
    fps: 0,
    latency: 0,
    detectionCount: 0,
    bandwidth: 0
  });
  const [detections, setDetections] = useState([]);
  const [errors, setErrors] = useState([]);

  // Refs for video and canvas elements
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const localStreamRef = useRef(null);
  const metricsIntervalRef = useRef(null);
  const frameCountRef = useRef(0);

  // Performance tracking
  const performanceDataRef = useRef({
    frameTimestamps: [],
    latencies: [],
    detectionTimes: []
  });

  const generateRoomId = () => {
    const newRoomId = Math.random().toString(36).substring(2, 8).toUpperCase();
    setRoomId(newRoomId);
    return newRoomId;
  };

  const qrCodeUrl = roomId ? `${window.location.origin}?room=${roomId}&mode=phone` : '';

  // WebSocket connection
  const connectWebSocket = useCallback((roomId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `${WS_URL}/ws/${roomId}`;
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket connected');
      
      // Request room users
      wsRef.current.send(JSON.stringify({ type: 'get_room_users' }));
    };

    wsRef.current.onmessage = async (event) => {
      const message = JSON.parse(event.data);
      console.log('WebSocket message:', message);

      switch (message.type) {
        case 'user_joined':
          console.log(`User ${message.client_id} joined`);
          break;

        case 'user_left':
          console.log(`User ${message.client_id} left`);
          break;

        case 'offer':
          await handleOffer(message);
          break;

        case 'answer':
          await handleAnswer(message);
          break;

        case 'ice_candidate':
          await handleIceCandidate(message);
          break;

        case 'detection_result':
          handleDetectionResult(message);
          break;

        case 'detection_error':
          setErrors(prev => [...prev, { timestamp: Date.now(), error: message.error }]);
          break;

        case 'room_users':
          console.log('Room users:', message.users);
          break;
      }
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
      setErrors(prev => [...prev, { timestamp: Date.now(), error: 'WebSocket connection failed' }]);
    };

    wsRef.current.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket disconnected');
    };
  }, []);

  // WebRTC setup
  const setupPeerConnection = () => {
    const peerConnection = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    });

    peerConnection.onicecandidate = (event) => {
      if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'ice_candidate',
          data: {
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex
          }
        }));
      }
    };

    peerConnection.ontrack = (event) => {
      console.log('Received remote track');
      if (remoteVideoRef.current) {
        remoteVideoRef.current.srcObject = event.streams[0];
        startObjectDetection(event.streams[0]);
      }
    };

    peerConnection.onconnectionstatechange = () => {
      console.log('Connection state:', peerConnection.connectionState);
      setConnectionStatus(peerConnection.connectionState);
    };

    return peerConnection;
  };

  const handleOffer = async (message) => {
    try {
      if (!peerConnectionRef.current) {
        peerConnectionRef.current = setupPeerConnection();
      }

      await peerConnectionRef.current.setRemoteDescription(
        new RTCSessionDescription(message.data)
      );

      const answer = await peerConnectionRef.current.createAnswer();
      await peerConnectionRef.current.setLocalDescription(answer);

      wsRef.current?.send(JSON.stringify({
        type: 'answer',
        data: {
          sdp: answer.sdp,
          type: answer.type
        },
        target_id: message.sender_id
      }));
    } catch (error) {
      console.error('Error handling offer:', error);
      setErrors(prev => [...prev, { timestamp: Date.now(), error: 'Failed to handle WebRTC offer' }]);
    }
  };

  const handleAnswer = async (message) => {
    try {
      await peerConnectionRef.current?.setRemoteDescription(
        new RTCSessionDescription(message.data)
      );
    } catch (error) {
      console.error('Error handling answer:', error);
    }
  };

  const handleIceCandidate = async (message) => {
    try {
      await peerConnectionRef.current?.addIceCandidate(
        new RTCIceCandidate(message.data)
      );
    } catch (error) {
      console.error('Error handling ICE candidate:', error);
    }
  };

  // Object detection
  const startObjectDetection = (stream) => {
    if (!canvasRef.current || !stream) return;

    const video = remoteVideoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    const processFrame = () => {
      if (!video || video.paused || video.ended) return;

      // Set canvas size to match video
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;

      // Draw video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Capture frame for detection
      const frameData = canvas.toDataURL('image/jpeg', 0.8);
      const frameId = `frame_${frameCountRef.current++}`;
      const captureTs = performance.now();

      // Send frame for detection
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'detection_frame',
          frame_id: frameId,
          frame_data: frameData,
          capture_ts: captureTs
        }));
      }

      // Continue processing
      if (isRecording) {
        requestAnimationFrame(processFrame);
      }
    };

    if (isRecording) {
      processFrame();
    }
  };

  const handleDetectionResult = (result) => {
    const now = performance.now();
    const e2eLatency = now - result.capture_ts;
    const serverLatency = result.inference_ts - result.recv_ts;

    // Update performance data
    performanceDataRef.current.latencies.push(e2eLatency);
    performanceDataRef.current.detectionTimes.push(result.inference_ts - result.recv_ts);

    // Keep only last 100 measurements
    if (performanceDataRef.current.latencies.length > 100) {
      performanceDataRef.current.latencies.shift();
      performanceDataRef.current.detectionTimes.shift();
    }

    // Update detections
    setDetections(result.detections || []);

    // Draw detections on canvas
    drawDetections(result.detections || []);

    // Update metrics
    setMetrics(prev => ({
      ...prev,
      latency: Math.round(e2eLatency),
      detectionCount: result.detections?.length || 0
    }));
  };

  const drawDetections = (detections) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    // Clear previous detections (redraw video frame)
    const video = remoteVideoRef.current;
    if (video) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    }

    // Draw bounding boxes
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 3;
    ctx.font = '16px Arial';
    ctx.fillStyle = '#00ff00';

    detections.forEach((detection) => {
      const { bbox, class_name, confidence } = detection;
      
      // Scale bounding box to canvas size
      const scaleX = canvas.width / 300; // Assuming model input is 300x300
      const scaleY = canvas.height / 300;
      
      const x = bbox.x1 * scaleX;
      const y = bbox.y1 * scaleY;
      const width = bbox.width * scaleX;
      const height = bbox.height * scaleY;

      // Draw bounding box
      ctx.strokeRect(x, y, width, height);

      // Draw label
      const label = `${class_name}: ${(confidence * 100).toFixed(1)}%`;
      const textWidth = ctx.measureText(label).width;
      
      // Label background
      ctx.fillStyle = '#00ff00';
      ctx.fillRect(x, y - 25, textWidth + 10, 25);
      
      // Label text
      ctx.fillStyle = '#000000';
      ctx.fillText(label, x + 5, y - 5);
    });
  };

  // Start local camera (for phone interface)
  const startLocalCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { 
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 }
        },
        audio: false
      });

      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
      }

      localStreamRef.current = stream;

      // Add stream to peer connection
      if (peerConnectionRef.current) {
        stream.getTracks().forEach(track => {
          peerConnectionRef.current.addTrack(track, stream);
        });

        // Create and send offer
        const offer = await peerConnectionRef.current.createOffer();
        await peerConnectionRef.current.setLocalDescription(offer);

        wsRef.current?.send(JSON.stringify({
          type: 'offer',
          data: {
            sdp: offer.sdp,
            type: offer.type
          }
        }));
      }
    } catch (error) {
      console.error('Error accessing camera:', error);
      setErrors(prev => [...prev, { timestamp: Date.now(), error: 'Failed to access camera' }]);
    }
  };

  // Metrics calculation
  useEffect(() => {
    if (isRecording) {
      metricsIntervalRef.current = setInterval(() => {
        const data = performanceDataRef.current;
        
        if (data.latencies.length > 0) {
          const avgLatency = data.latencies.reduce((a, b) => a + b, 0) / data.latencies.length;
          const fps = Math.min(30, 1000 / (avgLatency || 33)); // Estimate FPS
          
          setMetrics(prev => ({
            ...prev,
            fps: Math.round(fps * 10) / 10,
            latency: Math.round(avgLatency)
          }));
        }
      }, 1000);
    } else {
      if (metricsIntervalRef.current) {
        clearInterval(metricsIntervalRef.current);
      }
    }

    return () => {
      if (metricsIntervalRef.current) {
        clearInterval(metricsIntervalRef.current);
      }
    };
  }, [isRecording]);

  // URL parameter handling for phone interface
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const urlRoomId = urlParams.get('room');
    const mode = urlParams.get('mode');

    if (urlRoomId) {
      setRoomId(urlRoomId);
      if (mode === 'phone') {
        setCurrentView('phone');
      } else {
        setCurrentView('browser');
      }
    }
  }, []);

  // Connect when room ID changes
  useEffect(() => {
    if (roomId) {
      connectWebSocket(roomId);
      if (!peerConnectionRef.current) {
        peerConnectionRef.current = setupPeerConnection();
      }
    }
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [roomId, connectWebSocket]);

  const startSession = () => {
    if (!roomId) {
      generateRoomId();
    }
    setCurrentView('browser');
    setIsRecording(true);
  };

  const stopSession = () => {
    setIsRecording(false);
    setCurrentView('home');
    
    // Stop local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
    }
    
    // Close peer connection
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
  };

  // Render different views
  const renderHomeView = () => (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-6">
            <div className="p-4 bg-purple-600/20 rounded-2xl backdrop-blur-sm border border-purple-500/30">
              <Camera className="w-12 h-12 text-purple-400" />
            </div>
          </div>
          <h1 className="text-5xl font-bold text-white mb-4 bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
            WebRTC Object Detection
          </h1>
          <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
            Real-time multi-object detection with phone camera streaming to browser via WebRTC. 
            Advanced computer vision meets modern web technology.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-12">
          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/20">
            <Video className="w-8 h-8 text-purple-400 mb-4" />
            <h3 className="text-xl font-semibold text-white mb-3">Server Mode</h3>
            <p className="text-gray-300 mb-4">High-accuracy detection using server-side ONNX Runtime with MobileNet-SSD</p>
            <ul className="text-sm text-gray-400 space-y-1">
              <li>• CPU-optimized inference</li>
              <li>• 10-15 FPS performance</li>
              <li>• 80 COCO object classes</li>
            </ul>
          </div>

          <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/20">
            <Zap className="w-8 h-8 text-yellow-400 mb-4" />
            <h3 className="text-xl font-semibold text-white mb-3">WASM Mode</h3>
            <p className="text-gray-300 mb-4">Client-side detection with WebAssembly for privacy and low latency</p>
            <ul className="text-sm text-gray-400 space-y-1">
              <li>• Browser-based inference</li>
              <li>• No server dependency</li>
              <li>• Quantized models</li>
            </ul>
          </div>
        </div>

        <div className="text-center">
          <button
            onClick={startSession}
            className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white px-8 py-4 rounded-xl font-semibold text-lg transition-all transform hover:scale-105 shadow-lg"
          >
            <Play className="w-5 h-5 inline mr-2" />
            Start Detection Session
          </button>
        </div>
      </div>
    </div>
  );

  const renderBrowserView = () => (
    <div className="min-h-screen bg-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Monitor className="w-6 h-6 text-purple-400" />
              <h1 className="text-xl font-bold">Detection Studio</h1>
            </div>
            <div className="text-sm text-gray-400">Room: {roomId}</div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className={`px-3 py-1 rounded-full text-xs ${
              connectionStatus === 'connected' ? 'bg-green-500/20 text-green-400' :
              connectionStatus === 'error' ? 'bg-red-500/20 text-red-400' :
              'bg-yellow-500/20 text-yellow-400'
            }`}>
              {connectionStatus}
            </div>
            
            <select
              value={detectionMode}
              onChange={(e) => setDetectionMode(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-1 text-sm"
            >
              <option value="server">Server Mode</option>
              <option value="wasm">WASM Mode</option>
            </select>

            <button
              onClick={stopSession}
              className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg transition-colors"
            >
              <Square className="w-4 h-4 inline mr-1" />
              Stop
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Video Area */}
          <div className="lg:col-span-2">
            <div className="bg-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-4">Live Stream & Detection</h2>
              
              <div className="relative bg-black rounded-lg overflow-hidden aspect-video">
                {/* Remote video (from phone) */}
                <video
                  ref={remoteVideoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover"
                />
                
                {/* Detection overlay canvas */}
                <canvas
                  ref={canvasRef}
                  className="absolute top-0 left-0 w-full h-full pointer-events-none"
                />
                
                {connectionStatus !== 'connected' && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/70">
                    <div className="text-center">
                      <Smartphone className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                      <p className="text-lg text-gray-300">Waiting for phone connection...</p>
                      <p className="text-sm text-gray-500">Scan QR code with your phone</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Metrics Panel */}
            <div className="mt-6 bg-slate-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center">
                <BarChart3 className="w-5 h-5 mr-2" />
                Performance Metrics
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">{metrics.fps}</div>
                  <div className="text-sm text-gray-400">FPS</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">{metrics.latency}ms</div>
                  <div className="text-sm text-gray-400">Latency</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-400">{metrics.detectionCount}</div>
                  <div className="text-sm text-gray-400">Objects</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-yellow-400">{metrics.bandwidth}</div>
                  <div className="text-sm text-gray-400">Kbps</div>
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* QR Code */}
            <div className="bg-slate-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">Phone Connection</h3>
              {qrCodeUrl && (
                <div className="bg-white p-4 rounded-lg">
                  <QRCodeSVG
                    value={qrCodeUrl}
                    size={200}
                    className="w-full h-auto"
                  />
                </div>
              )}
              <div className="mt-4 text-sm text-gray-400">
                <p>Scan with phone camera to connect</p>
                <p className="mt-2 font-mono text-xs break-all">{qrCodeUrl}</p>
              </div>
            </div>

            {/* Detection Results */}
            <div className="bg-slate-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">Detections</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {detections.length > 0 ? detections.map((detection, idx) => (
                  <div key={idx} className="bg-slate-700 rounded-lg p-3">
                    <div className="flex justify-between items-center">
                      <span className="font-medium">{detection.class_name}</span>
                      <span className="text-sm text-green-400">
                        {(detection.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                )) : (
                  <div className="text-gray-400 text-sm text-center py-8">
                    No objects detected
                  </div>
                )}
              </div>
            </div>

            {/* Errors */}
            {errors.length > 0 && (
              <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-6">
                <h3 className="text-lg font-semibold mb-4 text-red-400 flex items-center">
                  <AlertCircle className="w-5 h-5 mr-2" />
                  Errors
                </h3>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {errors.slice(-5).map((error, idx) => (
                    <div key={idx} className="text-sm text-red-300">
                      {error.error}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const renderPhoneView = () => (
    <div className="min-h-screen bg-slate-900 text-white p-4">
      <div className="max-w-md mx-auto">
        <div className="text-center mb-6">
          <Smartphone className="w-12 h-12 text-purple-400 mx-auto mb-4" />
          <h1 className="text-2xl font-bold">Phone Camera</h1>
          <p className="text-gray-400">Room: {roomId}</p>
        </div>

        {/* Local video */}
        <div className="bg-black rounded-xl overflow-hidden aspect-video mb-6">
          <video
            ref={localVideoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
          />
        </div>

        <div className="space-y-4">
          <button
            onClick={startLocalCamera}
            className="w-full bg-purple-600 hover:bg-purple-700 py-3 rounded-lg font-semibold transition-colors"
          >
            <Camera className="w-5 h-5 inline mr-2" />
            Start Camera
          </button>

          <div className={`p-4 rounded-lg text-center ${
            connectionStatus === 'connected' ? 'bg-green-900/20 border border-green-500/30' :
            'bg-yellow-900/20 border border-yellow-500/30'
          }`}>
            <div className="font-semibold">Connection Status</div>
            <div className="text-sm opacity-75">{connectionStatus}</div>
          </div>
        </div>
      </div>
    </div>
  );

  // Main render logic
  if (currentView === 'phone') {
    return renderPhoneView();
  } else if (currentView === 'browser') {
    return renderBrowserView();
  } else {
    return renderHomeView();
  }
};

export default WebRTCDetectionApp;