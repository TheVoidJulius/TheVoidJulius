#!/usr/bin/env python3
"""Build the profile heatmap from GitHub's real public contribution calendar."""

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


def main():
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
    DATA_FILE.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    SVG_FILE.write_text(render_svg(now, total, days), encoding="utf-8")
    print(f"Updated real contribution data for {LOGIN}: {len(days)} days, {total} total.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"profile refresh failed: {error}", file=sys.stderr)
        raise

