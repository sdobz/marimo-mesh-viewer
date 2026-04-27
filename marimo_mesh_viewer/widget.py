from __future__ import annotations

from array import array
import gzip
import json
from pathlib import Path
import struct
from textwrap import dedent
from typing import Any, Iterable, Literal, Sequence, SupportsIndex, TypedDict

import anywidget
from traitlets import Dict, Int, Unicode

Number = int | float
Compression = Literal["none", "gzip"]


class MaterialPayload(TypedDict, total=False):
    color: str
    opacity: float
    metalness: float
    roughness: float
    wireframe: bool
    double_sided: bool


class BufferMeta(TypedDict):
    dtype: str
    shape: list[int]
    offset: int
    nbytes: int


class MeshDescriptor(TypedDict, total=False):
    id: str | None
    name: str | None
    material: MaterialPayload
    vertices: BufferMeta
    faces: BufferMeta


class MeshInput(TypedDict, total=False):
    id: str | None
    name: str | None
    vertices: Any
    faces: Any
    material: MaterialPayload


class SceneSource(TypedDict):
    uri: str
    format: str
    compression: Compression
    byte_length: int


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


def _array_like_bytes(data: Any) -> bytes:
    tobytes = getattr(data, "tobytes", None)
    if not callable(tobytes):
        raise TypeError("Expected an array-like object with .tobytes()")
    try:
        return tobytes(order="C")
    except TypeError:
        return tobytes()


def _shape2(data: Any, *, name: str) -> tuple[int, int]:
    shape = getattr(data, "shape", None)
    if shape is None:
        raise TypeError(f"{name} array-like input must provide .shape")
    shape_tuple = tuple(int(x) for x in shape)
    if len(shape_tuple) != 2 or shape_tuple[1] != 3:
        raise ValueError(f"{name} must have shape (N, 3)")
    return int(shape_tuple[0]), int(shape_tuple[1])


def _dtype_str(data: Any) -> str:
    dtype = getattr(data, "dtype", None)
    if dtype is None:
        raise TypeError("array-like input must provide .dtype")
    return str(dtype)


def _rows_of_three(data: Iterable[Sequence[Any]], *, name: str) -> Iterable[tuple[Any, Any, Any]]:
    for row_index, row in enumerate(data):
        values = tuple(row)
        if len(values) != 3:
            raise ValueError(f"{name} row {row_index} must have exactly 3 values")
        yield values[0], values[1], values[2]


def _encode_vertices(vertices: Any) -> tuple[str, list[int], bytes]:
    if hasattr(vertices, "shape") and hasattr(vertices, "dtype") and hasattr(vertices, "tobytes"):
        rows, _ = _shape2(vertices, name="vertices")
        dtype = _dtype_str(vertices)
        if dtype != "float32":
            raise ValueError(
                "vertices dtype must be float32 for WebGL/three.js vertex attributes; "
                "convert upstream (e.g. astype('float32'))"
            )
        return dtype, [rows, 3], _array_like_bytes(vertices)

    packed = array("f")
    row_count = 0
    for x, y, z in _rows_of_three(vertices, name="vertices"):
        packed.extend((float(x), float(y), float(z)))
        row_count += 1
    return "float32", [row_count, 3], packed.tobytes()


def _encode_faces(faces: Any) -> tuple[str, list[int], bytes]:
    if hasattr(faces, "shape") and hasattr(faces, "dtype") and hasattr(faces, "tobytes"):
        rows, _ = _shape2(faces, name="faces")
        dtype = _dtype_str(faces)
        if dtype not in {"uint16", "uint32"}:
            raise ValueError("faces dtype must be uint16 or uint32")
        return dtype, [rows, 3], _array_like_bytes(faces)

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
    return "uint32", [row_count, 3], packed.tobytes()


def mesh_payload(
    vertices: Any,
    faces: Any,
    *,
    name: str | None = None,
    mesh_id: str | None = None,
    material: MaterialPayload | None = None,
) -> MeshInput:
    """Create a mesh input descriptor.

    This function does not serialize geometry immediately; it stores references
    and metadata until `scene_binary_payload(...)` is called.
    """
    return {
        "id": mesh_id,
        "name": name,
        "vertices": vertices,
        "faces": faces,
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


def _build_binary_scene_payload(
    meshes: list[MeshInput],
    *,
    camera: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> bytes:
    blob = bytearray()
    mesh_descriptors: list[MeshDescriptor] = []
    offset = 0

    for mesh in meshes:
        vertices = mesh.get("vertices")
        faces = mesh.get("faces")
        if vertices is None or faces is None:
            raise ValueError("Each mesh must include both 'vertices' and 'faces'")

        v_dtype, v_shape, v_bytes = _encode_vertices(vertices)
        f_dtype, f_shape, f_bytes = _encode_faces(faces)

        v_meta: BufferMeta = {
            "dtype": v_dtype,
            "shape": v_shape,
            "offset": offset,
            "nbytes": len(v_bytes),
        }
        blob.extend(v_bytes)
        offset += len(v_bytes)

        f_meta: BufferMeta = {
            "dtype": f_dtype,
            "shape": f_shape,
            "offset": offset,
            "nbytes": len(f_bytes),
        }
        blob.extend(f_bytes)
        offset += len(f_bytes)

        mesh_descriptors.append(
            {
                "id": mesh.get("id"),
                "name": mesh.get("name"),
                "material": mesh.get("material", {}),
                "vertices": v_meta,
                "faces": f_meta,
            }
        )

    header = {
        "version": 1,
        "meshes": mesh_descriptors,
        "camera": camera or {},
        "options": options or {},
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")

    magic = b"MMV2"
    header_len = len(header_bytes)
    aligned_header_len = (header_len + 7) & ~7
    padding_len = aligned_header_len - header_len
    prefix = (
        magic
        + struct.pack("<I", header_len)
        + header_bytes
        + (b"\x00" * padding_len)
    )
    return prefix + bytes(blob)


def _scene_bytes_to_uri(payload: bytes) -> str:
    """Register payload in marimo's virtual-file store and return a browser URL."""
    from marimo._runtime.virtual_file.virtual_file import VirtualFile

    vfile = VirtualFile.create_and_register(payload, "bin")
    return vfile.url


def scene_binary_payload(
    meshes: list[MeshInput],
    *,
    camera: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    compression: Compression = "none",
) -> SceneSource:
    payload = _build_binary_scene_payload(meshes, camera=camera, options=options)

    if compression == "gzip":
        payload = gzip.compress(payload, compresslevel=1)
    elif compression != "none":
        raise ValueError("compression must be 'none' or 'gzip'")

    uri = _scene_bytes_to_uri(payload)
    return {
        "uri": uri,
        "format": "mmv2",
        "compression": compression,
        "byte_length": len(payload),
    }


class MeshViewer(anywidget.AnyWidget):
    """AnyWidget mesh viewer using a single binary scene payload transport."""

    _esm = _load_anywidget_esm()
    _css = Path(__file__).parent / "static" / "index.css"

    scene_source = Dict(default_value={}).tag(sync=True)
    render_stats = Dict(default_value={}).tag(sync=True)
    width = Unicode(default_value="100%").tag(sync=True)
    height = Int(default_value=560).tag(sync=True)

    def __init__(
        self,
        *,
        scene: dict[str, Any] | None = None,
        width: str = "100%",
        height: int = 560,
        compression: Compression = "none",
    ):
        super().__init__()
        self.width = width
        self.height = height
        if scene is not None:
            self.set_scene(
                meshes=list(scene.get("meshes", [])),
                camera=dict(scene.get("camera", {})),
                options=dict(scene.get("options", {})),
                compression=compression,
            )

    def set_scene(
        self,
        *,
        meshes: list[MeshInput],
        camera: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        compression: Compression = "none",
    ) -> None:
        self.scene_source = scene_binary_payload(
            meshes,
            camera=camera,
            options=options,
            compression=compression,
        )

    def set_meshes(self, meshes: list[MeshInput], *, compression: Compression = "none") -> None:
        self.set_scene(meshes=meshes, compression=compression)

    def add_mesh(self, mesh: MeshInput, *, compression: Compression = "none") -> None:
        raise NotImplementedError(
            "add_mesh is disabled for binary-only transport; rebuild scene via set_scene(...)."
        )
