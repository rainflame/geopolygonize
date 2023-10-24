from rasterio.features import shapes
from shapely.geometry import shape

from cover import Cover


def build(data, transform):
    shapes_gen = shapes(data, transform=transform)   
    all_covers = [Cover(shape(s), v) for s, v in shapes_gen]
    return all_covers

def rebuild(covers, loops):
    for c in range(len(covers)):
        cover = covers[c]
        exterior = loops[cover.exterior_idx].modified_line
        interiors = [loops[i].modified_line for i in cover.interior_idxes]
        cover.rebuild(exterior, interiors)