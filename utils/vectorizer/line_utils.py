from shapely.geometry import LineString, Point


def is_along_line(line, point):
    start = Point(line.coords[0])
    end = Point(line.coords[-1])
    return point.intersects(line) or point.equals(start) or point.equals(end)

def get_distance(line, point):
    key = (line, point)

    distance = 0
    for i in range(len(line.coords) - 1):
        segment = LineString([line.coords[i], line.coords[i + 1]])
        if is_along_line(segment, point):
            distance += segment.project(point)
            break
        else:
            distance += segment.length
    return distance