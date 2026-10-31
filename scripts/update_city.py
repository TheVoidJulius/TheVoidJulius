#!/usr/bin/env python3
"""Render a 365-day isometric commit city from GitHub's daily commit contributions."""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "commit-city.json"
SVG_FILE = ROOT / "assets" / "commit-city.svg"
LOGIN = os.environ.get("PROFILE_LOGIN", "TheVoidJulius")
PROFILE_REPO = os.environ.get("PROFILE_REPO", f"{LOGIN}/{LOGIN}").lower()
TOKEN = os.environ.get("GITHUB_TOKEN", "")
CITY_CAP = 50
RENDERER_VERSION = 2
WINDOW_DAYS = 365
REPOSITORY_LIMIT = 100
WINDOW_SIZE_DAYS = 30

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalRepositoriesWithContributedCommits
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner }
        contributions(first: 100) {
          nodes { occurredAt commitCount }
        }
      }
    }
  }
}
"""


def graphql(variables):
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to read commit contributions")
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-commit-city",
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
    collection = user.get("contributionsCollection")
    if not collection:
        raise RuntimeError("GitHub returned no commit contribution collection")
    if collection["totalRepositoriesWithContributedCommits"] > REPOSITORY_LIMIT:
        raise RuntimeError(
            f"GitHub reports more than {REPOSITORY_LIMIT} contributed repositories; "
            "increase REPOSITORY_LIMIT before publishing an incomplete city"
        )
    return collection


def fetch_daily_commits(now, previous_daily=None, full_refresh=False):
    """Fetch 30-day windows so each repository's per-day connection stays complete."""
    end = now.date()
    window_start = end - timedelta(days=WINDOW_DAYS - 1)
    recent_start = max(window_start, end - timedelta(days=WINDOW_SIZE_DAYS - 1))
    start = window_start if full_refresh or previous_daily is None else recent_start
    counts = {
        item["date"]: item["commits"]
        for item in (previous_daily or [])
        if window_start <= date.fromisoformat(item["date"]) < start
    }
    cursor = start

    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=WINDOW_SIZE_DAYS - 1), end)
        from_utc = datetime.combine(cursor, time.min, timezone.utc)
        to_utc = datetime.combine(chunk_end + timedelta(days=1), time.min, timezone.utc) - timedelta(seconds=1)
        collection = graphql({
            "login": LOGIN,
            "from": from_utc.isoformat(),
            "to": to_utc.isoformat(),
        })
        for repository_data in collection["commitContributionsByRepository"]:
            repository = repository_data["repository"]["nameWithOwner"].lower()
            if repository == PROFILE_REPO:
                continue
            for contribution in repository_data["contributions"]["nodes"]:
                contribution_date = datetime.fromisoformat(
                    contribution["occurredAt"].replace("Z", "+00:00")
                ).date()
                if start <= contribution_date <= end:
                    key = contribution_date.isoformat()
                    counts[key] = counts.get(key, 0) + contribution["commitCount"]
        cursor = chunk_end + timedelta(days=1)

    daily = [
        {"date": (start + timedelta(days=offset)).isoformat(),
         "commits": counts.get((start + timedelta(days=offset)).isoformat(), 0)}
        for offset in range(WINDOW_DAYS)
    ]
    return start, end, daily


def building_colors(commits):
    if commits >= 40:
        return "#1C654B", "#13936A", "#0B654A", "#73F6CA", "#D9FFF0", "#FFE49A"
    if commits >= 20:
        return "#15543A", "#0E805A", "#09583F", "#53E9B8", "#D1FFEA", "#A5FFE1"
    if commits >= 8:
        return "#10452F", "#0B704D", "#084A35", "#39C995", "#BAF8DA", "#63E6BE"
    if commits > 0:
        return "#0D3826", "#095B3F", "#073C2C", "#27A979", "#A1EBCB", "#45D5A2"
    return "#0A2015", "#0D281B", "#091D14", "#123323", "#8DE7BE", "#63E6BE"


def render_city_svg(now, start, end, daily, synced=True):
    by_date = {item["date"]: item["commits"] for item in daily}
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    last_saturday = end + timedelta(days=(5 - end.weekday()) % 7)
    week_count = ((last_saturday - first_sunday).days // 7) + 1
    width, height = 1200, 680
    tile_width, tile_height = 26, 14
    half_width, half_height = tile_width / 2, tile_height / 2
    center_x, center_y = 600, 422
    week_mid = (week_count - 1) / 2
    active_days = sum(value > 0 for value in by_date.values())
    total_commits = sum(by_date.values())
    peak = max(by_date.values(), default=0)

    def cell_center(week, row):
        x = center_x + ((week - week_mid) - (row - 3)) * half_width
        y = center_y + ((week - week_mid) + (row - 3)) * half_height
        return x, y

    first_center = cell_center(0, 0)
    east_center = cell_center(week_count - 1, 0)
    far_center = cell_center(week_count - 1, 6)
    west_center = cell_center(0, 6)
    plane_top = (first_center[0], first_center[1] - half_height)
    plane_east = (east_center[0] + half_width, east_center[1] + half_height)
    plane_far = (far_center[0], far_center[1] + half_height)
    plane_west = (west_center[0] - half_width, west_center[1] + half_height)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="city-title city-desc">',
        '<title id="city-title">TheVoidJulius commit city</title>',
        '<desc id="city-desc">A tilted isometric city grid with one plot for each day in the last year. Building height scales with daily commits; 50 commits or more reaches the skyline cap.</desc>',
        '<defs><linearGradient id="city-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#081711"/><stop offset=".52" stop-color="#06110C"/><stop offset="1" stop-color="#07130D"/></linearGradient><radialGradient id="city-halo"><stop stop-color="#1B9B70" stop-opacity=".2"/><stop offset="1" stop-color="#0A1710" stop-opacity="0"/></radialGradient><linearGradient id="plane-face" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#123B29"/><stop offset="1" stop-color="#07180F"/></linearGradient><linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0E2117"/><stop offset="1" stop-color="#09170F"/></linearGradient></defs>',
        '<rect x="2" y="2" width="1196" height="676" rx="20" fill="url(#city-bg)" stroke="#244A35" stroke-width="2"/>',
        '<ellipse cx="604" cy="404" rx="430" ry="240" fill="url(#city-halo)"/>',
        '<path d="M26 88h1148" stroke="#244A35"/>',
        '<rect x="26" y="92" width="350" height="3" rx="2" fill="#43C995" opacity=".7"/>',
        '<style>text{font-family:Consolas,"Courier New",monospace}.eyebrow{fill:#65E7B7;font-size:10px;letter-spacing:2px}.title{fill:#F0F7F2;font-size:22px;font-weight:700;letter-spacing:.4px}.label{fill:#87A594;font-size:9px;letter-spacing:1px}.micro{fill:#6D8978;font-size:8px;letter-spacing:.6px}.metric{fill:#F0F7F2;font-size:29px;font-weight:700}.metric-small{fill:#CBF5DF;font-size:13px;font-weight:700}.panel-title{fill:#63E6BE;font-size:9px;letter-spacing:1.5px;font-weight:700}.key-label{fill:#D5E9DC;font-size:9px}</style>',
        '<text x="28" y="30" class="eyebrow">THE VOID / LIVE BUILD LOG</text>',
        '<text x="28" y="63" class="title">THE CITY I BUILT THIS YEAR</text>',
        f'<text x="1172" y="30" text-anchor="end" class="label">{start:%Y-%m-%d}  →  {end:%Y-%m-%d}</text>',
        f'<text x="1172" y="61" text-anchor="end" class="label">UPDATED {now:%Y-%m-%d %H:%M} UTC  ·  LIVE COMMIT DATA</text>',
    ]

    out.extend([
        '<rect x="24" y="278" width="184" height="178" rx="14" fill="url(#glass)" stroke="#25533B"/>',
        '<path d="M42 302h148" stroke="#204A35"/>',
        '<text x="42" y="296" class="panel-title">CITY RECORD</text>',
        f'<text x="42" y="340" class="metric">{total_commits:,}</text>',
        '<text x="42" y="359" class="label">PROJECT COMMITS / YEAR</text>',
        f'<text x="42" y="391" class="metric-small">{active_days} active days</text>',
        f'<text x="42" y="414" class="key-label">Peak day  <tspan fill="#63E6BE">{peak} / {CITY_CAP}</tspan></text>',
        '<rect x="42" y="428" width="148" height="6" rx="3" fill="#142B1D"/>',
        f'<rect x="42" y="428" width="{148 * min(peak, CITY_CAP) / CITY_CAP:.1f}" height="6" rx="3" fill="#47D8A8"/>',
        '<text x="42" y="447" class="micro">HEIGHT MAPS TO DAILY COMMITS</text>',
        '<rect x="992" y="278" width="184" height="178" rx="14" fill="url(#glass)" stroke="#25533B"/>',
        '<path d="M1010 302h148" stroke="#204A35"/>',
        '<text x="1010" y="296" class="panel-title">BUILDING KEY</text>',
    ])

    for x, sample, color_index in ((1030, 1, 0), (1084, 25, 1), (1138, 50, 2)):
        base_y = 411
        tower_h = max(3, round(56 * sample / CITY_CAP))
        fw, fh = 22, 12
        roof_top = (x, base_y - tower_h - fh / 2)
        roof_right = (x + fw / 2, base_y - tower_h)
        roof_front = (x, base_y - tower_h + fh / 2)
        roof_left = (x - fw / 2, base_y - tower_h)
        base_right = (x + fw / 2, base_y)
        base_front = (x, base_y + fh / 2)
        base_left = (x - fw / 2, base_y)
        roof_colors = ("#27A979", "#53E9B8", "#73F6CA")
        left_colors = ("#095B3F", "#0E805A", "#13936A")
        right_colors = ("#073C2C", "#09583F", "#0B654A")
        out.append(f'<path d="M{roof_left[0]:.1f} {roof_left[1]:.1f}L{roof_front[0]:.1f} {roof_front[1]:.1f}L{base_front[0]:.1f} {base_front[1]:.1f}L{base_left[0]:.1f} {base_left[1]:.1f}Z" fill="{left_colors[color_index]}"/>')
        out.append(f'<path d="M{roof_right[0]:.1f} {roof_right[1]:.1f}L{roof_front[0]:.1f} {roof_front[1]:.1f}L{base_front[0]:.1f} {base_front[1]:.1f}L{base_right[0]:.1f} {base_right[1]:.1f}Z" fill="{right_colors[color_index]}"/>')
        out.append(f'<path d="M{roof_top[0]:.1f} {roof_top[1]:.1f}L{roof_right[0]:.1f} {roof_right[1]:.1f}L{roof_front[0]:.1f} {roof_front[1]:.1f}L{roof_left[0]:.1f} {roof_left[1]:.1f}Z" fill="{roof_colors[color_index]}"/>')
        out.append(f'<text x="{x}" y="433" text-anchor="middle" class="key-label">{sample if sample < CITY_CAP else "50+"}</text>')
    out.extend([
        '<path d="M1012 440h8" stroke="#142B1D" stroke-width="5" stroke-linecap="round"/>',
        '<text x="1027" y="443" class="micro">0 = OPEN LOT</text>',
        '<text x="1010" y="453" class="micro">50 COMMITS REACHES THE SKYLINE</text>',
    ])

    top_s = f'{plane_top[0]:.1f} {plane_top[1]:.1f}'
    east_s = f'{plane_east[0]:.1f} {plane_east[1]:.1f}'
    far_s = f'{plane_far[0]:.1f} {plane_far[1]:.1f}'
    west_s = f'{plane_west[0]:.1f} {plane_west[1]:.1f}'
    out.append(f'<path d="M{east_s}L{far_s}L{plane_far[0]:.1f} {plane_far[1] + 15:.1f}L{plane_east[0]:.1f} {plane_east[1] + 15:.1f}Z" fill="#06150D" stroke="#153D29"/>')
    out.append(f'<path d="M{west_s}L{far_s}L{plane_far[0]:.1f} {plane_far[1] + 15:.1f}L{plane_west[0]:.1f} {plane_west[1] + 15:.1f}Z" fill="url(#plane-face)" stroke="#1C5237"/>')
    out.append(f'<path d="M{top_s}L{east_s}L{far_s}L{west_s}Z" fill="#0A1F14" stroke="#2A7651" stroke-width="1.5"/>')

    calendar_days = []
    day = first_sunday
    while day <= last_saturday:
        week = ((day - first_sunday).days // 7)
        row = (day.weekday() + 1) % 7
        calendar_days.append((day, week, row))
        day += timedelta(days=1)

    for day, week, row in calendar_days:
        x, y = cell_center(week, row)
        commits = by_date.get(day.isoformat())
        tile, _, _, _, _, _ = building_colors(commits or 0)
        tooltip = "outside the 365-day window" if commits is None else html.escape(
            f"{day.isoformat()} · {commits} commit" + ("s" if commits != 1 else "")
        )
        opacity = ".42" if commits is None else "1"
        out.append(f'<g><title>{tooltip}</title><path d="M{x:.1f} {y - half_height:.1f}l{half_width:.1f} {half_height:.1f}l-{half_width:.1f} {half_height:.1f}l-{half_width:.1f} -{half_height:.1f}Z" fill="{tile}" stroke="#1B4A32" stroke-width=".7" opacity="{opacity}"/></g>')

    for day, week, row in sorted(calendar_days, key=lambda item: (item[1] + item[2], item[1])):
        commits = by_date.get(day.isoformat())
        if commits is None or commits <= 0:
            continue
        x, y = cell_center(week, row)
        _, left_color, right_color, roof_color, window_color, cap_color = building_colors(commits)
        building_height = max(3, round(100 * min(commits, CITY_CAP) / CITY_CAP))
        fw, fh = 19, 10
        roof_top = (x, y - building_height - fh / 2)
        roof_right = (x + fw / 2, y - building_height)
        roof_front = (x, y - building_height + fh / 2)
        roof_left = (x - fw / 2, y - building_height)
        base_right = (x + fw / 2, y)
        base_front = (x, y + fh / 2)
        base_left = (x - fw / 2, y)
        tooltip = html.escape(f"{day.isoformat()} · {commits} commit" + ("s" if commits != 1 else ""))
        out.append(f'<g><title>{tooltip}</title>')
        out.append(f'<path d="M{roof_left[0]:.1f} {roof_left[1]:.1f}L{roof_front[0]:.1f} {roof_front[1]:.1f}L{base_front[0]:.1f} {base_front[1]:.1f}L{base_left[0]:.1f} {base_left[1]:.1f}Z" fill="{left_color}" stroke="#06170F" stroke-width=".7"/>')
        out.append(f'<path d="M{roof_right[0]:.1f} {roof_right[1]:.1f}L{roof_front[0]:.1f} {roof_front[1]:.1f}L{base_front[0]:.1f} {base_front[1]:.1f}L{base_right[0]:.1f} {base_right[1]:.1f}Z" fill="{right_color}" stroke="#06170F" stroke-width=".7"/>')
        out.append(f'<path d="M{roof_top[0]:.1f} {roof_top[1]:.1f}L{roof_right[0]:.1f} {roof_right[1]:.1f}L{roof_front[0]:.1f} {roof_front[1]:.1f}L{roof_left[0]:.1f} {roof_left[1]:.1f}Z" fill="{roof_color}" stroke="#86F9CD" stroke-width=".65"/>')
        floors = min(8, building_height // 12)
        for floor in range(1, floors + 1):
            wy = y - 5 - floor * 10
            if wy <= roof_front[1] + 1:
                continue
            out.append(f'<rect x="{x - 6:.1f}" y="{wy:.1f}" width="2.4" height="3.4" rx=".6" fill="{window_color}" opacity=".9"/>')
            out.append(f'<rect x="{x - 1.5:.1f}" y="{wy:.1f}" width="2.4" height="3.4" rx=".6" fill="{window_color}" opacity=".72"/>')
            out.append(f'<rect x="{x + 3.3:.1f}" y="{wy:.1f}" width="2.4" height="3.4" rx=".6" fill="{window_color}" opacity=".82"/>')
        if commits >= CITY_CAP:
            out.append(f'<path d="M{x:.1f} {roof_top[1]:.1f}v-9" stroke="{cap_color}" stroke-width="1.4"/>')
            out.append(f'<circle cx="{x:.1f}" cy="{roof_top[1] - 10:.1f}" r="2.3" fill="{cap_color}"/>')
        out.append('</g>')

    if not total_commits:
        message = "NO VISIBLE PROJECT COMMITS IN THIS WINDOW YET" if synced else "AWAITING FIRST GITHUB SYNC"
        out.append(f'<text x="600" y="415" text-anchor="middle" class="label">{message}</text>')
    out.extend([
        '<text x="28" y="663" class="micro">365 DAYS / ONE LOT PER DAY / HOVER FOR THE EXACT COUNT</text>',
        '<text x="1172" y="663" text-anchor="end" class="micro">50 COMMITS = TALLEST BUILDING</text>',
    ])
    out.append('</svg>')
    return "\n".join(out) + "\n"


def main():
    now = datetime.now(timezone.utc)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    SVG_FILE.parent.mkdir(parents=True, exist_ok=True)

    previous = {}
    if DATA_FILE.exists():
        previous = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    full_refresh = os.environ.get("CITY_FULL_REFRESH", "false").lower() == "true"
    start, end, daily = fetch_daily_commits(
        now,
        previous_daily=previous.get("daily_commits"),
        full_refresh=full_refresh,
    )
    same_days = (
        previous.get("daily_commits") == daily
        and previous.get("renderer_version") == RENDERER_VERSION
    )
    if same_days and SVG_FILE.exists():
        print("Commit city is current; skipping file updates.")
        return

    record = {
        "user": LOGIN,
        "source": "GitHub GraphQL commitContributionsByRepository",
        "profile_repository_excluded": PROFILE_REPO,
        "renderer_version": RENDERER_VERSION,
        "refresh_mode": "full" if full_refresh or previous.get("daily_commits") is None else "recent-window",
        "updated_at_utc": now.isoformat(),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "daily_commits": daily,
        "total_commits": sum(item["commits"] for item in daily),
        "peak_commits": max((item["commits"] for item in daily), default=0),
    }
    SVG_FILE.write_text(render_city_svg(now, start, end, daily), encoding="utf-8")
    DATA_FILE.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        f"Updated commit city for {LOGIN}: {record['total_commits']} commits "
        f"across {sum(item['commits'] > 0 for item in daily)} days."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"commit city refresh failed: {error}", file=sys.stderr)
        raise
