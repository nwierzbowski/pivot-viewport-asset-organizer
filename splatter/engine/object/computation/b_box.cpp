#include "b_box.h"

#include "share/vec.h"


Vec3 factor_to_coord(float factor, BoundingBox3D box)
{
    return box.min_corner + ((box.max_corner - box.min_corner) * factor);
}

Vec2 factor_to_coord(float factor, BoundingBox2D box)
{
    return box.min_corner + ((box.max_corner - box.min_corner) * factor);
}

Vec2 get_bounding_box_origin(BoundingBox2D box)
{
    return Vec2{(box.min_corner.x + box.max_corner.x) * 0.5f, (box.min_corner.y + box.max_corner.y) * 0.5f};
}