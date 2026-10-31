#!/usr/bin/env python3
"""Build local profile telemetry from GitHub's real public contribution calendar."""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "contributions.json"
SVG_FILE = ROOT / "contrib-heatmap.svg"
STATS_FILE = ROOT / "assets" / "github-stats.svg"
RECENT_DATA_FILE = ROOT / "data" / "recent-builds.json"
RECENT_SVG_FILE = ROOT / "assets" / "recent-builds.svg"
RECENT_LIMIT = 4
LOGIN = os.environ.get("PROFILE_LOGIN", "TheVoidJulius")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            weekday
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""

RECENT_REPOSITORIES_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(
      first: 100
      affiliations: [OWNER]
      privacy: PUBLIC
      isFork: false
      orderBy: { field: UPDATED_AT, direction: DESC }
    ) {
      nodes {
        name
        description
        url
        pushedAt
        primaryLanguage { name color }
        stargazerCount
        forkCount
        isArchived
        isFork
      }
    }
  }
}
"""


def fetch_recent_repositories():
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to read public repositories")
    body = json.dumps({
        "query": RECENT_REPOSITORIES_QUERY,
        "variables": {"login": LOGIN},
    }).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-profile-refresh",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub repository query failed ({exc.code}): {detail}") from exc
    if payload.get("errors"):
        raise RuntimeError("GitHub repository query error: " + json.dumps(payload["errors"]))
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {LOGIN!r} was not returned")
    nodes = user["repositories"]["nodes"]
    repositories = [
        node for node in nodes
        if node.get("pushedAt")
        and not node.get("isArchived")
        and not node.get("isFork")
        and node.get("name", "").casefold() != LOGIN.casefold()
    ]
    repositories.sort(key=lambda node: node["pushedAt"], reverse=True)
    return repositories[:RECENT_LIMIT]


def refresh_recent_builds(now):
    repositories = fetch_recent_repositories()
    records = [
        {
            "name": repo["name"],
            "url": repo["url"],
            "description": repo.get("description"),
            "language": repo.get("primaryLanguage"),
            "pushed_at": repo["pushedAt"],
            "stars": repo.get("stargazerCount", 0),
            "forks": repo.get("forkCount", 0),
        }
        for repo in repositories
    ]
    if not records:
        raise RuntimeError("GitHub returned no public repositories with push activity")

    previous = {}
    if RECENT_DATA_FILE.exists():
        try:
            previous = json.loads(RECENT_DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    if previous.get("repositories") == records:
        print("No public repository activity changes.")
        return False

    record = {
        "user": LOGIN,
        "source": "GitHub GraphQL public repositories",
        "generated_by": "commit-city refresh",
        "updated_at_utc": now.isoformat(),
        "repositories": records,
    }
    RECENT_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECENT_SVG_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECENT_DATA_FILE.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    RECENT_SVG_FILE.write_text(render_recent_builds_svg(now, records), encoding="utf-8")
    print(f"Updated recent build stream with {len(records)} public repositories.")
    return True


def render_recent_builds_svg(now, repositories):
    width = 1100
    pad = 24
    gap = 16
    card_height = 112
    row_gap = 12
    rows = (len(repositories) + 1) // 2
    height = 96 + rows * (card_height + row_gap) + 12
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">TheVoidJulius live public build stream</title>',
        '<desc id="desc">The four most recently pushed public, non-fork repositories, with source language, stars, forks, and exact push timestamps.</desc>',
        '<defs><linearGradient id="stream-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0A1710"/><stop offset="1" stop-color="#07100B"/></linearGradient><linearGradient id="stream-accent" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#63E6BE"/><stop offset="1" stop-color="#1F7850"/></linearGradient></defs>',
        '<style>text{font-family:Consolas,"Courier New",monospace}.eyebrow{fill:#63E6BE;font-size:10px;letter-spacing:2px}.headline{fill:#EAF4ED;font-size:20px;font-weight:700;letter-spacing:1px}.meta{fill:#91A79A;font-size:10px;letter-spacing:1px}.repo{fill:#ECF8F0;font-size:16px;font-weight:700}.detail{fill:#A5BCAF;font-size:11px}.rank{fill:#63E6BE;font-size:10px;letter-spacing:1px}</style>',
        f'<rect x="2" y="2" width="{width - 4}" height="{height - 4}" rx="18" fill="url(#stream-bg)" stroke="#294734" stroke-width="2"/>',
        '<text x="26" y="28" class="eyebrow">VOID / LIVE BUILD STREAM</text>',
        '<text x="26" y="54" class="headline">RECENT REPOSITORY ACTIVITY</text>',
        f'<text x="{width - 26}" y="28" class="meta" text-anchor="end">UPDATED {now:%Y-%m-%d %H:%M} UTC</text>',
        '<text x="26" y="76" class="meta">PUBLIC · OWNER BUILDS · SORTED BY LATEST SOURCE PUSH · PROFILE REPO EXCLUDED</text>',
        '<path d="M26 86h1048" stroke="#294734"/>',
    ]
    def short(value, limit):
        value = str(value or "")
        return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"

    for index, repo in enumerate(repositories):
        row, column = divmod(index, 2)
        full_last = len(repositories) % 2 == 1 and index == len(repositories) - 1
        card_width = width - 2 * pad if full_last else (width - 2 * pad - gap) // 2
        x = pad if full_last else pad + column * (card_width + gap)
        y = 96 + row * (card_height + row_gap)
        name_limit = 58 if card_width > 700 else 38
        name = html.escape(short(repo["name"], name_limit))
        url = html.escape(repo["url"], quote=True)
        language = repo.get("language") or {}
        language_name = language.get("name") or "LANGUAGE NOT SET"
        description = repo.get("description")
        detail = short(description, 76 if card_width > 700 else 42) if description else f"SOURCE / {language_name}"
        detail = html.escape(detail)
        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
        pushed_label = pushed.strftime("%b %d · %H:%M UTC").upper()
        stars = int(repo.get("stars") or 0)
        forks = int(repo.get("forks") or 0)
        out.extend([
            f'<a href="{url}">',
            f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="12" fill="#0B1B12" stroke="#294734"/>',
            f'<rect x="{x + 1}" y="{y + 14}" width="3" height="{card_height - 28}" rx="2" fill="url(#stream-accent)"/>',
            f'<text x="{x + 18}" y="{y + 29}" class="repo">{name}</text>',
            f'<text x="{x + card_width - 16}" y="{y + 28}" class="rank" text-anchor="end">BUILD {index + 1:02d}</text>',
            f'<text x="{x + 18}" y="{y + 53}" class="detail">{detail}</text>',
            f'<path d="M{x + 18} {y + 69}h{card_width - 36}" stroke="#203B2A"/>',
            f'<text x="{x + 18}" y="{y + 91}" class="meta">PUSHED {pushed_label}</text>',
            f'<text x="{x + card_width - 16}" y="{y + 91}" class="meta" text-anchor="end">STARS {stars}  /  FORKS {forks}</text>',
            '</a>',
        ])
    out.append("</svg>")
    return "\n".join(out) + "\n"



def fetch_calendar():
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to read the contribution calendar")
    now = datetime.now(timezone.utc)
    start = now.date() - timedelta(days=364)
    variables = {
        "login": LOGIN,
        "from": datetime.combine(start, datetime.min.time(), timezone.utc).isoformat(),
        "to": now.isoformat(),
    }
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-profile-refresh",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub GraphQL request failed ({exc.code}): {detail}") from exc
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL error: " + json.dumps(payload["errors"]))
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {LOGIN!r} was not returned")
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        day for week in calendar["weeks"] for day in week["contributionDays"]
        if start.isoformat() <= day["date"] <= now.date().isoformat()
    ]
    if not days:
        raise RuntimeError("GitHub returned an empty contribution calendar")
    return now, calendar["totalContributions"], days


def streak_lengths(days):
    active_dates = sorted(
        date.fromisoformat(day["date"])
        for day in days
        if day["contributionCount"] > 0
    )
    if not active_dates:
        return 0, 0
    longest = run = 1
    for previous, current in zip(active_dates, active_dates[1:]):
        run = run + 1 if current == previous + timedelta(days=1) else 1
        longest = max(longest, run)
    active_set = set(active_dates)
    today = datetime.now(timezone.utc).date()
    cursor = today if today in active_set else today - timedelta(days=1)
    current = 0
    while cursor in active_set:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def color_for(level):
    return {
        "NONE": "#102219",
        "FIRST_QUARTILE": "#16472E",
        "SECOND_QUARTILE": "#1F7850",
        "THIRD_QUARTILE": "#32B77B",
        "FOURTH_QUARTILE": "#63E6BE",
    }.get(level, "#102219")


def render_svg(now, total, days):
    by_date = {day["date"]: day for day in days}
    start = date.fromisoformat(days[0]["date"])
    end = date.fromisoformat(days[-1]["date"])
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    last_saturday = end + timedelta(days=(5 - end.weekday()) % 7)
    weeks = []
    cursor = first_sunday
    while cursor <= last_saturday:
        weeks.append(cursor)
        cursor += timedelta(days=7)

    width = max(780, 54 + len(weeks) * 14)
    height = 184
    current, longest = streak_lengths(days)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">TheVoidJulius GitHub contribution calendar</title>',
        '<desc id="desc">One year of GitHub contributions, refreshed automatically. Scheduled profile maintenance commits may be included.</desc>',
        '<rect width="100%" height="100%" rx="12" fill="#07110C"/>',
        '<style>text{font-family:Consolas,"Courier New",monospace}.label{fill:#91A79A;font-size:11px}.headline{fill:#EAF4ED;font-size:13px;font-weight:700}</style>',
        f'<text x="22" y="24" class="headline">{html.escape(LOGIN)} / CONTRIBUTION SIGNAL</text>',
        f'<text x="22" y="43" class="label">{total} contributions · current streak {current}d · longest {longest}d · refreshed {now:%Y-%m-%d %H:%M} UTC</text>',
    ]
    month_seen = set()
    for col, sunday in enumerate(weeks):
        x = 22 + col * 14
        if sunday.month not in month_seen:
            month_seen.add(sunday.month)
            out.append(f'<text x="{x}" y="62" class="label">{sunday.strftime("%b")}</text>')
        for row in range(7):
            day_date = sunday + timedelta(days=row)
            item = by_date.get(day_date.isoformat())
            if item is None:
                continue
            y = 72 + row * 14
            title = html.escape(f"{day_date.isoformat()}: {item['contributionCount']} contributions")
            out.append(
                f'<rect x="{x}" y="{y}" width="10" height="10" rx="2" fill="{color_for(item["contributionLevel"])}">'
                f"<title>{title}</title></rect>"
            )
    legend_y = height - 17
    lx = width - 150
    out.append(f'<text x="{lx - 35}" y="{legend_y + 9}" class="label">less</text>')
    for idx, level in enumerate(["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]):
        out.append(f'<rect x="{lx + idx * 16}" y="{legend_y}" width="11" height="11" rx="2" fill="{color_for(level)}"/>')
    out.append(f'<text x="{lx + 91}" y="{legend_y + 9}" class="label">more</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_stats_svg(now, total, days):
    current, longest = streak_lengths(days)
    by_month = {}
    for item in days:
        day = date.fromisoformat(item["date"])
        key = (day.year, day.month)
        by_month[key] = by_month.get(key, 0) + item["contributionCount"]

    end_index = now.year * 12 + now.month - 1
    months = []
    for index in range(end_index - 11, end_index + 1):
        year, month_zero = divmod(index, 12)
        month = month_zero + 1
        months.append((year, month, by_month.get((year, month), 0)))
    max_month = max((value for _, _, value in months), default=0) or 1

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="286" viewBox="0 0 1100 286" role="img" aria-labelledby="title desc">',
        '<title id="title">Live GitHub contribution readout</title>',
        '<desc id="desc">Real contribution total, current and longest streaks, and monthly activity over the last year. Refreshed daily by GitHub Actions.</desc>',
        '<defs><linearGradient id="stats-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0A1710"/><stop offset="1" stop-color="#07100B"/></linearGradient><linearGradient id="bar-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#63E6BE"/><stop offset="1" stop-color="#1F7850"/></linearGradient></defs>',
        '<rect x="2" y="2" width="1096" height="282" rx="18" fill="url(#stats-bg)" stroke="#294734" stroke-width="2"/>',
        '<style>text{font-family:Consolas,"Courier New",monospace}.label{fill:#8FA99A;font-size:11px;letter-spacing:1px}.metric{fill:#F0F7F2;font-size:28px;font-weight:700}.sub{fill:#63E6BE;font-size:11px;letter-spacing:1px}.month{fill:#849B8D;font-size:10px}</style>',
        '<text x="28" y="30" class="sub">GITHUB SIGNAL / 365-DAY READOUT</text>',
        f'<text x="1070" y="30" class="label" text-anchor="end">UPDATED {now:%Y-%m-%d %H:%M} UTC</text>',
    ]
    metrics = [
        (28, str(total), "CONTRIBUTIONS / YEAR"),
        (374, f"{current}d", "CURRENT STREAK"),
        (720, f"{longest}d", "LONGEST STREAK"),
    ]
    for x, value, label in metrics:
        out.append(f'<rect x="{x}" y="46" width="328" height="80" rx="12" fill="#0D2016" stroke="#294734"/>')
        out.append(f'<text x="{x + 18}" y="82" class="metric">{html.escape(value)}</text>')
        out.append(f'<text x="{x + 18}" y="108" class="label">{label}</text>')

    out.append('<text x="28" y="160" class="sub">MONTHLY CONTRIBUTIONS / LAST 12 MONTHS</text>')
    base_y = 249
    x_start = 258
    gap = 67
    bar_width = 34
    for i, (year, month, value) in enumerate(months):
        x = x_start + i * gap
        height = round(55 * value / max_month) if value else 0
        if height:
            out.append(f'<rect x="{x}" y="{base_y - height}" width="{bar_width}" height="{height}" rx="5" fill="url(#bar-fill)"/>')
        else:
            out.append(f'<path d="M{x} {base_y}h{bar_width}" stroke="#24412F" stroke-width="3" stroke-linecap="round"/>')
        out.append(f'<text x="{x + bar_width / 2}" y="269" class="month" text-anchor="middle">{date(year, month, 1):%b}</text>')
    out.append(f'<path d="M{x_start - 7} {base_y + 1}h{12 * gap - 20}" stroke="#345342" stroke-width="1"/>')
    out.append('<text x="1070" y="269" class="label" text-anchor="end">AUTOMATED / REAL GITHUB DATA</text>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


def main():
    if "--recent-only" in sys.argv[1:]:
        refresh_recent_builds(datetime.now(timezone.utc))
        return
    now, total, days = fetch_calendar()
    current, longest = streak_lengths(days)
    record = {
        "user": LOGIN,
        "source": "GitHub GraphQL contributionCalendar",
        "generated_by": "scheduled profile refresh",
        "updated_at_utc": now.isoformat(),
        "total_contributions": total,
        "current_streak_days": current,
        "longest_streak_days": longest,
        "days": days,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    SVG_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    SVG_FILE.write_text(render_svg(now, total, days), encoding="utf-8")
    STATS_FILE.write_text(render_stats_svg(now, total, days), encoding="utf-8")
    try:
        refresh_recent_builds(now)
    except Exception as error:
        print(f"Recent build stream refresh skipped: {error}", file=sys.stderr)
    print(f"Updated real contribution data for {LOGIN}: {len(days)} days, {total} total.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"profile refresh failed: {error}", file=sys.stderr)
        raise

