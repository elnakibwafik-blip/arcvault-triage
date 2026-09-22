"""Package the assessment deliverables into submission/ (PDFs, JSON files and a zip).

Renders the Markdown docs to PDF with headless Microsoft Edge, so reviewers
without repo access can read them as email attachments. The source of truth is
still the Markdown/JSON in the repo; this only formats it.

    python scripts/build_submission.py
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import markdown
from pypdf import PdfReader

from common import ROOT, load_json

sys.stdout.reconfigure(encoding="utf-8")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = ROOT / "submission"
# Temporary HTML lives outside the repo: OneDrive locks freshly created folders, so deleting them fails.
BUILD = Path(tempfile.gettempdir()) / "arcvault_submission_build"
MERMAID = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"

CSS = """
@page { size: A4; margin: 13mm 14mm; }
body { font: 10pt/1.36 "Segoe UI", system-ui, sans-serif; color: #1f2328; }
h1 { font-size: 17pt; margin: 0 0 2pt; letter-spacing: -0.2pt; }
h2 { font-size: 12pt; margin: 10pt 0 4pt; color: #0b3b5e; border-bottom: 1.5px solid #0b3b5e; padding-bottom: 2pt; }
h3 { font-size: 10.5pt; margin: 9pt 0 3pt; } p, ul, ol { margin: 3.5pt 0; } li { margin: 1.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0; font-size: 9pt; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #d0d7de; padding: 3.5pt 5pt; text-align: left; vertical-align: top; }
th { background: #eef3f8; color: #0b3b5e; }
code { font: 8.6pt Consolas, monospace; background: #f3f4f6; padding: 0 2pt; border-radius: 2pt; }
pre { background: #f6f8fa; border: 1px solid #d0d7de; padding: 6pt; white-space: pre-wrap; font: 8pt/1.35 Consolas, monospace; }
pre code { background: none; padding: 0; font-size: 8pt; }
pre.mermaid { background: none; border: none; text-align: center; }
a { color: #0969da; text-decoration: none; }
img { max-width: 100%; border: 1px solid #c8d1da; border-radius: 3px; }
.note { color: #57606a; font-size: 9pt; }

/* Title block */
.titleblock { border-top: 4px solid #0b3b5e; padding-top: 6pt; margin-bottom: 8pt; }
.titleblock .sub { font-size: 10.5pt; color: #3d4a57; margin: 1pt 0 4pt; }
.meta { font-size: 8.5pt; color: #57606a; border-top: 1px solid #d0d7de; padding-top: 3pt; }
.meta span { margin-right: 14pt; }

/* Figures */
.figure { page-break-inside: avoid; margin: 9pt 0 13pt; }
.figure .cap { font-size: 9.5pt; font-weight: 600; color: #0b3b5e; margin-bottom: 2pt; }
.figure .exp { font-size: 9.2pt; color: #3d4a57; margin: 0 0 5pt; }
.figure .exp b { color: #1f2328; }
.lead { font-size: 9.6pt; color: #3d4a57; margin: 0 0 8pt; }
.box { background: #f6f8fa; border-left: 3px solid #0b3b5e; padding: 6pt 9pt; margin: 7pt 0; font-size: 9.2pt; }
.box ul { margin: 3pt 0 0 0; padding-left: 14pt; }
.tag { display: inline-block; background: #0b3b5e; color: #fff; border-radius: 3px; padding: 0 5pt;
       font: 8pt Consolas, monospace; margin-right: 3pt; }
.tag.warn { background: #9a6700; }
"""


def md_to_html(md_text, title, subtitle="", deliverable=""):
    # Mermaid fences become <pre class="mermaid"> so mermaid.js renders them.
    md_text = re.sub(r"```mermaid\n(.*?)```",
                     lambda m: '<pre class="mermaid">' + html.escape(m.group(1)) + "</pre>", md_text, flags=re.S)
    md_text = re.sub(r"^<!-- GENERATED.*?-->\n", "", md_text)
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    # Wrap the document's own <h1> in a title block with the same meta line as the other PDFs.
    meta = f"<span>Valsoft AI Engineer assessment{', ' + deliverable if deliverable else ''}</span><span>ArcVault Intake &amp; Triage</span>"
    body = re.sub(r"<h1>(.*?)</h1>",
                  lambda m: (f"<div class='titleblock'><h1>{m.group(1)}</h1>"
                             + (f"<div class='sub'>{subtitle}</div>" if subtitle else "")
                             + f"<div class='meta'>{meta}</div></div>"),
                  body, count=1)
    return page(title, body, "mermaid" in md_text)


def page(title, body, mermaid=False):
    script = (f'<script src="{MERMAID}"></script><script>mermaid.initialize({{startOnLoad:true, theme:"neutral",'
              ' flowchart:{useMaxWidth:true}}});</script>') if mermaid else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{CSS}</style></head><body>{body}{script}</body></html>")


def to_pdf(html_text, name):
    BUILD.mkdir(parents=True, exist_ok=True)
    src = BUILD / f"{name}.html"
    src.write_text(html_text, encoding="utf-8")
    pdf = OUT / f"{name}.pdf"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=15000", "--run-all-compositor-stages-before-draw",
                    f"--print-to-pdf={pdf}", src.as_uri()], check=True, capture_output=True, timeout=120)
    pages = len(PdfReader(pdf).pages)
    print(f"wrote {pdf.relative_to(ROOT)}  ({pages} page{'s' * (pages != 1)})")
    return pages


# What makes each sample worth looking at. The measured outcome underneath is
# generated from records.json, so the text can't drift from the screenshots.
SAMPLE_NOTES = {
    1: "A login failure for one named account. It tests the Bug Report vs Incident/Outage boundary (one user, not the service) "
       "and the <code>security_signal</code> rule: a 403 raises priority but does not escalate on its own, because escalating "
       "every login problem would flood the human queue. The advisory signal is still recorded.",
    2: "A plain feature request, and the easiest case. It is here to show the normal path: no rule fires, so the record goes "
       "straight to the owning queue with no human in the loop.",
    3: "An invoice dispute, and the main escalation case. The dollar amounts are parsed from the raw text by code, not taken "
       "from the LLM, so a hallucinated number cannot trigger or suppress the escalation.",
    4: "A pre-sales question about SSO. It tests the Technical Question vs Feature Request boundary (\"is there a way\" rather "
       "than \"please build\"), and confirms that merely mentioning SSO is not treated as a security signal.",
    5: "An outage report. Two independent rules fire: one from the category, one from phrase matching on the raw text. The "
       "second is a safety net that still escalates an outage even if the model had labelled it a Bug Report.",
}


def sample_outcome(rec):
    """One sentence of measured outcome, taken from the record itself."""
    c, r, esc = rec["classification"], rec["routing"], rec["escalation"]
    if esc["flagged"]:
        rules = ", ".join(f"<code>{html.escape(x['rule'])}</code>" for x in esc["triggered_rules"])
        where = (f"escalated to <code>{r['destination_queue']}</code> by {rules}; "
                 f"the standard owner, <code>{r['standard_queue']}</code>, is kept in the record")
    else:
        where = f"routed to <code>{r['destination_queue']}</code> with no rule fired"
    adv = ""
    if esc["advisory_signals"]:
        adv = (" Advisory: " + ", ".join(f"<code>{html.escape(x['rule'])}</code>" for x in esc["advisory_signals"])
               + " (recorded, not an escalation).")
    return (f"<b>Result:</b> {html.escape(str(c['category']))}, priority {c['priority']}, confidence {c['confidence']}; "
            f"{where}.{adv}")


def figure(shots, filename, caption, explanation):
    return (f"<div class='figure'><div class='cap'>{caption}</div>"
            f"<p class='exp'>{explanation}</p><img src='{(shots / filename).as_uri()}'></div>")


def screenshots_html():
    shots = ROOT / "docs" / "screenshots"
    records = load_json("output/records.json")
    model = records[0]["processing"]["model"]
    version = records[0]["processing"]["workflow_version"]
    escalated = sum(1 for r in records if r["escalation"]["flagged"])

    parts = [
        "<div class='titleblock'><h1>ArcVault Intake &amp; Triage</h1>"
        "<div class='sub'>Working workflow: exported n8n workflow and screenshots of each step with output</div>"
        f"<div class='meta'><span>Valsoft AI Engineer assessment, deliverable 4.1</span>"
        f"<span>n8n Cloud + Groq <code>{html.escape(model)}</code></span>"
        f"<span>workflow version {html.escape(version)}</span></div></div>",

        "<p class='lead'>This document shows the workflow running and what each step produced for the five sample requests in "
        "the brief. <b>Section A</b> was captured in n8n Cloud from the live, published workflow. <b>Section B</b> lays out the "
        "output of every step for each sample; those pages are rendered directly from <code>records.json</code>, the records the "
        "live workflow returned, so no value in them was typed by hand. Sample #5 appears in both sections as the same record "
        "(<code>1cd7d42b…</code>), which ties the two together.</p>",

        "<div class='box'><b>The pipeline, in order.</b> Webhook &rarr; Normalize &rarr; "
        "<span class='tag'>LLM</span>Classify &rarr; validate &rarr; <span class='tag'>LLM</span>Enrich &rarr; validate &rarr; "
        "Route &amp; Escalate &rarr; <span class='tag'>LLM</span>Summarize &rarr; Assemble record &rarr; POST to queue &rarr; "
        "respond. The three LLM calls classify, extract and summarise. The routing and escalation decisions are made by "
        "deterministic code, so they are repeatable and can be explained without reference to a model."
        f"<ul><li>Of the five samples, <b>{escalated} escalated</b> to the human review queue and "
        f"{len(records) - escalated} went straight to their owning team.</li>"
        "<li>Every escalated record keeps the queue it <i>would</i> have gone to, so the reviewer knows who to hand it to.</li>"
        "</ul></div>",

        "<h2>A. The workflow running in n8n Cloud</h2>",
        "<p class='lead'>These five screenshots are the evidence that the exported JSON is what actually ran.</p>",
    ]

    parts.append(figure(shots, "workflow.png", "Figure 1. The published workflow (12 nodes)",
        "The canvas, left to right, as listed above. The branch below the main line is the <b>Has Text?</b> check: an empty "
        "message skips both LLM calls and goes straight to routing, where it is escalated rather than dropped. The <b>Published</b> "
        "badge at the top right means the production webhook URL is live."))
    parts.append(figure(shots, "n8n-02-executions.png", "Figure 2. Execution history",
        "One row per inbound message, each about four seconds end to end, with every node green. Opening a run shows the input "
        "and output of every node, which is where the workflow's state lives for debugging."))
    parts.append(figure(shots, "n8n-03-sample3-route.png", "Figure 3. Sample #3: the escalation decision (Route &amp; Escalate node)",
        "The output of the deterministic routing step for the invoice dispute. <code>standard_queue</code> is <code>billing</code>, "
        "but <code>destination_queue</code> is <code>human_review_escalation</code> because "
        "<code>billing_amount_over_threshold</code> fired. The <code>detail</code> line records exactly why: the largest amount "
        "found in the text was $1,240 against a $500 threshold. No LLM is involved in this decision."))
    parts.append(figure(shots, "n8n-04a-sample5-record.png", "Figure 4. Sample #5: the final record, part 1 (Assemble Record node)",
        "The first half of the record for the outage report: the raw message, the classification with its confidence and "
        "rationale, and the extracted identifiers. Identifiers that do not appear literally in the message are dropped, and "
        "<code>dropped_identifiers</code> would list them."))
    parts.append(figure(shots, "n8n-04b-sample5-record.png", "Figure 5. Sample #5: the final record, part 2",
        "The second half: routing, the two escalation rules that fired with their reasons, the summary written for the receiving "
        "team, and the processing metadata (model, prompt versions, latency, workflow version). This is the complete payload "
        "POSTed to the queue and returned to the caller."))

    parts.append("<h2 style='page-break-before:always'>B. Step-by-step output for the five sample requests</h2>")
    parts.append("<p class='lead'>One page per sample. Each page shows the six workflow steps in the brief's order, labelled with "
                 "the n8n node that produced each one, so classification, enrichment, routing, escalation and the final summary "
                 "can be read together. The table below is the same five records side by side.</p>")
    parts.append(figure(shots, "00-overview-all-samples.png", "Figure 6. All five records at a glance",
        "Category, priority, confidence, extracted identifiers, the standard and destination queue, the escalation rules that "
        "fired, and the summary sent to the receiving team. Rows 3 and 5 are the two escalations; the arrow shows the queue the "
        "ticket would have gone to without one."))

    for i, rec in enumerate(records, 1):
        msg = html.escape(rec["raw_message"])
        parts.append(
            f"<div class='figure' style='page-break-before:always'>"
            f"<div class='cap'>Figure {i + 6}. Sample #{i} ({html.escape(rec['source'])}): every step</div>"
            f"<p class='exp'><i>&ldquo;{msg}&rdquo;</i></p>"
            f"<p class='exp'>{SAMPLE_NOTES[i]}</p>"
            f"<p class='exp'>{sample_outcome(rec)}</p>"
            f"<img src='{(shots / f'sample{i}-steps.png').as_uri()}'></div>")

    parts.append("<p class='note'>Reproduce any of this with <code>python scripts/send_samples.py</code> against the published "
                 "workflow; the screenshots in section B are regenerated from the resulting records by "
                 "<code>python scripts/render_screenshots.py</code>.</p>")
    return page("Workflow screenshots", "".join(parts))


def main():
    OUT.mkdir(exist_ok=True)
    docs = [
        ("docs/ARCHITECTURE.md", "ArcVault_Architecture", "Architecture",
         "System design, routing, escalation, production scale and Phase 2", "deliverable 4.4"),
        ("docs/PROMPTS.md", "ArcVault_Prompts", "Prompts",
         "Every LLM prompt verbatim, with the reasoning, tradeoffs and what I would change", "deliverable 4.3"),
        ("output/eval_report.md", "ArcVault_Eval_Report", "Evaluation report",
         "The five samples run three times, plus eight edge cases, against the live workflow", "supporting evidence"),
        ("docs/AI_ASSISTANCE_LOG.md", "ArcVault_AI_Assistance_Log", "AI assistance log",
         "What the AI got wrong while building this, and how each problem was fixed", "supporting evidence"),
    ]
    arch_pages = 0
    for src, name, title, subtitle, deliverable in docs:
        pages = to_pdf(md_to_html((ROOT / src).read_text(encoding="utf-8"), title, subtitle, deliverable), name)
        if name.endswith("Architecture"):
            arch_pages = pages
    to_pdf(screenshots_html(), "ArcVault_Workflow_Screenshots")

    for src, dst in [("n8n/workflow.arcvault.json", "ArcVault_n8n_workflow.json"),
                     ("output/records.json", "ArcVault_records.json")]:
        shutil.copyfile(ROOT / src, OUT / dst)
        print(f"copied {src} -> submission/{dst}")

    zip_path = OUT / "ArcVault_Submission.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.iterdir()):
            if f.is_file() and f.suffix in (".pdf", ".json") :
                z.write(f, f.name)
        z.write(ROOT / "SUBMISSION.md", "README.md")
    shutil.rmtree(BUILD, ignore_errors=True)
    print(f"wrote {zip_path.relative_to(ROOT)}")
    if arch_pages > 2:
        print(f"WARNING: architecture write-up is {arch_pages} pages; the brief asks for one to two")


if __name__ == "__main__":
    main()
