# -*- coding: utf-8 -*-
"""Widen the map window to the full COP30 tile so the Mahaweli and Amban Ganga
trunks -- and every basin confluence -- actually fall inside the map."""
import base64, json, os
import numpy as np
from osgeo import gdal
gdal.UseExceptions()
SC = os.path.dirname(os.path.abspath(__file__))
DEM = r"C:\Users\thush\OneDrive\Desktop\Knuckles\DEM\Knuckles_COP30_SLD99_30m.tif"

data = json.load(open(os.path.join(SC, "knuckles_data.json")))
old = data["grid"]
oOX, oOY = old["ox"], old["oy"]

ds = gdal.Open(DEM); gt = ds.GetGeoTransform(); band = ds.GetRasterBand(1)
STEP = 2
W, H = ds.RasterXSize // STEP, ds.RasterYSize // STEP
CELL = gt[1] * STEP
OX, OY = gt[0], gt[3]
print("new grid %dx%d  cell=%.0f m  x %.0f..%.0f  y %.0f..%.0f  (%.1f x %.1f km)"
      % (W, H, CELL, OX, OX + W*CELL, OY - H*CELL, OY, W*CELL/1000, H*CELL/1000))

elev = band.ReadAsArray(0, 0, W*STEP, H*STEP, buf_xsize=W, buf_ysize=H,
                        resample_alg=gdal.GRIORA_Average).astype(np.float32)
nod = band.GetNoDataValue()
if nod is not None:
    elev[elev == nod] = np.nan
bad = ~np.isfinite(elev) | (elev < -100)
elev[bad] = 0.0
elev = np.round(elev).astype(np.int16)
print("elev %d..%d  (%d bad cells zeroed)" % (elev.min(), elev.max(), int(bad.sum())))

data["grid"] = {"w": W, "h": H, "cell": CELL, "ox": OX, "oy": OY,
                "zmin": int(elev.min()), "zmax": int(elev.max())}
data["elev"] = base64.b64encode(elev.tobytes()).decode("ascii")

# every stored point is metres from the old NW corner: a pure translation
dx, dy = oOX - OX, OY - oOY
print("shifting stored points by dx=%+.0f dy=%+.0f m" % (dx, dy))
n = 0
for key in ("peaks", "falls", "villages", "attractions"):
    for p in data.get(key, []):
        p["x"] = round(p["x"] + dx, 1); p["y"] = round(p["y"] + dy, 1); n += 1
print("translated %d points" % n)
for k in ("rings", "trunks", "tribs", "trunkLabels", "tribLabels",
          "confluences", "outlets", "stems", "rivers", "ids"):
    data.pop(k, None)
for b in data["basins"]:
    b.pop("rings", None)
json.dump(data, open(os.path.join(SC, "knuckles_data.json"), "w"),
          ensure_ascii=True, separators=(",", ":"))
print("payload %.2f MB (rings/rivers cleared, will be rebuilt on the new grid)"
      % (os.path.getsize(os.path.join(SC, "knuckles_data.json"))/1e6))
