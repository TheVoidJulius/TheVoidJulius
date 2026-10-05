import json, os, re, requests
from bs4 import BeautifulSoup
USER = os.environ.get("GH_USER", "TheVoidJulius")
html = requests.get(f"https://github.com/users/{USER}/contributions",
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
soup = BeautifulSoup(html, "html.parser")
tips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip")}
days = []
for td in soup.select("td.ContributionCalendar-day"):
    d = td.get("data-date")
    if not d: continue
    txt = tips.get(td.get("id"), "")
    m = re.match(r"(\d[\d,]*)\s+contribution", txt)
    days.append({"date": d, "level": int(td.get("data-level", 0)), "count": int(m.group(1).replace(",", "")) if m else 0})
days.sort(key=lambda x: x["date"])
total = sum(x["count"] for x in days)
cur = longest = run = 0
for x in days:
    run = run + 1 if x["count"] > 0 else 0
    longest = max(longest, run)
cur = 0
for x in reversed(days):
    if x["count"] > 0: cur += 1
    elif x is days[-1]: continue
    else: break
best = max(days, key=lambda x: x["count"]) if days else {"date": "-", "count": 0}
os.makedirs("data", exist_ok=True)
json.dump({"user": USER, "total": total, "current_streak": cur, "longest_streak": longest, "best_day": best, "days": days}, open("data/contributions.json", "w"))
print(len(days), "days,", total, "contributions")
