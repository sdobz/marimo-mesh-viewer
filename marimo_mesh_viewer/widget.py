from __future__ import annotations

from array import array
import base64
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterable, Sequence, SupportsIndex, TypedDict

import anywidget
from traitlets import Dict, Int, Unicode


Number = int | float


class WireArray(TypedDict):
    codec: str
    dtype: str
    shape: list[int]
    buffer: str


class MaterialPayload(TypedDict, total=False):
    color: str
    opacity: float
    metalness: float
    roughness: float
    wireframe: bool
    double_sided: bool


class MeshPayload(TypedDict, total=False):
    id: str | None
    name: str | None
    vertices: WireArray
    faces: WireArray
    material: MaterialPayload


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


def _rows_of_three(data: Iterable[Sequence[Any]], *, name: str) -> Iterable[tuple[Any, Any, Any]]:
    for row_index, row in enumerate(data):
        values = tuple(row)
        if len(values) != 3:
            raise ValueError(f"{name} row {row_index} must have exactly 3 values")
        yield values[0], values[1], values[2]


def _encode_vertices(vertices: Iterable[Sequence[Number]]) -> WireArray:
    packed = array("f")
    row_count = 0
    for x, y, z in _rows_of_three(vertices, name="vertices"):
        packed.extend((float(x), float(y), float(z)))
        row_count += 1

    return {
        "codec": "b64",
        "dtype": "float32",
        "shape": [row_count, 3],
        "buffer": base64.b64encode(packed.tobytes()).decode("ascii"),
    }


def _encode_faces(faces: Iterable[Sequence[SupportsIndex]]) -> WireArray:
    packed = array("I")
    row_count = 0
    max_uint32 = (1 << 32) - 1

    for i0, i1, i2 in _rows_of_three(faces, name="faces"):
        tri = (int(i0), int(i1), int(i2))
        for index in tri:
            if index < 0 or index > max_uint32:
                raise ValueError("faces indices must be within uint32 range")
        packed.extend(tri)
        row_count += 1

    return {
        "codec": "b64",
        "dtype": "uint32",
        "shape": [row_count, 3],
        "buffer": base64.b64encode(packed.tobytes()).decode("ascii"),
    }


def mesh_payload(
    vertices: Iterable[Sequence[Number]],
    faces: Iterable[Sequence[SupportsIndex]],
    *,
    name: str | None = None,
    mesh_id: str | None = None,
    material: MaterialPayload | None = None,
) -> MeshPayload:
    """Build one mesh payload suitable for `MeshViewer.scene`.

    This API intentionally stays at a medium abstraction level:
    geometry + material metadata, without mirroring full three.js objects.
    """
    payload: MeshPayload = {
        "id": mesh_id,
        "name": name,
        "vertices": _encode_vertices(vertices),
        "faces": _encode_faces(faces),
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

    def set_meshes(self, meshes: list[MeshPayload]) -> None:
        self.scene = {
            **(self.scene or {}),
            "version": 1,
            "meshes": meshes,
        }

    def add_mesh(self, mesh: MeshPayload) -> None:
        scene = dict(self.scene or {})
        meshes = list(scene.get("meshes", []))
        meshes.append(mesh)
        scene["version"] = 1
        scene["meshes"] = meshes
        self.scene = scene
