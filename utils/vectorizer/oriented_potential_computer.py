from intersections_computer import compute_intersections
from cutpoints_computer import compute_cutpoints
from references_computer import compute_references


def update(oriented_potentials, function):
    for _key, op in oriented_potentials.items():
        modified_segment = function(op.modified_segment)
        op.modified_segment = modified_segment

def build(loops):
    compute_intersections(loops)
    compute_cutpoints(loops)
    compute_references(loops)

    oriented_potentials = {}
    for l in range(len(loops)):
        loop = loops[l]
        for op in loop.oriented_potentials:
            if loop.idx == op.reference:
                oriented_potentials[op.get_key()] = op
    return oriented_potentials