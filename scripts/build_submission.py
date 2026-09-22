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

from common import ROOT

sys.stdout.reconfigure(encoding="utf-8")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = ROOT / "submission"
# Temporary HTML lives outside the repo: OneDrive locks freshly created folders, so deleting them fails.
BUILD = Path(tempfile.gettempdir()) / "arcvault_submission_build"
MERMAID = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"

CSS = """
@page { size: A4; margin: 12mm 14mm; }
body { font: 10pt/1.38 "Segoe UI", system-ui, sans-serif; color: #1f2328; }
h1 { font-size: 17pt; margin: 0 0 6pt; } h2 { font-size: 12.5pt; margin: 12pt 0 4pt; border-bottom: 1px solid #d0d7de; padding-bottom: 2pt; }
h3 { font-size: 11pt; margin: 10pt 0 3pt; } p, ul, ol { margin: 4pt 0; } li { margin: 1.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0; font-size: 9pt; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #d0d7de; padding: 3pt 5pt; text-align: left; vertical-align: top; } th { background: #f6f8fa; }
code { font: 8.6pt Consolas, monospace; background: #f3f4f6; padding: 0 2pt; border-radius: 2pt; }
pre { background: #f6f8fa; border: 1px solid #d0d7de; padding: 6pt; white-space: pre-wrap; font: 8pt/1.35 Consolas, monospace; }
pre code { background: none; padding: 0; font-size: 8pt; }
pre.mermaid { background: none; border: none; text-align: center; }
a { color: #0969da; text-decoration: none; }
img { max-width: 100%; border: 1px solid #d0d7de; }
.shot { page-break-inside: avoid; margin: 0 0 10pt; } .shot h3 { margin-top: 0; }
.note { color: #57606a; font-size: 9pt; }
"""


def md_to_html(md_text, title):
    # Mermaid fences become <pre class="mermaid"> so mermaid.js renders them.
    md_text = re.sub(r"```mermaid\n(.*?)```",
                     lambda m: '<pre class="mermaid">' + html.escape(m.group(1)) + "</pre>", md_text, flags=re.S)
    md_text = re.sub(r"^<!-- GENERATED.*?-->\n", "", md_text)
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
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


def screenshots_html():
    shots = ROOT / "docs" / "screenshots"
    uri = lambda f: (shots / f).as_uri()
    parts = ["<h1>ArcVault Intake &amp; Triage: workflow screenshots</h1>",
             "<p class='note'>Section A was captured in n8n Cloud from the live, published workflow. Section B shows the output of "
             "every workflow step for each of the five sample requests, rendered by <code>scripts/render_screenshots.py</code> "
             "directly from <code>records.json</code> (the records the live workflow returned). Sample #5 is the same record "
             "(<code>1cd7d42b…</code>) in both sections.</p>",
             "<h2>A. n8n Cloud</h2>"]
    for f, cap in [("workflow.png", "Published workflow canvas (12 nodes)"),
                   ("n8n-02-executions.png", "Executions: successful production runs"),
                   ("n8n-03-sample3-route.png", "Sample #3: Route & Escalate output (escalated by billing_amount_over_threshold)"),
                   ("n8n-04a-sample5-record.png", "Sample #5: Assemble Record output (part 1)"),
                   ("n8n-04b-sample5-record.png", "Sample #5: Assemble Record output (part 2)")]:
        parts.append(f"<div class='shot'><h3>{html.escape(cap)}</h3><img src='{uri(f)}'></div>")
    parts.append("<h2 style='page-break-before:always'>B. Step-by-step output for the 5 sample requests</h2>")
    parts.append(f"<div class='shot'><h3>Overview: all five records</h3><img src='{uri('00-overview-all-samples.png')}'></div>")
    for i in range(1, 6):
        parts.append(f"<div class='shot' style='page-break-before:always'><h3>Sample #{i}: each workflow step</h3>"
                     f"<img src='{uri(f'sample{i}-steps.png')}'></div>")
    return page("Workflow screenshots", "".join(parts))


def main():
    OUT.mkdir(exist_ok=True)
    arch_pages = to_pdf(md_to_html((ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8"), "Architecture"),
                        "ArcVault_Architecture")
    to_pdf(md_to_html((ROOT / "docs" / "PROMPTS.md").read_text(encoding="utf-8"), "Prompts"), "ArcVault_Prompts")
    to_pdf(screenshots_html(), "ArcVault_Workflow_Screenshots")
    for src, name in [("output/eval_report.md", "ArcVault_Eval_Report"),
                      ("docs/AI_ASSISTANCE_LOG.md", "ArcVault_AI_Assistance_Log")]:
        to_pdf(md_to_html((ROOT / src).read_text(encoding="utf-8"), name), name)

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
