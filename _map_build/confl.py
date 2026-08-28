# -*- coding: utf-8 -*-
"""Real confluences: follow each named river to where it actually meets a trunk,
and label the basins whose river OSM does not name, using their own channels."""
import json, math, os, re, collections
import numpy as np
from PIL import Image
from osgeo import gdal, osr
gdal.UseExceptions()

SC = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\thush\OneDrive\Desktop\Knuckles"
data = json.load(open(os.path.join(SC, "knuckles_data.json")))
G = data["grid"]
OX, OY, W, H, CELL = G["ox"], G["oy"], G["w"], G["h"], G["cell"]
X1, Y0 = OX + W*CELL, OY - H*CELL

dem = gdal.Open(os.path.join(ROOT, "DEM", "Knuckles_COP30_SLD99_30m.tif"))
gt = dem.GetGeoTransform()
DZ = dem.GetRasterBand(1).ReadAsArray().astype(np.float32)
tgt = osr.SpatialReference(); tgt.ImportFromWkt(dem.GetProjection())
tgt.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326)
wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
CT = osr.CoordinateTransformation(wgs, tgt)
def elev(x, y):
    c = int((x-gt[0])/gt[1]); r = int((gt[3]-y)/-gt[5])
    if 0 <= r < DZ.shape[0] and 0 <= c < DZ.shape[1]:
        v = float(DZ[r, c]); return None if v < -100 else v
    return None

FIX = {"amban gaga":"Amban Ganga","hassalaka oya":"Hasalaka Oya","memure oya":"Meemure Oya",
       "ulhiti oaya":"Ulhiti Oya","mahaweli":"Mahaweli Ganga","mahaweli river":"Mahaweli Ganga",
       "galoya":"Gal Oya","hulu ganga":"Hulu Ganga","thelgamu oya":"Thelgamu Oya"}
DROP = re.compile(r"_FC_|_Tract_|MC$|MC_|RBMC|LBMC|Canal|canal|^D_|^ZD|Field|Feeder|Anicut|^Ela$|^ela$")
def norm(n):
    n = re.sub(r"\s*\(.*?\)\s*","",n).strip(); k = n.lower()
    return FIX.get(k, " ".join(w[:1].upper()+w[1:] if w.islower() else w for w in n.split()))
TRUNK = {"Mahaweli Ganga", "Amban Ganga"}

raw = json.load(open(os.path.join(SC,"osm_named.json")))["lines"]
groups = collections.defaultdict(list)
for l in raw:
    if l["t"] not in ("river","stream"): continue
    nm = (l["n"] or "").strip()
    if not nm or DROP.search(nm): continue
    pts = []
    for lon,lat in l["g"]:
        x,y,_ = CT.TransformPoint(lon,lat); pts.append((x,y))
    groups[norm(nm)].append(pts)

def densify(pts, step=40.0):
    out=[]
    for i in range(len(pts)-1):
        (x0,y0),(x1,y1)=pts[i],pts[i+1]
        d=math.hypot(x1-x0,y1-y0); n=max(1,int(d/step))
        for k in range(n): out.append((x0+(x1-x0)*k/n, y0+(y1-y0)*k/n))
    if pts: out.append(pts[-1])
    return out

TR={}
for t in TRUNK:
    v=[]
    for s in groups.get(t,[]): v.extend(densify(s))
    if v: TR[t]=np.array(v,float)
print("trunk vertices:", {k:len(v) for k,v in TR.items()})

def nearest(x,y):
    best=(None,1e18,None)
    for k,a in TR.items():
        d=np.hypot(a[:,0]-x,a[:,1]-y); i=int(np.argmin(d))
        if d[i]<best[1]: best=(k,float(d[i]),(float(a[i,0]),float(a[i,1])))
    return best

# ---- confluence for every named non-trunk river ---------------------------
conf=[]
for name,segs in groups.items():
    if name in TRUNK: continue
    allpts=[p for s in segs for p in s]
    if len(allpts)<5: continue
    best=(None,1e18,None,None)
    for x,y in allpts:
        k,d,pt = nearest(x,y)
        if d<best[1]: best=(k,d,pt,(x,y))
    k,d,pt,src = best
    if d>1500: continue                     # not actually joining a trunk here
    inwin = OX<=pt[0]<=X1 and Y0<=pt[1]<=OY
    conf.append({"n":name,"trunk":k,"d":round(d),
                 "x":round(pt[0]-OX,1),"y":round(OY-pt[1],1),
                 "z":round(elev(*pt) or 0,1),"inwin":inwin})
conf.sort(key=lambda c:(c["trunk"],c["n"]))
print("\nconfluences found (<=1.5 km):")
for c in conf:
    print("   %-18s -> %-15s gap %4d m  z=%5.0f m  %s"
          % (c["n"],c["trunk"],c["d"],c["z"],"in view" if c["inwin"] else "OUTSIDE window"))

# ---- basins whose river OSM does not name: label their own main channel ----
bas = np.asarray(Image.open(os.path.join(SC,"basins.png")))
ovl = np.asarray(Image.open(os.path.join(SC,"overlay.png")))
if bas.ndim==3: bas=bas[:,:,0]
GCH = ovl[:,:,1]
TH_, TW_ = bas.shape
MPP = (X1-OX)/TW_
print("\nmask %dx%d at %.1f m/px" % (TW_,TH_,MPP))
named_lc = {n.lower() for n in groups}
stems=[]
for b in data["basins"]:
    m = (bas == b["id"]*32)
    if not m.any(): continue
    pick=None
    for lo,hi,lab in ((220,256,"L4"),(150,220,"L3"),(55,150,"L1")):
        sel = m & (GCH>=lo) & (GCH<hi)
        if sel.sum() >= 60: pick=(sel,lab); break
    if pick is None: continue
    sel,lab = pick
    ys,xs = np.nonzero(sel)
    X = OX + (xs+0.5)*MPP; Y = OY - (ys+0.5)*MPP
    zs = np.array([elev(a,bb) or 9e9 for a,bb in zip(X,Y)])
    ok = zs<9e8
    if ok.sum()<10: continue
    X,Y,zs = X[ok],Y[ok],zs[ok]
    i = int(np.argsort(zs)[len(zs)//2])         # mid-elevation point on that channel
    have = b["name"].lower() in named_lc
    stems.append({"n":b["name"],"b":b["id"],"x":round(X[i]-OX,1),"y":round(OY-Y[i],1),
                  "z":round(float(zs[i]),1),"lvl":lab,"osm":have})
    print("   basin %d %-22s main channel %s  label z=%4.0f m  %s"
          % (b["id"],b["name"],lab,zs[i],"(OSM has this name)" if have else "(derived label)"))

data["confluences"]=conf
data["stems"]=[s for s in stems if not s["osm"]]
json.dump(data,open(os.path.join(SC,"knuckles_data.json"),"w"),
          ensure_ascii=True,separators=(",",":"))
print("\nderived stem labels kept: %s" % [s["n"] for s in data["stems"]])
print("payload %.2f MB" % (os.path.getsize(os.path.join(SC,"knuckles_data.json"))/1e6))
