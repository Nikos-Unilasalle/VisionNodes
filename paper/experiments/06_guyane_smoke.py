"""
06_guyane_smoke.py
==================

Smoke-test data availability over the Sinnamary basin, French Guiana.

AOI rough envelope (lon/lat WGS84):
  coast (mangrove aval): -53.10, 5.10  →  -52.50, 5.40   (~60 km × 35 km)
  upstream (orpaillage): -53.30, 4.50  →  -52.50, 5.30   (~90 km × 90 km)

Checks:
  1. Microsoft Planetary Computer  — Sentinel-1 RTC STAC query
  2. Microsoft Planetary Computer  — Sentinel-2 L2A STAC query
  3. Microsoft Planetary Computer  — MapBiomas LULC collection (if available)
  4. Global Mangrove Watch          — direct HTTP test (Zenodo / WCMC mirror)
  5. Hub'Eau Naïades                — station list within Guyane bbox
  6. Optional: WWF Guianas orpaillage map (manual URL test)

Goal: confirm gratuit access + non-empty result for 2018-2024 window.
Output: paper/experiments/out/guyane_smoke.json with per-source status.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
REPORT = OUT / "guyane_smoke.json"

# ── AOIs ───────────────────────────────────────────────────────────────────
BBOX_COAST  = [-53.10, 5.10, -52.50, 5.40]   # mangrove aval Kourou-Iracoubo
BBOX_UPSTRM = [-53.30, 4.50, -52.50, 5.30]   # bassin Sinnamary
BBOX_ALL    = [-53.30, 4.50, -52.50, 5.40]   # union
DATE_RANGE  = "2023-01-01/2023-12-31"


def section(title: str):
    print(f"\n=== {title} ===", flush=True)


def check_planetary_s1() -> dict:
    section("1. Planetary Computer — Sentinel-1 RTC")
    try:
        import pystac_client
        import planetary_computer
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )
        search = catalog.search(
            collections=["sentinel-1-rtc"],
            bbox=BBOX_ALL,
            datetime=DATE_RANGE,
            limit=200,
        )
        items = list(search.items())
        if not items:
            return {"ok": False, "reason": "no items"}
        sample = items[0]
        assets = list(sample.assets.keys())
        return {
            "ok": True,
            "n_items": len(items),
            "first_date": str(sample.datetime),
            "assets": assets,
            "polarizations": [a for a in assets if a in ("vv", "vh", "hh", "hv")],
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def check_planetary_s2() -> dict:
    section("2. Planetary Computer — Sentinel-2 L2A")
    try:
        import pystac_client
        import planetary_computer
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )
        # query with cloud < 30 — Guyane is very cloudy
        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=BBOX_ALL,
            datetime=DATE_RANGE,
            query={"eo:cloud_cover": {"lt": 30}},
            limit=200,
        )
        items = list(search.items())
        n_low_cloud = len([i for i in items if i.properties.get("eo:cloud_cover", 100) < 10])
        return {
            "ok": len(items) > 0,
            "n_items_lt30pct_cloud": len(items),
            "n_items_lt10pct_cloud": n_low_cloud,
            "first_date": str(items[0].datetime) if items else None,
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def check_planetary_mapbiomas() -> dict:
    section("3. Planetary Computer — collections containing MapBiomas/io-lulc")
    try:
        import pystac_client
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
        )
        collections = list(catalog.get_collections())
        matches = [
            c.id for c in collections
            if any(k in c.id.lower() for k in ("mapbiomas", "io-lulc", "lulc", "esa-cci-lc", "esa-worldcover"))
        ]
        return {"ok": len(matches) > 0, "candidates": matches}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def check_global_mangrove_watch() -> dict:
    section("4. Global Mangrove Watch — direct download test")
    import requests
    # GMW v3 hosted on Zenodo
    urls = [
        "https://zenodo.org/records/6894273",                       # GMW v3 landing
        "https://data.unep-wcmc.org/datasets/45",                   # WCMC mirror
    ]
    out = {"ok": False, "tested": []}
    for u in urls:
        try:
            r = requests.head(u, timeout=15, allow_redirects=True)
            out["tested"].append({"url": u, "status": r.status_code})
            if r.status_code < 400:
                out["ok"] = True
        except Exception as e:
            out["tested"].append({"url": u, "error": str(e)[:120]})
    return out


def check_naiades_guyane() -> dict:
    section("5. Hub'Eau Naïades — stations in Guyane bbox")
    import requests
    # Hub'Eau Naïades stations endpoint
    url = "https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/station_pc"
    params = {
        "bbox": f"{BBOX_ALL[0]},{BBOX_ALL[1]},{BBOX_ALL[2]},{BBOX_ALL[3]}",
        "format": "json",
        "size": 1000,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "body": r.text[:200]}
        j = r.json()
        stations = j.get("data", []) or []
        return {
            "ok": len(stations) > 0,
            "n_stations": len(stations),
            "sample": [
                {
                    "code": s.get("code_station"),
                    "name": s.get("libelle_station"),
                    "lat": s.get("coordonnee_y") or s.get("lat"),
                    "lon": s.get("coordonnee_x") or s.get("lon"),
                }
                for s in stations[:5]
            ],
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def check_naiades_turbidity_guyane() -> dict:
    section("6. Hub'Eau Naïades — turbidity measurements in Guyane")
    import requests
    url = "https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/analyse_pc"
    params = {
        "bbox": f"{BBOX_ALL[0]},{BBOX_ALL[1]},{BBOX_ALL[2]},{BBOX_ALL[3]}",
        "code_parametre": "1295",   # turbidité formazine NTU
        "date_debut_prelevement": "2018-01-01",
        "date_fin_prelevement": "2024-12-31",
        "format": "json",
        "size": 5000,
    }
    try:
        r = requests.get(url, params=params, timeout=60)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "body": r.text[:200]}
        j = r.json()
        rows = j.get("data", []) or []
        if not rows:
            return {"ok": False, "reason": "0 rows"}
        # cheap aggregate
        vals = [
            r.get("resultat") for r in rows
            if isinstance(r.get("resultat"), (int, float))
        ]
        years = sorted({(r.get("date_prelevement") or "")[:4] for r in rows} - {""})
        return {
            "ok": True,
            "n_rows": len(rows),
            "n_stations": len({r.get("code_station") for r in rows}),
            "years": years,
            "value_min": min(vals) if vals else None,
            "value_max": max(vals) if vals else None,
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)[:200]}


def check_mapbiomas_direct() -> dict:
    section("7. MapBiomas Amazonia — collection landing page")
    import requests
    urls = [
        "https://amazonia.mapbiomas.org/",
        "https://storage.googleapis.com/mapbiomas-public/initiatives/amazonia/collection5/",
    ]
    out = {"ok": False, "tested": []}
    for u in urls:
        try:
            r = requests.head(u, timeout=15, allow_redirects=True)
            out["tested"].append({"url": u, "status": r.status_code})
            if r.status_code < 400:
                out["ok"] = True
        except Exception as e:
            out["tested"].append({"url": u, "error": str(e)[:120]})
    return out


def main():
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bbox": {"coast": BBOX_COAST, "upstream": BBOX_UPSTRM, "all": BBOX_ALL},
        "date_range": DATE_RANGE,
        "checks": {},
    }

    report["checks"]["s1_rtc_planetary"]      = check_planetary_s1()
    report["checks"]["s2_l2a_planetary"]      = check_planetary_s2()
    report["checks"]["planetary_lulc_collections"] = check_planetary_mapbiomas()
    report["checks"]["global_mangrove_watch"] = check_global_mangrove_watch()
    report["checks"]["naiades_stations"]      = check_naiades_guyane()
    report["checks"]["naiades_turbidity"]     = check_naiades_turbidity_guyane()
    report["checks"]["mapbiomas_amazonia"]    = check_mapbiomas_direct()

    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {REPORT}")

    # Console summary
    print("\n=== SUMMARY ===")
    for k, v in report["checks"].items():
        ok = "✓" if v.get("ok") else "✗"
        extra = ""
        if "n_items" in v: extra = f" ({v['n_items']} items)"
        elif "n_stations" in v: extra = f" ({v['n_stations']} stations)"
        elif "n_rows" in v: extra = f" ({v['n_rows']} rows)"
        elif "candidates" in v: extra = f" → {v['candidates']}"
        print(f"  {ok}  {k}{extra}")


if __name__ == "__main__":
    main()
