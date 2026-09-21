"""Render step-by-step screenshots of the 5 sample records from a live run.

Every value shown comes from output/records.json (the records the live n8n
workflow returned). Nothing is typed in by hand. Each page is rendered with
headless Microsoft Edge and saved as a PNG under docs/screenshots/.

This does NOT replace screenshots of the n8n UI itself (canvas, executions):
those need a logged-in browser session; see docs/SCREENSHOTS.md.

    python scripts/render_screenshots.py
"""
import html
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

from common import ROOT, load_json

sys.stdout.reconfigure(encoding="utf-8")
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
OUT = ROOT / "docs" / "screenshots"
WIDTH = 1400
QUEUE_COLORS = {
    "engineering": "#2563eb", "incident_response": "#dc2626", "billing": "#059669",
    "product": "#7c3aed", "technical_support": "#0891b2", "human_review_escalation": "#b45309",
    "unassigned": "#6b7280",
}
LEVEL_COLORS = {"High": "#dc2626", "Medium": "#d97706", "Low": "#059669"}
e = html.escape

CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: 28px 32px 36px; background: #f4f5f7; color: #1f2328;
       font: 15px/1.45 "Segoe UI", system-ui, sans-serif; width: %dpx; }
h1 { font-size: 22px; margin: 0 0 4px; }
.sub { color: #57606a; font-size: 13px; margin-bottom: 18px; }
.sub code { font-size: 12px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card { background: #fff; border: 1px solid #d0d7de; border-radius: 10px; padding: 16px 18px; }
.card.wide { grid-column: 1 / -1; }
.step { font-size: 11px; font-weight: 700; letter-spacing: .08em; color: #57606a; text-transform: uppercase; }
.title { font-size: 17px; font-weight: 600; margin: 2px 0 10px; }
.node { font-size: 12px; color: #57606a; font-weight: 400; }
.msg { background: #f6f8fa; border-left: 4px solid #8c959f; padding: 10px 12px; border-radius: 4px; font-style: italic; }
table.kv { border-collapse: collapse; width: 100%%; }
table.kv td { padding: 5px 0; vertical-align: top; border-bottom: 1px solid #eaeef2; }
table.kv td:first-child { color: #57606a; width: 34%%; padding-right: 10px; font-size: 13px; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px; color: #fff; font-size: 12.5px; font-weight: 600; }
.chip { display: inline-block; background: #eef2f6; border: 1px solid #d0d7de; border-radius: 6px;
        padding: 1px 7px; margin: 1px 4px 1px 0; font: 12.5px Consolas, monospace; }
.none { color: #8c959f; font-size: 13px; }
.bar { height: 8px; background: #eaeef2; border-radius: 4px; overflow: hidden; margin-top: 4px; width: 220px; }
.bar > div { height: 100%%; }
.arrow { font-size: 18px; color: #57606a; margin: 0 8px; }
.rule { background: #fff8c5; border: 1px solid #d4a72c; border-radius: 6px; padding: 6px 9px; margin: 4px 0; font-size: 13.5px; }
.rule b { font-family: Consolas, monospace; }
.adv { background: #ddf4ff; border-color: #54aeff; }
.summary { font-size: 15.5px; background: #f6f8fa; padding: 10px 12px; border-radius: 6px; }
.quote { font-family: Consolas, monospace; font-size: 12.5px; }
pre { margin: 0; font: 12.5px/1.45 Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.k { color: #0550ae; } .s { color: #0a3069; } .n { color: #953800; } .b { color: #8250df; }
table.over { border-collapse: collapse; width: 100%%; background: #fff; font-size: 13.5px; }
table.over th, table.over td { border: 1px solid #d0d7de; padding: 7px 9px; text-align: left; vertical-align: top; }
table.over th { background: #f6f8fa; font-size: 12.5px; }
""" % WIDTH


def badge(text, color):
    return f'<span class="badge" style="background:{color}">{e(str(text))}</span>'


def queue(q):
    return badge(q, QUEUE_COLORS.get(q, "#6b7280"))


def chips(values):
    return "".join(f'<span class="chip">{e(v)}</span>' for v in values) or '<span class="none">none found</span>'


def page(title, body):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"


def header(i, rec, what):
    return (f"<h1>Sample #{i} &mdash; {e(what)}</h1><div class='sub'>Live n8n run &middot; "
            f"record_id <code>{e(rec['record_id'])}</code> &middot; received {e(rec['received_at'])} &middot; "
            f"model <code>{e(rec['processing']['model'])}</code> &middot; rendered from <code>output/records.json</code></div>")


def steps_page(i, rec):
    c, en, r, esc, p = rec["classification"], rec["enrichment"], rec["routing"], rec["escalation"], rec["processing"]
    conf = c["confidence"] or 0
    conf_color = "#059669" if conf >= 0.7 else "#dc2626"
    prio = badge(c["priority"], LEVEL_COLORS[c["priority"]])
    if c["priority_adjusted_by"]:
        prio += f' <span class="node">(LLM said {e(c["llm_priority"])}, raised by {e(c["priority_adjusted_by"])})</span>'
    ids = "".join(f"<tr><td>{e(k)}</td><td>{chips(v)}</td></tr>" for k, v in en["identifiers"].items())
    urg = en["urgency_signal"]
    rules = "".join(f'<div class="rule"><b>{e(x["rule"])}</b> &mdash; {e(x["detail"])}</div>' for x in esc["triggered_rules"]) \
        or '<span class="none">no escalation rule fired</span>'
    adv = "".join(f'<div class="rule adv"><b>{e(x["rule"])}</b> (advisory) &mdash; {e(x["detail"])}</div>' for x in esc["advisory_signals"])
    flag = badge("ESCALATED - human review", "#b45309") if esc["flagged"] else badge("not escalated", "#059669")
    body = header(i, rec, "workflow steps") + f"""
<div class="grid">
 <div class="card wide"><div class="step">Step 1 &middot; Ingestion</div>
  <div class="title">Webhook &rarr; Normalize <span class="node">(n8n nodes: Webhook, Normalize)</span></div>
  <table class="kv"><tr><td>source</td><td>{badge(rec['source'], '#57606a')}</td></tr>
  <tr><td>raw_message</td><td><div class="msg">{e(rec['raw_message'])}</div></td></tr></table></div>

 <div class="card"><div class="step">Step 2 &middot; Classification (LLM)</div>
  <div class="title">Category, priority, confidence <span class="node">(Classify (LLM) &rarr; Parse Classification)</span></div>
  <table class="kv"><tr><td>category</td><td><b>{e(str(c['category']))}</b></td></tr>
  <tr><td>secondary_categories</td><td>{chips(c['secondary_categories'])}</td></tr>
  <tr><td>priority</td><td>{prio}</td></tr>
  <tr><td>confidence</td><td><b>{conf}</b> <span class="node">(threshold 0.70)</span><div class="bar"><div style="width:{conf * 100:.0f}%;background:{conf_color}"></div></div></td></tr>
  <tr><td>rationale</td><td>{e(c['rationale'])}</td></tr></table></div>

 <div class="card"><div class="step">Step 3 &middot; Enrichment (LLM)</div>
  <div class="title">Core issue, identifiers, urgency <span class="node">(Enrich (LLM) &rarr; Parse Enrichment)</span></div>
  <table class="kv"><tr><td>core_issue</td><td>{e(en['core_issue'])}</td></tr>{ids}
  <tr><td>urgency_signal</td><td>{badge(urg['level'], LEVEL_COLORS[urg['level']])} {''.join(f'<div class="quote">&ldquo;{e(q)}&rdquo;</div>' for q in urg['evidence'])}</td></tr>
  <tr><td>dropped (not in text)</td><td>{chips(en.get('dropped_identifiers', []))}</td></tr></table></div>

 <div class="card"><div class="step">Step 4 &middot; Routing (code)</div>
  <div class="title">Queue decision <span class="node">(Route &amp; Escalate)</span></div>
  <table class="kv"><tr><td>standard_queue</td><td>{queue(r['standard_queue'])}</td></tr>
  <tr><td>destination_queue</td><td>{queue(r['destination_queue'])}</td></tr>
  <tr><td>routing_reason</td><td>{e(r['routing_reason'])}</td></tr></table></div>

 <div class="card"><div class="step">Step 6 &middot; Human escalation flag (code)</div>
  <div class="title">{flag}</div>{rules}{adv}</div>

 <div class="card wide"><div class="step">Step 5 &middot; Structured output</div>
  <div class="title">Summary for the receiving team <span class="node">(Summarize (LLM) &rarr; Assemble Record &rarr; Publish to Queue &rarr; Respond)</span></div>
  <div class="summary">{e(rec['summary'])}</div>
  <table class="kv" style="margin-top:10px"><tr><td>published to</td><td><code>WEBHOOK_SITE_URL/{e(r['destination_queue'])}</code></td></tr>
  <tr><td>workflow latency</td><td>{p['latency_ms']} ms (3 LLM calls)</td></tr>
  <tr><td>prompt versions</td><td>{chips(f'{k}: {v}' for k, v in p['prompt_versions'].items())}</td></tr>
  <tr><td>llm_errors</td><td>{chips(p['llm_errors'])}</td></tr></table></div>
</div>"""
    return page(f"Sample {i} steps", body)


def json_html(obj):
    """Pretty JSON with light syntax colouring."""
    s = e(json.dumps(obj, indent=2, ensure_ascii=False))
    import re
    s = re.sub(r'^(\s*)(&quot;[^&]*?&quot;)(:)', r'\1<span class="k">\2</span>\3', s, flags=re.M)
    s = re.sub(r'(: )(&quot;.*?&quot;)(,?)$', r'\1<span class="s">\2</span>\3', s, flags=re.M)
    s = re.sub(r'(: )(-?\d+(?:\.\d+)?)(,?)$', r'\1<span class="n">\2</span>\3', s, flags=re.M)
    s = re.sub(r'(: )(true|false|null)(,?)$', r'\1<span class="b">\2</span>\3', s, flags=re.M)
    return s


def json_page(i, rec):
    body = header(i, rec, "final JSON record") + f'<div class="card"><pre>{json_html(rec)}</pre></div>'
    return page(f"Sample {i} JSON", body)


def overview_page(records):
    rows = []
    for i, rec in enumerate(records, 1):
        c, r, esc, en = rec["classification"], rec["routing"], rec["escalation"], rec["enrichment"]
        ids = [v for vals in en["identifiers"].values() for v in vals]
        rules = "<br>".join(e(x["rule"]) for x in esc["triggered_rules"]) or "&ndash;"
        rows.append(
            f"<tr><td><b>#{i}</b><br><span class='node'>{e(rec['source'])}</span></td>"
            f"<td>{e(str(c['category']))}</td><td>{badge(c['priority'], LEVEL_COLORS[c['priority']])}</td>"
            f"<td>{c['confidence']}</td><td>{chips(dict.fromkeys(ids))}</td>"
            f"<td>{queue(r['standard_queue'])}<br><span class='arrow'>&darr;</span><br>{queue(r['destination_queue'])}</td>"
            f"<td>{'<b>yes</b><br>' + rules if esc['flagged'] else 'no'}</td><td>{e(rec['summary'])}</td></tr>")
    body = ("<h1>ArcVault triage &mdash; structured output for the 5 sample requests</h1>"
            "<div class='sub'>Live n8n run &middot; rendered from <code>output/records.json</code> &middot; "
            f"model <code>{e(records[0]['processing']['model'])}</code></div>"
            "<table class='over'><tr><th>#</th><th>Category</th><th>Priority</th><th>Conf.</th><th>Identifiers</th>"
            "<th>Standard &rarr; destination queue</th><th>Escalated (rules)</th><th>Summary</th></tr>"
            + "".join(rows) + "</table>")
    return page("Overview", body)


def shoot(html_text, name):
    html_dir = OUT / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    src = html_dir / f"{name}.html"
    src.write_text(html_text, encoding="utf-8")
    png = OUT / f"{name}.png"
    subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={WIDTH + 64},4000", f"--screenshot={png}", src.as_uri()],
                   check=True, capture_output=True, timeout=60)
    # Crop the empty background right of and below the content (symmetric margins).
    img = Image.open(png).convert("RGB")
    bg = Image.new("RGB", img.size, img.getpixel((img.width - 1, img.height - 1)))
    box = ImageChops.difference(img, bg).getbbox()
    if box:
        img = img.crop((0, 0, min(img.width, box[2] + box[0]), min(img.height, box[3] + 36)))
    img.save(png)
    print(f"wrote {png.relative_to(ROOT)}  ({img.width}x{img.height})")


def main():
    if not EDGE.exists():
        sys.exit(f"Edge not found at {EDGE}")
    records = load_json("output/records.json")
    shoot(overview_page(records), "00-overview-all-samples")
    for i, rec in enumerate(records, 1):
        shoot(steps_page(i, rec), f"sample{i}-steps")
        shoot(json_page(i, rec), f"sample{i}-record-json")


if __name__ == "__main__":
    main()
