import os
STATIC = os.environ.get("STATIC") == "1"
USER = "TheVoidJulius"
rows = [
    ("Now",        "OCTARAX (Hinglish AI captions)"),
    ("Building",   "video caption editor, zero-cost stack"),
    ("Stack",      "Python | MERN | SQL | AI | ML"),
    ("Highlights", "Google Gemini Ambassador"),
    ("",           "GSSoC '26 contributor"),
    ("",           "Microsoft Student Ambassador"),
    ("Member",     "Tryst IIT Delhi, Mediaverse"),
]
W, LH, TOP = 490, 26, 58
H = TOP + LH * len(rows) + 22
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
 '<style>text{font-family:"SFMono-Regular",Menlo,Consolas,monospace;font-size:13px}'
 '.k{fill:#58a6ff;font-weight:bold}.v{fill:#c9d1d9}.t{fill:#8b949e}.g{fill:#3fb950}'
 + ('' if STATIC else '.l{opacity:0;animation:in .5s ease-out forwards}@keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}')
 + '</style>',
 f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="8" fill="#0d1117" stroke="#30363d"/>',
 f'<rect x="0.5" y="0.5" width="{W-1}" height="30" rx="8" fill="#161b22"/>',
 '<circle cx="18" cy="15" r="5" fill="#ff5f56"/><circle cx="36" cy="15" r="5" fill="#ffbd2e"/><circle cx="54" cy="15" r="5" fill="#27c93f"/>',
 f'<text x="{W/2}" y="19" text-anchor="middle" class="t" style="font-size:12px">{USER.lower()}@github: ~</text>']
def line(i, body):
    d = f' style="animation-delay:{0.25*i:.2f}s"' if not STATIC else ''
    return f'<g class="l"{d}>{body}</g>' if not STATIC else f'<g>{body}</g>'
o.append(line(0, f'<text x="20" y="{TOP-8}" class="g">$ neofetch</text>'))
for i, (k, v) in enumerate(rows, 1):
    y = TOP + LH * i - 10
    key = f'<text x="20" y="{y}" class="k">{k}</text>' if k else ''
    o.append(line(i, key + f'<text x="130" y="{y}" class="v">{v.replace("&","&amp;")}</text>'))
o.append('</svg>')
open("info-card.svg", "w").write("\n".join(o))
