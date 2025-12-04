# classification.pyx - C declarations and Python constants for classification

cdef extern from "classification.h":
    cdef int SurfaceType_Ground "static_cast<int>(SurfaceType::Ground)"
    cdef int SurfaceType_Wall "static_cast<int>(SurfaceType::Wall)"
    cdef int SurfaceType_Ceiling "static_cast<int>(SurfaceType::Ceiling)"
    cdef int SurfaceType_Unknown "static_cast<int>(SurfaceType::Unknown)"

# Expose enum values as Python constants using the imported C enum values
SURFACE_GROUND = SurfaceType_Ground
SURFACE_WALL = SurfaceType_Wall
SURFACE_CEILING = SurfaceType_Ceiling
SURFACE_UNKNOWN = SurfaceType_Unknown

# Also expose as a dict for easy lookup
SURFACE_TYPE_NAMES = {
    str(SurfaceType_Ground): "Ground Objects",
    str(SurfaceType_Wall): "Wall Objects",
    str(SurfaceType_Ceiling): "Ceiling Objects",
    str(SurfaceType_Unknown): "Unknown Objects"
}
