import numpy as np

# https://stackoverflow.com/a/47255374
def chaikins_corner_cutting(coords, refinements=5):
    if not coords or len(coords) == 0:
        return coords
    
    coords = np.array(coords)

    for _ in range(refinements):
        L = coords.repeat(2, axis=0)
        R = np.empty_like(L)
        R[0] = L[0]
        R[2::2] = L[1:-1:2]
        R[1:-1:2] = L[2::2]
        R[-1] = L[-1]
        coords = L * 0.75 + R * 0.25

    return coords