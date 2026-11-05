#!/usr/bin/env python3
"""Generate self-hosted GitHub profile cards using GitHub's API."""
import json
import os
import urllib.request
import urllib.error
from collections import Counter
from datetime import date, timedelta
from html import escape

USERNAME = os.getenv("GH_USERNAME", "nawsintabassum")
TOKEN = os.getenv("GH_TOKEN")
OUT = "assets"
BG = "#1a1b27"
CARD = "#24283b"
TEXT = "#c0caf5"
MUTED = "#a9b1d6"
ACCENT = "#7aa2f7"
PURPLE = "#bb9af7"
GREEN = "#9ece6a"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login name followers { totalCount } following { totalCount }
    repositories( first: 100, ownerAffiliations: OWNER, privacy: PUBLIC,
                  orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

def request_json(url, data=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "nawsintabassum-profile-cards",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc

def fetch_profile():
    if not TOKEN:
        raise RuntimeError("GH_TOKEN is missing. Enable the GITHUB_TOKEN secret in Actions.")
    result = request_json(
        "https://api.github.com/graphql",
        json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    )
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user @{USERNAME} was not found.")
    return user

def fetch_languages():
    repos = request_json(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated&type=owner"
    )
    totals = Counter()
    for repo in repos:
        if not repo.get("fork"):
            try:
                langs = request_json(repo["languages_url"])
                totals.update(langs)
            except Exception as exc:
                print(f"Skipping languages for {repo.get('name')}: {exc}")
    return totals

def svg_card(title, width=495, height=190):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7aa2f7"/><stop offset="1" stop-color="#bb9af7"/></linearGradient></defs>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" fill="{BG}" stroke="#414868"/>',
        f'<text x="24" y="34" fill="{ACCENT}" font-family="Segoe UI,Arial,sans-serif" font-size="17" font-weight="700">{escape(title)}</text>',
    ]

def label_value(parts, x, y, label, value, color=TEXT, size=23):
    parts.append(f'<text x="{x}" y="{y}" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="12">{escape(label)}</text>')
    parts.append(f'<text x="{x}" y="{y+29}" fill="{color}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="700">{escape(str(value))}</text>')

def write_svg(name, parts):
    parts.append("</svg>")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as file:
        file.write("\n".join(parts))

def streak_values(days):
    counts = [d["contributionCount"] for d in days]
    current = 0
    # If today has no contribution yet, a streak ending yesterday is still active.
    start = len(counts) - 1
    if counts and counts[-1] == 0 and date.fromisoformat(days[-1]["date"]) == date.today():
        start -= 1
    for index in range(start, -1, -1):
        if counts[index] > 0:
            current += 1
        else:
            break
    longest = run = 0
    for count in counts:
        run = run + 1 if count > 0 else 0
        longest = max(longest, run)
    return current, longest

def main():
    user = fetch_profile()
    collection = user["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    languages = fetch_languages()
    public_repos = user["repositories"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in user["repositories"]["nodes"])
    total = calendar["totalContributions"]

    # Main statistics card
    p = svg_card(f"{USERNAME}'s GitHub Stats")
    label_value(p, 25, 76, "TOTAL CONTRIBUTIONS", f"{total:,}", ACCENT)
    label_value(p, 190, 76, "PUBLIC REPOSITORIES", public_repos, PURPLE)
    label_value(p, 355, 76, "TOTAL STARS", stars, GREEN)
    label_value(p, 25, 139, "COMMITS", collection["totalCommitContributions"], ACCENT)
    label_value(p, 190, 139, "PULL REQUESTS", collection["totalPullRequestContributions"], PURPLE)
    label_value(p, 355, 139, "ISSUES", collection["totalIssueContributions"], GREEN)
    write_svg("github-stats.svg", p)

    # Top languages card
    p = svg_card("Most Used Languages", height=190)
    top = languages.most_common(6)
    total_bytes = sum(languages.values()) or 1
    colors = ["#7aa2f7", "#bb9af7", "#9ece6a", "#e0af68", "#f7768e", "#7dcfff"]
    x, y, bar_w, gap = 25, 66, 445, 13
    used = 0
    for idx, (lang, amount) in enumerate(top):
        pct = amount / total_bytes * 100
        w = bar_w * amount / total_bytes
        p.append(f'<rect x="{x+used:.2f}" y="{y}" width="{max(w,1):.2f}" height="10" rx="4" fill="{colors[idx]}"/>')
        used += w
    for idx, (lang, amount) in enumerate(top):
        col = idx % 2
        row = idx // 2
        lx = 25 + col * 235
        ly = 105 + row * 27
        p.append(f'<circle cx="{lx+4}" cy="{ly-4}" r="4" fill="{colors[idx]}"/>')
        p.append(f'<text x="{lx+16}" y="{ly}" fill="{TEXT}" font-family="Segoe UI,Arial,sans-serif" font-size="12">{escape(lang)}</text>')
        p.append(f'<text x="{lx+210}" y="{ly}" fill="{MUTED}" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" font-size="12">{amount/total_bytes*100:.1f}%</text>')
    if not top:
        p.append(f'<text x="25" y="90" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="13">No language data available yet.</text>')
    write_svg("top-langs.svg", p)

    # Contribution streak card: calculated from GitHub's contribution calendar.
    current, longest = streak_values(days)
    p = svg_card("GitHub Contribution Streak")
    label_value(p, 55, 92, "CURRENT STREAK", f"{current} days", ACCENT, 27)
    label_value(p, 275, 92, "LONGEST STREAK", f"{longest} days", PURPLE, 27)
    p.append(f'<text x="55" y="157" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="12">Based on your GitHub contribution calendar (last 12 months).</text>')
    write_svg("github-streak.svg", p)

    # Contribution graph (daily count over the last year)
    p = svg_card("Contribution Activity — Last 12 Months", width=1000, height=300)
    chart_days = days[-365:]
    left, top, plot_w, plot_h = 48, 65, 920, 175
    max_count = max([d["contributionCount"] for d in chart_days] or [1]) or 1
    points = []
    for i, day in enumerate(chart_days):
        x = left + (i / max(1, len(chart_days)-1)) * plot_w
        y = top + plot_h - (day["contributionCount"] / max_count) * plot_h
        points.append(f"{x:.1f},{y:.1f}")
    p.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#414868"/>')
    if points:
        p.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="url(#g)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    p.append(f'<text x="{left}" y="270" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="11">{escape(chart_days[0]["date"] if chart_days else "")}</text>')
    p.append(f'<text x="{left+plot_w}" y="270" text-anchor="end" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="11">{escape(chart_days[-1]["date"] if chart_days else "")}</text>')
    write_svg("contributions.svg", p)
    print(f"Generated profile cards for @{USERNAME}.")

if __name__ == "__main__":
    main()
