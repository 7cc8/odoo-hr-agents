"""
صفحات الواجهة البديلة لـ web_service.py
=======================================
web_service.py خدمة API؛ الأسطح المرئية الوحيدة فيه هي الصفحات البديلة التي تُعرض
عند غياب ملف القالب (dashboard.html / user_guide.html / sijil.html).
هذه الوحدة تحوّلها من `<h1>` خام إلى صفحة بنفس لغة الهوية (ورق دافئ، ذهب كعلامة،
حبر دافئ، وضع داكن تلقائي)، مع حركة خفيفة تحترم Reduced motion.

الحركة: Fade in + Stagger (60ms) و Ease-out، على transform/opacity فقط.
"""

from __future__ import annotations

import html as _html
from typing import Optional

_CSS = """
:root{
  --paper:oklch(97% 0.012 95);--card:oklch(99% 0.008 95);--ink:oklch(18% 0.02 95);
  --muted:oklch(45% 0.015 95);--rule:oklch(86% 0.012 95);--gold:oklch(77% 0.13 82);
  --link:oklch(49% 0.08 188);--focus:oklch(49% 0.08 188);
  --font:"IBM Plex Sans Arabic","Noto Sans Arabic","Segoe UI",Tahoma,system-ui,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Consolas,monospace;--ease:cubic-bezier(.23,1,.32,1)}
@media(prefers-color-scheme:dark){:root{
  --paper:oklch(7% 0.006 95);--card:oklch(11% 0.006 95);--ink:oklch(91% 0 0);
  --muted:oklch(72% 0 0);--rule:oklch(26% 0.01 95);--gold:oklch(84% 0.19 80);
  --link:oklch(76% 0.088 190);--focus:oklch(70% 0.12 188)}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;
  background:var(--paper);color:var(--ink);font:15px/1.8 var(--font)}
.card{position:relative;width:min(520px,100%);padding:36px 36px 30px;
  background:var(--card);border:1px solid var(--rule);border-radius:2px}
.card::before{content:"";position:absolute;inset:-1px -1px auto -1px;height:3px;background:var(--gold)}
.code{font:500 11px var(--mono);letter-spacing:.14em;color:var(--muted);direction:ltr;text-align:right}
h1{margin:10px 0 8px;font-size:24px;line-height:1.35;font-weight:700}
p{margin:0 0 10px;color:var(--muted);max-width:60ch}
.hint{padding-inline-start:12px;border-inline-start:2px solid var(--rule);font-size:13.5px}
.btn{display:inline-block;margin-top:14px;padding:9px 18px;border:1px solid var(--gold);
  border-radius:2px;color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;
  transition:background-color 160ms var(--ease),transform 160ms var(--ease)}
.btn:hover{background:color-mix(in oklch,var(--gold) 14%,transparent);transform:translateY(-1px)}
.btn:active{transform:scale(.98)}
.btn:focus-visible{outline:2px solid var(--focus);outline-offset:4px}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media screen and (prefers-reduced-motion:no-preference){
  .rise{animation:rise 340ms var(--ease) both;animation-delay:calc(var(--i,0)*60ms)}}
"""


def render_notice_page(
    title: str,
    message: str,
    *,
    code: str = "",
    hint: str = "",
    href: Optional[str] = None,
    href_label: str = "",
) -> str:
    """صفحة إشعار رسمية (RTL) بدل نص خام. كل المدخلات تُهرَّب قبل الإدراج."""
    e = _html.escape
    parts = []
    if code:
        parts.append(f'<div class="code rise" style="--i:0">{e(code)}</div>')
    parts.append(f'<h1 class="rise" style="--i:1">{e(title)}</h1>')
    parts.append(f'<p class="rise" style="--i:2">{e(message)}</p>')
    if hint:
        parts.append(f'<p class="hint rise" style="--i:3">{e(hint)}</p>')
    if href and href_label:
        parts.append(f'<a class="btn rise" style="--i:4" href="{e(href, quote=True)}">{e(href_label)}</a>')
    return (
        '<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{e(title)}</title><style>{_CSS}</style></head>"
        f'<body><main class="card">{"".join(parts)}</main></body></html>'
    )