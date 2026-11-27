"""Animated pixel-art room: a dev at his PC, a cat, coffee, and a cyber city
through the window. Pure SVG; every unit in the viewBox is one 'pixel'.

    python pixel_room.py            -> writes assets/pixel-room.svg
"""
import random
from pathlib import Path

W, H = 172, 88
FLOOR_Y = 66


def r(x, y, w, h, c, extra="", inner=""):
    if inner:
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" {extra}>{inner}</rect>'
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" {extra}/>'


def sprite(rows, palette, ox, oy):
    """ASCII rows -> rects, merging horizontal runs of the same colour."""
    out = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            ch = row[x]
            if ch == "." or ch == " ":
                x += 1
                continue
            start = x
            while x < len(row) and row[x] == ch:
                x += 1
            out.append(r(ox + start, oy + y, x - start, 1, palette[ch]))
    return "".join(out)


def blink(values, dur, begin="0s"):
    return (f'<animate attributeName="opacity" values="{values}" dur="{dur}" '
            f'begin="{begin}" repeatCount="indefinite"/>')


# ---------------------------------------------------------------- window city
def city():
    rnd = random.Random(7)
    X0, Y0, X1, Y1 = 10, 10, 70, 50
    parts = [f'<clipPath id="win"><rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}"/></clipPath>',
             '<g clip-path="url(#win)">']
    # sky bands
    for i, c in enumerate(["#0a0720", "#120b30", "#1c0f42", "#2a1356", "#3d1a68"]):
        parts.append(r(X0, Y0 + i * 8, X1 - X0, 8, c))
    # stars
    for _ in range(14):
        sx, sy = rnd.randint(X0, X1 - 1), rnd.randint(Y0, Y0 + 18)
        parts.append(r(sx, sy, 1, 1, "#cfd8ff", "opacity=\".8\"",
                       blink(".9;.2;.9", f"{rnd.uniform(2, 5):.1f}s", f"{rnd.uniform(0, 3):.1f}s")))
    # moon
    parts.append(r(58, 13, 5, 5, "#f3e9c6") + r(57, 14, 1, 3, "#f3e9c6") + r(63, 14, 1, 3, "#f3e9c6")
                 + r(60, 14, 2, 2, "#ded2a8"))

    def skyline(color, base_h, var, lit_p, lit_colors, layer_seed):
        lr = random.Random(layer_seed)
        x = X0 - 2
        out = []
        while x < X1:
            w = lr.randint(5, 10)
            h = base_h + lr.randint(0, var)
            top = Y1 - h
            out.append(r(x, top, w, h, color))
            if lr.random() < .35:  # antenna with a red light
                ax = x + w // 2
                out.append(r(ax, top - 4, 1, 4, color))
                out.append(r(ax, top - 5, 1, 1, "#ff3b6b", "", blink("1;.1;1", "1.6s", f"{lr.uniform(0, 1.5):.1f}s")))
            for wy in range(top + 2, Y1 - 1, 3):
                for wx in range(x + 1, x + w - 1, 2):
                    if lr.random() < lit_p:
                        c = lr.choice(lit_colors)
                        anim = blink("1;1;.15;1", f"{lr.uniform(3, 8):.1f}s", f"{lr.uniform(0, 4):.1f}s") \
                            if lr.random() < .15 else ""
                        out.append(r(wx, wy, 1, 1, c, "", anim))
            x += w + lr.randint(0, 1)
        return out

    parts += skyline("#251a4a", 22, 12, .30, ["#5b4a9b", "#7d5fd0"], 3)
    parts += skyline("#120d26", 12, 14, .45, ["#ffd166", "#3ef0ff", "#ff5ccf", "#ffe7a3"], 11)

    # neon signs on the front buildings
    parts.append(r(18, 34, 6, 2, "#ff2bd6", "", blink("1;1;.2;1;.2;1", "3s")))
    parts.append(r(47, 30, 2, 7, "#22f0ff", "", blink("1;.3;1", "2.2s", ".7s")))
    parts.append(r(58, 38, 5, 1, "#8cff5a", "", blink("1;1;.1;1", "4s", "1s")))

    # flying cars
    for y, color, dur, begin in [(24, "#ff4fd8", "7s", "0s"), (19, "#3ef0ff", "11s", "3s")]:
        parts.append(
            f'<g><animateTransform attributeName="transform" type="translate" values="-12 0;76 0" '
            f'dur="{dur}" begin="{begin}" repeatCount="indefinite"/>'
            + r(X0 - 2, y, 5, 2, "#2a2350") + r(X0 + 2, y, 1, 1, color) + r(X0 - 4, y + 1, 2, 1, color, 'opacity=".5"')
            + "</g>")

    # rain
    for i in range(26):
        rx = rnd.randint(X0 - 10, X1)
        ry = rnd.randint(Y0 - 10, Y1)
        d = f"{rnd.uniform(.7, 1.2):.2f}s"
        parts.append(
            f'<g><animateTransform attributeName="transform" type="translate" values="0 -44;8 44" dur="{d}" '
            f'begin="{rnd.uniform(0, 1):.2f}s" repeatCount="indefinite"/>'
            + r(rx, ry, 1, 2, "#8fb8ff", 'opacity=".45"') + "</g>")
    parts.append("</g>")

    # frame, cross bars, sill
    frame = "#3b3355"
    parts.append(r(6, 6, 68, 4, frame) + r(6, 50, 68, 4, frame) + r(6, 6, 4, 48, frame) + r(70, 6, 4, 48, frame))
    parts.append(r(39, 10, 2, 40, frame) + r(10, 29, 60, 2, frame))
    parts.append(r(4, 54, 72, 2, "#4a4068") + r(4, 56, 72, 1, "#2a2440"))
    # tiny plant on the sill
    parts.append(r(12, 51, 4, 3, "#a0522d") + r(13, 48, 1, 3, "#4caf50") + r(14, 47, 1, 4, "#66d17a")
                 + r(15, 49, 1, 2, "#4caf50"))
    return "".join(parts)


# ---------------------------------------------------------------- room
def room():
    p = []
    # wall + floor
    p.append(r(0, 0, W, FLOOR_Y, "#1b1533"))
    for x in range(0, W, 12):  # subtle wall panels
        p.append(r(x, 0, 1, FLOOR_Y, "#211a3d"))
    p.append(r(0, FLOOR_Y, W, H - FLOOR_Y, "#2b2145"))
    p.append(r(0, FLOOR_Y, W, 1, "#3a2d5c"))
    for y in range(FLOOR_Y + 5, H, 5):
        p.append(r(0, y, W, 1, "#251c3c"))
    p.append(city())
    # neon spill from the window
    p.append(r(2, 2, 76, 58, "#3ef0ff", 'opacity=".05"'))
    p.append(f'<polygon points="10,{FLOOR_Y} 70,{FLOOR_Y} 86,{H} 0,{H}" fill="#ff4fd8" opacity=".06"/>')
    # rug
    p.append(r(70, 80, 50, 6, "#3d2a63") + r(72, 81, 46, 4, "#4a3378"))

    # poster
    p.append(r(80, 8, 18, 22, "#2c2450") + r(81, 9, 16, 20, "#0e0b22"))
    p.append(r(83, 12, 12, 1, "#ff4fd8") + r(83, 14, 9, 1, "#3ef0ff") + r(83, 16, 11, 1, "#ffd166"))
    p.append(sprite([
        "..C.....C..",
        ".C...P...C.",
        "C...P.....C",
        ".C.P.....C.",
        "..C.....C..",
    ], {"C": "#3ef0ff", "P": "#ff4fd8"}, 84, 20))

    # shelf with books + a mini cactus
    p.append(r(140, 18, 30, 2, "#5a4632") + r(142, 20, 1, 3, "#3d2f22") + r(166, 20, 1, 3, "#3d2f22"))
    for i, (c, h) in enumerate([("#e05555", 8), ("#4a90e2", 7), ("#f5c542", 9), ("#7d5fd0", 6), ("#3ecf8e", 8)]):
        p.append(r(142 + i * 3, 18 - h, 2, h, c))
    p.append(r(160, 14, 5, 4, "#c06030") + r(162, 9, 1, 5, "#3ecf8e") + r(161, 10, 1, 2, "#3ecf8e")
             + r(163, 11, 1, 2, "#3ecf8e"))

    # wall clock-ish LED strip above desk
    for i in range(14):
        c = ["#ff4fd8", "#7d5fd0", "#3ef0ff"][i % 3]
        p.append(r(104 + i * 3, 25, 2, 1, c, 'opacity=".9"', blink("1;.3;1", "2.4s", f"{i * .15:.2f}s")))

    # desk
    desk, desk_dark = "#6b4f3a", "#4e3828"
    p.append(r(96, 55, 74, 3, desk) + r(96, 58, 74, 1, desk_dark))
    p.append(r(98, 59, 3, 25, desk_dark) + r(165, 59, 3, 25, desk_dark))

    # PC tower under the desk with an RGB strip
    p.append(r(146, 64, 14, 20, "#20202c") + r(147, 65, 12, 18, "#2b2b3a"))
    p.append(r(149, 67, 1, 14, "#ff4fd8", "", '<animate attributeName="fill" '
             'values="#ff4fd8;#3ef0ff;#8cff5a;#ffd166;#ff4fd8" dur="4s" repeatCount="indefinite"/>'))
    for i in range(4):
        p.append(r(152, 68 + i * 3, 5, 1, "#3a3a4e"))
    p.append(r(155, 81, 2, 1, "#8cff5a", "", blink("1;.2;1", ".8s")))

    # monitor
    p.append(r(102, 28, 40, 24, "#15151f") + r(104, 30, 36, 20, "#0a0f1f"))
    p.append(r(100, 26, 44, 28, "#3ef0ff", 'opacity=".07"'))
    p.append(r(119, 52, 6, 3, "#15151f") + r(115, 54, 14, 1, "#15151f"))
    code = [(2, 14, "#ff79c6"), (4, 20, "#8be9fd"), (4, 11, "#f1fa8c"), (6, 17, "#50fa7b"),
            (6, 9, "#bd93f9"), (4, 22, "#8be9fd"), (2, 8, "#ff79c6")]
    n = len(code)
    for i, (indent, w, c) in enumerate(code):
        t0, t1 = i / (n + 2), (i + 1) / (n + 2)
        p.append(f'<rect x="{106 + indent}" y="{32 + i * 2}" width="0" height="1" fill="{c}">'
                 f'<animate attributeName="width" values="0;0;{w};{w};0" keyTimes="0;{t0:.3f};{t1:.3f};.97;1" '
                 f'dur="7s" repeatCount="indefinite"/></rect>')
    p.append(r(106, 47, 2, 1, "#e6e6e6", "", blink("1;1;0;0", "1s")))

    # keyboard + mouse
    p.append(r(104, 53, 22, 2, "#2b2b3a") + r(105, 53, 20, 1, "#3c3c52"))
    p.append(r(130, 53, 3, 2, "#2b2b3a"))

    # coffee + steam
    p.append(r(136, 50, 5, 5, "#f4f4f4") + r(141, 51, 1, 3, "#f4f4f4") + r(137, 50, 3, 1, "#6b3e26"))
    for i, (sx, d) in enumerate([(137, "0s"), (139, ".8s"), (138, "1.6s")]):
        p.append(f'<rect x="{sx}" y="48" width="1" height="2" fill="#d7d7e8" opacity="0">'
                 f'<animate attributeName="opacity" values="0;.7;0" dur="2.4s" begin="{d}" repeatCount="indefinite"/>'
                 f'<animate attributeName="y" values="49;42" dur="2.4s" begin="{d}" repeatCount="indefinite"/></rect>')

    # cat on the desk, looking at the dev
    cat_pal = {"C": "#e08a3c", "c": "#b86a28", "e": "#7cff6b", "p": "#ff8fb1", "w": "#f6e3c8"}
    cx, cy = 150, 42
    p.append(f'<g transform="translate({cx + 9} {cy + 11})">'
             '<animateTransform attributeName="transform" type="rotate" additive="sum" '
             'values="0;-25;0;10;0" dur="2.6s" repeatCount="indefinite"/>'
             + r(0, 0, 3, 1, "#e08a3c") + r(2, -1, 1, 1, "#e08a3c") + r(3, -3, 1, 2, "#e08a3c")
             + r(3, -5, 1, 2, "#b86a28") + "</g>")
    p.append(sprite([
        ".C...C....",
        ".CC.CC....",
        ".CCCCC....",
        "CeCCeCC...",
        "CCwpwCC...",
        ".CwwwC....",
        ".CCCCCC...",
        "CCCCCCCC..",
        "CCcCCCCCC.",
        "CCcCCCCCC.",
        "CCcCCCCCC.",
        "CCcCCCCCC.",
        ".ww.ww.CC.",
    ], cat_pal, cx, cy))
    for ex in (cx + 1, cx + 4):  # blink
        p.append(r(ex, cy + 3, 1, 1, "#e08a3c", 'opacity="0"', blink("0;0;1;0", "4s")))
    # zzz / heart bubble above the cat
    p.append('<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;.6;.7;.9;1" '
             'dur="6s" repeatCount="indefinite"/>'
             + sprite([".P.P.", "PPPPP", "PPPPP", ".PPP.", "..P.."], {"P": "#ff4fd8"}, 151, 34) + "</g>")

    # chair
    p.append(r(78, 40, 4, 24, "#2a2a3d") + r(79, 41, 2, 22, "#38384f"))
    p.append(r(78, 62, 20, 3, "#2a2a3d") + r(86, 65, 2, 14, "#1c1c29"))
    p.append(r(79, 79, 16, 2, "#1c1c29") + r(78, 81, 2, 2, "#111") + r(93, 81, 2, 2, "#111"))

    # the dev (seated, facing right, headphones + shades)
    dev_pal = {"H": "#1b1b2f", "S": "#f1c27d", "s": "#d9a066", "G": "#22f0ff", "K": "#3a3a4e",
               "R": "#b8323a", "r": "#8f2530", "Y": "#f5c542", "P": "#2d3561", "X": "#111111"}
    gx, gy = 82, 36
    head_body = [
        "....HHHHH.....",
        "...HHHHHHHH...",
        "..HHHHHHHHHH..",
        "..KHHHHHHSSH..",
        "..KKHHHHSSSSS.",
        "..KKHHHSGGGGG.",
        "..KHHHHSSGGS..",
        "...HHHHSSSSSs.",
        "....HHHSSSSs..",
        ".....sSSSS....",
        "......sSs.....",
        "...RRRRRRR....",
        "..RRRRRRRRR...",
        "..RRRRRRRRRR..",
        "..RRRRYRRRRR..",
        "..RRRRRRRRRR..",
        "..RRRRRRRRRR..",
        "..RRRRRRRRRR..",
        "..rRRRRRRRRR..",
        "..rRRRRRRRRR..",
        "..rRRRRRRRRR..",
        "..rrRRRRRRRR..",
        "..PPPPPPPPPPPPPPP",
        "..PPPPPPPPPPPPPPP",
    ]
    p.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 0;0 1;0 0" '
             f'dur="3s" repeatCount="indefinite"/>' + sprite(head_body, dev_pal, gx, gy) + "</g>")
    # headphone band over the hair
    p.append(r(gx + 3, gy + 1, 1, 3, "#3a3a4e") + r(gx + 4, gy, 4, 1, "#3a3a4e"))
    # shins + shoes
    p.append(r(gx + 14, gy + 24, 3, 20, "#2d3561") + r(gx + 13, gy + 44, 6, 2, "#111111")
             + r(gx + 16, gy + 44, 3, 1, "#e6e6e6"))
    # typing arms (two layers bobbing out of phase)
    arm = r(gx + 8, gy + 15, 6, 2, "#8f2530") + r(gx + 13, gy + 16, 7, 2, "#b8323a") + r(gx + 20, gy + 16, 2, 2, "#f1c27d")
    p.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -1;0 0" '
             f'dur=".35s" repeatCount="indefinite"/>{arm}</g>')
    p.append(f'<g><animateTransform attributeName="transform" type="translate" values="0 -1;0 0;0 -1" '
             f'dur=".35s" repeatCount="indefinite"/>'
             + r(gx + 18, gy + 15, 3, 1, "#b8323a") + r(gx + 21, gy + 15, 2, 2, "#d9a066") + "</g>")
    return "".join(p)


def pixel_room_svg(caption="// pushing pixels in neo-delhi"):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="860" height="440" viewBox="0 0 {W} {H}" shape-rendering="crispEdges" role="img" aria-label="Pixel art: a developer coding at night with a cat and coffee, a cyber city outside the window">
  <title>late night build</title>
  <defs><clipPath id="frame"><rect width="{W}" height="{H}" rx="4"/></clipPath></defs>
  <g clip-path="url(#frame)">
  {room()}
  <text x="{W - 4}" y="{H - 3}" font-family="Consolas, 'JetBrains Mono', monospace" font-size="3.2" fill="#8b7fc0" text-anchor="end" shape-rendering="auto">{caption}</text>
  </g>
</svg>
"""


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "assets" / "pixel-room.svg"
    out.write_text(pixel_room_svg(), encoding="utf-8")
    print(f"wrote {out}")
