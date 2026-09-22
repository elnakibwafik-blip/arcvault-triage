# ArcVault Intake & Triage: submission

Valsoft AI Engineer technical assessment. Every deliverable in section 4 of the brief is listed below, with where to find it. Repository: https://github.com/elnakibwafik-blip/arcvault-triage (private; access on request).

| Brief | Deliverable | Attachment (in the zip) | In the repository |
|---|---|---|---|
| **4.1** Working workflow: exported n8n JSON + screenshots of each step with output | Importable n8n workflow, and screenshots from n8n Cloud plus step-by-step output for all five samples | `ArcVault_n8n_workflow.json`, `ArcVault_Workflow_Screenshots.pdf` | `n8n/workflow.arcvault.json`, `docs/screenshots/`, `docs/SCREENSHOTS.md` |
| **4.2** Structured output file | One JSON record per sample input: category, priority, confidence, extracted entities, standard and destination queue, escalation flag with the rules that fired, and summary. All five pass JSON Schema validation. | `ArcVault_records.json` | `output/records.json`, `schema/record.schema.json` |
| **4.3** Prompt documentation | Each of the three prompts verbatim, each followed by why it is structured that way, the tradeoffs, and what I'd change with more time | `ArcVault_Prompts.pdf` | `docs/PROMPTS.md`, `prompts/`, `docs/CHANGELOG_PROMPTS.md` |
| **4.4** Architecture write-up (one to two pages) | System design and where state lives, routing, escalation, production scale, Phase 2 | `ArcVault_Architecture.pdf` | `docs/ARCHITECTURE.md` |

**Supporting evidence (also in the zip):**
- `ArcVault_Eval_Report.pdf` (`output/eval_report.md`): the 5 samples run 3 times, plus 8 edge cases, against the live workflow. The 5 samples match expectations and are identical across all 3 runs; 6 of 8 edge cases pass, and both failures are documented.
- `ArcVault_AI_Assistance_Log.pdf` (`docs/AI_ASSISTANCE_LOG.md`): what the AI got wrong while building this, and how each problem was fixed.
- Offline tests (`tests/`) for the routing rules, the LLM-output validation and the generated workflow code.

**Stack:** n8n Cloud, Groq `openai/gpt-oss-120b` (free tier), Webhook.site as the downstream queue. All free tooling.

**Results for the five sample inputs:**

| # | Category | Priority | Conf. | Destination queue | Escalated because |
|---|---|---|---|---|---|
| 1 | Bug Report | High | 0.94 | engineering | not escalated (a 403 raises priority but doesn't escalate) |
| 2 | Feature Request | Low | 0.94 | product | not escalated |
| 3 | Billing Issue | Medium | 0.95 | human_review_escalation (owner: billing) | invoice amount > $500 |
| 4 | Technical Question | Low | 0.92 | technical_support | not escalated |
| 5 | Incident/Outage | High | 0.96 | human_review_escalation (owner: incident_response) | incident category + outage language |

**Import and run:** see `README.md` in the repository. Import the JSON, attach a Groq Bearer Auth credential to the three LLM nodes, publish, then run `python scripts/send_samples.py`.
