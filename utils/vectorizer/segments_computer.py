from intersections_computer import compute_intersections
from cutpoints_computer import compute_cutpoints
from references_computer import compute_references


def build(loops):
    compute_intersections(loops)
    compute_cutpoints(loops)
    compute_references(loops)

    segments = []
    for l in range(len(loops)):
        loop = loops[l]
        for segment in loop.segments:
            if loop.idx == segment.reference.loop.idx:
                segments.append(segment)
    return segments


def update(segments, function):
    for segment in segments:
        modified_line = function(segment.modified_line)
        segment.modified_line = modified_line
