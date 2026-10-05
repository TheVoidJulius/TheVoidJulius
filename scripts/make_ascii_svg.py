import numpy as np
from PIL import Image
RAMP = " .`:-=+*cs#%@"
COLS = 100
CW, CH = 7.2, 12.0          # char cell size in svg units
img = Image.open("source-prepped.png").convert("L")
rows = round(COLS * img.height / img.width * (CW / CH) * (CH / CW) * 0.5 * (CW / CW))
rows = round(COLS * img.height / img.width * (CW / CH))
small = np.array(img.resize((COLS, rows), Image.LANCZOS)) / 255.0
small = np.clip((small - 0.05) / 0.9, 0, 1) ** 0.9
out = []
W, H = COLS * CW + 20, rows * CH + 20
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}">')
out.append('<style>text{font-family:"SFMono-Regular",Menlo,Consolas,monospace;font-size:11.5px;fill:#c9d1d9;white-space:pre}</style>')
out.append('<defs>')
dur, stag = 0.5, 0.045
for r in range(rows):
    out.append(f'<clipPath id="c{r}"><rect x="0" y="{10 + r*CH:.1f}" height="{CH:.1f}" width="0">'
               f'<animate attributeName="width" from="0" to="{W:.0f}" dur="{dur}s" begin="{r*stag:.3f}s" fill="freeze"/></rect></clipPath>')
out.append('</defs>')
for r in range(rows):
    line = "".join(RAMP[int((1 - v) * (len(RAMP) - 1))] for v in small[r])
    line = line.replace("&", "&amp;").replace("<", "&lt;")
    if not line.strip():
        continue
    y = 10 + r * CH + CH * 0.8
    out.append(f'<g clip-path="url(#c{r})"><text x="10" y="{y:.1f}" textLength="{COLS*CW:.0f}" lengthAdjust="spacing" xml:space="preserve">{line}</text></g>')
    # cursor block riding the wipe edge
    out.append(f'<rect x="10" y="{10 + r*CH + 2:.1f}" width="6" height="{CH-3:.1f}" fill="#c9d1d9" opacity="0">'
               f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.05;0.95;1" dur="{dur}s" begin="{r*stag:.3f}s" fill="freeze"/>'
               f'<animate attributeName="x" from="10" to="{W-16:.0f}" dur="{dur}s" begin="{r*stag:.3f}s" fill="freeze"/></rect>')
out.append('</svg>')
open("ascii-portrait.svg", "w").write("\n".join(out))
print(COLS, rows)
