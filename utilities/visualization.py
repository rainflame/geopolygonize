import random
import numpy as np

from matplotlib.path import Path
from matplotlib.collections import PatchCollection
from matplotlib.patches import PathPatch
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


def generate_random_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return (r / 255, g / 255, b / 255)


def generate_n_random_colors(n):
    return [generate_random_color() for _ in range(n)]


def generate_color_map(labels):
    uniq_labels = set(labels)
    n = len(uniq_labels)
    render_colors = generate_n_random_colors(n)
    color_to_render_color = {
        c: render_colors[i] for i, c in enumerate(uniq_labels)
    }
    return color_to_render_color


def get_show_config(data):
    num_unique_values = len(np.unique(data))
    random_colors = np.random.rand(num_unique_values, 3)
    custom_cmap = mcolors.ListedColormap(random_colors)

    min_value = np.min(data)
    max_value = np.max(data)

    return custom_cmap, min_value, max_value


def show_raster(data, cmap, min_value, max_value):
    normalized_data = (data - min_value) / (max_value - min_value)
    colors = cmap(normalized_data)

    plt.imshow(colors, cmap=cmap)
    plt.axis('off')
    plt.show()


def show_polygons(polygons, show=True, labels=None, color_map=None):
    fig, ax = plt.subplots(figsize=(10, 10))

    if labels is None:
        labels = list(range(len(polygons)))
    if color_map is None:
        color_map = generate_color_map(labels)

    for i, polygon in enumerate(polygons):
        color = color_map[labels[i]]
        ps = []
        if polygon.geom_type == "Polygon":
            ps.append(polygon)
        elif polygon.geom_type == "MultiPolygon":
            for p in list(polygon.geoms):
                ps.append(p)

        for p in ps:
            vertices = []
            codes = []
            exterior_vertices = list(p.exterior.coords)
            vertices.extend(exterior_vertices)
            exterior_codes = [Path.MOVETO] \
                + [Path.LINETO] * (len(exterior_vertices) - 1)
            codes.extend(exterior_codes)

            for interior in p.interiors:
                interior_vertices = list(interior.coords)[::-1]
                vertices.extend(interior_vertices)
                interior_codes = [Path.MOVETO] \
                    + [Path.LINETO] * (len(interior_vertices) - 1)
                codes.extend(interior_codes)
        
            path = Path(vertices, codes)
            patch = PathPatch(path, facecolor=color, alpha=0.3)
            ax.add_patch(patch)

    plt.axis('equal')
    if show:
        plt.show()
    return fig


def save_polygons(image_path, polygons, dpi=324, **args):
    fig = show_polygons(polygons, show=False, **args)
    fig.savefig(image_path, dpi=dpi)
