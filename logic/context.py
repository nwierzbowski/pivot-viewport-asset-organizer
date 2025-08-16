import bpy
import bmesh
from contextlib import contextmanager
from typing import Iterator

def ensure_active(obj: bpy.types.Object) -> None:
    view_layer = bpy.context.view_layer
    view_layer.objects.active = obj
    obj.select_set(True)

@contextmanager
def object_mode(obj: bpy.types.Object) -> Iterator[None]:
    """Temporarily switch to OBJECT mode."""
    ensure_active(obj)
    prev_mode = obj.mode
    if prev_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        yield
    finally:
        if obj.mode != prev_mode:
            bpy.ops.object.mode_set(mode=prev_mode)

@contextmanager
def edit_bmesh(obj: bpy.types.Object) -> Iterator[bmesh.types.BMesh]:
    """Enter EDIT mode, yield BMesh, write back on exit."""
    ensure_active(obj)
    prev_mode = obj.mode
    if prev_mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    try:
        yield bm
    finally:
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        bm.free()
        if obj.mode != prev_mode:
            bpy.ops.object.mode_set(mode=prev_mode)

@contextmanager
def object_bmesh(obj: bpy.types.Object) -> Iterator[bmesh.types.BMesh]:
    """Yield a BMesh from the object's mesh data."""
    ensure_active(obj)
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    try:
        yield bm
    finally:
        bm.free()
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')