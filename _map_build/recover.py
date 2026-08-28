# -*- coding: utf-8 -*-
"""Rebuild the working set from the published HTML: it embeds every asset."""
import base64, io, json, os, re
SRC = r"C:\Users\thush\OneDrive\Desktop\Knuckles\Knuckles_3D_Map.html"
SC = os.path.dirname(os.path.abspath(__file__))
html = io.open(SRC, encoding="utf-8").read()
print("html %.2f MB" % (len(html)/1e6))

# --- assets -----------------------------------------------------------------
for tag, name, mime in [("satImg", "satellite.jpg", "image/jpeg"),
                        ("ovlImg", "overlay.png", "image/png"),
                        ("basImg", "basins.png", "image/png")]:
    m = re.search(r'<img id="%s"[^>]*src="data:%s;base64,([A-Za-z0-9+/=]+)"' % (tag, mime), html)
    raw = base64.b64decode(m.group(1))
    open(os.path.join(SC, name), "wb").write(raw)
    print("  %-14s %.2f MB" % (name, len(raw)/1e6))
    html = html.replace(m.group(0), '<img id="%s" alt="" style="display:none" src="__%s__">'
                        % (tag, {"satImg":"SAT","ovlImg":"OVL","basImg":"BAS"}[tag]))

# --- fonts ------------------------------------------------------------------
faces = []
for m in re.finditer(r"@font-face\{font-family:'([^']+)';font-style:normal;font-weight:(\d+);"
                     r"font-display:swap;src:url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)"
                     r" format\('woff2'\)\}", html):
    faces.append({"family": m.group(1), "weight": int(m.group(2)),
                  "b64": m.group(3), "bytes": len(base64.b64decode(m.group(3)))})
json.dump(faces, open(os.path.join(SC, "fonts.json"), "w"))
print("  fonts.json     %d faces" % len(faces))
block = re.search(r"(@font-face\{font-family:'Poppins'.*?format\('woff2'\)\})\s*\n(/\* ---)", html, re.S)
css_all = "\n".join(re.findall(r"@font-face\{[^}]*\}", html))
html = html.replace(css_all, "__FONTS__")

# --- payload ----------------------------------------------------------------
m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
data = json.loads(m.group(1))
json.dump(data, open(os.path.join(SC, "knuckles_data.json"), "w"),
          ensure_ascii=True, separators=(",", ":"))
print("  payload        basins=%d peaks=%d villages=%d falls=%d attractions=%d rivers=%d"
      % (len(data["basins"]), len(data["peaks"]), len(data["villages"]),
         len(data["falls"]), len(data["attractions"]), len(data.get("rivers", []))))
json.dump(data.get("rivers", []), open(os.path.join(SC, "rivers.json"), "w"))
html = html.replace(m.group(1), "__DATA__")

io.open(os.path.join(SC, "template.html"), "w", encoding="utf-8", newline="\n").write(html)
print("  template.html  %.0f KB" % (len(html)/1024))
