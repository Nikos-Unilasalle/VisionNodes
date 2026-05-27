# Sinnamary AOI — Phase 1

WGS84 lon/lat bounding boxes for Phase 1 (mangrove dynamics + upstream orpaillage).

## Key landmarks

| Site | Lon | Lat | Role |
|---|---|---|---|
| Kourou (CSG) | -52.65 | 5.16 | east coast anchor |
| Sinnamary (town) | -52.95 | 5.38 | river mouth, town |
| Iracoubo | -53.20 | 5.48 | west coast anchor |
| Petit-Saut (hydro dam) | -53.05 | 5.07 | hydrological pivot |
| Saut Tigre | -53.10 | 4.65 | upstream orpaillage zone |

## BBOX

```python
# Aval — mangrove coast + Sinnamary estuary
BBOX_AVAL    = [-53.25,  5.05, -52.60,  5.50]   # ~72 km × 50 km

# Amont — Sinnamary watershed (Petit-Saut reservoir + tributaries + Saut Tigre orpaillage)
BBOX_AMONT   = [-53.30,  4.40, -52.70,  5.20]   # ~67 km × 89 km

# Union — single bbox for joint fetch
BBOX_UNION   = [-53.30,  4.40, -52.60,  5.50]   # ~78 km × 122 km ≈ 9500 km²
```

## ASCII map

```
                 lon   -53.30          -52.95          -52.60
            lat ┌────────────────────────────────────────┐
          5.50  │           IRACOUBO ●     Atlantic       │
                │  ╔══════════════════════════════╗       │
                │  ║      MANGROVE COAST         ║       │
                │  ║   (aval, ~3600 km²)         ║       │
          5.20  │  ╚══════╤═══════════════════════╝  KOUROU●
                │         │  Sinnamary estuary       │   │
          5.05  │         │  ●Sinnamary town        │   │
                │  ╔══════╧══════════════════════╗       │
                │  ║                              ║       │
          5.00  │  ║      Petit-Saut reservoir   ║       │
                │  ║      ● (hydro dam)           ║       │
                │  ║                              ║       │
                │  ║      WATERSHED               ║       │
          4.65  │  ║      (amont, ~6000 km²)     ║       │
                │  ║      ● Saut Tigre            ║       │
          4.40  │  ╚══════════════════════════════╝       │
                └────────────────────────────────────────┘
```

## Sentinel-2 / Sentinel-1 tile coverage

- S2 MGRS tiles: **22NCH**, **22NDH** (both 100×100 km, covering the union)
- S1 relative orbits ascending: 156, descending: 105 (typical pairings for this latitude)

## Naïades stations within BBOX_UNION (Phase 1 ground truth)

From smoke test 06_guyane_smoke.py (313 turbidity rows, 16 stations):

- 09110503 Crique Petit
- 09110984 Crique Eau Claire
- 09120711 Crique Piste Saint-Élie
- 09121003 Crique Humus
- 09128002 Crique Paracou
- (+ 11 others — see raw output)

All "Criques" = small forested headwater streams → perfect downstream indicators
of upstream orpaillage activity.
