
#!/usr/bin/env python3
"""Generate self-hosted GitHub profile cards using GitHub's API."""

import json
import os
import urllib.request
import urllib.error
from collections import Counter
from datetime import date
from html import escape

USERNAME = os.getenv("GH_USERNAME", "nawsintabassum")
TOKEN = os.getenv("GH_TOKEN")
OUT = "assets"

# Original Tokyo Night Colors - Unchanged
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
    repositories(
      first: 100,
      ownerAffiliations: OWNER,
      privacy: PUBLIC,
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


# ---------------- API FUNCTIONS ----------------

def request_json(url, data=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "nawsintabassum-profile-cards",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {exc.code}: {detail}"
        ) from exc


def fetch_profile():
    if not TOKEN:
        raise RuntimeError(
            "GH_TOKEN is missing. Enable the GITHUB_TOKEN secret in Actions."
        )

    result = request_json(
        "https://api.github.com/graphql",
        json.dumps({
            "query": QUERY,
            "variables": {"login": USERNAME}
        }).encode()
    )

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))

    user = result.get("data", {}).get("user")

    if not user:
        raise RuntimeError(
            f"GitHub user @{USERNAME} was not found."
        )

    return user


def fetch_languages():
    repos = request_json(
        f"https://api.github.com/users/{USERNAME}/repos"
        "?per_page=100&sort=updated&type=owner"
    )

    totals = Counter()

    for repo in repos:
        if not repo.get("fork"):
            try:
                langs = request_json(repo["languages_url"])
                totals.update(langs)

            except Exception as exc:
                print(
                    f"Skipping languages for {repo.get('name')}: {exc}"
                )

    return totals


# ---------------- SVG FUNCTIONS ----------------

def svg_card(title, width=495, height=190):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',

        '<defs>',

        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">',
        f'<stop offset="0" stop-color="{ACCENT}"/>',
        f'<stop offset="1" stop-color="{PURPLE}"/>',
        '</linearGradient>',

        '<linearGradient id="area" x1="0" y1="0" x2="0" y2="1">',
        f'<stop offset="0" stop-color="{ACCENT}" stop-opacity="0.4"/>',
        f'<stop offset="1" stop-color="{PURPLE}" stop-opacity="0.02"/>',
        '</linearGradient>',

        '</defs>',

        f'<rect x="1" y="1" width="{width-2}" '
        f'height="{height-2}" rx="12" '
        f'fill="{BG}" stroke="#414868"/>',

        f'<text x="24" y="34" fill="{ACCENT}" '
        f'font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="17" font-weight="700">'
        f'{escape(title)}</text>',
    ]


def label_value(parts, x, y, label, value, color=TEXT, size=23):
    parts.append(
        f'<text x="{x}" y="{y}" fill="{MUTED}" '
        f'font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="12">{escape(label)}</text>'
    )

    parts.append(
        f'<text x="{x}" y="{y+29}" fill="{color}" '
        f'font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="{size}" font-weight="700">'
        f'{escape(str(value))}</text>'
    )


def write_svg(name, parts):
    parts.append("</svg>")

    os.makedirs(OUT, exist_ok=True)

    with open(
        os.path.join(OUT, name),
        "w",
        encoding="utf-8"
    ) as file:
        file.write("\n".join(parts))


# ---------------- STREAK CALCULATION ----------------

def streak_values(days):
    counts = [d["contributionCount"] for d in days]

    current = 0

    start = len(counts) - 1

    if (
        counts
        and counts[-1] == 0
        and date.fromisoformat(days[-1]["date"]) == date.today()
    ):
        start -= 1

    for index in range(start, -1, -1):
        if counts[index] > 0:
            current += 1
        else:
            break

    longest = 0
    run = 0

    for count in counts:
        run = run + 1 if count > 0 else 0
        longest = max(longest, run)

    return current, longest


# ---------------- MAIN GENERATOR ----------------

def main():

    user = fetch_profile()

    collection = user["contributionsCollection"]

    calendar = collection["contributionCalendar"]

    days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]

    languages = fetch_languages()

    public_repos = user["repositories"]["totalCount"]

    stars = sum(
        repo["stargazerCount"]
        for repo in user["repositories"]["nodes"]
    )

    total = calendar["totalContributions"]

    # ==========================================
    # 1. MAIN STATISTICS CARD - DASHBOARD DESIGN
    # ==========================================

    p = svg_card(
        f"{USERNAME}'s GitHub Stats",
        width=495,
        height=230
    )

    stats = [
        ("CONTRIBUTIONS", f"{total:,}", ACCENT),
        ("REPOSITORIES", public_repos, PURPLE),
        ("TOTAL STARS", stars, GREEN),
        ("COMMITS", collection["totalCommitContributions"], ACCENT),
        ("PULL REQUESTS", collection["totalPullRequestContributions"], PURPLE),
        ("ISSUES", collection["totalIssueContributions"], GREEN),
    ]

    positions = [
        (20, 55),
        (175, 55),
        (330, 55),
        (20, 140),
        (175, 140),
        (330, 140),
    ]

    for (label, value, color), (x, y) in zip(stats, positions):

        p.append(
            f'<rect x="{x}" y="{y}" width="145" height="70" '
            f'rx="9" fill="{CARD}" stroke="#414868"/>'
        )

        p.append(
            f'<circle cx="{x+13}" cy="{y+19}" '
            f'r="4" fill="{color}"/>'
        )

        p.append(
            f'<text x="{x+24}" y="{y+23}" fill="{MUTED}" '
            f'font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="9" font-weight="600">'
            f'{escape(label)}</text>'
        )

        p.append(
            f'<text x="{x+13}" y="{y+53}" fill="{color}" '
            f'font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="21" font-weight="700">'
            f'{escape(str(value))}</text>'
        )

    write_svg("github-stats.svg", p)

    # ==========================================
    # 2. MOST USED LANGUAGES - PROGRESS BAR DESIGN
    # ==========================================

    p = svg_card(
        "Most Used Languages",
        width=495,
        height=230
    )

    top = languages.most_common(6)

    total_bytes = sum(languages.values()) or 1

    colors = [
        "#7aa2f7",
        "#bb9af7",
        "#9ece6a",
        "#e0af68",
        "#f7768e",
        "#7dcfff",
    ]

    for idx, (lang, amount) in enumerate(top):

        col = idx % 2
        row = idx // 2

        x = 25 + col * 230
        y = 82 + row * 48

        pct = amount / total_bytes * 100

        bar_width = 195 * pct / 100

        p.append(
            f'<text x="{x}" y="{y}" fill="{TEXT}" '
            f'font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="12" font-weight="600">'
            f'{escape(lang)}</text>'
        )

        p.append(
            f'<text x="{x+195}" y="{y}" fill="{MUTED}" '
            f'text-anchor="end" '
            f'font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="11">{pct:.1f}%</text>'
        )

        p.append(
            f'<rect x="{x}" y="{y+9}" width="195" height="7" '
            f'rx="4" fill="{CARD}"/>'
        )

        p.append(
            f'<rect x="{x}" y="{y+9}" '
            f'width="{bar_width:.2f}" height="7" '
            f'rx="4" fill="{colors[idx]}"/>'
        )

    if not top:

        p.append(
            f'<text x="25" y="100" fill="{MUTED}" '
            f'font-size="13">'
            f'No language data available yet.</text>'
        )

    write_svg("top-langs.svg", p)

    # ==========================================
    # 3. CONTRIBUTION STREAK - ORIGINAL DESIGN
    # ==========================================

    current, longest = streak_values(days)

    p = svg_card("GitHub Contribution Streak")

    label_value(
        p,
        55,
        92,
        "CURRENT STREAK",
        f"{current} days",
        ACCENT,
        27
    )

    label_value(
        p,
        275,
        92,
        "LONGEST STREAK",
        f"{longest} days",
        PURPLE,
        27
    )

    p.append(
        f'<text x="55" y="157" fill="{MUTED}" '
        f'font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="12">'
        f'Based on your GitHub contribution calendar '
        f'(last 12 months).</text>'
    )

    write_svg("github-streak.svg", p)

    # ==========================================
    # 4. CONTRIBUTION GRAPH - GRADIENT AREA DESIGN
    # ==========================================

    p = svg_card(
        "Contribution Activity — Last 12 Months",
        width=1000,
        height=300
    )

    chart_days = days[-365:]

    left = 48
    top = 65
    plot_w = 920
    plot_h = 175

    max_count = max(
        [d["contributionCount"] for d in chart_days] or [1]
    ) or 1

    # Horizontal grid lines
    for i in range(5):

        gy = top + (plot_h / 4) * i

        p.append(
            f'<line x1="{left}" y1="{gy:.1f}" '
            f'x2="{left+plot_w}" y2="{gy:.1f}" '
            f'stroke="#414868" '
            f'stroke-dasharray="4 5" opacity="0.7"/>'
        )

    points = []

    for i, day in enumerate(chart_days):

        x = left + (
            i / max(1, len(chart_days)-1)
        ) * plot_w

        y = top + plot_h - (
            day["contributionCount"] / max_count
        ) * plot_h

        points.append((x, y))

    if points:

        point_string = " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in points
        )

        area_path = (
            f"M {left},{top+plot_h} "
            f"L {point_string} "
            f"L {left+plot_w},{top+plot_h} Z"
        )

        # Gradient filled area
        p.append(
            f'<path d="{area_path}" '
            f'fill="url(#area)"/>'
        )

        # Contribution line
        p.append(
            f'<polyline points="{point_string}" '
            f'fill="none" stroke="url(#g)" '
            f'stroke-width="2.5" '
            f'stroke-linejoin="round" '
            f'stroke-linecap="round"/>'
        )

        # Latest contribution point
        last_x, last_y = points[-1]

        p.append(
            f'<circle cx="{last_x:.1f}" '
            f'cy="{last_y:.1f}" r="4" '
            f'fill="{PURPLE}" '
            f'stroke="{BG}" stroke-width="2"/>'
        )

    # Date labels
    p.append(
        f'<text x="{left}" y="270" fill="{MUTED}" '
        f'font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="11">'
        f'{escape(chart_days[0]["date"] if chart_days else "")}'
        f'</text>'
    )

    p.append(
        f'<text x="{left+plot_w}" y="270" '
        f'text-anchor="end" fill="{MUTED}" '
        f'font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="11">'
        f'{escape(chart_days[-1]["date"] if chart_days else "")}'
        f'</text>'
    )

    write_svg("contributions.svg", p)

    print(
        f"Generated profile cards for @{USERNAME}."
    )


if __name__ == "__main__":
    main()
