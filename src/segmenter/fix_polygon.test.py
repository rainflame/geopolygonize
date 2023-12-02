from .fix_polygon import fix_polygon


# Example 1:
# a - b - a
# Keep: NONE

# Example 2:
# a - A - a - B - b - C - b - D - a
# Keep: a - A - a, b - C - b, a - B - b - D - a

# Example 3:
# a - b - c - d - b - e - a
# Keep: b - c - d - b, a - b - e - a

# Example 4:
# s - a - b - a - b - s
# Keep: s - a - b - s

# Example 5:
# a - x - y - a - z - a
# Keep: a - x - y - a

