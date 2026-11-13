"""Choice of the metaxylem anchor between two searches of the vessel ring.

Ring A is searched inside the stele, located beforehand by the jump of cell size along the radius
(the template as it is). Ring B is searched over the whole section and is the innermost evenly
spaced ring of large lumens (geom_ring_pattern, 'Innermost ring of large objects'): it needs no
stele, so it still works when stele and cortex cells have similar sizes, and it does not take a
ring of aerenchyma lacunae, which lies further out in the cortex, for the vessels.

Each ring is judged on the vessels that survive the cleaning (blob filter, clean_vessels), not
on its raw members: a ring left with fewer than MIN_VESSELS vessels is not plausible.
The most plausible of the two is kept:
  - only one found: that one;
  - same circle (centres and radii within SAME_CIRCLE of the radius): the one with more members,
    which recovers a vessel that the stele outline clipped; on a tie, A;
  - different circles: the more evenly spaced (angular regularity); within REGULARITY_MARGIN, A.
"""
import copy

SAME_CIRCLE = 0.15          # centres and radii within 15 % of the radius: the same ring
REGULARITY_MARGIN = 0.05    # a different ring must be clearly more regular to replace A
STELE_FED = ('mx_and', 'st_lum2', 'mx_region')   # template nodes that restrict candidates to the stele
INNERMOST_LARGE = 1         # geom_ring_pattern 'select' option
MIN_VESSELS = 5             # the method needs a ring of at least five metaxylem vessels


def whole_section_template(vn):
    """Copy of the template where vessel candidates come from the whole section and the ring
    pattern keeps the innermost ring of large lumens."""
    out = copy.deepcopy(vn)
    for e in out['edges']:
        if e['source'] == 'stele' and e['target'] in STELE_FED:
            e['source'] = 'section'
    for n in out['nodes']:
        if n['id'] == 'mx_ring':
            n['data']['params']['select'] = INNERMOST_LARGE
    return out


def ring_of(pipe, n_vessels):
    """The ring found by one run (cleaned vessel count, centre, radius, regularity), or None."""
    r = pipe.get('mx_ring') or {}
    if n_vessels < MIN_VESSELS or r.get('radius') is None:
        return None
    return {'count': int(n_vessels), 'cx': float(r['center_x']), 'cy': float(r['center_y']),
            'radius': float(r['radius']), 'regularity': float(r.get('regularity') or 0.0)}


def same_circle(a, b):
    scale = max(a['radius'], b['radius'], 1e-9)
    centre = ((a['cx'] - b['cx']) ** 2 + (a['cy'] - b['cy']) ** 2) ** 0.5
    return centre <= SAME_CIRCLE * scale and abs(a['radius'] - b['radius']) <= SAME_CIRCLE * scale


def choose(a, b):
    """('stele' | 'whole' | None, reason)."""
    if a is None and b is None:
        return None, 'no ring in either search'
    if b is None:
        return 'stele', 'only the stele search found a ring'
    if a is None:
        return 'whole', 'only the whole-section search found a ring'
    if same_circle(a, b):
        if b['count'] > a['count']:
            return 'whole', 'same ring, more vessels over the whole section'
        return 'stele', 'same ring'
    if b['regularity'] > a['regularity'] + REGULARITY_MARGIN:
        return 'whole', 'different rings, the whole-section one is more regular'
    return 'stele', 'different rings, the stele one is as regular'
