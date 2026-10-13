"""
إعادة تصميم واجهات المشروع (dashboard / sijil / user_guide) بالبايثون
====================================================================
الاستخدام من جذر المشروع:

    python apply_ui_redesign.py                 # يعالج الملفات الثلاثة
    python apply_ui_redesign.py path/to/file.html ...

ما يفعله (بلا لمس أي منطق JavaScript أو معرّفات DOM):
1) impeccable: لوحة «لاكر دافئ + كينباكو»: أسود دافئ، ذهب للإجراء الأساسي، باتينا
   (أخضر نحاسي) للنجاح. بلا توهّج، بلا بنفسجي «AI». ألوان OKLCH.
2) design-taste-frontend: إزالة الإيموجي (SVG أو حذف)، تصحيح letter-spacing مع العربية،
   أنصاف أقطار هادئة، transition محددة بدل all، أهداف لمس ≥32px، حلقات تركيز.
   وإصلاح أخطاء شكلية: .btn-success/.btn-secondary بلا CSS، و@keyframes modal-pop غير معرّف.
3) animation-vocabulary: Fade in + Rise، Stagger للبطاقات والخطوات، Pop in للنوافذ،
   Ease-out، و Reduced motion والطباعة بلا حركة.
4) diagram-design: مخطط خط سير الاستيراد في user_guide يتحول إلى SVG بموصّلات
   ومنطقتَي «قراءة فقط / كتابة محكومة».

آمن للتكرار (علامة UI-THEME-V2) ويحفظ نسخة .bak لكل ملف.
"""

from __future__ import annotations

import math
import re
import shutil
import sys
from pathlib import Path

MARK = "UI-THEME-V2"


# ───────────────────────── ألوان OKLCH → sRGB (لاستبدال rgba الثابتة) ─────────────────────────
def oklch_rgb(l: float, c: float, h: float) -> str:
    a = c * math.cos(math.radians(h))
    b = c * math.sin(math.radians(h))
    l_ = l + 0.3963377774 * a + 0.2158037573 * b
    m_ = l - 0.1055613458 * a - 0.0638541728 * b
    s_ = l - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    g = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    bl = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3

    def enc(x: float) -> int:
        x = max(0.0, min(1.0, x))
        x = 12.92 * x if x <= 0.0031308 else 1.055 * (x ** (1 / 2.4)) - 0.055
        return round(x * 255)

    return f"{enc(r)}, {enc(g)}, {enc(bl)}"


RGB_VERDIGRIS = oklch_rgb(0.76, 0.088, 190)
RGB_GOLD = oklch_rgb(0.84, 0.19, 80)
RGB_SKY = oklch_rgb(0.74, 0.09, 235)
RGB_AMBER = oklch_rgb(0.78, 0.15, 60)

RGBA_MAP = {
    "62, 207, 142": RGB_VERDIGRIS,
    "0, 197, 115": RGB_VERDIGRIS,
    "146, 129, 247": RGB_GOLD,
    "56, 189, 248": RGB_SKY,
    "59, 158, 255": RGB_SKY,
    "255, 202, 22": RGB_AMBER,
}

HEX_MAP = {
    "#121212": "oklch(7% 0.006 95)",
    "#141414": "oklch(9% 0.006 95)",
    "#161616": "oklch(9.5% 0.006 95)",
    "#181818": "oklch(10% 0.006 95)",
    "#191919": "oklch(10.5% 0.006 95)",
    "#1a1a1a": "oklch(10.5% 0.006 95)",
    "#202020": "oklch(12% 0.006 95)",
    "#232323": "oklch(13.5% 0.006 95)",
    "#242424": "oklch(13.5% 0.006 95)",
    "#252525": "oklch(14% 0.006 95)",
    "#282828": "oklch(15% 0.007 95)",
    "#2e2e2e": "oklch(21% 0.008 95)",
    "#393939": "oklch(27% 0.01 95)",
    "#4d4d4d": "oklch(36% 0.01 95)",
    "#0b0c10": "oklch(12% 0.01 85)",
    "#9281f7": "var(--color-iris-violet)",
}

# ───────────────────────── الأيقونات (بدل الإيموجي في سياقات HTML) ─────────────────────────
def _svg(body: str, size: str = "1em") -> str:
    return (
        f'<svg class="ico" viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">{body}</svg>'
    )


ICONS = {
    "🔍": _svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'),
    "📂": _svg('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>', "32"),
    "⚙️": _svg('<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>'),
    "📜": _svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>'),
    "💬": _svg('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'),
    "📊": _svg('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>'),
    "🔏": _svg('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'),
    "📋": _svg('<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>'),
    "ℹ️": _svg('<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'),
}

# إيموجي تُحذف كلياً (رسائل نصية / confirm / نصوص escapeHtml حيث لا يصلح SVG)
STRIP_EMOJI = re.compile("[\u26a0\u2753\u2705\u274c\U0001F4CE\U0001F4CB\U0001F512\U0001F50D\U0001F4C2]\ufe0f?[ \t]?")

# ───────────────────────── CSS المشترك ─────────────────────────
THEME_CSS = """
/* UI-THEME-V2 : لاكر دافئ + كينباكو (impeccable / design-taste-frontend / animation-vocabulary) */
:root{
  --color-obsidian:oklch(7% 0.006 95);
  --color-ash:oklch(10% 0.006 95);
  --color-card:oklch(12% 0.006 95);
  --color-card-elevated:oklch(15% 0.007 95);
  --color-charcoal:oklch(21% 0.008 95);
  --color-slate:oklch(27% 0.01 95);
  --color-graphite:oklch(36% 0.01 95);
  --color-snow:oklch(94% 0.004 95);
  --color-silver-mist:oklch(75% 0.008 95);
  --color-smoke:oklch(63% 0.008 95);
  --color-phosphor-green:oklch(76% 0.088 190);
  --color-mint-pulse:oklch(70% 0.09 185);
  --color-forest-depth:oklch(30% 0.05 190);
  --color-midnight-emerald:oklch(36% 0.06 190);
  --color-iris-violet:oklch(84% 0.19 80);
  --color-iris-glow:oklch(90% 0.12 85);
  --color-iris-soft:oklch(84% 0.19 80 / 0.12);
  --color-amber:oklch(78% 0.15 60);
  --color-coral:oklch(70% 0.15 22);
  --color-blue:oklch(74% 0.09 235);
  --agent-seraj:oklch(74% 0.09 235);
  --agent-fahas:oklch(74% 0.09 205);
  --agent-modaqeq:oklch(72% 0.09 275);
  --agent-mowafaq:oklch(72% 0.10 350);
  --agent-hares:oklch(70% 0.12 25);
  --agent-musleh:oklch(78% 0.11 75);
  --agent-katib:oklch(74% 0.09 160);
  --agent-sijil:oklch(84% 0.19 80);
  --agent-laya:oklch(72% 0.09 310);
  --radius-cards:10px;
  --radius-inputs:6px;
  --ease-out:cubic-bezier(0.23,1,0.32,1);
}
html{color-scheme:dark}
body{background:var(--color-obsidian)}

/* عربي: لا تباعد حروف (يكسر الاتصال)، وأرقام بعرض ثابت */
html body :is(h1,h2,h3,h4,p,span,div,th,td,a,button,label,li,code,pre,.badge,.eyebrow,.tag-step,.node-pill){letter-spacing:0}
.mono,.metric-value,.step-time,td.mono,.num-tabular{font-variant-numeric:tabular-nums lining-nums}

/* أيقونات SVG بدل الإيموجي */
.ico{display:inline-block;vertical-align:-0.15em;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
.sec-icon .ico{width:18px;height:18px}

/* أصناف مستخدمة في الكود لكنها بلا CSS أصلاً */
.btn-success{background:var(--color-iris-violet);color:oklch(14% 0.02 85);border-color:var(--color-iris-violet);font-weight:600}
.btn-success:hover:not(:disabled){filter:brightness(1.06)}
.btn-secondary{background:transparent;border-color:var(--color-slate);color:var(--color-snow)}
.font-xs{font-size:11.5px}
.bold{font-weight:600}

/* الإجراء الأساسي = ذهب */
.btn-primary,.btn-primary:hover:not(:disabled){background:var(--color-iris-violet);border-color:var(--color-iris-violet);color:oklch(14% 0.02 85)}
.btn-primary:hover:not(:disabled){filter:brightness(1.06)}
.nav-tab-btn.is-active{color:var(--color-iris-violet)}
.nav-brand-icon svg{stroke:var(--color-iris-violet)}
.chat-textarea:focus,.search-input:focus{border-color:var(--color-iris-violet);box-shadow:none}

/* بلا توهّج ولا نبض لا نهائي */
.nav-brand-pulse{box-shadow:none;background:var(--color-iris-violet)}
.agent-character-card.is-active{box-shadow:none;background:color-mix(in oklch,var(--agent-color,var(--color-iris-violet)) 7%,transparent)}
.agent-character-card.is-active::after{animation:none;opacity:0.35;inset:-2px}
.drawer-overlay{backdrop-filter:none;-webkit-backdrop-filter:none}
.drawer-sheet{box-shadow:none}

/* أنصاف أقطار هادئة وانتقالات محددة */
.btn,.nav-tab-btn,.suggestion-chip{border-radius:var(--radius-inputs)}
.nav-tabs{border-radius:var(--radius-cards)}
.btn,.nav-tab-btn,.suggestion-chip,.agent-character-card,.agent-full-card,.step-node,.candidate-item,.back-link,.quick-nav a,.chip,.trouble-card,.node-card{
  transition:color .15s var(--ease-out),background-color .15s var(--ease-out),border-color .15s var(--ease-out),transform .15s var(--ease-out),opacity .15s var(--ease-out)}
.btn-sm{min-height:32px}
.btn:active:not(:disabled){transform:scale(0.98)}
:focus-visible{outline:2px solid var(--color-iris-violet);outline-offset:2px}
.chat-textarea:focus-visible,.search-input:focus-visible{outline:none}

/* شريط علوي متجاوب (كان يفيض عرضياً تحت ~1180px) */
@media (max-width:1180px){
  .top-nav{height:auto;flex-wrap:wrap;padding:12px 16px;row-gap:10px}
  .nav-tabs{order:3;width:100%;overflow-x:auto;border-radius:var(--radius-cards);scrollbar-width:none}
  .nav-controls{flex-wrap:wrap}
}

/* ───── الحركة: Fade in + Rise، Stagger، Pop in، Ease-out ───── */
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes modal-pop{from{opacity:0;transform:scale(0.96) translateY(6px)}to{opacity:1;transform:none}}
.view-section.is-visible{animation:rise .28s var(--ease-out) backwards}
.msg-bubble{animation:rise .3s var(--ease-out) backwards}
.stepper-container>.step-node:last-child{animation:rise .3s var(--ease-out) backwards}
.drawer-overlay.is-open,.op-modal-overlay.is-open{animation:fade .18s var(--ease-out) backwards}
.op-modal{animation:modal-pop .22s var(--ease-out) backwards}
.operation-view>*{animation:rise .34s var(--ease-out) backwards}
#operationView{animation:fade .2s var(--ease-out) backwards}
.agents-strip>*,.agents-grid>*,.metrics-grid>*,.trouble-grid>*,.candidates-list>*,.timeline>*,.results-comparison>*,.pipe-svg .node{animation:rise .34s var(--ease-out) backwards}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-delay:0ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;scroll-behavior:auto!important}
}
@media print{*,*::before,*::after{animation:none!important;transition:none!important}}
"""

_STAGGER_CONTAINERS = [
    (".agents-strip", 40), (".agents-grid", 50), (".metrics-grid", 60), (".trouble-grid", 60),
    (".candidates-list", 40), (".timeline", 40), (".results-comparison", 80), (".operation-view", 60),
    (".pipe-svg", 70),
]


def _stagger_css() -> str:
    out = []
    for sel, step in _STAGGER_CONTAINERS:
        child = ">.node" if sel == ".pipe-svg" else ">*"
        for i in range(2, 10):
            out.append(f"{sel}{child}:nth-child({i}){{animation-delay:{(i - 1) * step}ms}}")
    return "\n".join(out) + "\n"


GUIDE_CSS = """
/* user_guide: مخطط SVG (diagram-design) */
.pipe-wrap{overflow-x:auto}
.pipe-svg{display:block;width:100%;height:auto;min-width:760px}
.pipe-svg text{unicode-bidi:plaintext}
.pipe-svg .box{fill:var(--color-ash);stroke:var(--color-slate);stroke-width:1}
.pipe-svg .gate{fill:color-mix(in oklch,var(--color-iris-violet) 8%,transparent);stroke:var(--color-iris-violet)}
.pipe-svg .tag{font:500 10px var(--font-mono);fill:var(--color-smoke)}
.pipe-svg .nm{font:600 13px var(--font-arabic);fill:var(--color-snow)}
.pipe-svg .sb{font:11px var(--font-arabic);fill:var(--color-silver-mist)}
.pipe-svg .ln{stroke:var(--color-smoke);stroke-width:1.2;fill:none}
.pipe-svg .mk{fill:var(--color-smoke)}
.pipe-svg .zr{stroke:var(--color-slate);stroke-width:1;fill:none}
.pipe-svg .zw{stroke:var(--color-iris-violet);stroke-width:1;fill:none}
.pipe-svg .zl{font:500 11px var(--font-arabic);fill:var(--color-smoke)}
.pipe-svg .zl.w{fill:var(--color-iris-glow)}
h2 .tag-step,.badge{color:var(--color-iris-violet)}
.badge-dot{background:var(--color-iris-violet)}
.quick-nav a:hover{border-color:var(--color-iris-violet);background:color-mix(in oklch,var(--color-iris-violet) 6%,transparent)}
"""


def build_pipeline_block() -> str:
    """مخطط خط السير: 5 عقد، موصّلات مستقيمة، منطقتان (قراءة فقط / كتابة محكومة). اتجاه RTL."""
    W, H, NW, NH, GAP, Y = 1000, 214, 156, 100, 45, 32
    nodes = [
        ("01", "ملف Excel", ["القالب الرسمي المعتمد", "قوائم منسدلة جاهزة"], False),
        ("02", "الفحص التجريبي Dry-Run", ["مطابقة الأقسام والوظائف", "قراءة فقط · عزل كامل"], True),
        ("03", "تقرير التدقيق والفرز", ["مقبول · يحتاج مراجعة", "مرفوض"], False),
        ("04", "الاعتماد البشري", ["Four-Eyes", "توقيع المسؤول في السجل"], True),
        ("05", "الإنشاء والتحقق في Odoo", ["قراءة odoo_id راجعة", "إشعار تيليقرام"], False),
    ]
    xs = [W - 20 - NW - i * (NW + GAP) for i in range(5)]
    parts = []
    for i, (tag, name, subs, gate) in enumerate(nodes):
        x = xs[i]
        cls = "box gate" if gate else "box"
        parts.append(
            f'<g class="node">'
            f'<rect x="{x}" y="{Y}" width="{NW}" height="{NH}" rx="6" class="{cls}"/>'
            f'<text x="{x + NW - 18}" y="{Y + 20}" class="tag" text-anchor="middle">{tag}</text>'
            f'<text x="{x + NW / 2}" y="{Y + 52}" class="nm" text-anchor="middle">{name}</text>'
            f'<text x="{x + NW / 2}" y="{Y + 72}" class="sb" text-anchor="middle">{subs[0]}</text>'
            f'<text x="{x + NW / 2}" y="{Y + 88}" class="sb" text-anchor="middle">{subs[1]}</text>'
            f"</g>"
        )
    cy = Y + NH // 2
    arrows = "".join(
        f'<line x1="{xs[i]}" y1="{cy}" x2="{xs[i] - GAP}" y2="{cy}" class="ln" marker-end="url(#pa)"/>'
        for i in range(4)
    )
    zy = Y + NH + 26
    r0, r1 = xs[2], xs[0] + NW
    w0, w1 = xs[4], xs[3] + NW
    zones = (
        f'<path d="M{r0},{zy - 6} V{zy} H{r1} V{zy - 6}" class="zr"/>'
        f'<text x="{(r0 + r1) / 2}" y="{zy + 20}" class="zl" text-anchor="middle">قراءة فقط · لا كتابة في Odoo</text>'
        f'<path d="M{w0},{zy - 6} V{zy} H{w1} V{zy - 6}" class="zw"/>'
        f'<text x="{(w0 + w1) / 2}" y="{zy + 20}" class="zl w" text-anchor="middle">كتابة محكومة بالاعتماد البشري</text>'
    )
    svg = (
        f'<svg class="pipe-svg" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-labelledby="pipe-t pipe-d">'
        f'<title id="pipe-t">مسار تدفق بيانات استيراد الموظفين</title>'
        f'<desc id="pipe-d">من ملف الإكسل إلى الفحص التجريبي للقراءة فقط، ثم تقرير الفرز، ثم الاعتماد البشري، ثم الإنشاء والتحقق في Odoo.</desc>'
        f'<defs><marker id="pa" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">'
        f'<polygon points="0 0, 8 3, 0 6" class="mk"/></marker></defs>'
        f'<g>{arrows}</g>{"".join(parts)}{zones}</svg>'
    )
    return (
        '<div class="pipeline-diagram">\n'
        '          <div class="diagram-title">\n'
        '            <h4><span class="badge-dot"></span> مسار تدفق البيانات الحصري (Path A)</h4>\n'
        '            <span class="diagram-caption">Odoo 19 HR Integration Bridge</span>\n'
        "          </div>\n"
        f'          <div class="pipe-wrap">{svg}</div>\n'
        "        </div>"
    )


# ───────────────────────── المعالجة ─────────────────────────
def patch_html(text: str, name: str) -> tuple[str, list[str]]:
    log: list[str] = []
    if MARK in text:
        return text, ["مُطبّق سابقاً"]

    # 1) ألوان ثابتة → رموز/OKLCH دافئة
    n_before = text
    for old, rgb in RGBA_MAP.items():
        text = re.sub(rf"rgba\({re.escape(old)},", f"rgba({rgb},", text)
    text = re.sub(r"rgba\(18, 18, 18, ([\d.]+)\)", r"oklch(7% 0.006 95 / \1)", text)
    for hx, repl in HEX_MAP.items():
        text = re.sub(rf"{hx}(?![0-9a-fA-F])", repl, text, flags=re.I)
    if text != n_before:
        log.append("ألوان ثابتة → لوحة دافئة")

    # 2) transition: all → خصائص محددة
    text, n = re.subn(
        r"transition:\s*all\s+[\d.]+s\s*(?:ease(?:-out)?)?;",
        "transition: color .15s var(--ease-out, ease), background-color .15s var(--ease-out, ease), "
        "border-color .15s var(--ease-out, ease), transform .15s var(--ease-out, ease), opacity .15s var(--ease-out, ease);",
        text,
    )
    if n:
        log.append(f"transition:all ×{n}")

    # 3) الإيموجي: SVG في سياقات HTML الثابتة (sijil/guide) وحذف في الباقي
    if name != "dashboard":
        for emo, svg in ICONS.items():
            if emo in text:
                text = text.replace(emo, svg)
    text, n = STRIP_EMOJI.subn("", text)
    for emo in ICONS:
        if name == "dashboard" and emo in text:
            text = text.replace(emo, "")
    if n:
        log.append(f"إيموجي محذوف ×{n}")

    # 4) color-scheme للعناصر الأصلية (scrollbars/inputs)
    if 'name="color-scheme"' not in text:
        text = text.replace("</head>", '  <meta name="color-scheme" content="dark">\n</head>', 1)

    # 5) مخطط user_guide
    extra_css = ""
    if name == "user_guide" and '<div class="pipeline-diagram">' in text:
        start = text.index('<div class="pipeline-diagram">')
        end = text.index("</section>", start)
        text = text[:start] + build_pipeline_block() + "\n      " + text[end:]
        extra_css = GUIDE_CSS
        log.append("مخطط SVG جديد")

    # 6) حقن CSS في نهاية أول <style>
    css = THEME_CSS + _stagger_css() + extra_css
    if "</style>" not in text:
        raise ValueError("لا يوجد وسم </style>")
    text = text.replace("</style>", css + "</style>", 1)
    log.append("حقن CSS الموحّد")
    return text, log


def kind_of(path: Path) -> str:
    n = path.stem.lower()
    return "dashboard" if "dashboard" in n else ("sijil" if "sijil" in n else ("user_guide" if "guide" in n else "other"))


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or [
        Path("templates/dashboard.html"),
        Path("templates/sijil.html"),
        Path("docs/user_guide.html"),
    ]
    rc = 0
    for p in targets:
        if not p.exists():
            print(f"[تخطّي] غير موجود: {p}")
            continue
        src = p.read_text(encoding="utf-8")
        try:
            out, log = patch_html(src, kind_of(p))
        except ValueError as exc:
            print(f"[خطأ] {p}: {exc}")
            rc = 2
            continue
        if out != src:
            shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
            p.write_text(out, encoding="utf-8")
        print(f"[تم] {p}: " + " · ".join(log))
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
