# https://github.com/shapely/shapely/issues/1046

import numpy as np
from shapely import Polygon

EPSILON = 1e-10


def get_angles(vec_1, vec_2):
    """
    return the angle, in degrees, between two vectors
    """

    dot = np.dot(vec_1, vec_2)
    det = np.cross(vec_1, vec_2)
    angle_in_rad = np.arctan2(det, dot)
    return np.degrees(angle_in_rad)


def simplify_by_angle(poly_in, deg_tol=1):
    '''Try to remove persistent coordinate points that remain after
    simplify, convex hull, or something, etc. with some trig instead

    poly_in: shapely Polygon
    deg_tol: degree tolerance for comparison between successive vectors
    '''
    ext_poly_coords = poly_in.exterior.coords[:]
    vector_rep = np.diff(ext_poly_coords, axis=0)
    num_vectors = len(vector_rep)
    angles_list = []
    for i in range(0, num_vectors):
        angles_list.append(np.abs(get_angles(
            vector_rep[i],
            vector_rep[(i + 1) % num_vectors])
        ))

    # get mask satisfying tolerance
    thresh_vals_by_deg = np.where(np.array(angles_list) > deg_tol)

    new_idx = list(thresh_vals_by_deg[0] + 1)
    new_vertices = [ext_poly_coords[idx] for idx in new_idx]

    return Polygon(new_vertices)


def clean_polygon(polygon):
    return simplify_by_angle(polygon, EPSILON)
