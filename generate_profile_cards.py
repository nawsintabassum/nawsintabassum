#!/usr/bin/env python3
"""Generate dashboard-style GitHub profile cards in the Tokyo Night palette."""
import json
import os
import math
import urllib.request
import urllib.error
from collections import Counter
from datetime import date
from html import escape

USERNAME = os.getenv("GH_USERNAME", "nawsintabassum")
TOKEN = os.getenv("GH_TOKEN")
OUT = "assets"

# Keep the original Tokyo Night palette
BG = "#1a1b27"
CARD = "#24283b"
TEXT = "#c0caf5"
MUTED = "#a9b1d6"
ACCENT = "#7aa2f7"
PURPLE = "#bb9af7"
GREEN = "#9ece6a"
PINK = "#f7768e"
CYAN = "#7dcfff"
GOLD = "#e0af68"
BORDER = "#414868"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login name followers { totalCount } following { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC,
      orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount nodes { name stargazerCount }
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
    byte_totals = Counter()
    repo_counts = Counter()
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = request_json(repo["languages_url"])
            byte_totals.update(langs)
            for language in langs:
                repo_counts[language] += 1
        except Exception as exc:
            print(f"Skipping languages for {repo.get('name')}: {exc}")
    return byte_totals, repo_counts

def svg_start(title, width, height):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs>',
        f'<linearGradient id="panel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CARD}"/><stop offset="1" stop-color="{BG}"/></linearGradient>',
        f'<linearGradient id="glow" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{ACCENT}"/></linearGradient>',
        f'<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>',
        '</defs>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="18" fill="url(#panel)" stroke="{BORDER}"/>',
        f'<text x="28" y="39" fill="{TEXT}" font-family="Segoe UI,Arial,sans-serif" font-size="19" font-weight="700">{escape(title)}</text>',
    ]

def write_svg(name, parts):
    parts.append("</svg>")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as file:
        file.write("\n".join(parts))

def streak_values(days):
    counts = [d["contributionCount"] for d in days]
    current = 0
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

def add_donut(parts, cx, cy, radius, values, colors, total_label):
    total = sum(value for _, value in values) or 1
    circumference = 2 * math.pi * radius
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
        f'stroke="{BORDER}" stroke-width="17"/>'
    )
    offset = 0
    for index, (label, value) in enumerate(values):
        length = circumference * value / total
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
            f'stroke="{colors[index % len(colors)]}" stroke-width="17" '
            f'stroke-dasharray="{length:.2f} {circumference-length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += length
    parts.append(
        f'<text x="{cx}" y="{cy-2}" text-anchor="middle" fill="{TEXT}" '
        f'font-size="23" font-weight="700" font-family="Segoe UI,Arial,sans-serif">'
        f'{total_label}</text>'
    )
    parts.append(
        f'<text x="{cx}" y="{cy+18}" text-anchor="middle" fill="{MUTED}" '
        f'font-size="9" font-family="Segoe UI,Arial,sans-serif">LANGUAGES</text>'
    )

def add_legend(parts, x, y, values, colors, max_items=5):
    total = sum(v for _, v in values) or 1
    for index, (label, value) in enumerate(values[:max_items]):
        yy = y + index * 25
        color = colors[index % len(colors)]
        pct = value / total * 100
        parts.append(f'<circle cx="{x+5}" cy="{yy-4}" r="4" fill="{color}"/>')
        parts.append(
            f'<text x="{x+17}" y="{yy}" fill="{TEXT}" font-size="11" '
            f'font-family="Segoe UI,Arial,sans-serif">{escape(label[:17])}</text>'
        )
        parts.append(
            f'<text x="{x+132}" y="{yy}" fill="{MUTED}" font-size="10" '
            f'text-anchor="end" font-family="Segoe UI,Arial,sans-serif">{pct:.1f}%</text>'
        )

def main():
    user = fetch_profile()
    collection = user["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    byte_languages, repo_languages = fetch_languages()

    public_repos = user["repositories"]["totalCount"]
    stars = sum(repo["stargazerCount"] for repo in user["repositories"]["nodes"])
    total = calendar["totalContributions"]
    current, longest = streak_values(days)

    # 1) Main dashboard: contribution total, current streak, longest streak,
    # monthly contribution bars, and two language donut charts.
    p = svg_start("GitHub Stats", 1000, 610)

    # Three top metric panels
    metric_cards = [
        (25, "Total contributions", f"{total:,}", "in the last year", ACCENT),
        (345, "Current streak", f"{current}", "days", PURPLE),
        (665, "Longest streak", f"{longest}", "days", GREEN),
    ]
    for x, label, value, note, color in metric_cards:
        p.append(f'<rect x="{x}" y="62" width="300" height="112" rx="13" fill="{CARD}" stroke="{BORDER}"/>')
        p.append(f'<text x="{x+20}" y="88" fill="{MUTED}" font-size="11" font-family="Segoe UI,Arial,sans-serif">{escape(label)}</text>')
        if label == "Current streak":
            p.append(f'<circle cx="{x+62}" cy="129" r="27" fill="none" stroke="{BORDER}" stroke-width="7"/>')
            p.append(f'<circle cx="{x+62}" cy="129" r="27" fill="none" stroke="url(#glow)" stroke-width="7" stroke-dasharray="145 170" stroke-linecap="round" transform="rotate(-90 {x+62} 129)"/>')
            p.append(f'<text x="{x+62}" y="136" text-anchor="middle" fill="{TEXT}" font-size="20" font-weight="700" font-family="Segoe UI,Arial,sans-serif">{value}</text>')
            p.append(f'<text x="{x+105}" y="126" fill="{TEXT}" font-size="13" font-weight="700" font-family="Segoe UI,Arial,sans-serif">Current streak</text>')
            p.append(f'<text x="{x+105}" y="145" fill="{MUTED}" font-size="10" font-family="Segoe UI,Arial,sans-serif">{note}</text>')
        else:
            p.append(f'<text x="{x+20}" y="143" fill="{color}" font-size="34" font-weight="700" font-family="Segoe UI,Arial,sans-serif">{value}</text>')
            p.append(f'<text x="{x+105}" y="143" fill="{MUTED}" font-size="11" font-family="Segoe UI,Arial,sans-serif">{note}</text>')

    # Monthly contributions bar chart
    p.append(f'<rect x="25" y="190" width="950" height="155" rx="13" fill="{CARD}" stroke="{BORDER}"/>')
    p.append(f'<text x="45" y="216" fill="{TEXT}" font-size="13" font-weight="700" font-family="Segoe UI,Arial,sans-serif">Contributions by month</text>')
    monthly = Counter()
    for day in days:
        month = day["date"][:7]
        monthly[month] += day["contributionCount"]
    month_items = sorted(monthly.items())[-12:]
    max_month = max([v for _, v in month_items] or [1]) or 1
    chart_x, chart_y, chart_w, chart_h = 55, 238, 890, 78
    bar_gap = 17
    bar_w = (chart_w - bar_gap * 11) / 12 if month_items else 30
    for i, (month, value) in enumerate(month_items):
        x = chart_x + i * (bar_w + bar_gap)
        h = max(3, chart_h * value / max_month)
        y = chart_y + chart_h - h
        p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="url(#bar)"/>')
        p.append(f'<text x="{x+bar_w/2:.1f}" y="332" text-anchor="middle" fill="{MUTED}" font-size="8" font-family="Segoe UI,Arial,sans-serif">{escape(month[5:])}</text>')

    # Two language panels
    p.append(f'<rect x="25" y="360" width="465" height="225" rx="13" fill="{CARD}" stroke="{BORDER}"/>')
    p.append(f'<rect x="510" y="360" width="465" height="225" rx="13" fill="{CARD}" stroke="{BORDER}"/>')
    p.append(f'<text x="45" y="389" fill="{TEXT}" font-size="13" font-weight="700" font-family="Segoe UI,Arial,sans-serif">Top languages by repository</text>')
    p.append(f'<text x="530" y="389" fill="{TEXT}" font-size="13" font-weight="700" font-family="Segoe UI,Arial,sans-serif">Top languages by code size</text>')

    palette = [ACCENT, PURPLE, GREEN, GOLD, PINK, CYAN]
    repo_top = repo_languages.most_common(5)
    byte_top = byte_languages.most_common(5)

    add_donut(p, 365, 485, 65, repo_top, palette, str(len(repo_top)))
    add_legend(p, 48, 438, repo_top, palette)

    add_donut(p, 850, 485, 65, byte_top, palette, str(len(byte_top)))
    add_legend(p, 533, 438, byte_top, palette)

    if not repo_top:
        p.append(f'<text x="48" y="535" fill="{MUTED}" font-size="11">No repository language data yet.</text>')
    if not byte_top:
        p.append(f'<text x="533" y="535" fill="{MUTED}" font-size="11">No language data yet.</text>')

    p.append(f'<text x="28" y="600" fill="{MUTED}" font-size="9" font-family="Segoe UI,Arial,sans-serif">Public repositories: {public_repos}  •  Stars earned: {stars}  •  Commits: {collection["totalCommitContributions"]}</text>')
    write_svg("github-stats.svg", p)

    # 2) Keep a separate compact languages card for existing README references.
    p = svg_start("Most Used Languages", 495, 230)
    top = byte_languages.most_common(6)
    total_bytes = sum(byte_languages.values()) or 1
    colors = [ACCENT, PURPLE, GREEN, GOLD, PINK, CYAN]
    for idx, (lang, amount) in enumerate(top):
        col, row = idx % 2, idx // 2
        x, y = 25 + col * 230, 82 + row * 48
        pct = amount / total_bytes * 100
        p.append(f'<text x="{x}" y="{y}" fill="{TEXT}" font-family="Segoe UI,Arial,sans-serif" font-size="12" font-weight="600">{escape(lang)}</text>')
        p.append(f'<text x="{x+195}" y="{y}" fill="{MUTED}" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" font-size="11">{pct:.1f}%</text>')
        p.append(f'<rect x="{x}" y="{y+9}" width="195" height="7" rx="4" fill="{BG}"/>')
        p.append(f'<rect x="{x}" y="{y+9}" width="{195*pct/100:.2f}" height="7" rx="4" fill="{colors[idx]}"/>')
    if not top:
        p.append(f'<text x="25" y="100" fill="{MUTED}" font-size="13">No language data available yet.</text>')
    write_svg("top-langs.svg", p)

    # 3) Preserve the original contribution streak card.
    p = svg_start("GitHub Contribution Streak", 495, 190)
    p.append(f'<text x="55" y="78" fill="{MUTED}" font-size="12" font-family="Segoe UI,Arial,sans-serif">CURRENT STREAK</text>')
    p.append(f'<text x="55" y="116" fill="{ACCENT}" font-size="29" font-weight="700" font-family="Segoe UI,Arial,sans-serif">{current} days</text>')
    p.append(f'<text x="275" y="78" fill="{MUTED}" font-size="12" font-family="Segoe UI,Arial,sans-serif">LONGEST STREAK</text>')
    p.append(f'<text x="275" y="116" fill="{PURPLE}" font-size="29" font-weight="700" font-family="Segoe UI,Arial,sans-serif">{longest} days</text>')
    p.append(f'<text x="55" y="155" fill="{MUTED}" font-size="11" font-family="Segoe UI,Arial,sans-serif">Based on your GitHub contribution calendar (last 12 months).</text>')
    write_svg("github-streak.svg", p)

    # 4) Preserve the separate contribution activity chart.
    p = svg_start("Contribution Activity — Last 12 Months", 1000, 300)
    chart_days = days[-365:]
    left, top, plot_w, plot_h = 48, 65, 920, 175
    max_count = max([d["contributionCount"] for d in chart_days] or [1]) or 1
    points = []
    for i, day in enumerate(chart_days):
        x = left + (i / max(1, len(chart_days)-1)) * plot_w
        y = top + plot_h - (day["contributionCount"] / max_count) * plot_h
        points.append((x, y))
    for i in range(5):
        gy = top + plot_h * i / 4
        p.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{left+plot_w}" y2="{gy:.1f}" stroke="{BORDER}" stroke-dasharray="4 5"/>')
    if points:
        point_string = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        area = f'M {left},{top+plot_h} L {point_string} L {left+plot_w},{top+plot_h} Z'
        p.append(f'<path d="{area}" fill="url(#glow)" opacity="0.22"/>')
        p.append(f'<polyline points="{point_string}" fill="none" stroke="url(#glow)" stroke-width="2.5" stroke-linejoin="round"/>')
    p.append(f'<text x="{left}" y="270" fill="{MUTED}" font-size="11">{escape(chart_days[0]["date"] if chart_days else "")}</text>')
    p.append(f'<text x="{left+plot_w}" y="270" text-anchor="end" fill="{MUTED}" font-size="11">{escape(chart_days[-1]["date"] if chart_days else "")}</text>')
    write_svg("contributions.svg", p)

    print(f"Generated dashboard profile cards for @{USERNAME}.")

if __name__ == "__main__":
    main()
