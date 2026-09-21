# Screenshots

## A. Step-by-step output for the 5 sample requests (generated)

These are rendered by `scripts/render_screenshots.py` from `output/records.json`, the records returned by the live n8n workflow. Every value shown comes from those records. Re-run the script after a new `send_samples.py` + `assemble_output.py` run to refresh them.

| File | Shows |
|---|---|
| [00-overview-all-samples.png](screenshots/00-overview-all-samples.png) | All 5 records in one table: category, priority, confidence, identifiers, standard to destination queue, escalation rules, summary |
| [sample1-steps.png](screenshots/sample1-steps.png) ... [sample5-steps.png](screenshots/sample5-steps.png) | One card per workflow step (ingestion, classification, enrichment, routing, escalation, structured output), labelled with the n8n node that produced it |
| [sample1-record-json.png](screenshots/sample1-record-json.png) ... [sample5-record-json.png](screenshots/sample5-record-json.png) | The complete final JSON record |

![overview](screenshots/00-overview-all-samples.png)

## B. n8n UI (take by hand, logged in to n8n Cloud)

These show that the workflow actually ran in n8n. They need a logged-in browser session, so I couldn't generate them. Save them into `docs/screenshots/` with these names.

| # | File | What to capture |
|---|---|---|
| 1 | `n8n-01-canvas.png` | Whole workflow canvas, zoomed to fit, node notes visible |
| 2 | `n8n-02-executions.png` | Executions list showing the successful runs |
| 3 | `n8n-03-sample3-route.png` | Sample #3 execution, **Route & Escalate** node output in JSON view (`decision.escalation.triggered_rules`) |
| 4 | `n8n-04-sample5-record.png` | Sample #5 execution, **Assemble Record** node output |
| 5 | `n8n-05-webhook-site.png` | Webhook.site request list showing the queue paths (`/human_review_escalation`, `/engineering`, ...) |

Tip: in n8n's output panel, switch to **JSON** view; it fits more on screen.
