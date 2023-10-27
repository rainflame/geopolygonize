from rasterio.features import shapes

from shapely.geometry import shape

from area import Area


def build(data, transform):
    shapes_gen = shapes(data, transform=transform)
    all_areas = [Area(shape(s), v) for s, v in shapes_gen]
    return all_areas

def rebuild(areas):
    for i in range(len(areas)):
        area = areas[i]
        area.rebuild()