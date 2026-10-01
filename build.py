#!/usr/bin/env python3
"""Emit the self-hosted animated SVG profile into assets/. Stdlib only.

    python3 build.py

Importable: exposes PALETTES and FONT_CSS (used by stats.py). Importing does
not build anything.
"""

import base64
import math
import os
import random
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as esc

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
FONT_DIR = os.path.join(ASSETS, "font")

# ---------------------------------------------------------------- tokens
PALETTES = {
    "dark": {
        "bg": "#0B0C0E",
        "bg2": "#121418",
        "fg": "#F2F3F5",
        "muted": "#9AA0A8",
        "dim": "#5C626B",
        "accent": "#FFB020",
        "grid": "#1C1F24",
        "up": "#3DDC97",
        "down": "#FF5D6C",
    },
    "light": {
        "bg": "#FAFAF7",
        "bg2": "#F1F1EB",
        "fg": "#15171A",
        "muted": "#555B63",
        "dim": "#8B9098",
        "accent": "#C77700",
        "grid": "#E3E3DC",
        "up": "#0E8A57",
        "down": "#C7303F",
    },
}

MONO = "'JB','JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
ADV = 0.6  # JetBrains Mono advance, em


def _font_b64(name):
    with open(os.path.join(FONT_DIR, name), "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def _font_css():
    try:
        reg = _font_b64("JetBrainsMono-Regular.woff2")
        bold = _font_b64("JetBrainsMono-Bold.woff2")
    except OSError:
        return ""
    return (
        "@font-face{font-family:'JB';font-weight:400;font-style:normal;"
        "src:url(data:font/woff2;base64,%s) format('woff2')}"
        "@font-face{font-family:'JB';font-weight:700;font-style:normal;"
        "src:url(data:font/woff2;base64,%s) format('woff2')}" % (reg, bold)
    )


FONT_CSS = _font_css()

BASE_CSS = (
    "text{font-family:%s;font-variant-ligatures:none}.fb{transform-box:fill-box}" % MONO
)
REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def pct(t, cycle):
    return round(min(max(t / cycle * 100, 0), 100), 3)


class Svg:
    def __init__(self, w, h, label, pal):
        self.w, self.h, self.label, self.p = w, h, label, pal
        self.defs, self.body, self.css = [], [], []
        self._kf = {}

    # --- animation helpers
    def kf(self, frames):
        if frames not in self._kf:
            name = "k%d" % len(self._kf)
            self._kf[frames] = name
            self.css.append("@keyframes %s{%s}" % (name, frames))
        return self._kf[frames]

    def anim(self, frames, dur, ease="ease", delay=0.0):
        return 'style="animation:%s %ss %s %ss infinite backwards"' % (
            self.kf(frames),
            dur,
            ease,
            round(delay, 3),
        )

    def rv(self, t_in, cycle, out0, out1, dur=0.4, frm="", to="", ease="ease-out"):
        """Reveal at t_in, hold, fade out between out0..out1, inside one cycle."""
        pi = pct(t_in, cycle)
        pd = pct(t_in + dur, cycle)
        p0 = pct(out0, cycle)
        p1 = pct(out1, cycle)
        frm = frm + ";" if frm else ""
        to = to + ";" if to else ""
        frames = (
            "0%%,%s%%{opacity:0;%s}%s%%{opacity:1;%s}%s%%{opacity:1;%s}"
            "%s%%,100%%{opacity:0;%s}"
        ) % (pi, frm, pd, to, p0, to, p1, frm)
        return self.anim(frames, cycle, ease)

    def add(self, s):
        self.body.append(s)

    def render(self):
        p = self.p
        style = FONT_CSS + BASE_CSS + "".join(self.css) + REDUCED
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
            'height="%d" role="img" aria-label="%s">'
            "<title>%s</title><style>%s</style><defs>%s</defs>%s</svg>\n"
            % (
                self.w,
                self.h,
                self.w,
                self.h,
                esc(self.label, {'"': "&quot;"}),
                esc(self.label),
                style,
                "".join(self.defs),
                "".join(self.body),
            )
        )


def T(x, y, s, size, fill, weight=400, anchor=None, ls=None, extra=""):
    a = ' text-anchor="%s"' % anchor if anchor else ""
    l = ' letter-spacing="%s"' % ls if ls is not None else ""
    return (
        '<text x="%s" y="%s" font-size="%s" font-weight="%d" fill="%s"%s%s %s>%s</text>'
        % (round(x, 2), y, size, weight, fill, a, l, extra, esc(s))
    )


def cw(n, size, ls=0):
    return n * (ADV * size + ls)


def grad(id_, stops, x2=1, y2=0, x1=0, y1=0):
    st = "".join(
        '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % s for s in stops
    )
    return (
        '<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
        % (id_, x1, y1, x2, y2, st)
    )


def candle(x, cy, bh, wt, wb, up, p, op=1.0, w=8, extra=""):
    col = p["up"] if up else p["down"]
    return (
        '<g class="fb cb" %s><line x1="%s" x2="%s" y1="%s" y2="%s" stroke="%s" stroke-width="1.5" opacity="%s"/>'
        '<rect x="%s" y="%s" width="%d" height="%s" rx="1.5" fill="%s" opacity="%s"/></g>'
        % (
            extra,
            x,
            x,
            round(cy - bh / 2 - wt, 1),
            round(cy + bh / 2 + wb, 1),
            col,
            op,
            x - w / 2,
            round(cy - bh / 2, 1),
            w,
            bh,
            col,
            op,
        )
    )


# ---------------------------------------------------------------- hero
NAMES = [
    "claude-browse",
    "second-brain",
    "Zerodha-MCP-Trading",
    "stocky-ai",
    "openwispr",
    "continuum",
    "claude-code-harness",
    "stocky-fun",
    "trade-nexus",
    "yomu",
    "seed-hunter",
    "tldw",
]
PHRASES = ["trading systems", "memory for AI agents", "on-device voice"]


def equity(w_end=1200, step=40):
    rng = random.Random(11)
    pts = []
    for x in range(0, w_end + 1, step):
        t = x / w_end
        y = 288 - 200 * (t**1.7) + (rng.uniform(-9, 9) if x < w_end else 0)
        pts.append((x, round(min(y, 288), 1)))
    return pts


def hero(p):
    s = Svg(
        1280,
        340,
        "Charandeep Kapoor. AI × Trading, 2× ex-founder, IIT Kanpur. Trading systems, memory for AI agents, on-device voice.",
        p,
    )
    C = 12.0
    s.defs.append(grad("bg", [("0%", p["bg"], 1), ("100%", p["bg2"], 1)], 1, 1))
    s.defs.append(
        grad(
            "cv",
            [
                ("0%", p["accent"], 0),
                ("35%", p["accent"], 0.35),
                ("100%", p["accent"], 1),
            ],
        )
    )
    s.defs.append(
        grad("fl", [("0%", p["accent"], 0.18), ("100%", p["accent"], 0)], 0, 1)
    )
    s.defs.append(grad("fe", [("0%", p["bg"], 1), ("100%", p["bg"], 0)]))
    s.defs.append(grad("fe2", [("0%", p["bg"], 0), ("100%", p["bg"], 1)]))
    s.add('<rect width="1280" height="340" fill="url(#bg)"/>')
    g = "".join("M0 %d H1280" % y for y in (80, 160, 240)) + "".join(
        "M%d 0 V296" % x for x in range(80, 1280, 80)
    )
    s.add('<path d="%s" stroke="%s" stroke-width="1" fill="none"/>' % (g, p["grid"]))

    pts = equity()
    # candles
    rng = random.Random(5)
    cur = dict(pts)
    xs = sorted(cur)

    def cy_at(x):
        for a, b in zip(xs, xs[1:]):
            if a <= x <= b:
                return cur[a] + (cur[b] - cur[a]) * (x - a) / (b - a)
        return cur[xs[-1]]

    for i in range(27):
        x = 672 + 20 * i
        cy = cy_at(x) + rng.uniform(4, 24)
        bh = rng.choice([10, 14, 18, 22, 26])
        up = rng.random() < 0.62
        ex = s.anim(
            "0%{opacity:0;transform:scaleY(0)}6%{opacity:1;transform:scaleY(1)}"
            "90%{opacity:1;transform:scaleY(1)}98%{opacity:0;transform:scaleY(1)}100%{opacity:0;transform:scaleY(0)}",
            C,
            "cubic-bezier(.2,.8,.2,1)",
            i * 0.05,
        )
        s.add(
            candle(
                x,
                round(cy, 1),
                bh,
                rng.randint(4, 10),
                rng.randint(4, 10),
                up,
                p,
                0.5,
                extra=ex,
            )
        )
    d = "M" + " L".join("%s %s" % pt for pt in pts)
    area = d + " L1200 296 L0 296 Z"
    s.add(
        '<path d="%s" fill="url(#fl)" %s/>'
        % (
            area,
            s.anim(
                "0%{opacity:0}38%{opacity:0}48%{opacity:1}90%{opacity:1}98%{opacity:0}100%{opacity:0}",
                C,
            ),
        )
    )
    s.add(
        '<path d="%s" pathLength="1" fill="none" stroke="url(#cv)" stroke-width="3" stroke-linejoin="round" %s/>'
        % (
            d,
            s.anim(
                "0%{stroke-dasharray:1;stroke-dashoffset:1;opacity:1}40%{stroke-dasharray:1;stroke-dashoffset:0;opacity:1}"
                "90%{stroke-dasharray:1;stroke-dashoffset:0;opacity:1}98%{stroke-dasharray:1;stroke-dashoffset:0;opacity:0}"
                "100%{stroke-dasharray:1;stroke-dashoffset:1;opacity:0}",
                C,
                "cubic-bezier(.4,0,.2,1)",
            ),
        )
    )
    ex_, ey_ = pts[-1]
    s.add(
        '<g %s><circle cx="%s" cy="%s" r="5" fill="%s"/>'
        '<circle class="fb" cx="%s" cy="%s" r="10" fill="none" stroke="%s" stroke-opacity="0.45" stroke-width="1.5" %s/></g>'
        % (
            s.rv(4.8, C, 11.2, 11.8, 0.4),
            ex_,
            ey_,
            p["accent"],
            ex_,
            ey_,
            p["accent"],
            s.anim(
                "0%{transform:scale(.6);opacity:.8}45%{transform:scale(2.6);opacity:0}100%{transform:scale(2.6);opacity:0}",
                4,
                "ease-out",
            ),
        )
    )

    # text block
    s.add(T(64, 48, "~/SirCharan", 13, p["dim"], ls=1))
    s.add(T(64, 120, "Charandeep Kapoor", 56, p["fg"], 700, ls=-1))
    s.add(T(64, 152, "AI × TRADING · 2× EX-FOUNDER · IIT KANPUR", 14, p["accent"], ls=2.4))
    s.add(T(64, 200, "building", 24, p["muted"]))
    x0 = 64 + cw(9, 24)
    for k, ph in enumerate(PHRASES):
        hidden = ' opacity="0"' if k else ""
        for i, ch in enumerate(ph):
            if ch == " ":
                continue
            t_in = 4 * k + 0.3 + i * 0.07
            s.add(
                T(
                    x0 + i * cw(1, 24),
                    200,
                    ch,
                    24,
                    p["fg"],
                    700,
                    extra=hidden
                    + " "
                    + s.rv(t_in, C, 4 * k + 3.5, 4 * k + 3.8, 0.05, ease="linear"),
                )
            )
        cx = x0 + len(ph) * cw(1, 24) + 4
        blink = s.anim("0%,50%{opacity:1}50.01%,100%{opacity:0}", 1.2, "steps(1)")
        s.add(
            '<g%s %s><rect x="%s" y="180" width="11" height="26" fill="%s" %s/></g>'
            % (
                hidden,
                s.rv(
                    4 * k + 0.3 + len(ph) * 0.07,
                    C,
                    4 * k + 3.5,
                    4 * k + 3.8,
                    0.05,
                    ease="linear",
                ),
                round(cx, 2),
                p["accent"],
                blink,
            )
        )

    # ticker
    s.add(
        '<rect y="296" width="1280" height="44" fill="%s"/><path d="M0 296.5 H1280" stroke="%s"/>'
        % (p["bg"], p["grid"])
    )
    size = 13
    unit = []
    x = 0
    for n in NAMES:
        unit.append((x, n))
        x += cw(2 + len(n), size) + 48
    L = round(x, 2)
    tk = []
    for c in range(3):
        for ux, n in unit:
            tk.append(
                '<text x="%s" y="323" font-size="%d" fill="%s"><tspan fill="%s">▲</tspan> %s</text>'
                % (round(ux + c * L, 2), size, p["muted"], p["accent"], esc(n))
            )
    s.add(
        "<g %s>%s</g>"
        % (
            s.anim(
                "from{transform:translateX(0)}to{transform:translateX(-%spx)}" % L,
                14,
                "linear",
            ),
            "".join(tk),
        )
    )
    s.add(
        '<rect y="297" width="96" height="43" fill="url(#fe)"/><rect x="1184" y="297" width="96" height="43" fill="url(#fe2)"/>'
    )
    return s


# ---------------------------------------------------------------- cards
CARDS = {
    "browse": (
        "PYTHON",
        "Give Claude a browser, keep chat light",
        "Sonnet helper · short summaries back",
    ),
    "second-brain": (
        "PYTHON",
        "Persistent memory for Claude Code",
        "second-brain-web.vercel.app",
    ),
    "zerodha": ("PYTHON", "An MCP server for Zerodha Kite", "Indian equities · F&O"),
    "stocky": (
        "TYPESCRIPT",
        "Six-agent council, Indian markets",
        "stockyai.xyz · Telegram + FastAPI",
    ),
    "stocky-fun": (
        "TYPESCRIPT",
        "AI BTC signals, reasoning shown",
        "fun.stockyai.xyz · paper trading",
    ),
    "openwispr": (
        "SWIFT",
        "On-device dictation for macOS",
        "Whisper · Apple Neural Engine",
    ),
    "continuum": ("PYTHON", "second-brain as hooks only", "stdlib Python · no deps"),
    "harness": (
        "SHELL",
        "The Claude Code harness I run",
        "CLAUDE.md · skills · hooks · commands",
    ),
}
CARD_REPO = {
    "browse": "claude-browse",
    "stocky-fun": "stocky-fun",
    "second-brain": "second-brain",
    "zerodha": "Zerodha-MCP-Trading",
    "stocky": "stocky-ai",
    "openwispr": "openwispr",
    "continuum": "continuum",
    "harness": "claude-code-harness",
}
CARD_LABEL = {
    "browse": "claude-browse. Give Claude a browser and keep the chat light. Animated page scan collapsing into a short summary.",
    "stocky-fun": "stocky-fun. AI BTC signals with the reasoning shown. Animated price line, a LONG badge and typed reasoning.",
    "second-brain": "second-brain. Persistent memory for Claude Code. Animated graph of linked notes lighting up in sequence.",
    "zerodha": "Zerodha-MCP-Trading. An MCP server for Zerodha Kite. Animated candlesticks with an order-fill flash.",
    "stocky": "stocky-ai. A six-agent council for Indian markets. Animated dots converging into one verdict.",
    "openwispr": "openwispr. On-device dictation for macOS. Animated waveform turning into typed text.",
    "continuum": "continuum. second-brain as hooks only. Animated chain of hooks firing in sequence.",
    "harness": "claude-code-harness. The Claude Code harness I run. Animated mini terminal with a blinking cursor.",
}


def motif_graph(s, p):
    N = {
        "H": (112, 68),
        "A": (36, 40),
        "B": (84, 28),
        "C": (152, 32),
        "D": (196, 60),
        "E": (52, 100),
        "F": (124, 108),
        "G": (184, 104),
    }
    order = ["HA", "AB", "HB", "HC", "CD", "HD", "DG", "FG", "HF", "EF", "HE"]
    C = 12.0
    first = {}
    out = []
    for i, e in enumerate(order):
        (x1, y1), (x2, y2) = N[e[0]], N[e[1]]
        d = i * 0.75
        for n in e:
            first.setdefault(n, d)
        fr = (
            "0%%{stroke:%(d)s;stroke-width:1}5%%{stroke:%(a)s;stroke-width:2}14%%{stroke:%(a)s;stroke-width:2}"
            "26%%{stroke:%(d)s;stroke-width:1}100%%{stroke:%(d)s;stroke-width:1}"
        ) % {"d": p["dim"], "a": p["accent"]}
        out.append(
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1" stroke-linecap="round" %s/>'
            % (x1, y1, x2, y2, p["dim"], s.anim(fr, C, "ease-in-out", d))
        )
    for n, (x, y) in N.items():
        r = 7 if n == "H" else 4
        base = p["accent"] if n == "H" else p["muted"]
        fr = (
            "0%%{fill:%(m)s}5%%{fill:%(a)s}20%%{fill:%(a)s}32%%{fill:%(m)s}100%%{fill:%(m)s}"
        ) % {"m": base, "a": p["accent"]}
        out.append(
            '<circle cx="%d" cy="%d" r="%d" fill="%s" %s/>'
            % (x, y, r, base, s.anim(fr, C, "ease-in-out", first[n]))
        )
    return "".join(out)


def motif_zerodha(s, p):
    C = 10.0
    data = [
        (70, 14, 0),
        (62, 12, 1),
        (74, 16, 0),
        (66, 10, 1),
        (80, 14, 0),
        (84, 12, 0),
        (90, 16, 0),
        (76, 18, 1),
        (60, 20, 1),
    ]
    out = []
    for i, (cy, bh, up) in enumerate(data):
        ex = s.rv(
            0.2 + i * 0.25,
            C,
            9.0,
            9.6,
            0.4,
            "transform:scaleY(0)",
            "transform:scaleY(1)",
            "cubic-bezier(.2,.8,.2,1)",
        )
        out.append(candle(24 + 16 * i, cy, bh, 8, 8, bool(up), p, 0.9, 6, extra=ex))
    ly = 100
    out.append(
        '<line class="fb" x1="8" x2="222" y1="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="4 4" %s/>'
        % (
            ly,
            ly,
            p["muted"],
            s.rv(
                2.8,
                C,
                9.0,
                9.6,
                0.6,
                "transform:scaleX(0);transform-origin:left",
                "transform:scaleX(1);transform-origin:left",
            ),
        )
    )
    out.append(
        '<circle class="fb" cx="120" cy="%d" r="10" fill="none" stroke="%s" stroke-width="2" stroke-opacity="0.5" %s/>'
        % (
            ly,
            p["accent"],
            s.anim(
                "0%,34%{transform:scale(.2);opacity:0}36%{transform:scale(.4);opacity:1}48%{transform:scale(1.6);opacity:0}"
                "49%,100%{transform:scale(1.6);opacity:0}",
                C,
                "ease-out",
            ),
        )
    )
    out.append(
        "<g %s>%s%s</g>"
        % (
            s.rv(3.6, C, 9.0, 9.6, 0.3),
            T(120, 119, "▲", 12, p["accent"], anchor="middle"),
            '<circle cx="120" cy="%d" r="3" fill="%s"/>' % (ly, p["accent"]),
        )
    )
    out.append(
        "<g %s>%s</g>"
        % (
            s.rv(3.9, C, 9.0, 9.6, 0.4),
            T(214, 90, "FILLED", 11, p["accent"], 700, "end", 1.2),
        )
    )
    return "".join(out)


def motif_stocky(s, p):
    C = 10.0
    cx, cy = 115, 68
    out = []
    pos = [
        (
            round(cx + 64 * math.cos(math.radians(a))),
            round(cy + 40 * math.sin(math.radians(a))),
        )
        for a in (-90, -30, 30, 90, 150, 210)
    ]
    jit = [(6, 4), (-5, 6), (6, -5), (-6, -4), (5, 5), (-4, -6)]
    for x, y in pos:
        out.append(
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1" stroke-dasharray="2 4" %s/>'
            % (
                cx,
                cy,
                x,
                y,
                p["dim"],
                s.anim(
                    "0%,30%{opacity:1}48%,76%{opacity:0}92%,100%{opacity:1}",
                    C,
                    "ease-in-out",
                ),
            )
        )
    for i, ((x, y), (jx, jy)) in enumerate(zip(pos, jit)):
        dx, dy = cx - x, cy - y
        fr = (
            "0%%{transform:translate(0,0);opacity:1}14%%{transform:translate(%dpx,%dpx);opacity:1}28%%{transform:translate(%dpx,%dpx);opacity:1}"
            "48%%{transform:translate(%dpx,%dpx);opacity:1}54%%{transform:translate(%dpx,%dpx);opacity:0}76%%{transform:translate(%dpx,%dpx);opacity:0}"
            "78%%{transform:translate(%dpx,%dpx);opacity:1}92%%,100%%{transform:translate(0,0);opacity:1}"
        ) % (jx, jy, -jx, -jy, dx, dy, dx, dy, dx, dy, dx, dy)
        out.append(
            '<circle class="fb" cx="%d" cy="%d" r="5" fill="%s" stroke="%s" stroke-width="1.5" %s/>'
            % (x, y, p["bg"], p["muted"], s.anim(fr, C, "ease-in-out", i * 0.08))
        )
    out.append(
        '<circle class="fb" cx="%d" cy="%d" r="14" fill="none" stroke="%s" stroke-width="1.5" stroke-opacity="0.5" %s/>'
        % (
            cx,
            cy,
            p["accent"],
            s.anim(
                "0%,48%{transform:scale(.4);opacity:0}52%{transform:scale(.6);opacity:1}72%{transform:scale(1.5);opacity:0}100%{opacity:0}",
                C,
                "ease-out",
            ),
        )
    )
    out.append(
        '<circle class="fb" cx="%d" cy="%d" r="7" fill="%s" %s/>'
        % (
            cx,
            cy,
            p["accent"],
            s.anim(
                "0%,46%{transform:scale(1)}56%,70%{transform:scale(1.5)}82%,100%{transform:scale(1)}",
                C,
                "ease-in-out",
            ),
        )
    )
    return "".join(out)


def motif_wispr(s, p):
    C = 10.0
    out = []
    n = 17
    for i in range(n):
        h = round(
            8
            + 36
            * abs(math.sin(i * 0.55 + 0.4))
            * (0.45 + 0.55 * math.sin(math.pi * (i + 0.5) / n))
        )
        fr = (
            "0%{transform:scaleY(.3)}8%{transform:scaleY(1)}16%{transform:scaleY(.5)}24%{transform:scaleY(.9)}32%{transform:scaleY(.35)}"
            "40%{transform:scaleY(.85)}48%{transform:scaleY(.5)}58%{transform:scaleY(.1)}90%{transform:scaleY(.1)}100%{transform:scaleY(.3)}"
        )
        out.append(
            '<rect class="fb co" x="%d" y="%s" width="6" height="%d" rx="3" fill="%s" %s/>'
            % (
                32 + 10 * i,
                44 - h / 2,
                h,
                p["accent"] if 5 <= i <= 11 else p["muted"],
                s.anim(fr, C, "ease-in-out", i * 0.1).replace('style="', 'data-a="'),
            )
        )
    # note: animation style merged below
    text = "ship the fix"
    x0 = 64
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        out.append(
            T(
                x0 + i * cw(1, 14),
                108,
                ch,
                14,
                p["fg"],
                extra=s.rv(5.2 + i * 0.14, C, 9.0, 9.6, 0.05, ease="linear"),
            )
        )
    cx = x0 + len(text) * cw(1, 14) + 3
    out.append(
        '<g %s><rect x="%s" y="95" width="8" height="16" fill="%s" %s/></g>'
        % (
            s.rv(7.0, C, 9.0, 9.6, 0.05, ease="linear"),
            round(cx, 2),
            p["accent"],
            s.anim("0%,50%{opacity:1}50.01%,100%{opacity:0}", 1.2, "steps(1)"),
        )
    )
    return "".join(out)


def motif_continuum(s, p):
    C = 12.0
    out = []
    xs = [15, 87, 159]
    labels = ["start", "prompt", "stop"]
    ax = p["accent"]
    for i, (x, lb) in enumerate(zip(xs, labels)):
        d = 0.4 + i * 1.4
        fr = (
            "0%%{stroke:%(d)s;fill-opacity:0}4%%{stroke:%(a)s;fill-opacity:.2}14%%{stroke:%(a)s;fill-opacity:.2}"
            "24%%{stroke:%(d)s;fill-opacity:0}100%%{stroke:%(d)s;fill-opacity:0}"
        ) % {"d": p["dim"], "a": ax}
        out.append(
            '<rect x="%d" y="20" width="56" height="32" rx="6" fill="%s" fill-opacity="0" stroke="%s" stroke-width="1.5" %s/>'
            % (x, ax, p["muted"], s.anim(fr, C, "ease-in-out", d))
        )
        out.append(T(x + 28, 40, lb, 11, p["fg"], anchor="middle"))
        out.append(
            '<path d="M%d 52 V96" stroke="%s" stroke-width="1" stroke-dasharray="2 4" %s/>'
            % (
                x + 28,
                p["dim"],
                s.anim(
                    "0%%{stroke:%(d)s}6%%{stroke:%(a)s}16%%{stroke:%(a)s}28%%{stroke:%(d)s}100%%{stroke:%(d)s}"
                    % {"d": p["dim"], "a": ax},
                    C,
                    "ease-in-out",
                    d + 0.4,
                ),
            )
        )
        if i < 2:
            out.append(
                '<path d="M%d 36 H%d" stroke="%s" stroke-width="1.5"/><path d="M%d 32 L%d 36 L%d 40" fill="none" stroke="%s" stroke-width="1.5"/>'
                % (x + 56, x + 72, p["muted"], x + 68, x + 72, x + 68, p["muted"])
            )
    vf = (
        "0%%{stroke:%(d)s}6%%{stroke:%(a)s}18%%{stroke:%(a)s}30%%{stroke:%(d)s}100%%{stroke:%(d)s}"
    ) % {"d": p["muted"], "a": ax}
    out.append(
        '<rect x="15" y="96" width="200" height="24" rx="6" fill="none" stroke="%s" stroke-width="1.5" %s/>'
        % (p["muted"], s.anim(vf, C, "ease-in-out", 3.6))
    )
    out.append(T(115, 112, "vault", 11, p["muted"], anchor="middle"))
    return "".join(out)


def motif_harness(s, p):
    C = 10.0
    out = []
    for i, c in enumerate((p["down"], p["accent"], p["up"])):
        out.append(
            '<circle cx="%d" cy="16" r="3" fill="%s" opacity="0.85"/>'
            % (16 + 12 * i, c)
        )
    out.append('<path d="M0 32.5 H230" stroke="%s"/>' % p["grid"])
    sz = 11
    a = cw(1, sz)

    def line(y, t_in, parts):
        els, x = [], 16
        for txt, col in parts:
            els.append(T(x, y, txt, sz, col))
            x += cw(len(txt), sz)
        return "<g %s>%s</g>" % (
            s.rv(
                t_in,
                C,
                9.0,
                9.6,
                0.3,
                "transform:translateX(-6px)",
                "transform:translateX(0)",
            ),
            "".join(els),
        )

    # typed command
    out.append(
        T(
            16,
            56,
            "$",
            sz,
            p["accent"],
            700,
            extra=s.rv(0.4, C, 9.0, 9.6, 0.05, ease="linear"),
        )
    )
    for i, ch in enumerate("claude"):
        out.append(
            T(
                16 + a * (2 + i),
                56,
                ch,
                sz,
                p["fg"],
                extra=s.rv(0.8 + i * 0.1, C, 9.0, 9.6, 0.05, ease="linear"),
            )
        )
    out.append(line(76, 1.8, [("loaded ", p["dim"]), ("CLAUDE.md", p["muted"])]))
    out.append(line(96, 2.4, [("skills · hooks · commands", p["muted"])]))
    out.append(
        '<g %s>%s<rect x="%s" y="107" width="7" height="14" fill="%s" %s/></g>'
        % (
            s.rv(3.2, C, 9.0, 9.6, 0.05, ease="linear"),
            T(16, 118, "$", sz, p["accent"], 700),
            round(16 + 2 * a, 2),
            p["accent"],
            s.anim("0%,50%{opacity:1}50.01%,100%{opacity:0}", 1.2, "steps(1)"),
        )
    )
    return "".join(out)


def motif_browse(s, p):
    C = 10.0
    out = []
    for i, c in enumerate((p["down"], p["accent"], p["up"])):
        out.append('<circle cx="%d" cy="16" r="3" fill="%s" opacity="0.85"/>' % (16 + 12 * i, c))
    out.append('<rect x="56" y="8" width="158" height="16" rx="4" fill="%s" stroke="%s"/>' % (p["bg2"], p["grid"]))
    a = cw(1, 10)
    for i, ch in enumerate("news.ycombinator.com"):
        out.append(T(64 + a * i, 20, ch, 10, p["muted"], extra=s.rv(0.3 + i * 0.05, C, 9.0, 9.6, 0.05, ease="linear")))
    out.append('<path d="M0 32.5 H230" stroke="%s"/>' % p["grid"])
    for i, w in enumerate((150, 186, 120, 170)):
        out.append('<rect x="16" y="%d" width="%d" height="6" rx="3" fill="%s" opacity="0.35" %s/>'
                   % (44 + 12 * i, w, p["muted"], s.rv(1.4 + i * 0.15, C, 9.0, 9.6, 0.3)))
    # scan bar: decoration only, hidden in the static frame
    out.append('<rect x="12" y="40" width="206" height="2" rx="1" fill="%s" opacity="0" %s/>' % (
        p["accent"], s.anim("0%%,%s%%{opacity:0;transform:translateY(0)}%s%%{opacity:.9}%s%%{opacity:.9;transform:translateY(48px)}%s%%,100%%{opacity:0;transform:translateY(48px)}"
                            % (pct(2.2, C), pct(2.4, C), pct(3.8, C), pct(4.0, C)), C, "linear")))
    out.append('<g %s><rect x="16" y="98" width="198" height="24" rx="6" fill="%s" fill-opacity="0.12" stroke="%s" stroke-opacity="0.5"/>%s%s</g>' % (
        s.rv(4.2, C, 9.0, 9.6, 0.35, "transform:translateY(6px)", "transform:translateY(0)"),
        p["accent"], p["accent"],
        T(26, 114, "→", 11, p["accent"], 700),
        T(26 + cw(2, 11), 114, "summary · 3 lines back", 11, p["fg"])))
    return "".join(out)


def motif_signal(s, p):
    C = 10.0
    ys = [52, 48, 50, 42, 45, 38, 40, 32, 35, 26, 28, 20]
    pts = " L".join("%d,%d" % (16 + i * 11, y) for i, y in enumerate(ys))
    out = ['<path d="M16 56.5 H140" stroke="%s"/>' % p["grid"],
           '<path d="M%s" pathLength="1" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" stroke-dasharray="1" %s/>'
           % (pts, p["up"], s.anim("0%%{stroke-dashoffset:1}%s%%,100%%{stroke-dashoffset:0}" % pct(1.6, C), C, "ease-out")),
           '<circle cx="137" cy="20" r="3" fill="%s"/>' % p["up"]]
    out.append('<g %s><rect x="156" y="12" width="58" height="22" rx="6" fill="%s" fill-opacity="0.15" stroke="%s" stroke-opacity="0.6"/>%s</g>' % (
        s.rv(1.8, C, 9.0, 9.6, 0.3, "transform:scale(.8)", "transform:scale(1)"),
        p["up"], p["up"], T(185, 27, "LONG", 11, p["up"], 700, anchor="middle", ls=1.2)))
    for k, (txt, col) in enumerate((("trend up on the 4h", p["muted"]), ("momentum confirms", p["muted"]), ("→ long, stop set", p["fg"]))):
        out.append(T(16, 84 + 18 * k, txt, 11, col, extra=s.rv(2.6 + 0.9 * k, C, 9.0, 9.6, 0.35, "transform:translateX(-6px)", "transform:translateX(0)")))
    return "".join(out)


MOTIFS = {
    "browse": motif_browse,
    "stocky-fun": motif_signal,
    "second-brain": motif_graph,
    "zerodha": motif_zerodha,
    "stocky": motif_stocky,
    "openwispr": motif_wispr,
    "continuum": motif_continuum,
    "harness": motif_harness,
}


def card(key, p):
    chip, pitch, meta = CARDS[key]
    name = CARD_REPO[key]
    s = Svg(630, 200, CARD_LABEL[key], p)
    s.defs.append(grad("cg", [("0%", p["bg"], 1), ("100%", p["bg2"], 1)], 1, 1))
    s.add(
        '<rect x="0.5" y="0.5" width="629" height="199" rx="12" fill="url(#cg)" stroke="%s"/>'
        % p["grid"]
    )
    cwid = round(cw(len(chip), 11, 1.2) + 16 - 1.2)
    s.add(
        '<rect x="32" y="32" width="%d" height="24" rx="6" fill="%s" fill-opacity="0.12" stroke="%s" stroke-opacity="0.5"/>'
        % (cwid, p["accent"], p["accent"])
    )
    s.add(T(40, 48, chip, 11, p["accent"], 700, ls=1.2))
    s.add(T(32, 96, name, 22, p["fg"], 700, ls=-0.4))
    s.add(T(32, 128, pitch, 13, p["muted"]))
    s.add(T(32, 168, meta, 12, p["dim"]))
    s.add(
        '<rect x="368" y="32" width="230" height="136" rx="8" fill="%s" stroke="%s"/>'
        % (p["bg"], p["grid"])
    )
    s.add('<g transform="translate(368 32)">%s</g>' % MOTIFS[key](s, p))
    return s


# ---------------------------------------------------------------- terminal
def terminal(p):
    s = Svg(
        1280,
        272,
        "Terminal session. whoami: Charandeep Kapoor, AI × Trading, 2× ex-founder, Product at Delta Exchange, IIT Kanpur. ls ~/shipping: claude-browse, second-brain, Zerodha-MCP-Trading, stocky-ai, openwispr, continuum, claude-code-harness.",
        p,
    )
    C, OUT0, OUT1 = 14.0, 12.6, 13.4
    s.add(
        '<rect x="0.5" y="8.5" width="1279" height="271" rx="12" fill="%s" stroke="%s"/>'
        % (p["bg"], p["grid"])
    )
    s.add('<path d="M1 48.5 H1279" stroke="%s"/>' % p["grid"])
    for i, c in enumerate((p["down"], p["accent"], p["up"])):
        s.add(
            '<circle cx="%d" cy="28" r="6" fill="%s" opacity="0.85"/>'
            % (32 + 20 * i, c)
        )
    s.add(T(640, 33, "ck@delta — zsh", 12, p["dim"], anchor="middle", ls=0.5))
    size = 16
    a = cw(1, size)
    X = 64

    def typed(y, t0, cmd):
        s.add(
            T(
                X,
                y,
                "$",
                size,
                p["accent"],
                700,
                extra=s.rv(t0, C, OUT0, OUT1, 0.05, ease="linear"),
            )
        )
        for i, ch in enumerate(cmd):
            if ch != " ":
                s.add(
                    T(
                        X + a * (2 + i),
                        y,
                        ch,
                        size,
                        p["fg"],
                        extra=s.rv(
                            t0 + 0.3 + i * 0.09, C, OUT0, OUT1, 0.05, ease="linear"
                        ),
                    )
                )

    def outline(y, t0, txt, col):
        s.add(
            T(
                X,
                y,
                txt,
                size,
                col,
                extra=s.rv(
                    t0,
                    C,
                    OUT0,
                    OUT1,
                    0.35,
                    "transform:translateX(-8px)",
                    "transform:translateX(0)",
                ),
            )
        )

    typed(80, 0.4, "whoami")
    outline(104, 1.7, "Charandeep Kapoor · AI × Trading · 2× ex-founder", p["fg"])
    outline(
        128,
        2.1,
        "Product @ Delta Exchange · IIT Kanpur",
        p["muted"],
    )
    outline(152, 2.5, "trading systems for crypto and Indian markets · tooling for AI agents", p["muted"])
    typed(184, 3.4, "ls ~/shipping")
    x = X
    for j, n in enumerate(NAMES[:7]):
        s.add(
            T(
                x,
                208,
                n,
                size,
                p["fg"],
                extra=s.rv(
                    5.1 + j * 0.18,
                    C,
                    OUT0,
                    OUT1,
                    0.3,
                    "transform:translateX(-8px)",
                    "transform:translateX(0)",
                ),
            )
        )
        x += cw(len(n), size) + 24
    s.add(
        T(
            X,
            240,
            "$",
            size,
            p["accent"],
            700,
            extra=s.rv(6.6, C, OUT0, OUT1, 0.05, ease="linear"),
        )
    )
    s.add(
        '<g %s><rect x="%s" y="226" width="%s" height="18" fill="%s" %s/></g>'
        % (
            s.rv(6.8, C, OUT0, OUT1, 0.05, ease="linear"),
            round(X + 2 * a, 2),
            round(a, 2),
            p["accent"],
            s.anim("0%,50%{opacity:1}50.01%,100%{opacity:0}", 1.2, "steps(1)"),
        )
    )
    s.body = ['<g transform="translate(0 -8)">'] + s.body + ['</g>']
    return s


# ---------------------------------------------------------------- footer
def footer(p):
    s = Svg(
        1280,
        64,
        "Charandeep Kapoor. AI × Trading, 2× ex-founder. Footer strip with a slow amber scanline.",
        p,
    )
    s.defs.append(
        grad(
            "sg",
            [
                ("0%", p["accent"], 0),
                ("85%", p["accent"], 0.16),
                ("100%", p["accent"], 0),
            ],
        )
    )
    s.defs.append(
        grad(
            "sl",
            [
                ("0%", p["accent"], 0),
                ("80%", p["accent"], 0.9),
                ("100%", p["accent"], 0),
            ],
        )
    )
    s.add(
        '<rect width="1280" height="64" fill="%s"/><path d="M0 0.5 H1280 M0 63.5 H1280" stroke="%s"/>'
        % (p["bg"], p["grid"])
    )
    s.add(T(64, 37, "▲ SirCharan", 12, p["accent"], 700, ls=1.2))
    s.add(T(176, 37, "AI × Trading · 2× ex-founder · IIT Kanpur", 12, p["dim"]))
    s.add(T(1216, 37, "charandeepkapoor.com", 12, p["muted"], anchor="end"))
    fr = "from{transform:translateX(-760px)}to{transform:translateX(520px)}"
    st = s.anim(fr, 12, "linear")
    s.add(
        '<g %s><rect x="520" y="1" width="240" height="62" fill="url(#sg)"/><rect x="520" y="61" width="240" height="2" fill="url(#sl)"/></g>'
        % st
    )
    return s


# ---------------------------------------------------------------- build
def all_svgs():
    out = {}
    for mode, p in PALETTES.items():
        out["hero-%s.svg" % mode] = hero(p)
        out["terminal-%s.svg" % mode] = terminal(p)
        out["footer-%s.svg" % mode] = footer(p)
        for k in CARDS:
            out["card-%s-%s.svg" % (k, mode)] = card(k, p)
    return out


def write_preview():
    readme = os.path.join(HERE, "README.md")
    if not os.path.exists(readme):
        return
    with open(readme, encoding="utf-8") as fh:
        md = fh.read()
    html = (
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>preview</title><style>:root{color-scheme:light dark}body{max-width:1012px;margin:32px auto;padding:0 16px;"
        "font:16px/1.5 -apple-system,system-ui,sans-serif;background:#fff;color:#1f2328}"
        "@media(prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}}a{color:#4493f8}"
        "img{display:inline-block;vertical-align:top}picture{display:contents}</style><body>"
        + md
        + "</body>\n"
    )
    with open(os.path.join(HERE, "preview.html"), "w", encoding="utf-8") as fh:
        fh.write(html)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    for name, svg in sorted(all_svgs().items()):
        text = svg.render()
        ET.fromstring(text)  # must parse
        size = len(text.encode("utf-8"))
        assert size < 150_000, (name, size)
        with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%-34s %7.1f KB" % (name, size / 1024))
    write_preview()
    print("preview.html written")


if __name__ == "__main__":
    main()
