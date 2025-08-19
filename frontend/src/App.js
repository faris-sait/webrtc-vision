import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import { QRCodeSVG } from 'qrcode.react';
import { Camera, Video, Monitor, Smartphone, Zap, BarChart3, Settings, Play, Square, AlertCircle } from 'lucide-react';
import wasmDetector from './utils/wasmDetection';
import FrameQueue from './utils/frameQueue';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WS_URL = BACKEND_URL.replace('https:', 'wss:').replace('http:', 'ws:');
const API_URL = BACKEND_URL;

// Debug logging
console.log('🔧 DEBUG: Environment variables');
console.log('REACT_APP_BACKEND_URL:', process.env.REACT_APP_BACKEND_URL);
console.log('BACKEND_URL:', BACKEND_URL);
console.log('WS_URL:', WS_URL);
console.log('API_URL:', API_URL);

const WebRTCDetectionApp = () => {
  // State management
  const [currentView, setCurrentView] = useState('home');
  const [roomId, setRoomId] = useState('');
  const [mode, setMode] = useState(''); // 'phone' or 'browser' or ''
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
  const frameQueueRef = useRef(null);
  const iceCandidateQueueRef = useRef([]);
  const processLoopRef = useRef(null);

  // Performance tracking
  const performanceDataRef = useRef({
    frameTimestamps: [],
    latencies: [],
    detectionTimes: [],
    wasmMetrics: {
      queueLength: 0,
      dropRate: 0,
      actualFPS: 0
    }
  });

  // HTTP Signaling fallback class
  class HTTPSignaling {
    constructor(roomId, clientId, onMessage, onStatusChange) {
      this.roomId = roomId;
      this.clientId = clientId;
      this.onMessage = onMessage;
      this.onStatusChange = onStatusChange;
      this.polling = false;
      this.pollInterval = null;
      this.connected = false;
    }

    async connect() {
      try {
        console.log('🌐 HTTP Signaling: Attempting to join room...');
        // Join room
        const response = await fetch(`${API_URL}/api/signaling/${this.roomId}/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ client_id: this.clientId })
        });
        
        console.log(`📞 HTTP Signaling: Join room response status: ${response.status}`);
        
        if (response.ok) {
          const data = await response.json();
          console.log('📞 HTTP Signaling: Join room success:', data);
          
          this.connected = true;
          this.onStatusChange('connected');
          this.startPolling();
          console.log('✅ HTTP Signaling connected successfully');
          return true;
        } else {
          const errorText = await response.text();
          console.error('❌ HTTP Signaling join room failed:', response.status, errorText);
        }
      } catch (error) {
        console.error('❌ HTTP Signaling connection failed:', error);
        this.onStatusChange('error');
        return false;
      }
      return false;
    }

    startPolling() {
      if (this.polling) return;
      
      this.polling = true;
      this.pollInterval = setInterval(async () => {
        try {
          const response = await fetch(`${API_URL}/api/signaling/${this.roomId}/messages/${this.clientId}`);
          if (response.ok) {
            const data = await response.json();
            if (data.messages && data.messages.length > 0) {
              data.messages.forEach(message => this.onMessage(message));
            }
          }
        } catch (error) {
          console.error('HTTP Signaling polling error:', error);
        }
      }, 1000); // Poll every second
    }

    async send(message) {
      try {
        const response = await fetch(`${API_URL}/api/signaling/${this.roomId}/message?client_id=${this.clientId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(message)
        });
        return response.ok;
      } catch (error) {
        console.error('HTTP Signaling send error:', error);
        return false;
      }
    }

    close() {
      this.polling = false;
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
      }
      this.connected = false;
      this.onStatusChange('disconnected');
      
      // Leave room
      if (this.clientId && this.roomId) {
        fetch(`${API_URL}/api/signaling/${this.roomId}/leave`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ client_id: this.clientId })
        }).catch(err => console.error('Error leaving room:', err));
      }
    }
  }

  // Unified signaling interface
  const signalingRef = useRef(null);
  const clientIdRef = useRef(null);

  const generateRoomId = () => {
    const newRoomId = Math.random().toString(36).substring(2, 8).toUpperCase();
    setRoomId(newRoomId);
    return newRoomId;
  };

  const qrCodeUrl = roomId ? `${window.location.origin}?room=${roomId}&mode=phone` : '';

  // Message handling for both WebSocket and HTTP signaling
  const handleSignalingMessage = async (message) => {
    console.log('Signaling message:', message);

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
        // Handle server detection result
        if (window.pendingDetections && window.pendingDetections[message.frame_id]) {
          window.pendingDetections[message.frame_id](message);
          delete window.pendingDetections[message.frame_id];
        } else {
          // Fallback for direct handling
          handleDetectionResult(message);
        }
        break;

      case 'detection_error':
        setErrors(prev => [...prev, { timestamp: Date.now(), error: message.error }]);
        break;

      case 'room_users':
        console.log('Room users:', message.users);
        break;
    }
  };

  // Unified signaling connection (WebSocket + HTTP fallback)
  const connectSignaling = useCallback(async (roomId) => {
    // Close existing connection
    if (signalingRef.current) {
      signalingRef.current.close();
      signalingRef.current = null;
    }

    // Generate client ID
    if (!clientIdRef.current) {
      clientIdRef.current = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // Try WebSocket first
    console.log('🔌 DEBUG: Attempting WebSocket connection...');
    try {
      const wsUrl = `${WS_URL}/ws/${roomId}`;
      console.log('🔌 DEBUG: Constructed wsUrl:', wsUrl);
      const ws = new WebSocket(wsUrl);
      
      // Create WebSocket wrapper
      const wsWrapper = {
        send: (message) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
            return true;
          }
          return false;
        },
        close: () => {
          ws.close();
        }
      };

      ws.onopen = () => {
        console.log('WebSocket connected successfully');
        setConnectionStatus('connected');
        signalingRef.current = wsWrapper;
        
        // Request room users
        wsWrapper.send({ type: 'get_room_users' });
        
        // Retry pending offer if available
        if (window.pendingOffer) {
          console.log('🔄 Retrying pending WebRTC offer via WebSocket...');
          if (wsWrapper.send(window.pendingOffer)) {
            console.log('✅ Pending offer sent successfully');
            delete window.pendingOffer;
          }
        }
      };

      ws.onmessage = async (event) => {
        const message = JSON.parse(event.data);
        await handleSignalingMessage(message);
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        console.log('🔄 Falling back to HTTP signaling...');
        initHTTPSignaling(roomId);
      };

      ws.onclose = () => {
        console.log('🚪 WebSocket disconnected');
        if (!signalingRef.current || signalingRef.current === wsWrapper) {
          console.log('🔄 Falling back to HTTP signaling...');
          initHTTPSignaling(roomId);
        }
      };

      // Set timeout for WebSocket connection
      setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          console.log('⏰ WebSocket timeout, falling back to HTTP signaling...');
          ws.close();
          initHTTPSignaling(roomId);
        }
      }, 3000);

    } catch (error) {
      console.error('WebSocket connection failed:', error);
      console.log('Falling back to HTTP signaling...');
      initHTTPSignaling(roomId);
    }
  }, []);

  // Initialize HTTP signaling fallback
  const initHTTPSignaling = async (roomId) => {
    console.log('🔄 Initializing HTTP signaling fallback...');
    
    const httpSignaling = new HTTPSignaling(
      roomId,
      clientIdRef.current,
      handleSignalingMessage,
      (status) => {
        console.log(`📡 HTTP Signaling status change: ${status}`);
        setConnectionStatus(status);
      }
    );

    console.log('🔗 Attempting HTTP signaling connection...');
    const connected = await httpSignaling.connect();
    if (connected) {
      signalingRef.current = httpSignaling;
      console.log('✅ HTTP signaling fallback connected successfully');
      
      // Retry pending offer if available
      if (window.pendingOffer) {
        console.log('🔄 Retrying pending WebRTC offer via HTTP signaling...');
        if (httpSignaling.send(window.pendingOffer)) {
          console.log('✅ Pending offer sent successfully via HTTP signaling');
          delete window.pendingOffer;
        }
      }
    } else {
      console.error('❌ HTTP signaling fallback failed');
      setConnectionStatus('error');
      setErrors(prev => [...prev, { timestamp: Date.now(), error: 'All signaling methods failed' }]);
    }
  };

  // Send signaling message through current connection
  const sendSignalingMessage = (message) => {
    if (signalingRef.current && signalingRef.current.send) {
      return signalingRef.current.send(message);
    }
    console.error('No signaling connection available');
    return false;
  };

  // WebSocket connection (legacy - now replaced by unified signaling)
  const connectWebSocket = useCallback((roomId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `${WS_URL}/ws/${roomId}`;
    console.log('🔌 DEBUG: Legacy WebSocket URL:', wsUrl);
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
          // Handle server detection result
          if (window.pendingDetections && window.pendingDetections[message.frame_id]) {
            window.pendingDetections[message.frame_id](message);
            delete window.pendingDetections[message.frame_id];
          } else {
            // Fallback for direct handling
            handleDetectionResult(message);
          }
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
      if (event.candidate) {
        sendSignalingMessage({
          type: 'ice_candidate',
          data: {
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex
          }
        });
      }
    };

    peerConnection.ontrack = (event) => {
      console.log('🎥🎯 DEBUG: *** ONTRACK EVENT FIRED ***');
      console.log('🎥🎯 DEBUG: Event object:', event);
      console.log('🎥🎯 DEBUG: Track kind:', event.track?.kind);
      console.log('🎥🎯 DEBUG: Track enabled:', event.track?.enabled);
      console.log('🎥🎯 DEBUG: Track readyState:', event.track?.readyState);
      console.log('🎥🎯 DEBUG: Track ID:', event.track?.id);
      console.log('🎥🎯 DEBUG: Event streams array:', event.streams);
      console.log('🎥🎯 DEBUG: Stream count:', event.streams?.length);
      
      if (event.streams && event.streams.length > 0) {
        const stream = event.streams[0];
        console.log('🎥🎯 DEBUG: Stream ID:', stream.id);
        console.log('🎥🎯 DEBUG: Stream tracks:', stream.getTracks());
        console.log('🎥🎯 DEBUG: Stream video tracks:', stream.getVideoTracks());
        console.log('🎥🎯 DEBUG: Stream audio tracks:', stream.getAudioTracks());
        
        if (remoteVideoRef.current) {
          console.log('🎥🎯 DEBUG: Setting video srcObject to received stream');
          remoteVideoRef.current.srcObject = stream;
          console.log('🎥🎯 DEBUG: Video srcObject set successfully');
          
          // Add comprehensive video event listeners for debugging
          const video = remoteVideoRef.current;
          
          video.onloadstart = () => console.log('🎥 Video: loadstart event');
          video.onloadeddata = () => console.log('🎥 Video: loadeddata event');
          video.onloadedmetadata = () => {
            console.log('🎥 Video: loadedmetadata event', {
              videoWidth: video.videoWidth,
              videoHeight: video.videoHeight,
              duration: video.duration,
              readyState: video.readyState
            });
          };
          video.oncanplay = () => {
            console.log('🎥 Video: canplay event');
          };
          video.oncanplaythrough = () => {
            console.log('🎥 Video: canplaythrough event');
          };
          video.onplay = () => {
            console.log('🎥 Video: play event - Video started playing');
          };
          video.onerror = (e) => {
            console.error('🎥 Video error event:', e);
          };
          
          // Try to play the video
          video.play().then(() => {
            console.log('🎥 Video: play() promise resolved');
          }).catch(err => {
            console.error('🎥 Video: play() promise rejected:', err);
          });
          
          // Start object detection with the received stream
          startObjectDetection(stream);
        } else {
          console.error('🎥🎯 ERROR: remoteVideoRef.current is null when ontrack fired');
        }
      } else {
        console.error('🎥🎯 ERROR: No streams in ontrack event');
      }
    };

    peerConnection.onconnectionstatechange = () => {
      const state = peerConnection.connectionState;
      console.log('🔗 Connection state changed:', state);
      setConnectionStatus(state);
      
      // Log detailed state information
      console.log('🔗 ICE connection state:', peerConnection.iceConnectionState);
      console.log('🔗 ICE gathering state:', peerConnection.iceGatheringState);
      console.log('🔗 Signaling state:', peerConnection.signalingState);
    };

    peerConnection.oniceconnectionstatechange = () => {
      console.log('🧊 ICE connection state changed:', peerConnection.iceConnectionState);
    };

    peerConnection.onicegatheringstatechange = () => {
      console.log('🧊 ICE gathering state changed:', peerConnection.iceGatheringState);
    };

    peerConnection.onsignalingstatechange = () => {
      console.log('📡 Signaling state changed:', peerConnection.signalingState);
    };

    return peerConnection;
  };

  const handleOffer = async (message) => {
    try {
      console.log('🎯 DEBUG: Handling offer from', message.sender_id);
      console.log('🎯 DEBUG: Offer SDP:', message.data);

      // Ensure peer connection exists and is properly set up
      if (!peerConnectionRef.current) {
        console.log('🎯 DEBUG: Creating new peer connection for offer handling');
        peerConnectionRef.current = setupPeerConnection();
      }

      // Log current peer connection state
      console.log('🎯 DEBUG: Peer connection state before setRemoteDescription:', peerConnectionRef.current.connectionState);
      console.log('🎯 DEBUG: Signaling state before setRemoteDescription:', peerConnectionRef.current.signalingState);

      // Set the remote description (the offer)
      console.log('🎯 DEBUG: Setting remote description...');
      await peerConnectionRef.current.setRemoteDescription(
        new RTCSessionDescription(message.data)
      );
      console.log('🎯 DEBUG: Remote description set successfully');

      // Log state after setting remote description
      console.log('🎯 DEBUG: Signaling state after setRemoteDescription:', peerConnectionRef.current.signalingState);

      // Create answer
      console.log('🎯 DEBUG: Creating answer...');
      const answer = await peerConnectionRef.current.createAnswer();
      console.log('🎯 DEBUG: Answer created:', answer);

      // Set local description
      console.log('🎯 DEBUG: Setting local description (answer)...');
      await peerConnectionRef.current.setLocalDescription(answer);
      console.log('🎯 DEBUG: Local description set successfully');
      console.log('🎯 DEBUG: Signaling state after setLocalDescription:', peerConnectionRef.current.signalingState);

      // Send the answer back
      sendSignalingMessage({
        type: 'answer',
        data: {
          sdp: answer.sdp,
          type: answer.type
        },
        target_id: message.sender_id
      });
      console.log('🎯 DEBUG: Answer sent via signaling');
      
      // Process any queued ICE candidates now that remote description is set
      await processQueuedIceCandidates();
    } catch (error) {
      console.error('❌ Error handling offer:', error);
      console.error('❌ Error details:', error.message, error.stack);
      setErrors(prev => [...prev, { timestamp: Date.now(), error: `Failed to handle WebRTC offer: ${error.message}` }]);
    }
  };

  const handleAnswer = async (message) => {
    try {
      console.log('🎯 DEBUG: Handling answer from', message.sender_id);
      console.log('🎯 DEBUG: Answer SDP:', message.data);
      console.log('🎯 DEBUG: Peer connection state before setRemoteDescription:', peerConnectionRef.current?.connectionState);
      console.log('🎯 DEBUG: Signaling state before setRemoteDescription:', peerConnectionRef.current?.signalingState);

      if (!peerConnectionRef.current) {
        console.error('❌ No peer connection available when handling answer');
        throw new Error('Peer connection not available');
      }

      await peerConnectionRef.current.setRemoteDescription(
        new RTCSessionDescription(message.data)
      );
      console.log('🎯 DEBUG: Answer set as remote description successfully');
      console.log('🎯 DEBUG: Signaling state after setRemoteDescription:', peerConnectionRef.current.signalingState);
      console.log('🎯 DEBUG: Connection state after setRemoteDescription:', peerConnectionRef.current.connectionState);
    } catch (error) {
      console.error('❌ Error handling answer:', error);
      console.error('❌ Error details:', error.message, error.stack);
      setErrors(prev => [...prev, { timestamp: Date.now(), error: `Failed to handle WebRTC answer: ${error.message}` }]);
    }
  };

  const handleIceCandidate = async (message) => {
    try {
      console.log('🧊 DEBUG: Handling ICE candidate from', message.sender_id);
      console.log('🧊 DEBUG: ICE candidate data:', message.data);
      
      if (!peerConnectionRef.current) {
        console.error('❌ No peer connection available when handling ICE candidate');
        throw new Error('Peer connection not available for ICE candidate');
      }

      console.log('🧊 DEBUG: Peer connection state:', peerConnectionRef.current.connectionState);
      console.log('🧊 DEBUG: Signaling state:', peerConnectionRef.current.signalingState);

      // Check if remote description is set
      if (!peerConnectionRef.current.remoteDescription) {
        console.log('🧊 QUEUING: Remote description not set yet, queuing ICE candidate');
        iceCandidateQueueRef.current.push(message.data);
        return;
      }

      const candidate = new RTCIceCandidate(message.data);
      await peerConnectionRef.current.addIceCandidate(candidate);
      console.log('🧊 DEBUG: ICE candidate added successfully');
    } catch (error) {
      console.error('❌ Error handling ICE candidate:', error);
      console.error('❌ Error details:', error.message, error.stack);
      setErrors(prev => [...prev, { timestamp: Date.now(), error: `Failed to handle ICE candidate: ${error.message}` }]);
    }
  };

  // Process queued ICE candidates after remote description is set
  const processQueuedIceCandidates = async () => {
    if (iceCandidateQueueRef.current.length === 0) return;
    
    console.log('🧊 PROCESSING QUEUE: Processing', iceCandidateQueueRef.current.length, 'queued ICE candidates');
    
    while (iceCandidateQueueRef.current.length > 0) {
      const candidateData = iceCandidateQueueRef.current.shift();
      try {
        const candidate = new RTCIceCandidate(candidateData);
        await peerConnectionRef.current.addIceCandidate(candidate);
        console.log('🧊 QUEUE: Successfully processed queued ICE candidate');
      } catch (error) {
        console.error('❌ Error processing queued ICE candidate:', error);
        setErrors(prev => [...prev, { timestamp: Date.now(), error: `Failed to process queued ICE candidate: ${error.message}` }]);
      }
    }
  };

  // Initialize frame queue
  const initializeFrameQueue = () => {
    if (!frameQueueRef.current) {
      frameQueueRef.current = new FrameQueue(5, 15); // Max 5 frames, target 15 FPS
    }
  };

  // WASM Detection processing function
  const processWASMDetection = async (frame) => {
    try {
      const result = await wasmDetector.detect(frame.data, 0.5);
      
      return {
        type: 'detection_result',
        frame_id: frame.id,
        capture_ts: frame.captureTimestamp,
        recv_ts: frame.queueTimestamp,
        inference_ts: performance.now(),
        detections: result.detections,
        mode: 'wasm'
      };
    } catch (error) {
      console.error('WASM detection failed:', error);
      return null;
    }
  };

  // Server detection processing function  
  const processServerDetection = async (frame) => {
    return new Promise((resolve) => {
      if (signalingRef.current) {
        // Store resolve function to call when server responds
        const frameId = frame.id;
        window.pendingDetections = window.pendingDetections || {};
        window.pendingDetections[frameId] = resolve;

        sendSignalingMessage({
          type: 'detection_frame',
          frame_id: frameId,
          frame_data: frame.data,
          capture_ts: frame.captureTimestamp
        });

        // Timeout after 5 seconds
        setTimeout(() => {
          if (window.pendingDetections && window.pendingDetections[frameId]) {
            delete window.pendingDetections[frameId];
            resolve(null);
          }
        }, 5000);
      } else {
        resolve(null);
      }
    });
  };

  // Frame processing loop
  const startFrameProcessingLoop = () => {
    if (processLoopRef.current) return;

    const processLoop = async () => {
      if (!frameQueueRef.current || !isRecording) {
        processLoopRef.current = null;
        return;
      }

      try {
        const processFunction = detectionMode === 'wasm' ? 
          processWASMDetection : processServerDetection;
        
        const result = await frameQueueRef.current.dequeue(processFunction);
        
        if (result) {
          handleDetectionResult(result);
        }

        // Update WASM metrics
        if (detectionMode === 'wasm' && frameQueueRef.current) {
          const queueMetrics = frameQueueRef.current.getMetrics();
          performanceDataRef.current.wasmMetrics = queueMetrics;
          
          // Auto-adjust FPS for WASM mode
          frameQueueRef.current.autoAdjustFPS();
        }

      } catch (error) {
        console.error('Frame processing error:', error);
      }

      // Continue processing loop
      if (isRecording) {
        processLoopRef.current = setTimeout(processLoop, 16); // ~60 FPS check
      } else {
        processLoopRef.current = null;
      }
    };

    processLoopRef.current = setTimeout(processLoop, 0);
  };

  // Object detection
  const startObjectDetection = (stream) => {
    if (!canvasRef.current || !stream) return;

    // Initialize frame queue
    initializeFrameQueue();
    
    // Start frame processing loop
    startFrameProcessingLoop();

    const video = remoteVideoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    const captureFrame = () => {
      if (!video || video.paused || video.ended || !isRecording) return;

      // Set canvas size to match video
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;

      // Draw video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Capture frame for detection
      const frameData = canvas.toDataURL('image/jpeg', 0.8);
      const captureTs = performance.now();

      // Add frame to queue (with backpressure handling)
      if (frameQueueRef.current) {
        const success = frameQueueRef.current.enqueue(frameData, captureTs);
        if (!success) {
          console.log('Frame dropped due to backpressure');
        }
      }

      // Continue capturing
      if (isRecording) {
        requestAnimationFrame(captureFrame);
      }
    };

    if (isRecording) {
      captureFrame();
    }
  };

  const handleDetectionResult = (result) => {
    const now = performance.now();
    const e2eLatency = now - result.capture_ts;
    const serverLatency = (result.inference_ts - result.recv_ts) || 0;

    // Update performance data
    performanceDataRef.current.latencies.push(e2eLatency);
    performanceDataRef.current.detectionTimes.push(serverLatency);

    // Keep only last 100 measurements
    if (performanceDataRef.current.latencies.length > 100) {
      performanceDataRef.current.latencies.shift();
      performanceDataRef.current.detectionTimes.shift();
    }

    // Update detections
    setDetections(result.detections || []);

    // Draw detections on canvas
    drawDetections(result.detections || []);

    // Update metrics with mode-specific information
    const modeMetrics = detectionMode === 'wasm' ? 
      performanceDataRef.current.wasmMetrics : {};
    
    setMetrics(prev => ({
      ...prev,
      latency: Math.round(e2eLatency),
      detectionCount: result.detections?.length || 0,
      fps: modeMetrics.actualFPS || prev.fps,
      bandwidth: result.mode === 'wasm' ? 0 : prev.bandwidth // WASM doesn't use bandwidth
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

  // Create a mock video stream for testing environments
  const createMockVideoStream = () => {
    console.log('🎬 Creating mock video stream for testing environment');
    
    try {
      // Create a canvas element to generate mock video
      const canvas = document.createElement('canvas');
      canvas.width = 640;
      canvas.height = 480;
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        throw new Error('Failed to get canvas 2D context');
      }
      
      // Draw a simple moving pattern
      let frame = 0;
      const animate = () => {
        try {
          // Clear canvas
          ctx.fillStyle = '#2563eb';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          
          // Draw moving circle
          ctx.fillStyle = '#ffffff';
          ctx.beginPath();
          const x = (Math.sin(frame * 0.02) + 1) * (canvas.width / 2);
          const y = (Math.cos(frame * 0.03) + 1) * (canvas.height / 2);
          ctx.arc(x, y, 50, 0, 2 * Math.PI);
          ctx.fill();
          
          // Draw frame counter
          ctx.fillStyle = '#ffffff';
          ctx.font = '24px Arial';
          ctx.fillText(`Mock Video - Frame ${frame}`, 20, 40);
          
          // Draw testing indicator
          ctx.fillStyle = '#ff6b6b';
          ctx.font = '16px Arial';
          ctx.fillText('Testing Mode - Mock Camera', 20, canvas.height - 30);
          
          frame++;
          
          // Continue animation
          requestAnimationFrame(animate);
        } catch (animError) {
          console.error('🎬 Animation error:', animError);
        }
      };
      
      // Start animation
      animate();
      
      // Create video stream from canvas
      const stream = canvas.captureStream(30); // 30 FPS
      console.log('🎬 ✅ Mock video stream created successfully:', stream);
      console.log('🎬 Mock stream tracks count:', stream.getTracks().length);
      console.log('🎬 Mock stream video tracks:', stream.getVideoTracks().length);
      
      // Verify stream has video tracks
      if (stream.getVideoTracks().length === 0) {
        throw new Error('Mock stream has no video tracks');
      }
      
      return stream;
    } catch (error) {
      console.error('🎬 ❌ Error creating mock video stream:', error);
      throw error;
    }
  };

  // Start local camera (for phone interface)
  const startLocalCamera = useCallback(async () => {
    try {
      console.log('📱🎯 Starting camera access...');
      
      let stream;
      try {
        // First try to get real camera
        stream = await navigator.mediaDevices.getUserMedia({
          video: { 
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 30 }
          },
          audio: false
        });
        console.log('📱✅ Real camera access successful');
      } catch (cameraError) {
        console.warn('📱⚠️ Camera access failed:', cameraError.name, cameraError.message);
        console.log('📱🎬 Falling back to mock video stream for testing...');
        
        try {
          // Create mock video stream for testing
          stream = createMockVideoStream();
          console.log('📱✅ Mock video stream created successfully as fallback');
          
          // Add user feedback about mock stream
          setErrors(prev => [...prev, { 
            timestamp: Date.now(), 
            error: 'Using mock video stream - real camera not available in testing environment' 
          }]);
        } catch (mockError) {
          console.error('📱❌ CRITICAL: Mock video stream creation failed:', mockError);
          throw new Error(`Both real camera and mock stream failed: ${cameraError.message} | ${mockError.message}`);
        }
      }

      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
        console.log('📱 Local video element srcObject set');
      }

      localStreamRef.current = stream;
      console.log('📱 Stream saved to ref');

      // Add stream to peer connection
      if (peerConnectionRef.current) {
        console.log('📱🎯 DEBUG: Starting WebRTC offer creation process');
        console.log('📱🎯 DEBUG: Peer connection state:', peerConnectionRef.current.connectionState);
        console.log('📱🎯 DEBUG: Signaling state:', peerConnectionRef.current.signalingState);
        console.log('📱 DEBUG: Adding tracks to peer connection');
        console.log('📱 DEBUG: Stream tracks:', stream.getTracks());
        
        stream.getTracks().forEach(track => {
          console.log('📱 DEBUG: Adding track:', {
            kind: track.kind,
            enabled: track.enabled,
            readyState: track.readyState,
            id: track.id
          });
          peerConnectionRef.current.addTrack(track, stream);
        });
        console.log('📱 DEBUG: All tracks added to peer connection');

        // Verify tracks were added
        const senders = peerConnectionRef.current.getSenders();
        console.log('📱🎯 DEBUG: Peer connection senders after addTrack:', senders);
        senders.forEach((sender, index) => {
          console.log(`📱🎯 DEBUG: Sender ${index}:`, {
            track: sender.track,
            trackKind: sender.track?.kind,
            trackEnabled: sender.track?.enabled,
            trackReadyState: sender.track?.readyState
          });
        });

        // Create and send offer
        console.log('📱🎯 DEBUG: Creating offer...');
        const offer = await peerConnectionRef.current.createOffer();
        console.log('📱🎯 DEBUG: Offer created:', offer);
        
        await peerConnectionRef.current.setLocalDescription(offer);
        console.log('📱🎯 DEBUG: Local description set, signaling state:', peerConnectionRef.current.signalingState);

        const offerSent = sendSignalingMessage({
          type: 'offer',
          data: {
            sdp: offer.sdp,
            type: offer.type
          }
        });
        
        if (offerSent) {
          console.log('📱🎯 ✅ DEBUG: Offer sent successfully via signaling');
          console.log('📱🎯 🚀 WebRTC negotiation initiated - waiting for browser to respond');
        } else {
          console.error('📱🎯 ❌ DEBUG: Failed to send offer via signaling - will retry when connection is available');
          
          // Store offer for retry when signaling becomes available
          console.log('📱🎯 🔄 DEBUG: Storing offer for retry mechanism');
          window.pendingOffer = {
            type: 'offer',
            data: {
              sdp: offer.sdp,
              type: offer.type
            }
          };
        }
      } else {
        console.error('📱❌ ERROR: No peer connection available when trying to add tracks');
      }
    } catch (error) {
      console.error('❌ Critical error in startLocalCamera:', error);
      setErrors(prev => [...prev, { 
        timestamp: Date.now(), 
        error: `Critical camera error: ${error.message}` 
      }]);
    }
  }, []);

  // Detection mode switching
  useEffect(() => {
    const initializeDetectionMode = async () => {
      if (detectionMode === 'wasm') {
        try {
          setErrors(prev => prev.filter(e => !e.error.includes('WASM')));
          console.log('Initializing WASM detection mode...');
          await wasmDetector.loadModel();
          console.log('WASM detection mode ready');
        } catch (error) {
          console.error('Failed to initialize WASM mode:', error);
          setErrors(prev => [...prev, { 
            timestamp: Date.now(), 
            error: `WASM initialization failed: ${error.message}` 
          }]);
        }
      }
    };

    initializeDetectionMode();
  }, [detectionMode]);

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
  const handleUrlParameters = useCallback(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const urlRoomId = urlParams.get('room');
    const urlMode = urlParams.get('mode');
    
    console.log('🔗 Processing URL parameters:', { 
      urlRoomId, 
      urlMode, 
      currentUrl: window.location.href,
      searchParams: window.location.search 
    });

    if (urlRoomId) {
      setRoomId(urlRoomId);
      setMode(urlMode || '');
      console.log('📱 Setting room ID:', urlRoomId, 'and mode:', urlMode);
      
      if (urlMode === 'phone') {
        console.log('📱 URL MODE IS PHONE - setting currentView to phone');
        setCurrentView('phone');
        // Note: Camera will auto-start when signaling connection is established
        console.log('📱 Phone interface loaded - will auto-start camera when signaling is ready');
      } else {
        console.log('📱 URL MODE IS NOT PHONE - setting currentView to browser, urlMode:', urlMode);
        setCurrentView('browser');
      }
    } else {
      console.log('🔗 No room ID in URL, staying on home page');
    }
  }, []);

  useEffect(() => {
    // Process URL parameters on initial load
    handleUrlParameters();
    
    // Listen for browser navigation changes (back/forward buttons)
    const handlePopState = () => {
      console.log('🔄 Pop state detected, re-processing URL parameters');
      handleUrlParameters();
    };
    
    window.addEventListener('popstate', handlePopState);
    
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [handleUrlParameters]);

  // Connect when room ID changes
  useEffect(() => {
    if (roomId) {
      connectSignaling(roomId);
      if (!peerConnectionRef.current) {
        peerConnectionRef.current = setupPeerConnection();
      }
    }
    
    return () => {
      if (signalingRef.current) {
        signalingRef.current.close();
      }
    };
  }, [roomId, connectSignaling]);

  // Auto-start camera for phone interface when signaling is connected
  useEffect(() => {
    // Only auto-start for phone interface
    if (mode === 'phone' && connectionStatus === 'connected' && roomId && !localStreamRef.current) {
      console.log('📱🎯 TIMING FIX: Signaling connected, auto-starting camera now...');
      
      // Small delay to ensure peer connection is fully ready
      setTimeout(() => {
        startLocalCamera();
      }, 500);
    }
  }, [connectionStatus, roomId, mode, startLocalCamera]);

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
    
    // Stop frame processing loop
    if (processLoopRef.current) {
      clearTimeout(processLoopRef.current);
      processLoopRef.current = null;
    }
    
    // Clear frame queue
    if (frameQueueRef.current) {
      frameQueueRef.current.clear();
    }
    
    // Clear pending detections
    if (window.pendingDetections) {
      window.pendingDetections = {};
    }
    
    // Stop local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
      localStreamRef.current = null;
    }
    
    // Close peer connection
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    
    // Reset metrics
    setMetrics({ fps: 0, latency: 0, detectionCount: 0, bandwidth: 0 });
    setDetections([]);
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
                Performance Metrics ({detectionMode.toUpperCase()})
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">{metrics.fps}</div>
                  <div className="text-sm text-gray-400">FPS</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">{metrics.latency}ms</div>
                  <div className="text-sm text-gray-400">E2E Latency</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-400">{metrics.detectionCount}</div>
                  <div className="text-sm text-gray-400">Objects</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-yellow-400">
                    {detectionMode === 'wasm' ? 
                      `${performanceDataRef.current.wasmMetrics.dropRate?.toFixed(1) || 0}%` : 
                      `${metrics.bandwidth}`
                    }
                  </div>
                  <div className="text-sm text-gray-400">
                    {detectionMode === 'wasm' ? 'Drop Rate' : 'Kbps'}
                  </div>
                </div>
              </div>
              
              {/* WASM-specific metrics */}
              {detectionMode === 'wasm' && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Queue Length:</span>
                      <span className="text-white">{performanceDataRef.current.wasmMetrics.queueLength || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Processed:</span>
                      <span className="text-white">{performanceDataRef.current.wasmMetrics.processedFrames || 0}</span>
                    </div>
                  </div>
                </div>
              )}
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
          <div className={`p-4 rounded-lg text-center ${
            connectionStatus === 'connected' ? 'bg-green-900/20 border border-green-500/30' :
            connectionStatus === 'disconnected' ? 'bg-red-900/20 border border-red-500/30' :
            'bg-yellow-900/20 border border-yellow-500/30'
          }`}>
            <div className="font-semibold">Connection Status</div>
            <div className="text-sm opacity-75">{connectionStatus}</div>
          </div>

          <div className="p-3 bg-slate-800 rounded-lg text-center text-sm">
            <div className="font-semibold text-blue-400 mb-1">Camera Status</div>
            <div className="text-gray-300">
              {localStreamRef.current ? 
                (localStreamRef.current.getVideoTracks().length > 0 ? 
                  '✅ Camera Active' : '❌ No Video Track') : 
                '🔄 Initializing...'}
            </div>
          </div>

          <button
            onClick={startLocalCamera}
            className="w-full bg-purple-600 hover:bg-purple-700 py-3 rounded-lg font-semibold transition-colors"
          >
            <Camera className="w-5 h-5 inline mr-2" />
            Restart Camera
          </button>

          {errors.length > 0 && (
            <div className="p-3 bg-orange-900/20 border border-orange-500/30 rounded-lg">
              <div className="font-semibold text-orange-400 text-sm mb-1">Status Messages</div>
              <div className="text-xs text-gray-300 space-y-1">
                {errors.slice(-3).map((error, idx) => (
                  <div key={idx}>{error.error}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Main render logic
  console.log('🎬 RENDERING - currentView:', currentView, 'mode:', mode, 'roomId:', roomId);
  
  if (currentView === 'phone') {
    console.log('📱 Rendering phone view');
    return renderPhoneView();
  } else if (currentView === 'browser') {
    console.log('🖥️ Rendering browser view');
    return renderBrowserView();
  } else {
    console.log('🏠 Rendering home view');
    return renderHomeView();
  }
};

export default WebRTCDetectionApp;