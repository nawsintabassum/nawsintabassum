#!/usr/bin/env python3
import json, math, os, sys, urllib.request, urllib.error
from datetime import datetime
from xml.sax.saxutils import escape

API_URL = 'https://api.github.com/graphql'
USERNAME = os.getenv('GH_USERNAME', 'nawsintabassum')
TOKEN = os.getenv('GH_TOKEN')
WIDTH, HEIGHT = 1200, 420
LEFT, RIGHT, TOP, BOTTOM = 90, 50, 78, 72
PLOT_WIDTH = WIDTH - LEFT - RIGHT
PLOT_HEIGHT = HEIGHT - TOP - BOTTOM

QUERY = '''
query($login: String!) {
  user(login: $login) {
    login
    name
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
'''

def fail(msg):
    print('ERROR:', msg, file=sys.stderr)
    sys.exit(1)

def fetch_data():
    if not TOKEN:
        fail('GH_TOKEN is missing.')
    payload = json.dumps({'query': QUERY, 'variables': {'login': USERNAME}}).encode()
    req = urllib.request.Request(API_URL, data=payload, method='POST', headers={
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'nawsintabassum-github-activity-svg-generator'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        fail(f'GitHub API HTTP {e.code}: {e.read().decode(errors="replace")}')
    except urllib.error.URLError as e:
        fail(f'Connection failed: {e.reason}')
    if result.get('errors'):
        fail(json.dumps(result['errors']))
    user = result.get('data', {}).get('user')
    if not user:
        fail(f'GitHub user {USERNAME!r} was not found.')
    cal = user['contributionsCollection']['contributionCalendar']
    days = [d for w in cal['weeks'] for d in w['contributionDays']]
    days.sort(key=lambda x: x['date'])
    return user, cal, days[-365:]

def nice_max(v):
    if v <= 0: return 5
    raw = max(1, math.ceil(v / 5))
    mag = 10 ** max(0, len(str(raw)) - 1)
    n = raw / mag
    step = mag if n <= 1 else 2*mag if n <= 2 else 5*mag if n <= 5 else 10*mag
    return step * 5

def xpos(i, n):
    return LEFT if n <= 1 else LEFT + i/(n-1)*PLOT_WIDTH

def ypos(v, ymax):
    return TOP + PLOT_HEIGHT - v/ymax*PLOT_HEIGHT

def text(x, y, value, size=13, anchor='middle', weight='600', cls='axis'):
    return (f'<text x="{x:.2f}" y="{y:.2f}" class="{cls}" '
            f'font-size="{size}px" font-weight="{weight}" text-anchor="{anchor}">'
            f'{escape(str(value))}</text>')

def make_svg(user, cal, days):
    ymax = nice_max(max((d['contributionCount'] for d in days), default=0))
    pts = [(xpos(i, len(days)), ypos(d['contributionCount'], ymax)) for i,d in enumerate(days)]
    line = ' '.join(f'{x:.2f},{y:.2f}' for x,y in pts)
    base = TOP + PLOT_HEIGHT
    area = f'M{pts[0][0]:.2f},{base:.2f} ' + ' '.join(
        f'L{x:.2f},{y:.2f}' if i else f'L{x:.2f},{y:.2f}' for i,(x,y) in enumerate(pts)
    ) + f' L{pts[-1][0]:.2f},{base:.2f} Z'

    out = [f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg">']
    out.append('<rect x="0" y="0" width="100%" height="100%" fill="#1a1b27"/>')
    out.append('''<style>
.grid{stroke:#70a5fd;stroke-width:1;stroke-opacity:.25;stroke-dasharray:2 4}
.line{fill:none;stroke:#70a5fd;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:6000;stroke-dashoffset:6000;animation:draw 5s ease-in-out forwards}
.area{fill:#70a5fd;fill-opacity:.10}
.point{fill:#a9b1d6;opacity:0;animation:appear .7s ease-in-out forwards}
.title{font-family:'Segoe UI',Ubuntu,sans-serif;font-weight:700;fill:#70a5fd}
.subtitle,.axis{font-family:'Segoe UI',Ubuntu,sans-serif;fill:#a9b1d6}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes appear{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
</style>''')
    name = user.get('name') or user['login']
    total = cal.get('totalContributions', sum(d['contributionCount'] for d in days))
    out.append(f'<text x="{WIDTH/2}" y="30" class="title" font-size="22px" text-anchor="middle">{escape(name)}\'s Contribution Graph</text>')
    out.append(f'<text x="{WIDTH/2}" y="52" class="subtitle" font-size="14px" font-weight="600" text-anchor="middle">@{escape(user["login"])}  •  {total:,} contributions</text>')
    for i in range(6):
        value = ymax*i/5
        y = ypos(value,ymax)
        out.append(f'<line x1="{LEFT}" y1="{y:.2f}" x2="{WIDTH-RIGHT}" y2="{y:.2f}" class="grid"/>')
        out.append(text(LEFT-12,y+5,round(value),anchor='end'))
    seen=set()
    for i,d in enumerate(days):
        dt=datetime.strptime(d['date'],'%Y-%m-%d')
        key=(dt.year,dt.month)
        if key in seen: continue
        seen.add(key)
        x=xpos(i,len(days))
        out.append(f'<line x1="{x:.2f}" y1="{TOP}" x2="{x:.2f}" y2="{TOP+PLOT_HEIGHT}" class="grid"/>')
        out.append(text(x,HEIGHT-34,dt.strftime('%b %Y'),size=12))
    out.append(f'<path d="{area}" class="area"/>')
    out.append(f'<polyline points="{line}" class="line"/>')
    for i,((x,y),d) in enumerate(zip(pts,days)):
        r=2.8 if d['contributionCount']>0 else 1.6
        delay=min(i*.008,3)
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" class="point" style="animation-delay:{delay:.3f}s"><title>{escape(d["date"])}: {d["contributionCount"]} contributions</title></circle>')
    out.append(text(WIDTH/2,HEIGHT-10,'Days',size=13,anchor='middle',weight='600'))
    out.append(f'<text x="20" y="{HEIGHT/2}" transform="rotate(-90 20 {HEIGHT/2})" class="axis" font-size="13px" font-weight="600" text-anchor="middle">Contributions</text>')
    out.append('</svg>')
    return '\n'.join(out)

def main():
    user, cal, days = fetch_data()
    if not days: fail('No contribution days returned.')
    with open('activity.svg','w',encoding='utf-8') as f:
        f.write(make_svg(user,cal,days))
    print(f'Generated activity.svg for @{user["login"]}.')

if __name__ == '__main__': main()
