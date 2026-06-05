"""
Génère samples/ocean_temperature.nc — dataset SST pédagogique réaliste.

Inspiré des eaux au large de la Guyane française (rétroflexion du Courant
Nord-Brésil, upwelling côtier). Structure basse-dimension volontaire :
  - EOF1 ≈ cycle saisonnier (mode dominant)
  - EOF2+ ≈ tourbillons mésoéchelle propagatifs
→ idéal pour comparer ACP (linéaire) et U-Net (non-linéaire).

Usage:
    .venv/bin/python engine/tests/make_sample_sst.py
"""
import os
import numpy as np
import pandas as pd
import xarray as xr

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
OUT = os.path.join(_ROOT, 'samples', 'ocean_temperature.nc')

# Grille : 32×32 (multiple de 8 → pas de padding U-Net), 72 pas de 5 jours ≈ 1 an
T, H, W = 72, 32, 32
lat = np.linspace(4.0, 7.1, H).astype('float32')      # Guyane
lon = np.linspace(-54.0, -50.9, W).astype('float32')
time = pd.date_range('2023-01-01', periods=T, freq='5D')

LON, LAT = np.meshgrid(lon, lat)                       # (H, W)

rng = np.random.default_rng(42)

# ── Masque terre : marge continentale au sud-ouest (côte guyanaise) ──────────
# Orientation NW-SE, terre au SW. Seuil calibré pour ~22 % de terre.
coast = (LAT - 4.0) * 1.0 + (LON + 54.0) * 0.55
thresh = np.percentile(coast, 22.0)
land = coast < thresh

# ── Climatologie de base : plus chaud au large (NE), upwelling côtier ────────
dist_coast = np.clip(coast, 0, None)
base = 26.2 + 0.9 * np.tanh(dist_coast * 0.7)          # 26.2 → 27.1 °C

field = np.zeros((T, H, W), dtype='float32')

# 6 tourbillons mésoéchelle aux fréquences/propagations distinctes → la
# variance se répartit sur plusieurs EOF (pas un seul mode dominant).
eddies = [
    # lat0,  lon0,  sign, speed,  radius, freq
    (5.0, -52.0,  1.0, 0.013, 0.55, 1.0),
    (6.0, -52.8, -1.0, 0.009, 0.45, 1.7),
    (5.5, -51.4,  1.0, 0.016, 0.40, 2.3),
    (4.8, -51.8, -1.0, 0.011, 0.50, 0.7),
    (6.3, -51.6,  1.0, 0.008, 0.42, 1.3),
    (5.2, -53.0, -1.0, 0.014, 0.48, 2.9),
]

for t in range(T):
    day = t * 5
    phase = 2 * np.pi * day / 360.0

    # Cycle saisonnier modéré (un mode parmi d'autres) : ±0.35 °C
    seasonal = 0.35 * np.sin(phase - np.pi / 3)
    f = base + seasonal

    # Front méandreux qui migre N-S au fil du temps (mode spatial distinct)
    front_lat = 5.5 + 0.8 * np.sin(phase * 1.5)
    f = f + 0.5 * np.tanh((LAT - front_lat) * 1.2)

    # Tourbillons propagatifs vers le NW (rétroflexion NBC), amplitude forte
    for k, (lat0, lon0, sign, speed, radius, freq) in enumerate(eddies):
        clon = lon0 - speed * day * 30.0
        clat = lat0 + 0.30 * np.sin(phase * freq + k)
        amp  = sign * (0.9 + 0.4 * np.sin(phase * freq + k))
        d2 = ((LAT - clat) ** 2 + (LON - clon) ** 2) / (2 * radius ** 2)
        f = f + amp * np.exp(-d2)

    # Bruit fin
    f = f + rng.normal(0, 0.06, size=(H, W)).astype('float32')
    field[t] = f

# ── Appliquer le masque terre (NaN) ──────────────────────────────────────────
field[:, land] = np.nan

# ── Écrire le NetCDF (CF-ish, 4D avec depth=1 pour ressembler à GLORYS) ──────
da = xr.DataArray(
    field[:, np.newaxis, :, :],                        # (time, depth, lat, lon)
    dims=('time', 'depth', 'latitude', 'longitude'),
    coords={
        'time': time,
        'depth': np.array([0.49], dtype='float32'),
        'latitude': lat,
        'longitude': lon,
    },
    name='thetao',
    attrs={
        'long_name': 'Sea water potential temperature',
        'standard_name': 'sea_water_potential_temperature',
        'units': 'degrees_C',
    },
)
ds = da.to_dataset()
ds.attrs.update({
    'title': 'SST pédagogique — large de la Guyane (jeu synthétique)',
    'source': 'VNStudio teaching sample (synthetic, GLORYS-like)',
    'institution': 'VNStudio',
    'note': 'Donnees synthetiques pour TD oceanographie ML (ACP/AE/U-Net).',
})

os.makedirs(os.path.dirname(OUT), exist_ok=True)
ds.to_netcdf(OUT)
ds.close()

valid = ~np.isnan(field)
print(f"✓ écrit : {OUT}")
print(f"  shape (T,depth,H,W) = {da.shape}")
print(f"  terre : {(~valid[0]).mean():.1%}  |  océan range : "
      f"{np.nanmin(field):.2f} → {np.nanmax(field):.2f} °C")
print(f"  taille fichier : {os.path.getsize(OUT)//1024} KB")
