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
RENDERER_VERSION = 1
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
        return "#E9BE63", "#A4772F", "#FFE49A", "#182219"
    if commits >= 20:
        return "#55D7AD", "#268D6C", "#91F4D4", "#0E2118"
    if commits >= 8:
        return "#28A879", "#176A4A", "#63E6BE", "#0D1C14"
    if commits > 0:
        return "#176A4A", "#10452F", "#39B583", "#0B1911"
    return "#14251B", "#0F1D15", "#1D3023", "#122017"


def render_city_svg(now, start, end, daily, synced=True):
    by_date = {item["date"]: item["commits"] for item in daily}
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    last_saturday = end + timedelta(days=(5 - end.weekday()) % 7)
    week_count = ((last_saturday - first_sunday).days // 7) + 1
    width, height = 1200, 570
    left, week_pitch = 64, 21
    row_pitch, first_base = 50, 166
    active_days = sum(value > 0 for value in by_date.values())
    total_commits = sum(by_date.values())
    peak = max(by_date.values(), default=0)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="city-title city-desc">',
        '<title id="city-title">TheVoidJulius commit city</title>',
        '<desc id="city-desc">An isometric building for each day in the last year. Building height scales with the daily commit count; 50 commits or more reaches the skyline cap.</desc>',
        '<defs><linearGradient id="city-bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#08130D"/><stop offset="1" stop-color="#07100B"/></linearGradient><linearGradient id="city-glow" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#63E6BE" stop-opacity=".22"/><stop offset="1" stop-color="#63E6BE" stop-opacity="0"/></linearGradient></defs>',
        '<rect x="2" y="2" width="1196" height="566" rx="18" fill="url(#city-bg)" stroke="#294734" stroke-width="2"/>',
        '<path d="M24 78h1152" stroke="#294734"/>',
        '<rect x="24" y="83" width="290" height="3" rx="2" fill="url(#city-glow)"/>',
        '<style>text{font-family:Consolas,"Courier New",monospace}.eyebrow{fill:#63E6BE;font-size:11px;letter-spacing:2px}.title{fill:#F0F7F2;font-size:21px;font-weight:700}.label{fill:#8FA99A;font-size:10px;letter-spacing:1px}.month{fill:#94AA9A;font-size:10px}.rowlabel{fill:#60786A;font-size:8px}.count{fill:#EAF4ED;font-size:15px;font-weight:700}</style>',
        '<text x="28" y="31" class="eyebrow">THE VOID / BUILD LOG</text>',
        '<text x="28" y="60" class="title">COMMIT CITY</text>',
        f'<text x="1170" y="31" text-anchor="end" class="label">{total_commits:,} COMMITS  /  {active_days} BUILT DAYS  /  PEAK {peak}</text>',
        f'<text x="1170" y="59" text-anchor="end" class="label">{start:%Y-%m-%d} → {end:%Y-%m-%d}  ·  UPDATED {now:%Y-%m-%d %H:%M} UTC</text>',
    ]

    for row, weekday in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")):
        baseline = first_base + row * row_pitch
        out.append(f'<path d="M{left - 10} {baseline + 2}H{left + week_count * week_pitch + 8}" stroke="#142A1C" stroke-width="1"/>')
        out.append(f'<text x="{left - 17}" y="{baseline - 3}" text-anchor="end" class="rowlabel">{weekday}</text>')

    month_seen = set()
    for offset in range(WINDOW_DAYS):
        day = start + timedelta(days=offset)
        week = ((day - first_sunday).days // 7)
        row = (day.weekday() + 1) % 7
        x = left + week * week_pitch + row * 3
        baseline = first_base + row * row_pitch
        commits = by_date.get(day.isoformat(), 0)
        if day.day == 1 and day.month not in month_seen:
            month_seen.add(day.month)
            out.append(f'<text x="{left + week * week_pitch}" y="111" class="month">{day:%b}</text>')

        front, side, roof, window = building_colors(commits)
        building_height = max(3, round(44 * min(commits, CITY_CAP) / CITY_CAP)) if commits else 3
        top = baseline - building_height
        tooltip = html.escape(f"{day.isoformat()} · {commits} commit" + ("s" if commits != 1 else ""))
        out.append(f'<g><title>{tooltip}</title>')
        out.append(f'<path d="M{x} {top}h9v{building_height}h-9z" fill="{front}"/>')
        out.append(f'<path d="M{x + 9} {top}l5 -3v{building_height}l-5 3z" fill="{side}"/>')
        out.append(f'<path d="M{x} {top}l5 -3h9l-5 3z" fill="{roof}"/>')
        if commits:
            floors = max(1, min(6, (building_height - 2) // 7))
            for floor in range(floors):
                wy = baseline - 5 - floor * 7
                if wy < top + 2:
                    continue
                out.append(f'<rect x="{x + 2}" y="{wy}" width="2" height="3" rx=".5" fill="{window}"/>')
                out.append(f'<rect x="{x + 6}" y="{wy}" width="2" height="3" rx=".5" fill="{window}" opacity=".78"/>')
            if commits >= CITY_CAP:
                out.append(f'<path d="M{x + 4} {top - 3}v-4h2v4" stroke="#FFE49A" stroke-width="1" fill="none"/>')
        out.append('</g>')

    out.extend([
        '<text x="28" y="530" class="label">ONE DAY / ONE BUILDING</text>',
        '<text x="28" y="548" class="label">TOWER HEIGHT = DAILY COMMITS · 50+ HITS THE SKYLINE CAP · HOVER A BUILDING FOR ITS COUNT</text>',
    ])
    legend_x, legend_y = 805, 520
    out.append(f'<text x="{legend_x}" y="{legend_y + 8}" class="label">0</text>')
    for index, commits in enumerate((1, 8, 20, 40, 50)):
        front, _, _, _ = building_colors(commits)
        x = legend_x + 25 + index * 27
        out.append(f'<rect x="{x}" y="{legend_y}" width="18" height="13" rx="2" fill="{front}"/>')
    out.append(f'<text x="{legend_x + 170}" y="{legend_y + 8}" class="label">50+</text>')
    out.append(f'<text x="1170" y="548" text-anchor="end" class="label">AUTOMATIC / REAL COMMIT CONTRIBUTIONS</text>')
    if not total_commits:
        message = "NO VISIBLE PROJECT COMMITS IN THIS WINDOW YET" if synced else "AWAITING FIRST GITHUB SYNC"
        out.append(f'<text x="600" y="325" text-anchor="middle" class="label">{message}</text>')
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
