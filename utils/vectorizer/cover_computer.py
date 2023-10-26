import tqdm

from rasterio.features import shapes
from tqdm import tqdm

from shapely.geometry import shape

from cover import Cover


def build(data, transform):
    shapes_gen = shapes(data, transform=transform)
    all_covers = [Cover(shape(s), v) for s, v in tqdm(shapes_gen, desc="Building covers")]
    return all_covers

def rebuild(covers):
    for c in tqdm(range(len(covers)), desc="Rebulding covers"):
        cover = covers[c]
        cover.rebuild()