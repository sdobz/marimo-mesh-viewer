import marimo

__generated_with = "0.23.3"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import numpy as np

    from marimo_mesh_viewer import MeshViewer, mesh_payload, trimesh_payload

    try:
        import trimesh
    except Exception:
        trimesh = None
    return MeshViewer, mesh_payload, mo, np, trimesh, trimesh_payload


@app.cell
def _(mo):
    mo.md("""
    # marimo-mesh-viewer demo

    This notebook demonstrates the plugin API at the **scene payload** level:

    - `meshes[i].vertices`: Nx3 float32
    - `meshes[i].faces`: Mx3 uint32
    - `meshes[i].material`: lightweight material properties

    The goal is to avoid mirroring all of three.js while still supporting
    multiple meshes and flexible rendering.
    """)
    return


@app.cell
def _(MeshViewer, mesh_payload, np):
    # Simple tetrahedron + base slab as two independent meshes.
    tetra_vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.86, 0.0],
            [0.5, 0.28, 0.9],
        ],
        dtype=np.float32,
    )
    tetra_faces = np.array(
        [
            [0, 1, 2],
            [0, 1, 3],
            [1, 2, 3],
            [2, 0, 3],
        ],
        dtype=np.uint32,
    )

    slab_vertices = np.array(
        [
            [-0.4, -0.4, -0.08],
            [1.4, -0.4, -0.08],
            [1.4, 1.2, -0.08],
            [-0.4, 1.2, -0.08],
            [-0.4, -0.4, -0.14],
            [1.4, -0.4, -0.14],
            [1.4, 1.2, -0.14],
            [-0.4, 1.2, -0.14],
        ],
        dtype=np.float32,
    )
    slab_faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 5, 1],
            [0, 4, 5],
            [1, 6, 2],
            [1, 5, 6],
            [2, 7, 3],
            [2, 6, 7],
            [3, 4, 0],
            [3, 7, 4],
        ],
        dtype=np.uint32,
    )

    scene = {
        "version": 1,
        "meshes": [
            mesh_payload(
                tetra_vertices,
                tetra_faces,
                name="tetra",
                material={
                    "color": "#e08e79",
                    "metalness": 0.2,
                    "roughness": 0.7,
                },
            ),
            mesh_payload(
                slab_vertices,
                slab_faces,
                name="base",
                material={
                    "color": "#7d8ca3",
                    "opacity": 0.92,
                    "metalness": 0.05,
                    "roughness": 0.95,
                },
            ),
        ],
        "camera": {"fit": "all"},
        "options": {"background": "#f4f4f4", "show_grid": False},
    }

    viewer_raw = MeshViewer(scene=scene, height=440)
    viewer_raw
    return


@app.cell
def _(mo, trimesh, trimesh_payload):
    if trimesh is None:
        mo.md(
            """
            ## trimesh demo skipped

            `trimesh` is not installed in this environment.
            Install it to run the conversion helper demo.
            """
        )
        scene_trimesh = None
    else:
        sphere = trimesh.creation.icosphere(subdivisions=3, radius=0.45)
        sphere.apply_translation((1.0, 0.0, 0.5))

        box = trimesh.creation.box(extents=(1.2, 0.8, 0.2))
        box.apply_translation((0.4, 0.0, -0.2))

        scene_trimesh = {
            "version": 1,
            "meshes": [
                trimesh_payload(
                    sphere,
                    name="sphere",
                    material={
                        "color": "#48a868",
                        "metalness": 0.15,
                        "roughness": 0.65,
                    },
                ),
                trimesh_payload(
                    box,
                    name="box",
                    material={
                        "color": "#9aa0a6",
                        "opacity": 0.85,
                        "metalness": 0.05,
                        "roughness": 0.9,
                    },
                ),
            ],
        }
    return (scene_trimesh,)


@app.cell
def _(MeshViewer, scene_trimesh):
    if scene_trimesh is None:
        viewer_trimesh = None
    else:
        viewer_trimesh = MeshViewer(scene=scene_trimesh, height=440)

    viewer_trimesh
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
