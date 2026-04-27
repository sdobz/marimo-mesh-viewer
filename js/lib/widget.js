const THREE = require("three");
const {
  OrbitControls,
} = require("three/examples/jsm/controls/OrbitControls.js");

function decodeWireArray(wire) {
  if (Array.isArray(wire)) {
    return wire;
  }
  if (!wire || typeof wire !== "object") {
    throw new Error("Invalid wire array");
  }
  if (wire.codec !== "b64") {
    throw new Error(`Unsupported codec: ${wire.codec}`);
  }

  const binary = atob(wire.buffer);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  const view = bytes.buffer;
  const dtype = wire.dtype;
  if (dtype === "float32") {
    return new Float32Array(view);
  }
  if (dtype === "uint32") {
    return new Uint32Array(view);
  }
  if (dtype === "int32") {
    return new Int32Array(view);
  }
  throw new Error(`Unsupported dtype: ${dtype}`);
}

function inferCount(shape, fallbackStride) {
  if (Array.isArray(shape) && shape.length >= 2) {
    return shape[0] * shape[1];
  }
  return fallbackStride;
}

function toColor(input) {
  if (typeof input === "number") {
    return input;
  }
  if (typeof input === "string") {
    return input;
  }
  return "#9aa0a6";
}

class MeshViewerView {
  constructor({ model, el }) {
    this.model = model;
    this.el = el;
    this.root = null;
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.controls = null;
    this.meshGroup = null;
    this.disposed = false;
    this.resizeObserver = null;
    this.listeners = [];
    this.animHandle = null;
  }

  render() {
    this.root = document.createElement("div");
    this.root.className = "mmv-root";
    this.root.style.width = this.model.get("width") || "100%";
    this.root.style.height = `${this.model.get("height") || 560}px`;

    this.el.replaceChildren(this.root);

    this._initThree();
    this._bindModel();
    this._syncScene();
  }

  dispose() {
    this.disposed = true;

    if (this.animHandle != null) {
      cancelAnimationFrame(this.animHandle);
      this.animHandle = null;
    }

    this.listeners.forEach(([eventName, callback]) => {
      this.model.off(eventName, callback);
    });
    this.listeners = [];

    if (this.controls != null) {
      this.controls.dispose();
      this.controls = null;
    }

    if (this.resizeObserver != null) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }

    if (this.renderer != null) {
      this.renderer.dispose();
      this.renderer = null;
    }

    if (this.root != null) {
      this.root.replaceChildren();
    }
  }

  _initThree() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#f5f5f5");

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1e7);
    this.camera.position.set(1.8, 1.4, 1.8);

    const ambient = new THREE.AmbientLight(0xffffff, 0.8);
    this.scene.add(ambient);

    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(4, 5, 6);
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0xffffff, 0.3);
    fill.position.set(-6, -2, 3);
    this.scene.add(fill);

    this.meshGroup = new THREE.Group();
    this.scene.add(this.meshGroup);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.renderer.domElement.className = "mmv-canvas";
    this.root.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;

    this.resizeObserver = new ResizeObserver(() => this._resize());
    this.resizeObserver.observe(this.root);
    this._resize();

    const renderLoop = () => {
      if (this.disposed) {
        return;
      }
      if (this.controls != null) {
        this.controls.update();
      }
      this.renderer.render(this.scene, this.camera);
      this.animHandle = requestAnimationFrame(renderLoop);
    };
    renderLoop();
  }

  _bindModel() {
    const onScene = () => this._syncScene();
    const onSize = () => {
      if (this.root == null) {
        return;
      }
      this.root.style.width = this.model.get("width") || "100%";
      this.root.style.height = `${this.model.get("height") || 560}px`;
      this._resize();
    };

    this.model.on("change:scene", onScene);
    this.model.on("change:width", onSize);
    this.model.on("change:height", onSize);

    this.listeners.push(["change:scene", onScene]);
    this.listeners.push(["change:width", onSize]);
    this.listeners.push(["change:height", onSize]);
  }

  _resize() {
    if (this.root == null || this.renderer == null || this.camera == null) {
      return;
    }

    const width = Math.max(10, this.root.clientWidth || 1);
    const height = Math.max(10, this.root.clientHeight || 1);

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  _syncScene() {
    if (this.meshGroup == null) {
      return;
    }

    this.meshGroup.clear();

    const state = this.model.get("scene") || {};
    const meshes = Array.isArray(state.meshes) ? state.meshes : [];

    if (meshes.length === 0) {
      this.root.setAttribute("data-empty", "true");
      if (!this.root.querySelector(".mmv-empty")) {
        const empty = document.createElement("div");
        empty.className = "mmv-empty";
        empty.textContent = "No meshes in scene payload.";
        this.root.appendChild(empty);
      }
      return;
    }

    const emptyNode = this.root.querySelector(".mmv-empty");
    if (emptyNode) {
      emptyNode.remove();
    }

    for (const meshData of meshes) {
      const geometry = new THREE.BufferGeometry();

      const vertices = decodeWireArray(meshData.vertices);
      const faces = decodeWireArray(meshData.faces);

      const vertexCount = inferCount(
        meshData.vertices.shape,
        vertices.length / 3,
      );
      const indexCount = inferCount(meshData.faces.shape, faces.length / 3);

      geometry.setAttribute(
        "position",
        new THREE.BufferAttribute(vertices, 3, false),
      );
      geometry.setIndex(new THREE.BufferAttribute(faces, 1, false));

      if (vertexCount <= 0 || indexCount <= 0) {
        continue;
      }

      geometry.computeVertexNormals();

      const m = meshData.material || {};
      const opacity = Number.isFinite(m.opacity) ? m.opacity : 1.0;

      const material = new THREE.MeshStandardMaterial({
        color: toColor(m.color),
        metalness: Number.isFinite(m.metalness) ? m.metalness : 0.1,
        roughness: Number.isFinite(m.roughness) ? m.roughness : 0.9,
        wireframe: Boolean(m.wireframe),
        transparent: opacity < 1.0,
        opacity,
        side: m.double_sided ? THREE.DoubleSide : THREE.FrontSide,
      });

      const mesh = new THREE.Mesh(geometry, material);
      if (meshData.name) {
        mesh.name = meshData.name;
      }
      this.meshGroup.add(mesh);
    }

    this._fitCamera();
  }

  _fitCamera() {
    if (
      this.meshGroup == null ||
      this.camera == null ||
      this.controls == null
    ) {
      return;
    }

    const box = new THREE.Box3().setFromObject(this.meshGroup);
    if (box.isEmpty()) {
      return;
    }

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z) * 0.5;
    const distance = Math.max(0.5, radius * 2.6);

    this.camera.position
      .copy(center)
      .add(new THREE.Vector3(distance, distance, distance));
    this.controls.target.copy(center);
    this.controls.update();
  }
}

class MeshViewerModel {
  constructor(state = {}) {
    this.state = {
      scene: state.scene || { version: 1, meshes: [] },
      width: state.width || "100%",
      height: state.height || 560,
    };
    this.callbacks = new Map();
  }

  get(key) {
    return this.state[key];
  }

  set(key, value) {
    this.state[key] = value;
    this._emit(`change:${key}`);
  }

  on(eventName, callback) {
    if (!this.callbacks.has(eventName)) {
      this.callbacks.set(eventName, new Set());
    }
    this.callbacks.get(eventName).add(callback);
  }

  off(eventName, callback) {
    const set = this.callbacks.get(eventName);
    if (!set) {
      return;
    }
    set.delete(callback);
  }

  _emit(eventName) {
    const set = this.callbacks.get(eventName);
    if (!set) {
      return;
    }
    set.forEach((callback) => callback());
  }
}

module.exports = {
  MeshViewerView,
  MeshViewerModel,
};
