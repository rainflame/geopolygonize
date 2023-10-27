import tqdm

from rasterio.features import shapes
from tqdm import tqdm

from shapely.geometry import shape

from area import Area


def build(data, transform):
    shapes_gen = shapes(data, transform=transform)
    all_areas = [Area(shape(s), v) for s, v in tqdm(shapes_gen, desc="Building areas")]
    return all_areas

def rebuild(areas):
    for i in tqdm(range(len(areas)), desc="Rebulding areas"):
        area = areas[i]
        area.rebuild()