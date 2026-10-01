#!/usr/bin/env python3
"""Self-hosted GitHub stats card. Stdlib only. Writes assets/stats-{dark,light}.svg."""

import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = "SirCharan"
W, H = 1280, 260
OUT = Path(__file__).parent / "assets"

try:
    from build import PALETTES, FONT_CSS
except Exception:
    PALETTES = {
        "dark": dict(
            bg="#0B0C0E",
            bg2="#121418",
            fg="#F2F3F5",
            muted="#9AA0A8",
            dim="#5C626B",
            accent="#FFB020",
            grid="#FFFFFF",
            up="#3DD68C",
            down="#FF5C5C",
        ),
        "light": dict(
            bg="#FAFAF7",
            bg2="#F0EFEA",
            fg="#15171A",
            muted="#5A6069",
            dim="#8A9099",
            accent="#C77700",
            grid="#15171A",
            up="#1E9E62",
            down="#D63B3B",
        ),
    }
    FONT_CSS = ""

STACK = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
API = "https://api.github.com/graphql"


def gql(token, query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "User-Agent": "sircharan-stats",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if d.get("errors") or "data" not in d:
        raise RuntimeError(d.get("errors"))
    return d["data"]


REPOS_Q = """query($u:String!,$after:String){user(login:$u){repositories(first:100,after:$after,
ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,orderBy:{field:PUSHED_AT,direction:DESC}){
pageInfo{hasNextPage endCursor} nodes{name stargazerCount pushedAt
languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""
CONTRIB_Q = """query($u:String!,$from:DateTime!,$to:DateTime!){user(login:$u){
contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions
weeks{contributionDays{date contributionCount}}}}}}"""


def fetch(token):
    repos, after = [], None
    while True:
        r = gql(token, REPOS_Q, {"u": USER, "after": after})["user"]["repositories"]
        repos += r["nodes"]
        if not r["pageInfo"]["hasNextPage"]:
            break
        after = r["pageInfo"]["endCursor"]
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=29)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cal = gql(
        token, CONTRIB_Q, {"u": USER, "from": start.isoformat(), "to": now.isoformat()}
    )["user"]["contributionsCollection"]["contributionCalendar"]
    days = {
        d["date"]: d["contributionCount"]
        for w in cal["weeks"]
        for d in w["contributionDays"]
    }
    series = [
        days.get((start + timedelta(days=i)).date().isoformat(), 0) for i in range(30)
    ]
    langs = {}
    for rp in repos:
        for e in rp["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    top = sorted(langs.items(), key=lambda x: -x[1])[:5]
    recent = [
        (r["name"], datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00")))
        for r in repos
        if r["pushedAt"]
    ]
    recent.sort(key=lambda x: x[1], reverse=True)
    return dict(
        repos=len(repos),
        stars=sum(r["stargazerCount"] for r in repos),
        contrib=sum(series),
        series=series,
        langs=top,
        recent=recent[:3],
        now=now,
    )


def rel(t, now):
    s = int((now - t).total_seconds())
    for n, u in (
        (86400 * 365, "y"),
        (86400 * 30, "mo"),
        (86400, "d"),
        (3600, "h"),
        (60, "m"),
    ):
        if s >= n:
            return f"{s // n}{u} ago"
    return "just now"


def render(p, d):
    e = escape
    lbl = f'font-size="11" letter-spacing="1.6" fill="{p["dim"]}"'
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{e(USER)} GitHub stats: {d["repos"]} public repos, {d["stars"]} stars, '
        f'{d["contrib"]} contributions in the last 30 days">',
        f"<style>{FONT_CSS}text{{font-family:{STACK}}}"
        ".bar{transform-box:fill-box;transform-origin:bottom;animation:rise .6s cubic-bezier(.2,.8,.2,1) backwards}"
        "@keyframes rise{from{transform:scaleY(0)}}"
        "@keyframes fade{from{opacity:0}to{opacity:1}}"
        "@media (prefers-reduced-motion: reduce){*{animation:none!important}}</style>",
        f'<rect width="{W}" height="{H}" rx="8" fill="{p["bg"]}"/>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="8" fill="none" stroke="{p["grid"]}" stroke-opacity="0.12"/>',
        f'<text x="32" y="40" {lbl}>GITHUB / {e(USER.upper())}</text>',
        f'<text x="{W - 32}" y="40" text-anchor="end" {lbl}>UPDATED {d["now"]:%Y-%m-%d %H:%M} UTC</text>',
    ]
    # tiles
    for i, (v, name) in enumerate(
        ((d["repos"], "REPOS"), (d["stars"], "STARS"), (d["contrib"], "30D CONTRIBUTIONS"))
    ):
        x = 32 + i * 192
        o += [
            f'<rect x="{x}" y="64" width="176" height="80" rx="4" fill="{p["bg2"]}" stroke="{p["grid"]}" stroke-opacity="0.08"/>',
            f'<text x="{x + 16}" y="88" {lbl}>{name}</text>',
            f'<text x="{x + 16}" y="128" font-size="40" font-weight="700" fill="{p["accent"] if i == 2 else p["fg"]}">{v:,}</text>',
        ]
    # language bar
    o.append(f'<text x="32" y="176" {lbl}>LANGUAGES BY BYTES</text>')
    tot = sum(b for _, b in d["langs"]) or 1
    cols = [p["accent"], p["up"], p["fg"], p["muted"], p["dim"]]
    o.append(
        f'<clipPath id="lc"><rect x="32" y="184" width="560" height="8" rx="4"/></clipPath><g clip-path="url(#lc)">'
    )
    x = 32.0
    for (n, b), c in zip(d["langs"], cols):
        w = 560 * b / tot
        o.append(f'<rect x="{x:.1f}" y="184" width="{w:.1f}" height="8" fill="{c}"/>')
        x += w
    o.append("</g>")
    lx = 32
    for (n, b), c in zip(d["langs"], cols):
        o += [
            f'<rect x="{lx}" y="216" width="8" height="8" rx="2" fill="{c}"/>',
            f'<text x="{lx + 16}" y="225" font-size="11" fill="{p["muted"]}">{e(n)} {100 * b / tot:.0f}%</text>',
        ]
        lx += 16 + round(6.7 * len(f"{n} {100 * b / tot:.0f}%")) + 20
    # sparkline
    X0, X1, Y0, Y1 = 640, 1248, 72, 136
    o.append(
        f'<text x="{X0}" y="64" {lbl}>CONTRIBUTIONS / LAST 30 DAYS</text>'
        if False
        else f'<text x="{X0}" y="88" {lbl}>CONTRIBUTIONS / LAST 30 DAYS</text>'
    )
    s = d["series"]
    mx = max(max(s), 1)
    bw = (X1 - X0) / 30
    o.append(f'<line x1="{X0}" y1="148" x2="{X1}" y2="148" stroke="{p["grid"]}" stroke-opacity="0.12"/>')
    for i, v in enumerate(s):
        h = 2 + 44 * (v / mx) ** 0.5 if v else 2  # ponytail: sqrt so one spike day doesn't flatten the rest
        c = p["accent"] if i == 29 else (p["muted"] if v else p["dim"])
        o.append(
            f'<rect class="bar" style="animation-delay:{i * 30}ms" x="{X0 + i * bw + 2:.1f}" y="{148 - h:.1f}" '
            f'width="{bw - 4:.1f}" height="{h:.1f}" rx="1.5" fill="{c}" fill-opacity="{1 if v else 0.4}"/>'
        )
    # recent
    o.append(f'<text x="{X0}" y="176" {lbl}>RECENTLY PUSHED</text>')
    for i, (n, t) in enumerate(d["recent"]):
        y = 200 + i * 24
        o += [
            f'<text x="{X0}" y="{y}" font-size="13" fill="{p["fg"]}">{e(n)}</text>',
            f'<text x="{X1}" y="{y}" text-anchor="end" font-size="12" fill="{p["muted"]}">{e(rel(t, d["now"]))}</text>',
        ]
    o.append("</svg>")
    return "\n".join(o)


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("error: GITHUB_TOKEN missing")
    try:
        d = fetch(token)
        svgs = {k: render(PALETTES[k], d) for k in ("dark", "light")}
    except Exception as ex:
        sys.exit(f"error: {ex}")
    OUT.mkdir(exist_ok=True)
    for k, v in svgs.items():
        (OUT / f"stats-{k}.svg").write_text(v, encoding="utf-8")
    print(
        {k: d[k] for k in ("repos", "stars", "contrib", "langs")},
        [(n, rel(t, d["now"])) for n, t in d["recent"]],
    )


if __name__ == "__main__":
    main()
