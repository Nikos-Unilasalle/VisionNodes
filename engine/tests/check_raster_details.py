import os
import glob
import numpy as np
import rasterio

cache_dir = '/home/colonel/Bureau/VNStudio/engine/plugins/copernicus_cache'
tifs = glob.glob(os.path.join(cache_dir, 'stac_*.tif'))
tifs.sort(key=os.path.getmtime, reverse=True)

if len(tifs) < 2:
    print("Not enough stac_*.tif files in cache.")
    exit(0)

# LULC 2024 (latest)
t1_path = tifs[0]
# LULC 2017 (second latest)
t0_path = tifs[1]

print(f"t0 (2017): {os.path.basename(t0_path)}")
print(f"t1 (2024): {os.path.basename(t1_path)}")

with rasterio.open(t0_path) as src0, rasterio.open(t1_path) as src1:
    b0 = src0.read(1)
    b1 = src1.read(1)
    
    print("\nt0 class counts:")
    for val in np.unique(b0):
        print(f"  Class {val}: {np.sum(b0 == val)} pixels")
        
    print("\nt1 class counts:")
    for val in np.unique(b1):
        print(f"  Class {val}: {np.sum(b1 == val)} pixels")
        
    # Check Forest (2) -> Bare Ground (8) or Rangeland (11)
    defor = (b0 == 2) & ((b1 == 8) | (b1 == 11))
    print(f"\nDeforestation pixels (Forest 2 -> Bare 8 or Range 11): {np.sum(defor)}")
    
    # Calculate distance to water (1)
    water_mask = (b1 == 1).astype(np.uint8)
    print(f"Water pixels in t1: {np.sum(water_mask)}")
    
    if np.any(water_mask):
        import cv2
        land_mask = (b1 != 1).astype(np.uint8)
        dist_pixels = cv2.distanceTransform(land_mask, cv2.DIST_L2, 5)
        dist_meters = dist_pixels * 10.0  # Let's assume 10m resolution or whatever is actual
        
        # Check defor pixels close to water
        defor_near_water = defor & (dist_meters <= 300.0)
        print(f"Deforestation pixels close to water (<= 300m): {np.sum(defor_near_water)}")
        
        # Check defor pixels close to water (<= 500m)
        defor_near_water_500 = defor & (dist_meters <= 500.0)
        print(f"Deforestation pixels close to water (<= 500m): {np.sum(defor_near_water_500)}")
        
        # Let's check distance stats on defor pixels
        if np.any(defor):
            dists_defor = dist_meters[defor]
            print(f"Min dist to water for defor: {dists_defor.min():.1f}m")
            print(f"Mean dist to water for defor: {dists_defor.mean():.1f}m")
            print(f"Max dist to water for defor: {dists_defor.max():.1f}m")
            print(f"Percentiles of distance for defor:")
            for p in [5, 10, 25, 50, 75, 90]:
                print(f"  {p}%: {np.percentile(dists_defor, p):.1f}m")
