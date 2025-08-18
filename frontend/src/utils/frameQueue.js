/**
 * Frame Queue Manager for handling backpressure and adaptive rate control
 * Implements a fixed-length queue with frame dropping and adaptive thinning
 */
class FrameQueue {
  constructor(maxSize = 5, targetFPS = 15) {
    this.maxSize = maxSize;
    this.targetFPS = targetFPS;
    this.queue = [];
    this.processing = false;
    this.lastProcessTime = 0;
    this.frameInterval = 1000 / targetFPS; // ms between frames
    this.droppedFrames = 0;
    this.processedFrames = 0;
    this.totalFrames = 0;
    
    // Adaptive rate control
    this.avgProcessingTime = 0;
    this.processingTimes = [];
    this.maxProcessingTimeHistory = 10;
    
    // Performance metrics
    this.metrics = {
      queueLength: 0,
      droppedFrames: 0,
      processedFrames: 0,
      dropRate: 0,
      avgProcessingTime: 0,
      targetFPS: targetFPS,
      actualFPS: 0
    };
  }

  /**
   * Add a frame to the queue with backpressure handling
   */
  enqueue(frameData, captureTimestamp = performance.now()) {
    this.totalFrames++;
    
    // Check if we should thin frames based on rate control
    const now = performance.now();
    const timeSinceLastProcess = now - this.lastProcessTime;
    
    // Adaptive thinning: skip frame if processing is too slow
    if (this.avgProcessingTime > this.frameInterval * 1.5) {
      // Processing is slower than target FPS, increase thinning
      if (this.totalFrames % 2 === 0) {
        this.droppedFrames++;
        this.updateMetrics();
        return false; // Frame dropped due to adaptive thinning
      }
    }
    
    // Check if minimum interval has passed
    if (timeSinceLastProcess < this.frameInterval * 0.8) {
      this.droppedFrames++;
      this.updateMetrics();
      return false; // Frame dropped due to rate limiting
    }

    const frame = {
      id: `frame_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      data: frameData,
      captureTimestamp,
      queueTimestamp: now
    };

    // If queue is full, remove oldest frame
    if (this.queue.length >= this.maxSize) {
      const droppedFrame = this.queue.shift();
      this.droppedFrames++;
      console.log(`Dropped frame due to full queue: ${droppedFrame.id}`);
    }

    this.queue.push(frame);
    this.updateMetrics();
    return true; // Frame successfully queued
  }

  /**
   * Process the next frame in the queue
   */
  async dequeue(processFunction) {
    if (this.processing || this.queue.length === 0) {
      return null;
    }

    this.processing = true;
    const frame = this.queue.shift();
    
    try {
      const processStart = performance.now();
      
      // Call the processing function (detection)
      const result = await processFunction(frame);
      
      const processEnd = performance.now();
      const processingTime = processEnd - processStart;
      
      // Update processing time statistics
      this.updateProcessingTime(processingTime);
      
      this.processedFrames++;
      this.lastProcessTime = processEnd;
      
      // Add timing information to result
      if (result) {
        result.queueLatency = processStart - frame.queueTimestamp;
        result.totalLatency = processEnd - frame.captureTimestamp;
        result.frameId = frame.id;
        result.captureTimestamp = frame.captureTimestamp;
      }
      
      this.updateMetrics();
      return result;
      
    } catch (error) {
      console.error('Error processing frame:', error);
      return null;
    } finally {
      this.processing = false;
    }
  }

  /**
   * Update processing time statistics for adaptive control
   */
  updateProcessingTime(time) {
    this.processingTimes.push(time);
    
    // Keep only recent processing times
    if (this.processingTimes.length > this.maxProcessingTimeHistory) {
      this.processingTimes.shift();
    }
    
    // Calculate average processing time
    this.avgProcessingTime = this.processingTimes.reduce((a, b) => a + b, 0) / this.processingTimes.length;
  }

  /**
   * Update performance metrics
   */
  updateMetrics() {
    this.metrics = {
      queueLength: this.queue.length,
      droppedFrames: this.droppedFrames,
      processedFrames: this.processedFrames,
      dropRate: this.totalFrames > 0 ? (this.droppedFrames / this.totalFrames) * 100 : 0,
      avgProcessingTime: this.avgProcessingTime,
      targetFPS: this.targetFPS,
      actualFPS: this.calculateActualFPS()
    };
  }

  /**
   * Calculate actual FPS based on recent processing
   */
  calculateActualFPS() {
    if (this.processingTimes.length < 2) return 0;
    
    const avgProcessingTime = this.avgProcessingTime;
    if (avgProcessingTime === 0) return 0;
    
    return Math.min(this.targetFPS, 1000 / avgProcessingTime);
  }

  /**
   * Get current performance metrics
   */
  getMetrics() {
    return { ...this.metrics };
  }

  /**
   * Clear the queue and reset metrics
   */
  clear() {
    this.queue = [];
    this.processing = false;
    this.droppedFrames = 0;
    this.processedFrames = 0;
    this.totalFrames = 0;
    this.processingTimes = [];
    this.avgProcessingTime = 0;
    this.updateMetrics();
  }

  /**
   * Adjust target FPS for adaptive rate control
   */
  setTargetFPS(fps) {
    this.targetFPS = fps;
    this.frameInterval = 1000 / fps;
    this.updateMetrics();
  }

  /**
   * Get queue status information
   */
  getStatus() {
    return {
      queueLength: this.queue.length,
      processing: this.processing,
      avgProcessingTime: this.avgProcessingTime,
      dropRate: this.metrics.dropRate,
      actualFPS: this.metrics.actualFPS
    };
  }

  /**
   * Check if system is overloaded
   */
  isOverloaded() {
    return this.avgProcessingTime > this.frameInterval * 2 || this.queue.length >= this.maxSize;
  }

  /**
   * Auto-adjust target FPS based on system performance
   */
  autoAdjustFPS() {
    if (this.processingTimes.length < 5) return;

    const maxProcessingTime = Math.max(...this.processingTimes);
    const avgProcessingTime = this.avgProcessingTime;

    // If processing is consistently slow, reduce target FPS
    if (avgProcessingTime > this.frameInterval * 1.5) {
      this.setTargetFPS(Math.max(5, this.targetFPS - 1));
      console.log(`Auto-reduced target FPS to ${this.targetFPS} due to slow processing`);
    }
    // If processing is fast and queue is often empty, increase FPS
    else if (avgProcessingTime < this.frameInterval * 0.5 && this.queue.length < 2) {
      this.setTargetFPS(Math.min(30, this.targetFPS + 1));
      console.log(`Auto-increased target FPS to ${this.targetFPS} due to fast processing`);
    }
  }
}

export default FrameQueue;