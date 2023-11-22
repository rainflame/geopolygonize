from .boundary import Boundary


def build(areas):
    all_boundaries = []
    boundary_count = 0

    for i in range(len(areas)):
        area = areas[i]

        exterior = Boundary(boundary_count, area.polygon.exterior)
        boundary_count += 1

        interiors = [
            Boundary(boundary_count + j, l) for j, l
            in enumerate(area.polygon.interiors)
        ]
        boundary_count += len(area.polygon.interiors)

        area.exterior = exterior
        area.interiors = interiors

        all_boundaries.extend([exterior] + interiors)

    return all_boundaries


def rebuild(boundaries):
    for b in range(len(boundaries)):
        boundary = boundaries[b]
        boundary.rebuild()
