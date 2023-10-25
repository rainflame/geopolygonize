from loop import Loop

    
def build(covers):
    all_loops = []
    loop_count = 0

    for c in range(len(covers)):
        cover = covers[c]

        exterior_idx = loop_count
        exterior = Loop(exterior_idx, cover.polygon.exterior)
        loop_count += 1

        interior_idxes = list(range(loop_count, loop_count + len(cover.polygon.interiors)))
        interiors = [Loop(interior_idxes[i], l) for i, l in enumerate(cover.polygon.interiors)]
        loop_count += len(cover.polygon.interiors)

        cover.exterior = exterior
        cover.interiors = interiors

        loops = [l for l in [exterior] + interiors]
        all_loops.extend(loops)

    return all_loops

def rebuild(loops):
    for l in range(len(loops)):
        loop = loops[l]
        loop.rebuild()