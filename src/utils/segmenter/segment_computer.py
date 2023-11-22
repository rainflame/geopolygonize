from .intersections_computer import compute_intersections
from .cutpoints_computer import compute_cutpoints
from .references_computer import compute_references


def build(boundaries):
    compute_intersections(boundaries)
    compute_cutpoints(boundaries)
    compute_references(boundaries)

    segments = []
    for b in range(len(boundaries)):
        boundary = boundaries[b]
        for segment in boundary.segments:
            if boundary.idx == segment.reference.boundary.idx:
                segments.append(segment)
    return segments


def update(segments, function):
    for segment in segments:
        modified_line = function(segment.modified_line)
        segment.modified_line = modified_line
