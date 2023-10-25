from rasterio.features import shapes
from shapely.geometry import shape

from cover import Cover


def build(data, transform):
    shapes_gen = shapes(data, transform=transform)   
    all_covers = [Cover(shape(s), v) for s, v in shapes_gen]
    return all_covers

def rebuild(covers):
    for c in range(len(covers)):
        cover = covers[c]
        cover.rebuild()