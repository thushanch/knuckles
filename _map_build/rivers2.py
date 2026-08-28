# -*- coding: utf-8 -*-
"""Named watercourses as vector lines, plus each basin's outlet and the trunk it joins."""
import json, math, os, re, collections
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions(); ogr.UseExceptions(); osr.UseExceptions()

SC = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\thush\OneDrive\Desktop\Knuckles"
data = json.load(open(os.path.join(SC, "knuckles_data.json")))
G = data["grid"]
OX, OY, W, H, CELL = G["ox"], G["oy"], G["w"], G["h"], G["cell"]
X1, Y0 = OX + W*CELL, OY - H*CELL

dem = gdal.Open(os.path.join(ROOT, "DEM", "Knuckles_COP30_SLD99_30m.tif"))
gt = dem.GetGeoTransform(); band = dem.GetRasterBand(1)
DZ = band.ReadAsArray().astype(np.float32)
nod = band.GetNoDataValue()
if nod is not None:
    DZ[DZ == nod] = np.nan
tgt = osr.SpatialReference(); tgt.ImportFromWkt(dem.GetProjection())
tgt.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326)
wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
CT = osr.CoordinateTransformation(wgs, tgt)

def elev(x, y):
    c = int((x - gt[0]) / gt[1]); r = int((gt[3] - y) / -gt[5])
    if 0 <= r < DZ.shape[0] and 0 <= c < DZ.shape[1]:
        v = DZ[r, c]
        return None if not np.isfinite(v) else float(v)
    return None

# ---- name handling ---------------------------------------------------------
FIX = {"amban gaga": "Amban Ganga", "hassalaka oya": "Hasalaka Oya",
       "memure oya": "Meemure Oya", "ulhiti oaya": "Ulhiti Oya",
       "mahaweli": "Mahaweli Ganga", "mahaweli river": "Mahaweli Ganga",
       "galoya": "Gal Oya", "hulu ganga": "Hulu Ganga", "thelgamu oya": "Thelgamu Oya"}
DROP = re.compile(r"_FC_|_Tract_|MC$|MC_|RBMC|LBMC|Canal|canal|^D_|^ZD|^RBMC|Field|Feeder|Anicut|^Ela$|^ela$")
def norm(n):
    n = re.sub(r"\s*\(.*?\)\s*", "", n).strip()
    k = n.lower()
    if k in FIX:
        return FIX[k]
    return " ".join(w[:1].upper() + w[1:] if w.islower() else w for w in n.split())

TRUNK = {"Mahaweli Ganga", "Amban Ganga"}

raw = json.load(open(os.path.join(SC, "osm_named.json")))["lines"]
groups = collections.defaultdict(list)
for l in raw:
    if l["t"] not in ("river", "stream"):
        continue
    nm = (l["n"] or "").strip()
    if not nm or DROP.search(nm):
        continue
    groups[norm(nm)].append(l["g"])
print("named watercourses after cleaning: %d" % len(groups))

# ---- project + clip to the map window --------------------------------------
def to_grid(seg):
    out = []
    for lon, lat in seg:
        x, y, _ = CT.TransformPoint(lon, lat)
        out.append((x, y))
    return out

def clip(seg):
    """split a projected line where it leaves the window"""
    runs, cur = [], []
    for x, y in seg:
        if OX <= x <= X1 and Y0 <= y <= OY:
            cur.append((round(x - OX, 1), round(OY - y, 1)))
        else:
            if len(cur) >= 2: runs.append(cur)
            cur = []
    if len(cur) >= 2: runs.append(cur)
    return runs

def seglen(pts):
    return sum(math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]) for i in range(len(pts)-1))

trunks, tribs = [], []
trunk_pts = {"Mahaweli Ganga": [], "Amban Ganga": []}
for name, segs in groups.items():
    proj = [to_grid(s) for s in segs]
    if name in TRUNK:
        for p in proj:
            trunk_pts[name].extend(p)
    runs = []
    for p in proj:
        runs.extend(clip(p))
    if not runs:
        continue
    total = sum(seglen(r) for r in runs)
    if total < 400 and name not in TRUNK:
        continue
    rec = {"n": name, "segs": runs, "km": round(total/1000, 1)}
    (trunks if name in TRUNK else tribs).append(rec)

trunks.sort(key=lambda r: -r["km"])
tribs.sort(key=lambda r: -r["km"])
print("\ntrunks inside the window:")
for t in trunks: print("   %-18s %6.1f km  %d run(s)" % (t["n"], t["km"], len(t["segs"])))
print("\ntributaries inside the window: %d" % len(tribs))
for t in tribs[:30]: print("   %-24s %6.1f km" % (t["n"], t["km"]))

# ---- densified trunk vertices, for nearest-point queries -------------------
def densify(pts, step=40.0):
    out = []
    for i in range(len(pts)-1):
        (x0,y0),(x1,y1) = pts[i], pts[i+1]
        d = math.hypot(x1-x0, y1-y0)
        n = max(1, int(d/step))
        for k in range(n):
            out.append((x0 + (x1-x0)*k/n, y0 + (y1-y0)*k/n))
    if pts: out.append(pts[-1])
    return out

TR = {}
for k, v in trunk_pts.items():
    if v:
        TR[k] = np.array(densify(v), dtype=float)
        print("\n%s: %d densified vertices" % (k, len(TR[k])))

def nearest_trunk(x, y):
    best = (None, 1e18, None)
    for k, arr in TR.items():
        d = np.hypot(arr[:,0]-x, arr[:,1]-y)
        i = int(np.argmin(d))
        if d[i] < best[1]:
            best = (k, float(d[i]), (float(arr[i,0]), float(arr[i,1])))
    return best

# ---- basin outlets ---------------------------------------------------------
outlets = []
for b in data["basins"]:
    ring = b["rings"][0]
    best = None
    for gx, gy in ring:                       # ring is in grid metres from the NW corner
        x, y = OX + gx, OY - gy
        z = elev(x, y)
        if z is None: continue
        if best is None or z < best[0]:
            best = (z, x, y)
    z, x, y = best
    trunk, dist, pt = nearest_trunk(x, y)
    outlets.append({"b": b["id"], "bn": b["name"], "x": round(x-OX,1), "y": round(OY-y,1),
                    "z": round(z,1), "trunk": trunk, "d": round(dist),
                    "cx": round(pt[0]-OX,1), "cy": round(OY-pt[1],1),
                    "cz": round(elev(pt[0], pt[1]) or z, 1)})
    print("basin %d %-22s outlet %.0f m  -> %-15s %5.0f m away"
          % (b["id"], b["name"], z, trunk, dist))
data["outlets"] = outlets

# ---- label points ----------------------------------------------------------
def label_for(rec):
    run = max(rec["segs"], key=seglen)
    gx, gy = run[len(run)//2]
    z = elev(OX+gx, OY-gy)
    return {"n": rec["n"], "x": gx, "y": gy, "z": round(z or 0, 1), "km": rec["km"]}

data["trunks"] = trunks
data["tribs"] = tribs
data["trunkLabels"] = [label_for(t) for t in trunks]
data["tribLabels"] = [label_for(t) for t in tribs]
data.pop("rivers", None)
json.dump(data, open(os.path.join(SC, "knuckles_data.json"), "w"),
          ensure_ascii=True, separators=(",", ":"))
print("\npayload %.2f MB" % (os.path.getsize(os.path.join(SC, "knuckles_data.json"))/1e6))
