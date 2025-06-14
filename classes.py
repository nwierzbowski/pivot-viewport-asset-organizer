from bpy.types import PropertyGroup
from bpy.props import BoolProperty


class ObjectAttributes(PropertyGroup):
    isSeating: BoolProperty()
    isSurface: BoolProperty()
