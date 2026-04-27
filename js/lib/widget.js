const THREE = require("three");
const {
  OrbitControls,
} = require("three/examples/jsm/controls/OrbitControls.js");

function toColor(input) {
  if (typeof input === "number") {
    return input;
  }
  if (typeof input === "string") {
    return input;
  }
  return "#9aa0a6";
}

function dtypeToCtor(dtype) {
  if (dtype === "float32") {
    return Float32Array;
  }
  if (dtype === "uint16") {
    return Uint16Array;
  }
  if (dtype === "uint32") {
    return Uint32Array;
  }
  throw new Error(`Unsupported dtype: ${dtype}`);
}

async function maybeDecompress(buffer, compression) {
  if (compression !== "gzip") {
    return buffer;
  }
  if (typeof DecompressionStream === "undefined") {
    throw new Error(
      "gzip payload requires browser support for DecompressionStream",
    );
  }

  const stream = new Blob([buffer])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"));
  return await new Response(stream).arrayBuffer();
}

function parseMmv2Payload(buffer) {
  const view = new DataView(buffer);
  if (view.byteLength < 8) {
    throw new Error("Invalid MMV2 payload: too small");
  }

  const magic =
    String.fromCharCode(view.getUint8(0)) +
    String.fromCharCode(view.getUint8(1)) +
    String.fromCharCode(view.getUint8(2)) +
    String.fromCharCode(view.getUint8(3));
  if (magic !== "MMV2") {
    throw new Error(`Unsupported payload magic: ${magic}`);
  }

  const headerLength = view.getUint32(4, true);
  const headerStart = 8;
  const headerEnd = headerStart + headerLength;
  if (headerEnd > view.byteLength) {
    throw new Error("Invalid MMV2 payload: header overflows buffer");
  }

  const headerBytes = new Uint8Array(buffer, headerStart, headerLength);
  const headerText = new TextDecoder("utf-8").decode(headerBytes);
  const header = JSON.parse(headerText);

  const blobStart = (headerEnd + 7) & ~7;
  if (blobStart > view.byteLength) {
    throw new Error(
      "Invalid MMV2 payload: aligned blob start overflows buffer",
    );
  }
  return { header, blobStart };
}

function typedArrayFromMeta(buffer, blobStart, meta) {
  const ctor = dtypeToCtor(meta.dtype);
  const offset = blobStart + meta.offset;
  const elementSize = ctor.BYTES_PER_ELEMENT;
  if (meta.nbytes % elementSize !== 0) {
    throw new Error(`Buffer length for dtype ${meta.dtype} is not aligned`);
  }
  const length = meta.nbytes / elementSize;
  return new ctor(buffer, offset, length);
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
    this.syncToken = 0;
  }

  render() {
    this.root = document.createElement("div");
    this.root.className = "mmv-root";
    this.root.style.width = this.model.get("width") || "100%";
    this.root.style.height = `${this.model.get("height") || 560}px`;

    this.el.replaceChildren(this.root);

    this._initThree();
    this._bindModel();
    this._syncSceneSource();
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
    const onSource = () => this._syncSceneSource();
    const onSize = () => {
      if (this.root == null) {
        return;
      }
      this.root.style.width = this.model.get("width") || "100%";
      this.root.style.height = `${this.model.get("height") || 560}px`;
      this._resize();
    };

    this.model.on("change:scene_source", onSource);
    this.model.on("change:width", onSize);
    this.model.on("change:height", onSize);

    this.listeners.push(["change:scene_source", onSource]);
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

  _showEmpty(message) {
    if (!this.root.querySelector(".mmv-empty")) {
      const empty = document.createElement("div");
      empty.className = "mmv-empty";
      this.root.appendChild(empty);
    }
    const empty = this.root.querySelector(".mmv-empty");
    empty.textContent = message;
  }

  async _syncSceneSource() {
    if (this.meshGroup == null) {
      return;
    }

    const token = ++this.syncToken;
    this.meshGroup.clear();

    const source = this.model.get("scene_source") || {};
    const uri = source.uri;
    if (!uri) {
      this._showEmpty("No binary scene source configured.");
      this.model.set("render_stats", {
        status: "empty",
        mesh_count: 0,
      });
      this.model.save_changes();
      return;
    }

    const t0 = performance.now();

    try {
      const response = await fetch(uri);
      if (!response.ok) {
        throw new Error(`Failed to fetch scene payload: ${response.status}`);
      }

      const tFetch = performance.now();

      let payload = await response.arrayBuffer();
      payload = await maybeDecompress(payload, source.compression || "none");

      const tDecode = performance.now();

      if (this.disposed || token !== this.syncToken) {
        return;
      }

      const { header, blobStart } = parseMmv2Payload(payload);
      const meshes = Array.isArray(header.meshes) ? header.meshes : [];

      if (meshes.length === 0) {
        this._showEmpty("Binary payload contains no meshes.");
        this.model.set("render_stats", {
          status: "ok",
          mesh_count: 0,
          total_ms: Math.round((performance.now() - t0) * 1000) / 1000,
          fetch_ms: Math.round((tFetch - t0) * 1000) / 1000,
          decode_ms: Math.round((tDecode - tFetch) * 1000) / 1000,
          build_ms: 0,
        });
        this.model.save_changes();
        return;
      }

      const empty = this.root.querySelector(".mmv-empty");
      if (empty) {
        empty.remove();
      }

      for (const meshData of meshes) {
        const geometry = new THREE.BufferGeometry();

        if (meshData.vertices?.dtype === "float64") {
          throw new Error(
            "float64 vertices are not supported by WebGL; provide float32 vertices in the payload",
          );
        }

        const vertices = typedArrayFromMeta(
          payload,
          blobStart,
          meshData.vertices,
        );
        const faces = typedArrayFromMeta(payload, blobStart, meshData.faces);

        geometry.setAttribute(
          "position",
          new THREE.BufferAttribute(vertices, 3, false),
        );
        geometry.setIndex(new THREE.BufferAttribute(faces, 1, false));
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

      const tBuild = performance.now();

      this._fitCamera();

      await new Promise((resolve) => requestAnimationFrame(resolve));
      const tFrame = performance.now();

      this.model.set("render_stats", {
        status: "ok",
        mesh_count: meshes.length,
        total_ms: Math.round((tFrame - t0) * 1000) / 1000,
        fetch_ms: Math.round((tFetch - t0) * 1000) / 1000,
        decode_ms: Math.round((tDecode - tFetch) * 1000) / 1000,
        build_ms: Math.round((tBuild - tDecode) * 1000) / 1000,
        first_frame_ms: Math.round((tFrame - tBuild) * 1000) / 1000,
      });
      this.model.save_changes();
    } catch (error) {
      this._showEmpty(`Failed to load binary scene: ${error.message}`);
      this.model.set("render_stats", {
        status: "error",
        message: error.message,
        total_ms: Math.round((performance.now() - t0) * 1000) / 1000,
      });
      this.model.save_changes();
    }
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
      scene_source: state.scene_source || {},
      render_stats: state.render_stats || {},
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
