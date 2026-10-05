import json, datetime as dt
D = json.load(open("data/contributions.json"))
PAL = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
days = D["days"]
first = dt.date.fromisoformat(days[0]["date"])
offset = (first.weekday() + 1) % 7          # Sunday-first rows
CELL, GAP, LEFT, TOP = 12, 3, 34, 34
weeks = (len(days) + offset + 6) // 7
W = LEFT + weeks * (CELL + GAP) + 12
H = TOP + 7 * (CELL + GAP) + 50
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
 '<style>text{font-family:"SFMono-Regular",Menlo,Consolas,monospace;font-size:11px;fill:#8b949e}'
 '.c{opacity:0;animation:s .45s ease-out forwards}@keyframes s{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}</style>',
 f'<rect width="{W}" height="{H}" rx="8" fill="#0d1117"/>']
months, last_m = [], None
for i, d in enumerate(days):
    date = dt.date.fromisoformat(d["date"])
    idx = i + offset
    wk, row = idx // 7, idx % 7
    lv = d["level"]
    if d["count"] >= 15: lv = 5
    x, y = LEFT + wk * (CELL + GAP), TOP + row * (CELL + GAP)
    delay = (wk + row) * 0.018
    o.append(f'<rect class="c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="3" fill="{PAL[lv]}" style="animation-delay:{delay:.3f}s"/>')
    if row == 0 and date.month != last_m:
        months.append((x, date.strftime("%b"))); last_m = date.month
for x, m in months: o.append(f'<text x="{x}" y="{TOP-10}">{m}</text>')
for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")): o.append(f'<text x="4" y="{TOP + r*(CELL+GAP) + 10}">{n}</text>')
fy = TOP + 7 * (CELL + GAP) + 22
o.append(f'<text x="{LEFT}" y="{fy}">{D["total"]:,} contributions in the last year | streak {D["current_streak"]}d | longest {D["longest_streak"]}d</text>')
lx = W - 12 - 6 * 15 - 70
o.append(f'<text x="{lx}" y="{fy}">Less</text>')
for i, c in enumerate(PAL): o.append(f'<rect x="{lx+32+i*15}" y="{fy-10}" width="12" height="12" rx="3" fill="{c}"/>')
o.append(f'<text x="{lx+32+6*15+4}" y="{fy}">More</text></svg>')
open("contrib-heatmap.svg", "w").write("\n".join(o))
print(W, H)
