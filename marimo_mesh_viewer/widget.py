from __future__ import annotations

import base64
from pathlib import Path
from textwrap import dedent
from typing import Any

import anywidget
import numpy as np
from traitlets import Dict, Int, Unicode


def _load_anywidget_esm() -> str:
        """Wrap the webpack window bundle into an AnyWidget ESM module."""
        bundle_path = Path(__file__).parent / "static" / "index.js"
        if not bundle_path.exists():
                return dedent(
                        """
                        export default {
                            render({ el }) {
                                el.textContent = "marimo-mesh-viewer frontend bundle not found";
                            },
                        };
                        """
                )

        bundle = bundle_path.read_text(encoding="utf-8")
        return bundle + dedent(
                """

                function ensureBundle() {
                    if (!globalThis.MarimoMeshViewer) {
                        throw new Error("MarimoMeshViewer bundle did not initialize");
                    }
                    return globalThis.MarimoMeshViewer;
                }

                function adaptModel(model) {
                    const listeners = [];

                    return {
                        get(key) {
                            return model.get(key);
                        },
                        set(key, value) {
                            model.set(key, value);
                        },
                        save_changes() {
                            model.save_changes();
                        },
                        on(eventName, callback, context) {
                            const wrapped = (...args) => callback.call(context ?? model, ...args);
                            listeners.push([eventName, wrapped]);
                            model.on(eventName, wrapped);
                            return wrapped;
                        },
                        off(eventName, callback) {
                            model.off(eventName, callback);
                        },
                        disposeListeners() {
                            listeners.forEach(([eventName, callback]) => model.off(eventName, callback));
                            listeners.length = 0;
                        },
                    };
                }

                export default {
                    render({ model, el }) {
                        const api = ensureBundle();
                        const adaptedModel = adaptModel(model);
                        const view = new api.MeshViewerView({ model: adaptedModel, el });
                        view.render();

                        return () => {
                            adaptedModel.disposeListeners();
                            view.dispose();
                        };
                    },
                };
                """
        )


def _ensure_vertices(vertices: Any) -> np.ndarray:
    arr = np.asarray(vertices, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("vertices must have shape (N, 3)")
    if not arr.flags["C_CONTIGUOUS"]:
        arr = np.ascontiguousarray(arr)
    return arr


def _ensure_faces(faces: Any) -> np.ndarray:
    arr = np.asarray(faces)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("faces must have shape (M, 3)")
    if arr.dtype not in (np.uint32, np.int32, np.int64, np.uint64):
        arr = arr.astype(np.uint32)
    else:
        arr = arr.astype(np.uint32, copy=False)
    if not arr.flags["C_CONTIGUOUS"]:
        arr = np.ascontiguousarray(arr)
    return arr


def _ndarray_to_wire(arr: np.ndarray) -> dict[str, Any]:
    return {
        "codec": "b64",
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
        "buffer": base64.b64encode(arr.ravel().tobytes()).decode("ascii"),
    }


def mesh_payload(
    vertices: Any,
    faces: Any,
    *,
    name: str | None = None,
    mesh_id: str | None = None,
    material: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one mesh payload suitable for `MeshViewer.scene`.

    This API intentionally stays at a medium abstraction level:
    geometry + material metadata, without mirroring full three.js objects.
    """
    v = _ensure_vertices(vertices)
    f = _ensure_faces(faces)

    payload: dict[str, Any] = {
        "id": mesh_id,
        "name": name,
        "vertices": _ndarray_to_wire(v),
        "faces": _ndarray_to_wire(f),
        "material": {
            "color": "#9aa0a6",
            "opacity": 1.0,
            "metalness": 0.1,
            "roughness": 0.9,
            "wireframe": False,
            "double_sided": False,
            **(material or {}),
        },
    }
    return payload


def trimesh_payload(
    mesh: Any,
    *,
    name: str | None = None,
    mesh_id: str | None = None,
    material: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a `trimesh.Trimesh` into a `mesh_payload` dict."""
    vertices = getattr(mesh, "vertices", None)
    faces = getattr(mesh, "faces", None)
    if vertices is None or faces is None:
        raise TypeError("mesh must provide .vertices and .faces")
    return mesh_payload(vertices, faces, name=name, mesh_id=mesh_id, material=material)


class MeshViewer(anywidget.AnyWidget):
    """Minimal anywidget mesh viewer for marimo.

    Main trait:
    - scene: dict with `{version, meshes, camera, options}`
    """

    _esm = _load_anywidget_esm()
    _css = Path(__file__).parent / "static" / "index.css"

    scene = Dict(default_value={"version": 1, "meshes": []}).tag(sync=True)
    width = Unicode(default_value="100%").tag(sync=True)
    height = Int(default_value=560).tag(sync=True)

    def __init__(self, *, scene: dict[str, Any] | None = None, width: str = "100%", height: int = 560):
        super().__init__()
        self.width = width
        self.height = height
        if scene is not None:
            self.scene = scene

    def set_meshes(self, meshes: list[dict[str, Any]]) -> None:
        self.scene = {
            **(self.scene or {}),
            "version": 1,
            "meshes": meshes,
        }

    def add_mesh(self, mesh: dict[str, Any]) -> None:
        scene = dict(self.scene or {})
        meshes = list(scene.get("meshes", []))
        meshes.append(mesh)
        scene["version"] = 1
        scene["meshes"] = meshes
        self.scene = scene
