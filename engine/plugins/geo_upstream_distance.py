"""
geo_upstream_distance.py — Hydrological upstream distance along the drainage network.

Walks UPSTREAM from seed points (e.g. active mining sites) following the reverse
of the D8 flow direction, accumulating along-channel distance. Models the way a
displaced mining crew moves up a river to find a new site (typically ~40 km).

Unlike Euclidean distance (geo_distance_to_class), distance here is measured along
the river network, so it respects the real travel constraint by pirogue.

D8 encoding (from geo_dem_flow): 0=N 1=NE 2=E 3=SE 4=S 5=SW 6=W 7=NW, -1=sink.
The drainage upstream of any point forms a tree, so each reached cell has a unique
path back to a seed — a simple BFS accumulating step length gives exact distance.
"""
import numpy as np
import cv2
import base64
from collections import deque

from registry import vision_node, NodeProcessor

_NOTIF = 'upstream_distance'

# D8 neighbour offsets, same order/encoding as geo_dem_flow
_D8 = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]


def _band_2d(geo: dict) -> np.ndarray:
    """Extract the first band as a 2D array from a geo dict."""
    bands = np.asarray(geo['bands'])
    return bands[0] if bands.ndim == 3 else bands


@vision_node(
    type_id='geo_upstream_distance',
    label='Upstream Distance',
    category='geography',
    icon='Waves',
    description=(
        "Computes along-river distance UPSTREAM from seed sites, following the "
        "reverse D8 flow direction. Models a displaced mining crew moving up the "
        "river network (default reach 40 km). Outputs the reachable river search "
        "zone, a distance raster (metres), and a preview. Connect flow_dir from "
        "geo_dem_flow and a seed mask (e.g. OAM active sites)."
    ),
    inputs=[
        {'id': 'flow_dir', 'color': 'geotiff', 'label': 'Flow direction (D8, from geo_dem_flow)'},
        {'id': 'seed',     'color': 'mask',    'label': 'Seed sites (start points)'},
        {'id': 'flow_acc', 'color': 'geotiff', 'label': 'Flow accumulation (optional, defines channels)'},
    ],
    outputs=[
        {'id': 'search_zone', 'color': 'mask',    'label': 'Upstream search zone (mask)'},
        {'id': 'distance',    'color': 'geotiff', 'label': 'Upstream distance (m, -1 = unreachable)'},
        {'id': 'preview',     'color': 'image',   'label': 'Preview (RGB)'},
        {'id': 'stats',       'color': 'dict',    'label': 'Stats (dict)'},
    ],
    params=[
        {'id': 'max_distance_km', 'type': 'float', 'default': 40.0, 'min': 1.0, 'max': 200.0,
         'label': 'Max upstream reach (km)'},
        {'id': 'channel_min_acc', 'type': 'int', 'default': 500, 'min': 0, 'max': 100000,
         'label': 'Channel threshold (flow_acc cells, 0 = all upstream)'},
        {'id': 'pixel_size_m', 'type': 'float', 'default': 30.0, 'min': 0.1, 'max': 1000.0,
         'label': 'Pixel size fallback (m, if no transform)'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=260, min_height=200,
)
class UpstreamDistanceNode(NodeProcessor):

    def process(self, inputs: dict[str, object], params: dict[str, object]) -> dict[str, object]:
        flow_geo = inputs.get('flow_dir')
        seed_in = inputs.get('seed')

        if not isinstance(flow_geo, dict) or 'bands' not in flow_geo:
            return {'search_zone': None, 'distance': None, 'preview': None, 'stats': None}
        if seed_in is None:
            return {'search_zone': None, 'distance': None, 'preview': None, 'stats': None}

        fdir = _band_2d(flow_geo).astype(np.int32)
        H, W = fdir.shape

        # ── Seed mask → start cells ──────────────────────────────────────────
        if isinstance(seed_in, dict) and 'bands' in seed_in:
            seed_2d = _band_2d(seed_in)
        else:
            seed_2d = seed_in
        if seed_2d.ndim == 3:
            seed_2d = cv2.cvtColor(seed_2d, cv2.COLOR_BGR2GRAY)
        if seed_2d.shape != (H, W):
            seed_2d = cv2.resize(seed_2d, (W, H), interpolation=cv2.INTER_NEAREST)
        seed_mask = seed_2d > 0

        # ── Pixel size (metres) from transform, fallback to param ────────────
        pixel_size = float(params.get('pixel_size_m', 30.0))
        transform = flow_geo.get('transform')
        if transform is not None:
            try:
                pixel_size = abs(float(transform.a))
            except (AttributeError, TypeError, ValueError):
                pass

        max_distance_m = float(params.get('max_distance_km', 40.0)) * 1000.0
        channel_min_acc = int(params.get('channel_min_acc', 500))

        # ── Optional channel constraint from flow accumulation ───────────────
        acc_geo = inputs.get('flow_acc')
        channels = None
        if channel_min_acc > 0 and isinstance(acc_geo, dict) and 'bands' in acc_geo:
            acc = _band_2d(acc_geo).astype(np.float32)
            if acc.shape != (H, W):
                acc = cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)
            channels = acc >= channel_min_acc

        # ── Reverse-D8 BFS upstream ──────────────────────────────────────────
        # neighbour n is upstream of c if fdir[n] points toward c.
        # the D8 index at n pointing to c equals the index of offset (c - n).
        offset_to_idx = {off: i for i, off in enumerate(_D8)}
        step_len = [pixel_size * (np.sqrt(2.0) if abs(dr) + abs(dc) == 2 else 1.0)
                    for dr, dc in _D8]

        dist = np.full((H, W), -1.0, dtype=np.float32)
        q: deque = deque()
        seed_count = 0
        for r, c in zip(*np.nonzero(seed_mask)):
            dist[r, c] = 0.0
            q.append((int(r), int(c)))
            seed_count += 1

        if seed_count == 0:
            return {'search_zone': None, 'distance': None, 'preview': None, 'stats': None}

        self.report_progress(0.2, f"Upstream Distance: remontée depuis {seed_count} sites…")

        processed = 0
        while q:
            r, c = q.popleft()
            d_here = dist[r, c]
            for i, (dr, dc) in enumerate(_D8):
                nr, nc = r - dr, c - dc  # candidate upstream neighbour
                if nr < 0 or nr >= H or nc < 0 or nc >= W:
                    continue
                if dist[nr, nc] >= 0.0:
                    continue  # already reached (tree → unique path)
                # does n drain into c? fdir[n] must point from n to c = offset (r-nr, c-nc)
                idx = offset_to_idx.get((r - nr, c - nc))
                if idx is None or int(fdir[nr, nc]) != idx:
                    continue
                nd = d_here + step_len[i]
                if nd > max_distance_m:
                    continue
                dist[nr, nc] = nd
                q.append((nr, nc))

            processed += 1
            if processed % 50000 == 0:
                self.report_progress(0.5, f"Upstream Distance: {processed} cellules parcourues…")

        # ── Build outputs ────────────────────────────────────────────────────
        reached = dist >= 0.0
        if channels is not None:
            search_zone = reached & channels
        else:
            search_zone = reached.copy()
        # Seeds themselves are the source, not search candidates
        search_zone[seed_mask] = False

        search_u8 = (search_zone.astype(np.uint8)) * 255

        # Preview: distance gradient (JET) over the search zone, seeds in cyan
        norm = np.zeros((H, W), dtype=np.uint8)
        if max_distance_m > 0:
            norm = np.clip(dist / max_distance_m * 255.0, 0, 255).astype(np.uint8)
        preview = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
        preview[~reached] = [0, 0, 0]
        if channels is not None:
            preview[reached & ~channels] = [40, 40, 40]  # upstream but off-channel = dark grey
        preview[seed_mask] = [255, 255, 0]               # seeds = cyan

        # ── Stats ────────────────────────────────────────────────────────────
        total_px = float(H * W)
        reached_px = int(reached.sum())
        zone_px = int(search_zone.sum())
        max_reached_km = float(dist[reached].max() / 1000.0) if reached_px else 0.0
        stats_dict = {
            'seed_sites': seed_count,
            'reached_cells': reached_px,
            'search_zone_cells': zone_px,
            'search_zone_pct': round(zone_px / total_px * 100.0, 3),
            'max_upstream_km': round(max_reached_km, 2),
            'pixel_size_m': round(pixel_size, 2),
        }

        distance_geo = {
            **flow_geo,
            'bands': dist[np.newaxis].astype(np.float32),
            'count': 1,
            'dtype': 'float32',
            'band_names': ['upstream_distance_m'],
            '_source': 'upstream_distance',
            '_bands': ['upstream_distance_m'],
            'preview': preview,
        }

        # Thumbnail
        h, w = preview.shape[:2]
        sc = min(1.0, 120 / h, 120 / w)
        thumb = cv2.resize(preview, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        self.report_progress(1.0, f"Upstream Distance: zone de recherche {zone_px:,} px ✓")

        return {
            'search_zone': search_u8,
            'distance': distance_geo,
            'preview': preview,
            'stats': stats_dict,
            '_thumb': thumb_b64,
        }
