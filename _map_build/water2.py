# -*- coding: utf-8 -*-
"""Pull every named waterway around the Knuckles, plus the trunk rivers.

Wider than the first pass: any waterway with a name (drain/ditch included), a
larger bbox so the Mahaweli and Amban Ganga trunks are captured whole, and
relations so multi-way rivers come back complete.
"""
import json, os, time, collections
import requests
SC = os.path.dirname(os.path.abspath(__file__))
S, W, N, E = 7.05, 80.45, 7.85, 81.15

Q = """
[out:json][timeout:300];
(
  way["waterway"]["name"](%f,%f,%f,%f);
  relation["waterway"="river"]["name"](%f,%f,%f,%f);
  way["natural"="water"]["name"](%f,%f,%f,%f);
);
out geom;
""" % (S, W, N, E, S, W, N, E, S, W, N, E)

data = None
for ep in ["https://overpass.kumi.systems/api/interpreter",
           "https://overpass-api.de/api/interpreter"]:
    try:
        print("querying", ep, flush=True)
        r = requests.post(ep, data={"data": Q},
                          headers={"User-Agent": "KnucklesWatershedStudy/1.0"}, timeout=300)
        if r.status_code == 200:
            data = r.json(); break
        print("  status", r.status_code)
    except Exception as e:
        print("  failed:", type(e).__name__)
    time.sleep(3)
if data is None:
    raise SystemExit("Overpass unavailable")

lines, polys = [], []
for el in data.get("elements", []):
    t = el.get("tags", {})
    nm = (t.get("name") or "").strip()
    if el["type"] == "way" and "geometry" in el:
        pts = [[round(p["lon"], 6), round(p["lat"], 6)] for p in el["geometry"]]
        if len(pts) < 2:
            continue
        if "waterway" in t:
            lines.append({"t": t["waterway"], "n": nm, "g": pts,
                          "int": t.get("intermittent"), "id": el["id"]})
        elif nm:
            polys.append({"t": "water", "n": nm, "g": pts})
    elif el["type"] == "relation":
        for m in el.get("members", []):
            if "geometry" in m and len(m["geometry"]) > 1:
                pts = [[round(p["lon"], 6), round(p["lat"], 6)] for p in m["geometry"]]
                lines.append({"t": "river", "n": nm, "g": pts, "id": el["id"]})

by = collections.defaultdict(lambda: [0, set(), 0])
for l in lines:
    if l["n"]:
        by[l["n"]][0] += 1
        by[l["n"]][1].add(l["t"])
        by[l["n"]][2] += len(l["g"])
print("\n%d named waterway ways, %d distinct names\n" % (len(lines), len(by)))
for n in sorted(by, key=lambda k: (-by[k][2])):
    print("   %-30s %3d seg %5d pts  %s" % (n, by[n][0], by[n][2], ",".join(sorted(by[n][1]))))
json.dump({"lines": lines, "polys": polys}, open(os.path.join(SC, "osm_named.json"), "w"))
print("\nwrote osm_named.json  %.2f MB" % (os.path.getsize(os.path.join(SC,"osm_named.json"))/1e6))
