# marimo-mesh-viewer (prototype)

A minimal marimo/anywidget plugin for rendering triangle meshes with three.js.

This viewer uses **one transport only**: a single binary scene payload (MMV2)
served through a browser URL.

## API shape

The core abstraction is a list of mesh inputs converted to a single binary payload:

```python
[
  {
    "id": "mesh-1",
    "name": "terrain",
    "vertices": ...,  # (N, 3) float32/float64 array-like OR list rows
    "faces": ...,     # (M, 3) uint16/uint32 array-like OR list rows
    "material": {
      "color": "#9aa0a6",
      "opacity": 1.0,
      "metalness": 0.1,
      "roughness": 0.9,
      "wireframe": False,
      "double_sided": False,
    }
  }
]
```

This avoids exposing three.js directly while remaining flexible for multiple meshes/materials.

## Why this level

- Not tied to one mesh or one fixed renderer behavior.
- Not a reimplementation of the full three.js API.
- Uses a single binary payload for the whole scene.
- Supports list/iterable and numpy-like array inputs (numpy is optional).
- Does not run geometry optimization or simplification.
- Leaves room for future features like per-mesh transforms, lights, labels, and picking.

## Quick start

```python
from marimo_mesh_viewer import MeshViewer, mesh_payload

vertices = [
  [0.0, 0.0, 0.0],
  [1.0, 0.0, 0.0],
  [0.0, 1.0, 0.0],
]
faces = [[0, 1, 2]]

viewer = MeshViewer(height=500)
viewer.set_scene(
  meshes=[mesh_payload(vertices, faces, name="triangle")],
  compression="none",  # or "gzip"
)
viewer
```

If you pass numpy arrays, they are accepted as generic iterables of rows.

## Build frontend bundle

```bash
cd js
yarn install
yarn build
```

The bundle is emitted into `marimo_mesh_viewer/static/`.
