from collections import deque

import numpy as np

import rasterio

MIN_BLOB_SIZE = 5

# Get the eight neighbors of a pixel.
def get_neighbors(pixel):
    (x, y) = pixel
    sides = [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]
    diagonals = [(x-1, y-1), (x-1, y+1), (x+1, y-1), (x+1, y+1)]
    return sides + diagonals

# Return most common color from given list of colors
# or -1 if there is a tie.
def get_most_common_color(colors):
    count = {}
    for c in colors:
        count[c] = count.get(c, 0) + 1
    distribution = list(count.items())
    distribution.sort(key=lambda x: x[1])

    if len(distribution) == 0: return -1
    max1 = distribution[-1][0]
    if len(distribution) == 1: return max1
    max2 = distribution[-2][0]
    if max1 == max2: return -1
    return max1

# Return list of determinate colors from the selection.
def get_colors_from_selection(raster, selection):
    colors = []
    for pixel in selection:
        if pixel[0] < 0 or pixel[0] >= raster.shape[0]: continue
        if pixel[1] < 0 or pixel[1] >= raster.shape[1]: continue
        x, y = pixel
        if raster[x, y] != -1:
            colors.append(raster[pixel])
    return colors

# Increase the selection by one pixel outward in all directions.
def widen_selection(selection):
    wider_selection = []
    for s in selection:
        wider_selection += get_neighbors(s)
    return wider_selection

def choose_color(raster, pixel):
    # The selection may (eventually) include the pixel or other members of the blob,
    # but they will have a value of -1 and be ignored.
    # The selection may include pixels out of the bounds, but they will be ignored.
    selection = get_neighbors(pixel)
    while(True):
        colors = get_colors_from_selection(raster, selection)
        chosen_color = get_most_common_color(colors)
        if chosen_color != -1:
            break

        wider_selection = widen_selection(selection)
        if wider_selection == selection:
            raise Exception('No color chosen for pixel')
        selection = wider_selection
    return chosen_color


# Return if a pixel is completely surrounded by pixels in the blob.
def is_inner_pixel(blob, pixel):
    for neighbor in get_neighbors(pixel):
        if neighbor not in blob:
            return False
    return True

# Return set of pixels in outer ring of blob.
def get_outer_ring(blob):
    ring = []
    for pixel in blob:
        if not is_inner_pixel(blob, pixel):
            ring.append(pixel)
    return set(ring)

# Color the blob -1 so it is clear the color is indeterminate.
def negate_blob(raster, blob):
    for pixel in blob:
        x, y = pixel
        raster[x, y] = -1
    return raster

# Fill blob iteratively, going from out to in.
def fill_blob(raster, blob):
    while(True):
        ring = get_outer_ring(blob)
        if len(ring) == 0:
            break

        decision = []
        for pixel in ring:
            color = choose_color(raster, pixel)
            decision.append((pixel, color))

        for (pixel, color) in decision:
            x, y = pixel
            raster[x, y] = color

        blob = blob.difference(ring)
        
    return raster

def collect_blobs(blob_raster):
    blobs = {}
    for x in range(blob_raster.shape[0]):
        for y in range(blob_raster.shape[1]):
            blob = blob_raster[x, y]
            blobs[blob] = blobs.get(blob, set()).union(set([(x, y)]))
    return blobs

def identify_blobs_by_pixel(raster):
    # 0 means the blob is unmarked.
    blob_raster = np.zeros_like(raster, dtype=np.int32)

    def bfs(pixel, color, label):
        x, y = pixel

        queue = deque([(x, y)])
        while queue:
            i, j = queue.popleft()
            if i < 0 or i >= blob_raster.shape[0] or j < 0 or j >= blob_raster.shape[1]: continue
            if raster[i, j] != color: continue
            if blob_raster[i, j] != 0: continue # visited
            
            blob_raster[i, j] = label # mark as visited
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0: continue
                    if dx == 0 or dy == 0:
                        queue.append((i + dx, j + dy))

    label = 1
    for i in range(blob_raster.shape[0]):
        for j in range(blob_raster.shape[1]):
            if blob_raster[i, j] == 0:
                bfs((i, j), raster[i, j], label)
                label += 1

    return blob_raster

# Return list of blobs, where each blob is represented as a set of pixels.
def identify_blobs(raster):
    blob_raster = identify_blobs_by_pixel(raster)

    blobs = collect_blobs(blob_raster)
    return blobs

def blobify(original):
    raster = original.copy()

    blobs = identify_blobs(raster)

    small_blobs = [blob_pixels for (_blob_id, blob_pixels) in blobs.items() if len(blob_pixels) < MIN_BLOB_SIZE]

    for blob in small_blobs:
        raster = negate_blob(raster, blob)

    for blob in small_blobs:
        raster = fill_blob(raster, blob.copy())

    return raster

def blobify_raster_file(input_filepath, output_filepath):
    band = 1

    with rasterio.open(input_filepath) as src:
        meta = src.meta
        original = src.read(band)

    cleaned = blobify(original)

    with rasterio.open(output_filepath, 'w', **meta) as dst:
        dst.write_band(band, cleaned)