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
- Supports high-volume data transfer using base64-encoded typed arrays.
- Leaves room for future features like per-mesh transforms, lights, labels, and picking.

## Quick start

```python
import numpy as np
from marimo_mesh_viewer import MeshViewer, mesh_payload

vertices = np.array([
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
], dtype=np.float32)
faces = np.array([[0, 1, 2]], dtype=np.uint32)

viewer = MeshViewer(height=500)
viewer.scene = {
    "version": 1,
    "meshes": [mesh_payload(vertices, faces, name="triangle")],
}
viewer
```

Or from trimesh:

```python
import trimesh
from marimo_mesh_viewer import MeshViewer, trimesh_payload

mesh = trimesh.creation.icosphere(subdivisions=3)
viewer = MeshViewer(scene={"version": 1, "meshes": [trimesh_payload(mesh)]})
viewer
```

## Build frontend bundle

```bash
cd js
yarn install
yarn build
```

The bundle is emitted into `marimo_mesh_viewer/static/`.
