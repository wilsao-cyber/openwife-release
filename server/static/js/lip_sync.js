// Viseme-driven lip sync for VRM models
export class LipSyncEngine {
  constructor() {
    this._frames = [];
    this._startTime = 0;
    this._isPlaying = false;
    this._currentIndex = 0;
    this._vrm = null;
    this._rafId = null;
  }

  setVrm(vrm) {
    this._vrm = vrm;
  }

  start(visemeData) {
    if (!this._vrm || !this._vrm.expressionManager) return;
    this._frames = visemeData.sort((a, b) => a.time - b.time);
    this._startTime = performance.now() / 1000;
    this._currentIndex = 0;
    this._isPlaying = true;
    this._tick();
  }

  stop() {
    this._isPlaying = false;
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    this._resetMouth();
  }

  _tick() {
    if (!this._isPlaying || !this._vrm) return;
    const elapsed = performance.now() / 1000 - this._startTime;
    while (this._currentIndex < this._frames.length - 1 &&
           this._frames[this._currentIndex + 1].time <= elapsed) {
      this._currentIndex++;
    }
    if (this._currentIndex >= this._frames.length) {
      this.stop();
      return;
    }
    const frame = this._frames[this._currentIndex];
    this._applyViseme(frame.viseme, frame.weight);
    this._rafId = requestAnimationFrame(() => this._tick());
  }

  _applyViseme(viseme, weight) {
    if (!this._vrm.expressionManager) return;
    const mouthShapes = ['aa', 'ih', 'ou', 'ee', 'oh'];
    for (const shape of mouthShapes) {
      this._vrm.expressionManager.setValue(shape, 0);
    }
    if (mouthShapes.includes(viseme)) {
      this._vrm.expressionManager.setValue(viseme, weight);
    }
  }

  _resetMouth() {
    if (!this._vrm?.expressionManager) return;
    const mouthShapes = ['aa', 'ih', 'ou', 'ee', 'oh'];
    for (const shape of mouthShapes) {
      this._vrm.expressionManager.setValue(shape, 0);
    }
  }
}
