"""QA do deck: renderiza miniaturas por slide e detecta overflow de texto."""
import os
import pymupdf

SRC = ".qa/Apresentacao_Projeto_Bayer.pdf"
OUT = ".qa/thumbs"
os.makedirs(OUT, exist_ok=True)

doc = pymupdf.open(SRC)
N = len(doc)
print(f"paginas: {N} | tamanho pagina: {doc[0].rect.width:.0f}x{doc[0].rect.height:.0f} pt")
COUNT_OK = 0
for i, page in enumerate(doc, start=1):
    pr = page.rect
    # mini
    pix = page.get_pixmap(dpi=110)
    png = os.path.join(OUT, f"slide_{i:02d}.png")
    pix.save(png)

    # overflow off-page
    issues = []
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                bb = pymupdf.Rect(span["bbox"])
                txt = span["text"].strip()
                if not txt:
                    continue
                if bb.x1 > pr.x1 + 1 or bb.y1 > pr.y1 + 1 or bb.x0 < -1 or bb.y0 < -1:
                    issues.append(f"OFF-PAGE {txt[:28]!r} bbox={[round(v,1) for v in bb]}")
    status = f"pagina {i}: OK" if not issues else f"pagina {i}: {len(issues)} problema(s)"
    if not issues:
        COUNT_OK += 1
    for it in issues[:4]:
        print("   ", it)
    print(status)
doc.close()
print(f"\nRESUMO: {COUNT_OK}/{N} paginas sem overflow off-page. Miniaturas em {OUT}")