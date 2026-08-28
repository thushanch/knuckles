# -*- coding: utf-8 -*-
"""Assemble the single-file viewer: fonts, data, satellite/overlay/basin textures."""
import base64, io, json, os, re, shutil

SC = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\thush\OneDrive\Desktop\Knuckles\Knuckles_3D_Map.html"

tpl = io.open(os.path.join(SC, "template.html"), encoding="utf-8").read()
i = tpl.index('<img id="satImg"')
head, tail = tpl[:i], tpl[i:]
tail = re.sub(u"[^\x00-\x7F]", lambda m: "\u%04X" % ord(m.group(0)), tail)
tpl = head + tail

KEEP = {("Poppins", 500), ("Poppins", 600), ("Inter", 400), ("Inter", 600)}
faces = json.load(open(os.path.join(SC, "fonts.json")))
css = ["@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;"
       "src:url(data:font/woff2;base64,%s) format('woff2')}" % (f["family"], f["weight"], f["b64"])
       for f in faces if (f["family"], f["weight"]) in KEEP]
print("fonts: %d faces" % len(css))

data = json.load(open(os.path.join(SC, "knuckles_data.json")))
payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
assert "</script" not in payload and payload.isascii()

def datauri(path, mime):
    return "data:%s;base64,%s" % (mime, base64.b64encode(open(path, "rb").read()).decode("ascii"))

html = (tpl.replace("__FONTS__", "\n".join(css))
           .replace("__SAT__", datauri(os.path.join(SC, "satellite.jpg"), "image/jpeg"))
           .replace("__OVL__", datauri(os.path.join(SC, "overlay.png"), "image/png"))
           .replace("__BAS__", datauri(os.path.join(SC, "basins.png"), "image/png"))
           .replace("__DATA__", payload))
with io.open(OUT, "w", encoding="ascii", errors="xmlcharrefreplace", newline="\n") as f:
    f.write(html)
print("wrote %s  (%.2f MB)" % (OUT, os.path.getsize(OUT)/1e6))
shutil.copy(OUT, os.path.join(SC, "map.html"))
serve = os.path.join(SC, "serve"); os.makedirs(serve, exist_ok=True)
shutil.copy(OUT, os.path.join(serve, "index.html"))
