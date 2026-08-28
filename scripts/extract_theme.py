"""Extrai cores (clrScheme) e fontes (fontScheme) do tema do template Balthasar."""
import zipfile, re

ZIP = "Balthasar · SlidesCarnival.pptx"
with zipfile.ZipFile(ZIP) as z:
    name = next((n for n in z.namelist() if n.endswith("theme/theme1.xml")), None)
    xml = z.read(name).decode("utf-8")

def get(tag, attr="val"):
    m = re.search(rf"<a:{tag}><a:srgbClr '|\"'.*?>" , xml)
    pat = re.compile(rf'<a:{tag}>\s*<a:(srgbClr|sysClr)[^>]*?>')
    return xml

def between(tag):
    m = re.search(r"<a:" + tag + r"[^>]*>(.*?)</a:" + tag + ">", xml, re.S)
    return m.group(1) if m else None

# cores
clr = between("clrScheme")
names = ["dk1","lt1","dk2","lt2","accent1","accent2","accent3","accent4","accent5","accent6","hlink","folHlink"]
print("=== CORES ===")
if clr:
    for nm in names:
        mm = re.search(r"<a:"+nm+r">\s*<(?:a:)?(srgbClr|sysClr)[^>]*?(?:lastClr=\"[0-9A-F]+\"|val=\"[0-9A-F]+\")", clr)
        v = re.search(r"<a:"+nm+r">\s*<a:(?:srgbClr val=\"([0-9A-Fa-f]{6})\"|sysClr[^>]*val=\"([0-9A-Fa-f]{6})\")", clr)
        if v:
            print(f"  {nm}: #{v.group(1) or v.group(2)}")

# fontes
fs = between("fontScheme")
print("=== FONTES ===")
mm = re.search(r"<a:majorFont>\s*<a:latin typeface=\"([^\"]*)\"", fs or "")
sm = re.search(r"<a:minorFont>\s*<a:latin typeface=\"([^\"]*)\"", fs or "")
print(f"  majorFont (titulos): {mm.group(1) if mm else '?'}")
print(f"  minorFont (corpo):   {sm.group(1) if sm else '?'}")