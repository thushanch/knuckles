# -*- coding: utf-8 -*-
"""Esri World Imagery for the widened AOI, mosaicked straight to disk.

Esri's World Imagery is free to use with attribution; Google's tile endpoints
are not licensed for this, so they are not touched.
"""
import gc, io, json, math, os, threading
import numpy as np, requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from osgeo import gdal, osr
gdal.UseExceptions(); gdal.SetCacheMax(48*1024*1024)
Image.MAX_IMAGE_PIXELS = None

SC = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\thush\OneDrive\Desktop\Knuckles"
Z, TW = 14, 2400
URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
       "World_Imagery/MapServer/tile/{z}/{y}/{x}")
UA = "QGIS-KnucklesStudy/1.0"

g = json.load(open(os.path.join(SC, "knuckles_data.json")))["grid"]
W, H, CELL, X0, Y1 = g["w"], g["h"], g["cell"], g["ox"], g["oy"]
X1, Y0 = X0 + W*CELL, Y1 - H*CELL
TH = int(round(TW * (H*CELL) / (W*CELL)))
print("texture %dx%d  %.1f m/px" % (TW, TH, (X1-X0)/TW))

sld = osr.SpatialReference()
sld.ImportFromWkt(gdal.Open(os.path.join(ROOT,"DEM","Knuckles_COP30_SLD99_30m.tif")).GetProjection())
sld.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326)
wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
ct = osr.CoordinateTransformation(sld, wgs)
lons, lats = [], []
for x in (X0, X1):
    for y in (Y0, Y1):
        lo, la, _ = ct.TransformPoint(x, y); lons.append(lo); lats.append(la)
PAD = 0.012
lon0, lon1 = min(lons)-PAD, max(lons)+PAD
lat0, lat1 = min(lats)-PAD, max(lats)+PAD
tx = lambda lon: (lon+180.0)/360.0*(1<<Z)
def ty(lat):
    r = math.radians(lat)
    return (1.0-math.log(math.tan(r)+1.0/math.cos(r))/math.pi)/2.0*(1<<Z)
x0, x1 = int(math.floor(tx(lon0))), int(math.floor(tx(lon1)))
y0, y1 = int(math.floor(ty(lat1))), int(math.floor(ty(lat0)))
nx, ny = x1-x0+1, y1-y0+1
print("z=%d  %d x %d = %d tiles" % (Z, nx, ny, nx*ny))

HALF = 20037508.342789244
res = 2*HALF/(256.0*(1<<Z))
MOS = os.path.join(SC, "_mosaic.tif")
mos = gdal.GetDriverByName("GTiff").Create(MOS, nx*256, ny*256, 3, gdal.GDT_Byte,
        options=["TILED=YES","BLOCKXSIZE=256","BLOCKYSIZE=256","COMPRESS=LZW","BIGTIFF=YES"])
mos.SetGeoTransform((-HALF + x0*256*res, res, 0, HALF - y0*256*res, 0, -res))
merc = osr.SpatialReference(); merc.ImportFromEPSG(3857)
mos.SetProjection(merc.ExportToWkt())

lock = threading.Lock()
loc = threading.local()
fails = []
def grab(job):
    ix, iy = job
    if not hasattr(loc, "s"):
        loc.s = requests.Session(); loc.s.headers.update({"User-Agent": UA})
    for _ in range(3):
        try:
            r = loc.s.get(URL.format(z=Z, x=x0+ix, y=y0+iy), timeout=30)
            if r.status_code != 200: continue
            a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"))
            with lock:
                for b in range(3):
                    mos.GetRasterBand(b+1).WriteArray(a[:,:,b], ix*256, iy*256)
            return True
        except Exception:
            pass
    fails.append(job); return False

jobs = [(ix, iy) for iy in range(ny) for ix in range(nx)]
with ThreadPoolExecutor(max_workers=6) as ex:
    done = 0
    for _ in ex.map(grab, jobs):
        done += 1
        if done % 100 == 0: print("  %d/%d" % (done, len(jobs)), flush=True)
print("fetched %d, failed %d" % (len(jobs)-len(fails), len(fails)))
mos.FlushCache(); mos = None; gc.collect()

WRP = os.path.join(SC, "_warp.tif")
gdal.Warp(WRP, MOS, dstSRS=sld.ExportToWkt(), outputBounds=(X0, Y0, X1, Y1),
          width=TW, height=TH, resampleAlg="cubic",
          creationOptions=["TILED=YES","COMPRESS=LZW"])
ds = gdal.Open(WRP)
arr = np.dstack([ds.GetRasterBand(b+1).ReadAsArray() for b in range(3)])
ds = None
Image.fromarray(arr, "RGB").save(os.path.join(SC, "satellite.jpg"), "JPEG",
                                 quality=72, optimize=True)
del arr; gc.collect()
for t in (MOS, WRP):
    try: os.remove(t)
    except OSError: pass
print("satellite.jpg %.2f MB" % (os.path.getsize(os.path.join(SC,"satellite.jpg"))/1e6))
