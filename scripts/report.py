"""Portable chart and strictly one-page report; machine-readable detail remains in JSON."""
from __future__ import annotations
import csv
import os
from pathlib import Path
from xml.sax.saxutils import escape
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1]/'.cache'/'matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from data import write_json, DataError

COLORS = ['#2563eb','#0f766e','#db6b20','#9333ea','#dc2626','#64748b']

def pct(value):
    return 'N/A' if value is None else f'{value:+.1f}%'

def render(analysis, out):
    out = Path(out)
    write_json(out / 'analysis.json', analysis)
    with (out / 'monthly.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['series','month','views','project_views','views_per_million'])
        w.writeheader()
        for s in analysis['series']:
            w.writerows({'series':s['id'], **m} for m in s['monthly'])
    fig, axes = plt.subplots(1, 2, figsize=(10.3, 3.0), layout='constrained')
    for i,s in enumerate(analysis['series']):
        for ax, key in zip(axes, ('views','views_per_million')):
            vals = [m[key] if m[key] is not None else float('nan') for m in s['monthly']]
            ax.plot(range(len(vals)), vals, label=s['id'], color=COLORS[i], lw=1.7)
            keys = [m['month'] for m in s['monthly']]
            ticks = list(range(0,len(vals),max(1,len(vals)//5)))
            ax.set_xticks(ticks,[keys[t] for t in ticks], rotation=25, fontsize=8)
            ax.grid(alpha=.15)
            ax.spines[['top','right']].set_visible(False)
            ax.tick_params(axis='y', labelsize=8)
    axes[0].set_title('Monthly article views', loc='left', fontsize=11)
    axes[1].set_title('Views per million edition views', loc='left', fontsize=11)
    axes[0].legend(fontsize=7, frameon=False)
    fig.savefig(out / 'trend.png', dpi=170)
    plt.close(fig)
    make_pdf(analysis, out)
    lines = [f'# {analysis["question"]}',f'{analysis["start"]} to {analysis["end"]}; all-access / user / UTC.',
             f'Minimum raw growth criterion: {analysis["criteria"]["min_growth_pct"]:g}%.', '',
             '| Series | Latest 12m views | YoY | Share YoY | Peak excluded | Signal |',
             '|---|---:|---:|---:|---:|---|']
    for s in analysis['series']:
        lines.append(f'| {s["id"]} | {s["latest_views"]} | {pct(s["growth_pct"])} | {pct(s["share_growth_pct"])} | {pct(s["peak_excluded_growth_pct"])} | {s["signal"]} |')
        lines.extend([])
    lines += ['', 'Research order: ' + (', '.join(analysis['research_order']) or 'No automatic shortlist.'),
              'Validate the decision with independent evidence appropriate to the user question.', '', *['- '+x for x in analysis['caveats']]]
    for s in analysis['series']:
        lines += ['',f'**{s["id"]}: {s["label"]}** — coverage {s["coverage"]:.1%}; positive YoY months {s["positive_yoy_months"]}/12; warnings: '+(', '.join(s['warnings']) or 'none detected')]
        lines += [f'- [{a["title"]}]({a["url"]}) · {a["qid"]}' for a in s['articles']]
    lines += ['', 'Exact API URLs, retrieval timestamps and response hashes: provenance.json. Full inputs: snapshot.json.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')

def make_pdf(a, out):
    font = os.environ.get('WIKIPEDIA_REPORT_FONT') or font_manager.findfont('DejaVu Sans')
    face = TTFont('DejaVu', font)
    required = a['question'] + ''.join(x['title'] for s in a['series'] for x in s['articles'])
    missing = {ord(ch) for ch in required if not ch.isspace()} - set(face.face.charToGlyph)
    if missing:
        raise DataError('PDF font lacks characters; set WIKIPEDIA_REPORT_FONT to a suitable Unicode TTF font or use a supported report language')
    pdfmetrics.registerFont(face)
    canvas = Canvas(str(out/'report.pdf'), pagesize=A4)
    canvas.setTitle(a['question'])
    width,height = A4
    left, usable, y = 36, width-72, height-34
    def para(text, size=9, color='#334155', gap=7):
        nonlocal y
        p = Paragraph(text, ParagraphStyle('p',fontName='DejaVu',fontSize=size,leading=size*1.35,textColor=colors.HexColor(color)))
        _,h = p.wrap(usable, height)
        if y-h < 30:
            raise ValueError('PDF exceeds one page; shorten the research question or use fewer series')
        p.drawOn(canvas,left,y-h); y -= h+gap
    para('WIKIPEDIA / TOPIC RESEARCH',9,'#2563eb',8)
    para(escape(a['question']),16,'#0f172a',7)
    para(f'{a["start"]} — {a["end"]} · UTC · all-access / user',8)
    para('Compare the latest 12 complete months with the preceding 12. Growth is a research signal, not a launch decision.',9)
    y -= 153
    canvas.drawImage(str(out/'trend.png'),left,y,width=usable,height=153)
    y -= 10
    cell_style = ParagraphStyle('cell',fontName='DejaVu',fontSize=7.5,leading=10)
    rows = [['Series','Views / 12m','YoY','Share YoY','Peak excl.','Signal']]
    for s in a['series']:
        count = f'{s["latest_views"]:,}' if s['latest_views'] is not None else 'N/A'
        rows.append([s['id'],count,pct(s['growth_pct']),pct(s['share_growth_pct']),
                     pct(s['peak_excluded_growth_pct']),s['signal'].replace('_',' ')])
    table = Table([[Paragraph(escape(str(x)),cell_style) for x in row] for row in rows],
                  colWidths=[55,72,52,70,70,usable-319])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eff6ff')),
                               ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),
                               ('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.3,colors.HexColor('#e2e8f0'))]))
    _,th=table.wrap(usable,height)
    if y-th<30: raise ValueError('PDF table exceeds page')
    table.drawOn(canvas,left,y-th); y-=th+9
    for s in a['series']:
        para(f'{escape(s["id"])}: coverage {s["coverage"]:.0%}; positive YoY months {s["positive_yoy_months"]}/12'
             + (f'; {escape(", ".join(s["warnings"]))}' if s['warnings'] else ''),7,gap=4)
    order = ', '.join(a['research_order'])
    para('RESEARCH DECISION: '+escape(order or 'No automatic shortlist'),10,'#0f766e',5)
    para(f'Applied minimum raw growth criterion: {a["criteria"]["min_growth_pct"]:g}%.',7,gap=3)
    if order:
        decision='Investigate the shortlisted topics with independent evidence suited to the question. Order uses share growth, then volume.'
    elif any(s['signal']=='insufficient_data' for s in a['series']):
        decision='Resolve missing observations or the undefined baseline before drawing a growth conclusion.'
    elif any(s['signal']=='fragile' for s in a['series']):
        decision='Inspect peak dates and article history, then test broader concept coverage before prioritizing.'
    else:
        decision='The chosen proxies do not meet the growth criteria. Revisit topic coverage and decision-specific evidence before concluding.'
    if not a['comparable_baskets']: decision+=' Different baskets: cross-series ranking withheld.'
    para(decision,8)
    para('LIMITS: Attention ≠ people, intent or real-world prevalence; language ≠ country. Current titles omit redirect traffic and may miss historical moves. '
         'Seasonality, news and imperfect bot filtering remain. Heuristic signals are not confidence intervals.',8)
    for s in a['series']:
        links = '; '.join(f'<link href="{escape(x["url"], {chr(34): "&quot;"})}" color="#2563eb">{escape(x["title"])} ({x["qid"]})</link>' for x in s['articles'])
        para(f'{escape(s["id"])}: {links}',7,gap=3)
    retrieved = ' — '.join(t[:10] for t in a.get('source_retrieval_window', [])) or 'See provenance'
    para('SOURCE: <link href="https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html" color="#2563eb">Wikimedia Analytics API</link>. Retrieved: '+retrieved+'. Exact URLs and hashes: provenance.json. '
         'Share the report folder for the full audit trail. Peak excl. removes the highest latest-year month and its prior-year match.',7,gap=0)
    canvas.showPage(); canvas.save()
