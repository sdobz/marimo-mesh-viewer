# marimo-mesh-viewer (prototype)

A minimal marimo/anywidget plugin for rendering triangle meshes with three.js.

## API shape

The core abstraction is a **scene payload**:

```python
{
  "version": 1,
  "meshes": [
    {
      "id": "mesh-1",
      "name": "terrain",
      "vertices": ...,  # Nx3 float32
      "faces": ...,     # Mx3 uint32
      "material": {
        "color": "#9aa0a6",
        "opacity": 1.0,
        "metalness": 0.1,
        "roughness": 0.9,
        "wireframe": False,
        "double_sided": False,
      }
    }
  ],
  "camera": {
    "fit": "all"
  },
  "options": {
    "background": "#ffffff",
    "show_grid": False,
  }
}
```

This avoids exposing three.js directly while remaining flexible for multiple meshes/materials.

## Why this level

- Not tied to one mesh or one fixed renderer behavior.
- Not a reimplementation of the full three.js API.
- Supports list/iterable and numpy-like inputs (numpy is optional, not required by the package).
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
viewer.scene = {
    "version": 1,
    "meshes": [mesh_payload(vertices, faces, name="triangle")],
}
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
