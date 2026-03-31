import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { GLTFLoader } from 'three/addons/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ── State ──────────────────────────────────────────────────────────────────────
let scene, camera, renderer, controls, clock;
let currentVrm = null;
let blinkTimeoutId = null;

// ── Flutter bridge ─────────────────────────────────────────────────────────────
function sendToFlutter(type, data) {
  try {
    if (window.FlutterBridge) {
      window.FlutterBridge.postMessage(JSON.stringify({ type, data }));
    }
  } catch (e) {
    console.warn('FlutterBridge not available:', e);
  }
}

// ── Scene setup ────────────────────────────────────────────────────────────────
function initScene() {
  clock = new THREE.Clock();

  // Scene
  scene = new THREE.Scene();

  // Camera
  const aspect = window.innerWidth / window.innerHeight;
  camera = new THREE.PerspectiveCamera(30, aspect, 0.1, 100);
  camera.position.set(0, 1.3, 2.5);

  // Renderer
  renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  document.body.appendChild(renderer.domElement);

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambientLight);

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
  directionalLight.position.set(1, 2, 1);
  scene.add(directionalLight);

  // OrbitControls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.0, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.minDistance = 1;
  controls.maxDistance = 5;
  controls.update();

  // Resize handler
  window.addEventListener('resize', onResize);

  sendToFlutter('ready', {});
}

function onResize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

// ── Model loading ──────────────────────────────────────────────────────────────
function loadModel(url) {
  const loadingEl = document.getElementById('loading');
  const errorEl = document.getElementById('error');

  loadingEl.classList.remove('hidden');
  errorEl.style.display = 'none';

  // Remove previous model if any
  if (currentVrm) {
    scene.remove(currentVrm.scene);
    currentVrm = null;
  }
  stopBlink();

  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));

  loader.load(
    url,
    (gltf) => {
      const vrm = gltf.userData.vrm;
      if (!vrm) {
        showError('Loaded file does not contain VRM data.');
        return;
      }

      // Handle VRM 0.x orientation
      VRMUtils.rotateVRM0(vrm);

      currentVrm = vrm;
      scene.add(vrm.scene);

      // Auto-center camera on model
      autoCenterCamera(vrm.scene);

      // Gather expression names
      const expressionNames = vrm.expressionManager
        ? vrm.expressionManager.expressions.map((e) => e.expressionName)
        : [];

      loadingEl.classList.add('hidden');

      // Start idle animation
      startBlink();

      sendToFlutter('modelLoaded', { expressionNames });
    },
    undefined,
    (error) => {
      const msg = error && error.message ? error.message : String(error);
      showError('Failed to load model: ' + msg);
    }
  );
}

function autoCenterCamera(object) {
  const box = new THREE.Box3().setFromObject(object);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());

  // Position camera to look at model center, offset slightly above center
  const targetY = center.y;
  controls.target.set(center.x, targetY, center.z);

  // Adjust camera height to roughly face level
  camera.position.set(center.x, targetY + 0.1, center.z + size.y * 1.2);
  controls.update();
}

function showError(msg) {
  const loadingEl = document.getElementById('loading');
  const errorEl = document.getElementById('error');
  loadingEl.classList.add('hidden');
  errorEl.textContent = msg;
  errorEl.style.display = 'block';
  sendToFlutter('error', { message: msg });
}

// ── Expressions ────────────────────────────────────────────────────────────────
function setExpression(name, value) {
  if (!currentVrm || !currentVrm.expressionManager) return;

  // Reset all expressions to 0
  const expressions = currentVrm.expressionManager.expressions;
  for (const expr of expressions) {
    currentVrm.expressionManager.setValue(expr.expressionName, 0);
  }

  // Apply specified expression
  if (name) {
    currentVrm.expressionManager.setValue(name, value !== undefined ? value : 1.0);
  }
}

// ── Idle animation: breathing ──────────────────────────────────────────────────
function updateBreathing(delta) {
  if (!idleEnabled || !currentVrm || !currentVrm.humanoid) return;

  const chest = currentVrm.humanoid.getNormalizedBoneNode('chest');
  const spine = currentVrm.humanoid.getNormalizedBoneNode('spine');

  const t = clock.getElapsedTime();
  const breathOffset = Math.sin(t * 0.8) * 0.01;

  if (chest) {
    chest.rotation.x = breathOffset;
  }
  if (spine) {
    spine.rotation.x = breathOffset * 0.5;
  }
}

// ── Idle animation: blink ──────────────────────────────────────────────────────
function startBlink() {
  stopBlink();
  scheduleBlink();
}

function stopBlink() {
  if (blinkTimeoutId !== null) {
    clearTimeout(blinkTimeoutId);
    blinkTimeoutId = null;
  }
}

function scheduleBlink() {
  // Random interval between 2-6 seconds
  const interval = 2000 + Math.random() * 4000;
  blinkTimeoutId = setTimeout(() => {
    doBlink();
  }, interval);
}

function doBlink() {
  if (!currentVrm || !currentVrm.expressionManager) {
    scheduleBlink();
    return;
  }

  currentVrm.expressionManager.setValue('blink', 1.0);

  // Hold blink for 150ms then release
  setTimeout(() => {
    if (currentVrm && currentVrm.expressionManager) {
      currentVrm.expressionManager.setValue('blink', 0);
    }
    scheduleBlink();
  }, 150);
}

// ── Camera control ─────────────────────────────────────────────────────────────
function setCameraPosition(x, y, z) {
  camera.position.set(x, y, z);
  controls.update();
}

function setAutoRotate(enabled) {
  controls.autoRotate = !!enabled;
}

function setInteraction(enabled) {
  controls.enabled = !!enabled;
}

// ── Frame capture ──────────────────────────────────────────────────────────────
function captureFrame() {
  renderer.render(scene, camera);
  const dataUrl = renderer.domElement.toDataURL('image/png');
  // Strip the data:image/png;base64, prefix
  const imageData = dataUrl.replace(/^data:image\/png;base64,/, '');
  sendToFlutter('frameCaptured', { imageData });
  return imageData;
}

// ── Render loop ────────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();

  // Update VRM
  if (currentVrm) {
    updateBreathing(delta);
    currentVrm.update(delta);
  }

  controls.update();
  renderer.render(scene, camera);
}

// ── Idle animation control ────────────────────────────────────────────────────
let idleEnabled = true;

function startIdleAnimation() {
  idleEnabled = true;
  startBlink();
}

function stopIdleAnimation() {
  idleEnabled = false;
  stopBlink();
}

// ── Dispose ───────────────────────────────────────────────────────────────────
function dispose() {
  stopIdleAnimation();
  if (currentVrm) {
    VRMUtils.deepDispose(currentVrm.scene);
    scene.remove(currentVrm.scene);
    currentVrm = null;
  }
  controls.dispose();
  renderer.dispose();
}

// ── Public API ─────────────────────────────────────────────────────────────────
window.VrmController = {
  loadModel,
  setExpression,
  startIdleAnimation,
  stopIdleAnimation,
  setCameraPosition,
  setAutoRotate,
  setInteraction,
  captureFrame,
  dispose,
};

// ── Initialize ─────────────────────────────────────────────────────────────────
initScene();
animate();
