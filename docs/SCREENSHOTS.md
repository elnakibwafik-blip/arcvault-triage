# Screenshot checklist

The brief accepts "exported JSON + screenshots of each step with output". Take them from one execution of **sample #3** (it exercises escalation) and one of **sample #5**, via n8n **Executions -> open run**. Save them to `docs/screenshots/` with the names below.

| # | File | What to capture |
|---|---|---|
| 1 | `01-canvas.png` | Whole workflow canvas, zoomed to fit, node notes visible |
| 2 | `02-webhook.png` | Webhook node output: `body.source`, `body.message` |
| 3 | `03-normalize.png` | Normalize output: `record_id`, `received_at`, `source`, `has_text` |
| 4 | `04-classify-parse.png` | Parse Classification output: `classification` object (category, priority, confidence, rationale) |
| 5 | `05-enrich-parse.png` | Parse Enrichment output: `enrichment.identifiers` with `#8821`, `$1,240`, `$980/month` |
| 6 | `06-route.png` | Route & Escalate output: `decision.routing` and `decision.escalation.triggered_rules` |
| 7 | `07-route-config.png` | Route & Escalate code view, showing the CONFIG block |
| 8 | `08-summary.png` | Summarize (LLM) output: `choices[0].message.content` |
| 9 | `09-record.png` | Assemble Record output: the full final record |
| 10 | `10-webhook-site.png` | Webhook.site list showing requests under `/human_review_escalation`, `/engineering`, `/product`, `/technical_support` |
| 11 | `11-executions.png` | Executions list showing the 5 successful runs |
| 12 | `12-sample5-route.png` | Sample #5 Route & Escalate output with two triggered rules |

Tip: in n8n's output panel, switch to **JSON** view for 4–9. It fits more on screen than the table view.
