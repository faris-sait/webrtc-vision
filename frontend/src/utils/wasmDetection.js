import * as ort from 'onnxruntime-web';

// COCO class names for object detection
const COCO_CLASSES = [
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
];

class WASMDetector {
  constructor() {
    this.session = null;
    this.isLoading = false;
    this.isLoaded = false;
  }

  async loadModel() {
    if (this.isLoaded || this.isLoading) {
      return;
    }

    this.isLoading = true;
    
    try {
      console.log('Loading ONNX model for WASM inference...');
      
      // Configure ONNX Runtime for web
      ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/';
      ort.env.wasm.numThreads = Math.min(4, navigator.hardwareConcurrency || 1);
      
      // Load the model
      const modelUrl = '/models/ssd_mobilenet_v1_web.onnx';
      this.session = await ort.InferenceSession.create(modelUrl, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all',
        enableCpuMemArena: false,
        enableMemPattern: false,
      });
      
      this.isLoaded = true;
      console.log('ONNX model loaded successfully for WASM inference');
      console.log('Model inputs:', this.session.inputNames);
      console.log('Model outputs:', this.session.outputNames);
      
    } catch (error) {
      console.error('Failed to load ONNX model for WASM:', error);
      throw error;
    } finally {
      this.isLoading = false;
    }
  }

  async detect(imageData, confidenceThreshold = 0.5) {
    if (!this.isLoaded) {
      await this.loadModel();
    }

    try {
      const startTime = performance.now();

      // Preprocess image
      const inputTensor = await this.preprocessImage(imageData);
      
      // Run inference
      const feeds = {};
      feeds[this.session.inputNames[0]] = inputTensor;
      
      const inferenceStart = performance.now();
      const results = await this.session.run(feeds);
      const inferenceEnd = performance.now();
      
      // Parse results
      const detections = this.parseDetections(results, confidenceThreshold);
      
      const endTime = performance.now();
      
      console.log(`WASM inference completed in ${(inferenceEnd - inferenceStart).toFixed(2)}ms`);
      console.log(`Total WASM processing time: ${(endTime - startTime).toFixed(2)}ms`);
      
      return {
        detections,
        inferenceTime: inferenceEnd - inferenceStart,
        totalTime: endTime - startTime
      };

    } catch (error) {
      console.error('WASM object detection failed:', error);
      throw error;
    }
  }

  async preprocessImage(imageData) {
    return new Promise((resolve, reject) => {
      try {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        
        img.onload = () => {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          
          // Resize to model input size
          canvas.width = 300;
          canvas.height = 300;
          
          // Draw and resize image
          ctx.drawImage(img, 0, 0, 300, 300);
          
          // Get image data
          const imageDataObj = ctx.getImageData(0, 0, 300, 300);
          const pixels = imageDataObj.data;
          
          // Convert to tensor format [1, 3, 300, 300]
          const tensorData = new Float32Array(1 * 3 * 300 * 300);
          
          // Normalize and transpose from RGBA to RGB tensor
          for (let i = 0; i < 300 * 300; i++) {
            tensorData[i] = pixels[i * 4] / 255.0;                    // R
            tensorData[i + 300 * 300] = pixels[i * 4 + 1] / 255.0;    // G  
            tensorData[i + 2 * 300 * 300] = pixels[i * 4 + 2] / 255.0; // B
          }
          
          const inputTensor = new ort.Tensor('float32', tensorData, [1, 3, 300, 300]);
          resolve(inputTensor);
        };
        
        img.onerror = () => {
          reject(new Error('Failed to load image for preprocessing'));
        };
        
        img.src = imageData;
      } catch (error) {
        reject(error);
      }
    });
  }

  parseDetections(results, confidenceThreshold) {
    try {
      // Get output tensors
      const boxes = results[this.session.outputNames[0]].data;      // [1, N, 4]
      const classes = results[this.session.outputNames[1]].data;    // [1, N]
      const scores = results[this.session.outputNames[2]].data;     // [1, N]
      const numDetections = results[this.session.outputNames[3]].data[0];

      const detections = [];
      
      for (let i = 0; i < Math.min(numDetections, 100); i++) {
        const score = scores[i];
        
        if (score < confidenceThreshold) {
          continue;
        }
        
        // Get bounding box coordinates (normalized)
        const y1 = boxes[i * 4];
        const x1 = boxes[i * 4 + 1];
        const y2 = boxes[i * 4 + 2];
        const x2 = boxes[i * 4 + 3];
        
        // Scale to 300x300 and create detection object
        const detection = {
          class_id: Math.floor(classes[i]),
          class_name: COCO_CLASSES[Math.floor(classes[i])] || `class_${Math.floor(classes[i])}`,
          confidence: score,
          bbox: {
            x1: x1 * 300,
            y1: y1 * 300,
            x2: x2 * 300,
            y2: y2 * 300,
            width: (x2 - x1) * 300,
            height: (y2 - y1) * 300
          }
        };
        
        detections.push(detection);
      }
      
      return detections;
    } catch (error) {
      console.error('Failed to parse detection results:', error);
      return [];
    }
  }

  dispose() {
    if (this.session) {
      this.session.release();
      this.session = null;
      this.isLoaded = false;
    }
  }
}

// Create singleton instance
const wasmDetector = new WASMDetector();

export default wasmDetector;