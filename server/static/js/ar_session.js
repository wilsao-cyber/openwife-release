// WebXR AR session manager for VRM viewer

export class ARSession {
  constructor(renderer, scene, camera) {
    this._renderer = renderer;
    this._scene = scene;
    this._camera = camera;
    this._session = null;
    this._isSupported = false;
    this._checkSupport();
  }

  async _checkSupport() {
    if (navigator.xr) {
      try {
        this._isSupported = await navigator.xr.isSessionSupported('immersive-ar');
      } catch (e) {
        this._isSupported = false;
      }
    }
    return this._isSupported;
  }

  get isSupported() {
    return this._isSupported;
  }

  async enter() {
    if (!this._isSupported || this._session) return false;

    try {
      this._session = await navigator.xr.requestSession('immersive-ar', {
        requiredFeatures: ['hit-test', 'local-floor'],
        optionalFeatures: ['dom-overlay'],
      });

      this._renderer.xr.enabled = true;
      await this._renderer.xr.setSession(this._session);

      this._session.addEventListener('end', () => {
        this._session = null;
        this._renderer.xr.enabled = false;
      });

      return true;
    } catch (e) {
      console.error('AR session failed:', e);
      return false;
    }
  }

  async exit() {
    if (this._session) {
      await this._session.end();
      this._session = null;
      this._renderer.xr.enabled = false;
    }
  }
}
