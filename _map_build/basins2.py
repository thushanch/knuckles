# -*- coding: utf-8 -*-
"""Rebuild the basin set with Hunnasgiriyen Tika merged into Hulu Ganga.

Writes the new basin metadata + outline rings into the payload and re-burns the
15 m id raster the shader samples.
"""
import gc, json, os
import numpy as np
from PIL import Image
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()
gdal.SetCacheMax(48 * 1024 * 1024)     # this machine is short on RAM; keep GDAL lean

SC = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\thush\OneDrive\Desktop\Knuckles"
WS = os.path.join(ROOT, "Watersheds")

# new id -> (display name, source folders to union)
DEF = [
    (1, "Hasalaka Oya",         ["watershed(2)"]),
    (2, "Hulu Ganga",           ["watershed(4)", "watershed(3)"]),   # merged
    (3, "Amban Ganga Side Eka", ["watershed(5)"]),
    (4, "Thelgamu Oya",         ["watershed(6)"]),
    (5, "Kalu Ganga",           ["watershed"]),
    (6, "Heen Ganga",           ["watershed(1)"]),
]

data = json.load(open(os.path.join(SC, "knuckles_data.json")))
G = data["grid"]
OX, OY, W, H, CELL = G["ox"], G["oy"], G["w"], G["h"], G["cell"]
X0, Y1 = OX, OY
X1, Y0 = OX + W*CELL, OY - H*CELL
TW = 2400
TH = int(round(TW * (H*CELL) / (W*CELL)))
MPP = (X1 - X0) / TW

dem = gdal.Open(os.path.join(ROOT, "DEM", "Knuckles_COP30_SLD99_30m.tif"))
tgt = osr.SpatialReference(); tgt.ImportFromWkt(dem.GetProjection())
tgt.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

def load(folder):
    ds = ogr.Open(os.path.join(WS, folder, "watershed.shp"))
    lyr = ds.GetLayer(0)
    s = lyr.GetSpatialRef().Clone(); s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(s, tgt)
    f = lyr.GetNextFeature()
    g = f.GetGeometryRef().Clone(); g.Transform(ct)
    return g

TMP = os.path.join(SC, "_bas_tmp.tif")
mem = gdal.GetDriverByName("GTiff").Create(TMP, TW, TH, 1, gdal.GDT_Byte,
                                           options=["TILED=YES", "COMPRESS=LZW"])
mem.SetGeoTransform((X0, MPP, 0, Y1, 0, -MPP))
mem.SetProjection(tgt.ExportToWkt())
mem.GetRasterBand(1).Fill(0)
drv = ogr.GetDriverByName("MEM")

def drop_slivers(g, min_hole_km2=0.10, min_part_km2=0.50):
    """Discard interior rings too small to be real, and stray specks.

    Preferred over a buffer-out/in, which would shift the true outer boundary."""
    parts = ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())]
             if g.GetGeometryName() == "MULTIPOLYGON" else [g])
    out = ogr.Geometry(ogr.wkbMultiPolygon)
    dropped = 0
    for poly in parts:
        if poly.GetArea() < min_part_km2 * 1e6:
            dropped += 1
            continue
        np_ = ogr.Geometry(ogr.wkbPolygon)
        np_.AddGeometry(poly.GetGeometryRef(0))
        for j in range(1, poly.GetGeometryCount()):
            ring = poly.GetGeometryRef(j)
            t = ogr.Geometry(ogr.wkbPolygon); t.AddGeometry(ring)
            if t.GetArea() >= min_hole_km2 * 1e6:
                np_.AddGeometry(ring)
            else:
                dropped += 1
        out.AddGeometry(np_)
    if dropped:
        print("   dropped %d sliver ring(s)/part(s)" % dropped)
    return out.UnionCascaded() if out.GetGeometryCount() == 1 else out

meta, geoms = [], {}
for bid, name, folders in DEF:
    g = load(folders[0])
    for extra in folders[1:]:
        g = g.Union(load(extra))
    g = g.Buffer(0)
    g = drop_slivers(g)                  # union along a shared edge leaves gap holes
    geoms[bid] = g
    vds = drv.CreateDataSource("m"); vl = vds.CreateLayer("l", tgt, ogr.wkbMultiPolygon)
    nf = ogr.Feature(vl.GetLayerDefn()); nf.SetGeometry(g); vl.CreateFeature(nf)
    gdal.RasterizeLayer(mem, [1], vl, burn_values=[bid * 32])

    parts = ([g.GetGeometryRef(i) for i in range(g.GetGeometryCount())]
             if g.GetGeometryName() == "MULTIPOLYGON" else [g])
    rings = []
    for poly in parts:
        for j in range(poly.GetGeometryCount()):
            r = poly.GetGeometryRef(j)
            pts = [[round(x - OX, 1), round(OY - y, 1)] for x, y, *_ in r.GetPoints()]
            if len(pts) >= 4:
                rings.append(pts)
    meta.append({"id": bid, "name": name, "src": "+".join(folders),
                 "area_km2": round(g.GetArea() / 1e6, 2), "rings": rings})
    print("%d %-22s %7.2f km2  rings=%d verts=%d"
          % (bid, name, g.GetArea()/1e6, len(rings), sum(len(r) for r in rings)))

mem.FlushCache()
arr = mem.GetRasterBand(1).ReadAsArray()
for m in meta:
    n = int((arr == m["id"]*32).sum())
    print("   raster check %d: %7.2f km2" % (m["id"], n*MPP*MPP/1e6))
Image.fromarray(arr, "L").save(os.path.join(SC, "basins.png"), "PNG", optimize=True)
del arr; mem = None; gc.collect()
print("basins.png %.0f KB" % (os.path.getsize(os.path.join(SC, "basins.png"))/1024))

# 60 m id array the picker uses (low 3 bits)
TMP2 = os.path.join(SC, "_bas_small.tif")
small = gdal.GetDriverByName("GTiff").Create(TMP2, W, H, 1, gdal.GDT_Byte)
small.SetGeoTransform((X0, CELL, 0, Y1, 0, -CELL))
small.SetProjection(tgt.ExportToWkt())
small.GetRasterBand(1).Fill(0)
for bid, name, folders in DEF:
    vds = drv.CreateDataSource("m2"); vl = vds.CreateLayer("l", tgt, ogr.wkbMultiPolygon)
    nf = ogr.Feature(vl.GetLayerDefn()); nf.SetGeometry(geoms[bid]); vl.CreateFeature(nf)
    gdal.RasterizeLayer(small, [1], vl, burn_values=[bid])
small.FlushCache()
ids = small.GetRasterBand(1).ReadAsArray().astype(np.uint8)
import base64
data["ids"] = base64.b64encode(ids.tobytes()).decode("ascii")
data["basins"] = meta
total = sum(m["area_km2"] for m in meta)
data["totalArea"] = round(total, 1)
print("total %.2f km2 across %d basins" % (total, len(meta)))

# points carry a basin id; remap onto the new numbering
REMAP = {1:1, 2:2, 3:2, 4:3, 5:4, 6:5, 7:6}
for key in ("peaks", "falls", "villages", "attractions", "rivers"):
    for p in data.get(key, []):
        p["b"] = REMAP.get(p.get("b", 0), 0)
json.dump(data, open(os.path.join(SC, "knuckles_data.json"), "w"),
          ensure_ascii=True, separators=(",", ":"))
small = None; gc.collect()
for t in (TMP, TMP2):
    try: os.remove(t)
    except OSError: pass
print("payload %.2f MB" % (os.path.getsize(os.path.join(SC, "knuckles_data.json"))/1e6))
