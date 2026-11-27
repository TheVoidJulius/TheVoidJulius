"""Holo Card README generator.

Builds a holographic "collector card" profile README from your public GitHub data:
  assets/holo-card.svg   the hero card (avatar, languages, stats)
  assets/card-NN.svg     one foil card per featured repo (pinned repos first)
  README.md              ties it together, every card links to its repo

Standard library only. Needs a token for the GraphQL API:
  GITHUB_TOKEN=... python generate.py <username>
"""
import base64
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GH_USER", "TheVoidJulius")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
OUT = Path(__file__).resolve().parent
CARD_COUNT = 6
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', Consolas, 'SFMono-Regular', Menlo, monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login name bio location avatarUrl createdAt twitterUsername
    followers { totalCount }
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes { ... on Repository { name } }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name description url stargazerCount forkCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(url, data=None):
    headers = {"User-Agent": "holo-card-readme"}
    if TOKEN:
        headers["Authorization"] = f"bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def graphql():
    if not TOKEN:
        sys.exit("Set GITHUB_TOKEN (in Actions, the built-in token works).")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    res = json.loads(fetch("https://api.github.com/graphql", body))
    if res.get("errors"):
        sys.exit(f"GraphQL error: {res['errors']}")
    return res["data"]["user"]


def streaks(weeks):
    days = [d for w in weeks for d in w["contributionDays"]]
    today = dt.date.today().isoformat()
    # Today's empty square doesn't break the streak yet.
    if days and days[-1]["date"] >= today and days[-1]["contributionCount"] == 0:
        days = days[:-1]
    current = 0
    for d in reversed(days):
        if d["contributionCount"] == 0:
            break
        current += 1
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    return current, longest


def top_languages(repos, n=3):
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])[:n]
    return [(name, colors[name], size / total * 100) for name, size in ranked]


def short(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def clip(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def wrap(text, width, lines):
    words, out, line = (text or "").split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
            if len(out) == lines:
                break
        else:
            line = f"{line} {w}".strip()
    if len(out) < lines and line:
        out.append(line)
    if len(out) == lines and len(" ".join(out)) < len(" ".join(words)):
        out[-1] = clip(out[-1] + " …", width)
    return out


def pretty(name):
    """'Foo-Bar---Minor-Project' -> 'Foo Bar · Minor Project' (display only)."""
    name = name.strip("-_")
    parts = [p.replace("-", " ").replace("_", " ").strip() for p in name.split("---")]
    return " · ".join(p for p in parts if p)


def rarity(stars):
    if stars >= 50:
        return "LEGENDARY", "#ffd166"
    if stars >= 15:
        return "EPIC", "#c77dff"
    if stars >= 3:
        return "RARE", "#4cc9f0"
    return "COMMON", "#9aa4b2"


# Shared SVG defs: an animated foil gradient and a moving shine band.
def foil_defs(uid, w, h):
    return f"""
    <linearGradient id="foil{uid}" x1="0" y1="0" x2="{w}" y2="{h}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#00f5d4"/>
      <stop offset=".25" stop-color="#4cc9f0"/>
      <stop offset=".5" stop-color="#c77dff"/>
      <stop offset=".75" stop-color="#f15bb5"/>
      <stop offset="1" stop-color="#00f5d4"/>
      <animateTransform attributeName="gradientTransform" type="rotate"
        values="0 {w / 2} {h / 2};360 {w / 2} {h / 2}" dur="8s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="shine{uid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity="0"/>
      <stop offset=".45" stop-color="#fff" stop-opacity="0"/>
      <stop offset=".5" stop-color="#fff" stop-opacity=".22"/>
      <stop offset=".55" stop-color="#fff" stop-opacity="0"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
      <animate attributeName="x1" values="-1.2;1" dur="4.5s" repeatCount="indefinite"/>
      <animate attributeName="x2" values="-.2;2" dur="4.5s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="bg{uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#121826"/>
      <stop offset="1" stop-color="#0a0e17"/>
    </linearGradient>"""


def hero_svg(u, avatar_b64, langs, stats, stars, n_repos):
    W, H = 860, 440
    name = escape(clip(u["name"] or u["login"], 22))
    login = escape(u["login"].lower())
    bio = wrap(u["bio"] or "", 46, 2)
    since = u["createdAt"][:4]
    year = dt.date.today().year
    tag = rarity(stars)[0]

    lang_rows = ""
    for i, (lname, color, pct) in enumerate(langs):
        y = 340 + i * 22
        lang_rows += f"""
      <rect x="44" y="{y - 9}" width="10" height="10" rx="2" fill="{color}"/>
      <text x="62" y="{y}" class="mono" font-size="12" fill="#d7dde8">{escape(lname)}</text>
      <text x="290" y="{y}" class="mono" font-size="11" fill="#8b95a7" text-anchor="end">{pct:.0f}%</text>"""

    tiles = [("STARS", stars), ("FOLLOWERS", u["followers"]["totalCount"]),
             ("CONTRIBUTIONS", stats["total"]), ("DAY STREAK", stats["current"])]
    tile_svg = ""
    for i, (label, value) in enumerate(tiles):
        x = 380 + (i % 2) * 222
        y = 168 + 22 * len(bio) + 30 + (i // 2) * 92
        tile_svg += f"""
    <g transform="translate({x} {y})">
      <rect width="206" height="78" rx="12" fill="#151c2b" stroke="#25304a"/>
      <text x="18" y="42" class="mono" font-size="28" font-weight="700" fill="url(#foilH)">{short(value) if value >= 10000 else f"{value:,}"}</text>
      <text x="18" y="62" class="mono" font-size="10" letter-spacing="2" fill="#8b95a7">{label}</text>
    </g>"""

    bio_svg = "".join(
        f'<text x="380" y="{168 + i * 22}" font-size="15" fill="#aab4c5">{escape(line)}</text>'
        for i, line in enumerate(bio))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{name} holo card">
  <title>{name} · Collector's Edition</title>
  <style>
    text {{ font-family: {FONT}; }}
    .mono {{ font-family: {MONO}; }}
  </style>
  <defs>{foil_defs("H", W, H)}
    <clipPath id="avatarClip"><rect x="40" y="70" width="260" height="210" rx="10"/></clipPath>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8"/>
    </filter>
  </defs>

  <rect width="{W}" height="{H}" rx="22" fill="url(#bgH)"/>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="21" fill="none" stroke="#1f2940"/>

  <!-- the collector card -->
  <g>
    <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="5s" repeatCount="indefinite"/>
    <rect x="26" y="24" width="288" height="392" rx="18" fill="url(#foilH)" opacity=".55" filter="url(#glow)"/>
    <rect x="26" y="24" width="288" height="392" rx="18" fill="#0e1422" stroke="url(#foilH)" stroke-width="4"/>
    <text x="44" y="56" font-size="17" font-weight="700" fill="#f4f7fb">{name}</text>
    <text x="296" y="56" class="mono" font-size="11" fill="#ffd166" text-anchor="end">★ {short(stars)}</text>
    <image x="40" y="70" width="260" height="210" preserveAspectRatio="xMidYMid slice"
      href="data:image/png;base64,{avatar_b64}" clip-path="url(#avatarClip)"/>
    <rect x="40" y="70" width="260" height="210" rx="10" fill="url(#foilH)" opacity=".12"/>
    <rect x="40" y="70" width="260" height="210" rx="10" fill="none" stroke="url(#foilH)" stroke-width="1.5"/>
    <text x="44" y="306" class="mono" font-size="10" letter-spacing="1.5" fill="#8b95a7">{tag} · {n_repos} REPOS · SINCE {since}</text>
    <line x1="44" y1="318" x2="296" y2="318" stroke="#25304a"/>{lang_rows}
    <rect x="26" y="24" width="288" height="392" rx="18" fill="url(#shineH)"/>
  </g>

  <!-- right side -->
  <text x="380" y="72" class="mono" font-size="11" letter-spacing="3" fill="url(#foilH)">COLLECTOR'S EDITION · {year}</text>
  <text x="378" y="124" font-size="42" font-weight="800" fill="#f4f7fb">@{login}</text>
  {bio_svg}
  {tile_svg}
  <text x="{W - 30}" y="{H - 16}" class="mono" font-size="9" fill="#4a5568" text-anchor="end">refreshed {dt.date.today().isoformat()}</text>
</svg>
"""


def repo_svg(i, r):
    W, H = 420, 170
    uid = f"R{i}"
    tier, tier_color = rarity(r["stargazerCount"])
    lang = r["primaryLanguage"] or {"name": "—", "color": "#8b949e"}
    desc = wrap(r["description"] or "A project in progress.", 54, 2)
    desc_svg = "".join(
        f'<text x="24" y="{86 + j * 19}" font-size="13" fill="#aab4c5">{escape(line)}</text>'
        for j, line in enumerate(desc))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(r['name'])}">
  <title>{escape(r['name'])}</title>
  <style>
    text {{ font-family: {FONT}; }}
    .mono {{ font-family: {MONO}; }}
  </style>
  <defs>{foil_defs(uid, W, H)}</defs>
  <rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="16" fill="url(#bg{uid})" stroke="url(#foil{uid})" stroke-width="2.5"/>
  <text x="24" y="34" class="mono" font-size="10" letter-spacing="2.5" fill="url(#foil{uid})">CARD {i:02d}</text>
  <text x="{W - 24}" y="34" class="mono" font-size="10" letter-spacing="2" fill="{tier_color}" text-anchor="end">{tier}</text>
  <text x="24" y="60" font-size="18" font-weight="700" fill="#f4f7fb">{escape(clip(pretty(r['name']), 36))}</text>
  {desc_svg}
  <line x1="24" y1="132" x2="{W - 24}" y2="132" stroke="#25304a"/>
  <text x="24" y="152" class="mono" font-size="12" fill="#ffd166">★ {r['stargazerCount']}</text>
  <text x="76" y="152" class="mono" font-size="12" fill="#8b95a7">⑂ {r['forkCount']}</text>
  <circle cx="134" cy="148" r="5" fill="{lang['color'] or '#8b949e'}"/>
  <text x="145" y="152" class="mono" font-size="12" fill="#d7dde8">{escape(lang['name'])}</text>
  <rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="16" fill="url(#shine{uid})"/>
</svg>
"""


def readme(u, cards):
    login = u["login"]
    rows = ""
    for i in range(0, len(cards), 2):
        cells = "".join(
            f'<td><a href="{r["url"]}"><img src="assets/card-{n:02d}.svg" width="410" alt="{escape(r["name"])}"/></a></td>'
            for n, r in cards[i:i + 2])
        rows += f"  <tr>{cells}</tr>\n"
    socials = f'<a href="https://github.com/{login}">GitHub</a>'
    if u.get("twitterUsername"):
        socials += f' · <a href="https://x.com/{u["twitterUsername"]}">X / Twitter</a>'
    return f"""<div align="center">

<img src="assets/holo-card.svg" width="860" alt="{escape(u['name'] or login)} · holo card"/>

### ✦ The Collection ✦

<table>
{rows}</table>

<sub>{socials} · cards re-foiled daily from live GitHub data</sub>

</div>
"""


def main():
    u = graphql()
    repos = u["repositories"]["nodes"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    current, longest = streaks(cal["weeks"])
    stats = {"total": cal["totalContributions"], "current": current, "longest": longest}
    stars = sum(r["stargazerCount"] for r in repos)

    pinned = [p["name"] for p in u["pinnedItems"]["nodes"] if p]
    by_name = {r["name"]: r for r in repos}
    featured = [by_name[n] for n in pinned if n in by_name]
    rest = sorted((r for r in repos if r["name"] not in pinned and r["name"].lower() != USER.lower()),
                  key=lambda r: (-r["stargazerCount"], -r["forkCount"]))
    featured = (featured + rest)[:CARD_COUNT]

    avatar = base64.b64encode(fetch(u["avatarUrl"] + "&s=420")).decode()

    assets = OUT / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "holo-card.svg").write_text(
        hero_svg(u, avatar, top_languages(repos), stats, stars, u["repositories"]["totalCount"]),
        encoding="utf-8")
    cards = list(enumerate(featured, 1))
    for n, r in cards:
        (assets / f"card-{n:02d}.svg").write_text(repo_svg(n, r), encoding="utf-8")
    (OUT / "README.md").write_text(readme(u, cards), encoding="utf-8")
    print(f"{u['login']}: {stars} stars, {stats['total']} contributions, "
          f"streak {current} (best {longest}), {len(cards)} repo cards")


if __name__ == "__main__":
    main()
