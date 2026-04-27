import marimo

__generated_with = "0.23.3"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import numpy as np

    from marimo_mesh_viewer import MeshViewer, mesh_payload

    return MeshViewer, mesh_payload, mo, np


@app.cell
def _(mo):
    mo.md("""
    # marimo-mesh-viewer demo

    This notebook demonstrates the binary-only plugin API.

    - Build mesh descriptors with `mesh_payload(...)`
    - Send one scene binary payload with `viewer.set_scene(...)`

    The widget avoids inline/base64 geometry transport.
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

    viewer_raw = MeshViewer(height=440)
    viewer_raw.set_scene(
        meshes=[
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
        camera={"fit": "all"},
        options={"background": "#f4f4f4", "show_grid": False},
        compression="none",
    )
    viewer_raw
    return


@app.cell
def _(MeshViewer, mesh_payload, mo):
    mo.md("## List-based input (still binary transport)")

    vertices = [
        [-1.0, -1.0, 0.0],
        [1.0, -1.0, 0.0],
        [1.0, 1.0, 0.0],
        [-1.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    faces = [
        [0, 1, 4],
        [1, 2, 4],
        [2, 3, 4],
        [3, 0, 4],
        [0, 2, 1],
        [0, 3, 2],
    ]

    viewer_lists = MeshViewer(height=380)
    viewer_lists.set_scene(
        meshes=[
            mesh_payload(
                vertices,
                faces,
                name="list-pyramid",
                material={
                    "color": "#4f83cc",
                    "metalness": 0.05,
                    "roughness": 0.85,
                },
            )
        ],
        compression="none",
    )
    viewer_lists
    return


@app.cell
def _(mo):
    mo.md("""
    ## Large mesh benchmark

    This section builds a large grid mesh and reports:

    - Python `set_scene(...)` wall time (payload build + registration)
    - Frontend timings from `viewer.render_stats`:
      - `fetch_ms`
      - `decode_ms`
      - `build_ms`
      - `first_frame_ms`
      - `total_ms`

    Re-run this cell and the next timing cell to refresh numbers.
    """)
    return


@app.cell
def _(MeshViewer, mesh_payload, np):
    import time

    n = 800
    x = np.linspace(-2.0, 2.0, n, dtype=np.float32)
    y = np.linspace(-2.0, 2.0, n, dtype=np.float32)
    xx, yy = np.meshgrid(x, y, indexing="xy")
    zz = (0.25 * np.sin(xx * 3.0) * np.cos(yy * 2.0)).astype(np.float32)

    vertices_large = np.column_stack(
        [xx.ravel(order="C"), yy.ravel(order="C"), zz.ravel(order="C")]
    ).astype(np.float32, copy=False)

    cells = (n - 1) * (n - 1)
    faces_large = np.empty((cells * 2, 3), dtype=np.uint32)
    k = 0
    for row in range(n - 1):
        base = row * n
        next_base = (row + 1) * n
        for col in range(n - 1):
            i0 = base + col
            i1 = i0 + 1
            i2 = next_base + col
            i3 = i2 + 1
            faces_large[k] = (i0, i2, i1)
            faces_large[k + 1] = (i1, i2, i3)
            k += 2

    viewer_large = MeshViewer(height=460)

    t0 = time.perf_counter()
    viewer_large.set_scene(
        meshes=[
            mesh_payload(
                vertices_large,
                faces_large,
                name="large-grid",
                material={
                    "color": "#7f93b0",
                    "metalness": 0.05,
                    "roughness": 0.9,
                },
            )
        ],
        compression="none",
    )
    set_scene_ms = (time.perf_counter() - t0) * 1000.0

    viewer_large
    return faces_large, set_scene_ms, vertices_large, viewer_large


@app.cell
def _(faces_large, mo, set_scene_ms, vertices_large, viewer_large):
    stats = dict(viewer_large.render_stats)
    stats_lines = [f"- `{k}`: `{v}`" for k, v in sorted(stats.items())]
    stats_md = "\n".join(stats_lines) if stats_lines else "- waiting for frontend render stats"

    mo.md(
        f"""
        **Large mesh size**

        - vertices: `{len(vertices_large):,}`
        - faces: `{len(faces_large):,}`
        - python set_scene wall time: `{set_scene_ms:.2f} ms`

        **Frontend render stats**

        {stats_md}
        """
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
