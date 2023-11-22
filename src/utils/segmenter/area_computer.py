from .area import Area


def build(polygons):
    all_areas = [Area(p) for p in polygons]
    return all_areas


def rebuild(areas):
    for i in range(len(areas)):
        area = areas[i]
        area.rebuild()
