# Copilot Instructions for Pivot Project

## Architecture Overview
Pivot is a Blender add-on for object organization. It uses a hybrid Python/C++ architecture:
- **Python layer** (`pivot/`): Blender addon UI, data preparation, and IPC client.
- **C++ engine** (`engine/`): High-performance geometric computations (COG via convex hulls, slicing).
- **Communication**: JSON over stdin/stdout for control; shared memory (Boost.Interprocess) for large data arrays.
- **Why hybrid?**: Blender's Python is slow for heavy math; C++ engine handles performance-critical tasks.

Key data flows:
- Python marshals mesh data into shared memory segments.
- Engine processes via slicing/edge intersections, returns results as JSON.
- Example: `prepare_op.cpp` maps shared memory, calls `prepare_object_batch` in `engine.cpp`.

## Build and Run
- **Build engine**: `cmake --preset=default && cmake --build --preset=default-release` (outputs to `pivot/bin/pivot_engine`).
- **Run addon**: Install `pivot/` as Blender addon; engine auto-starts via subprocess.
- **Debug C++**: Use gdb on `pivot_engine`; attach to running process.
- **Debug Python**: Use Blender's text editor/console for addon scripts.
- **Dependencies**: Boost (IPC), Eigen (math), CMake/Ninja. Install via `apt` or build deps.

## Code Patterns
- **Types**: Use `Vec3`, `Quaternion`, `uVec2i` from `engine/src/share/`; avoid raw arrays, prefer `std::span`.
- **Enums**: Classification enums in `core/classification.h` for Blender-C++ communication to avoid magic numbers.
- **IPC**: Shared memory segments named by Python; engine maps read-write. Example: `map_shared_memory` in `shm_utils.cpp`.
- **Geometry**: COG computed via volume slicing (`calc_cog_volume_edges_intersections` in `cog.cpp`); convex hulls use `monotonic_chain`.
- **Error handling**: Throw `std::runtime_error` with descriptive messages; caught in `main.cpp` for JSON error responses.
- **Memory**: Reuse static vectors in hot paths (e.g., `comp_points` in `build_slice_islands`).
- **Naming**: Functions like `prepare_object_batch`; parameters like `out_origin` (renamed from `out_trans` for clarity).

## Integration Points
- **Blender API**: Use `bpy` for mesh access; register operators in `operators.py`.
- **External deps**: Eigen for matrices; Boost for JSON/IPC. Fetch via CMake `FetchContent`.
- **Cross-component**: Python calls engine with JSON `{"op": "prepare", "shm_verts": "..."}`; engine responds with `{"ok": true, "rots": [...]}`.

Reference: `engine/src/engine.h` for API; `pivot/engine.py` for Python wrapper.