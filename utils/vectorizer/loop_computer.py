from loop import Loop


def build(areas):
    all_loops = []
    loop_count = 0

    for i in range(len(areas)):
        area = areas[i]

        exterior = Loop(loop_count, area.polygon.exterior)
        loop_count += 1

        interiors = [
            Loop(loop_count + j, l) for j, l
            in enumerate(area.polygon.interiors)
        ]
        loop_count += len(area.polygon.interiors)

        area.exterior = exterior
        area.interiors = interiors

        all_loops.extend([exterior] + interiors)

    return all_loops


def rebuild(loops):
    for l in range(len(loops)):
        loop = loops[l]
        loop.rebuild()
