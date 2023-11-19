import random
import numpy as np

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


def show_polygons(polygons, labels=None, color_map=None):
    fig, ax = plt.subplots()

    if labels is None:
        labels = list(range(len(polygons)))
    if color_map is None:
        color_map = generate_color_map(labels)

    for i, p in enumerate(polygons):
        x, y = p.exterior.xy
        ax.plot(x, y, color=color_map[labels[i]])
        for interior in p.interiors:
            x, y = interior.xy
            ax.plot(x, y, color=color_map[labels[i]])

    plt.axis('equal')

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.legend()

    plt.show()


def show_lines(lines, labels=None, color_map=None):
    _fig, ax = plt.subplots()

    if labels is None:
        labels = list(range(len(lines)))
    if color_map is None:
        color_map = generate_color_map(labels)

    for i, l in enumerate(lines):
        x, y = l.xy
        ax.plot(x, y, color=color_map[labels[i]])

    plt.axis('equal')

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.legend()

    plt.show()
