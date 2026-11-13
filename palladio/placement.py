"""Queries against the north-aligned triangular terrain used by both renderers."""
import math
from .scene import ValidationError, number


def active_terrain(baseline, scene):
    return scene.get('terrain', baseline['terrain'])


def height_at(terrain, x, z):
    size, spacing = terrain['size'], terrain['spacing']
    edge = (size - 1) * spacing / 2
    if not -edge <= x <= edge or not -edge <= z <= edge:
        raise ValidationError('The footprint extends outside the saved terrain.')
    u, v = (x + edge) / spacing, (z + edge) / spacing
    col, row = min(size - 2, int(u)), min(size - 2, int(v))
    u, v = u - col, v - row
    values = terrain['heights']
    a, b = values[row * size + col], values[(row + 1) * size + col]
    c, d = values[(row + 1) * size + col + 1], values[row * size + col + 1]
    return a + (c - b) * u + (b - a) * v if v >= u else a + (d - a) * u + (c - d) * v


def footprint_range(terrain, spec):
    """Clip terrain triangles to the rotated footprint, including edge extrema."""
    w, d = spec['width'] / 2, spec['depth'] / 2
    px, _, pz = spec['position']
    angle = math.radians(spec['yaw'])
    c, s = math.cos(angle), math.sin(angle)
    corners = [(px + x*c + z*s, pz - x*s + z*c) for x,z in [(-w,-d),(w,-d),(w,d),(-w,d)]]
    for x,z in corners:
        height_at(terrain, x, z)
    n, spacing = terrain['size'], terrain['spacing']
    edge = (n - 1) * spacing / 2
    values = terrain['heights']
    def point(col, row):
        x,z = col * spacing - edge - px, row * spacing - edge - pz
        return [x*c - z*s, values[row*n + col], x*s + z*c]
    def clip(poly, axis, bound, sign):
        result = []
        for a,b in zip(poly, poly[1:] + poly[:1]):
            da, db = (a[axis] - bound)*sign, (b[axis] - bound)*sign
            if da <= 1e-9: result.append(a)
            if (da < 0 < db) or (db < 0 < da):
                t = da / (da - db)
                result.append([a[i] + t*(b[i] - a[i]) for i in range(3)])
        return result
    low_col = max(0, int((min(x for x,z in corners) + edge) / spacing))
    high_col = min(n-2, int((max(x for x,z in corners) + edge) / spacing))
    low_row = max(0, int((min(z for x,z in corners) + edge) / spacing))
    high_row = min(n-2, int((max(z for x,z in corners) + edge) / spacing))
    heights = []
    for row in range(low_row, high_row+1):
        for col in range(low_col, high_col+1):
            a,b,c1,d1 = point(col,row),point(col,row+1),point(col+1,row+1),point(col+1,row)
            for poly in ([a,b,c1],[a,c1,d1]):
                for axis,bound,sign in ((0,w,1),(0,-w,-1),(2,d,1),(2,-d,-1)):
                    poly = clip(poly,axis,bound,sign)
                heights.extend(p[1] for p in poly)
    if not heights:
        raise ValidationError('No terrain intersects this footprint.')
    return min(heights), max(heights)


def place_spec(baseline, scene, spec, offset):
    offset = number(offset, 'Ground offset (m)', -5, 50)
    low, high = footprint_range(active_terrain(baseline, scene), spec)
    return {**spec, 'position': [spec['position'][0], high + offset, spec['position'][2]]}
