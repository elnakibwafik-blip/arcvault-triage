# Demo script (about 5 minutes, Loom)

**Before recording:** check the workflow is published/active. Open three tabs: the n8n editor, n8n **Executions**, and your Webhook.site page (cleared). Have a terminal in `arcvault-triage/`. Warm up by sending one message about a minute before you start, so the Groq rate-limit window is clear. Use `--delay 45`, the default; the free tier allows about one message a minute.

| Time | Show | Say |
|---|---|---|
| 0:00 | README diagram | "ArcVault gets unstructured requests by email, form and portal. This workflow classifies, enriches and routes each one, and flags the ones a human should see. The design rule is that the LLM labels and extracts, and code decides." |
| 0:30 | n8n canvas, left to right | "Webhook in, Normalize, then two LLM calls, classify and enrich, each followed by a Code node that validates the output. Then Route & Escalate, which is plain JavaScript driven by a config file, a summary written for the receiving team, and the record is posted to the queue and returned." Point at the **Has Text?** branch: "Empty messages skip the LLM and go straight to escalation." |
| 1:15 | Open **Route & Escalate**, scroll to the CONFIG block | "Every threshold and keyword is here, generated from `config/rules.json`. The billing threshold, the 0.70 confidence floor, the outage phrases. Changing a rule is a config change, not a prompt change." |
| 1:45 | Terminal: `python scripts/send_samples.py --quiet` | Let it run. As each line prints, say what happened: #1 goes to engineering, priority High because of the 403; #2 goes to product; #3 is **escalated** because the invoice is over $500; #4 goes to technical support; #5 is **escalated** by two rules, incident category and outage language. |
| 3:15 | Webhook.site | "Each record lands under its queue path. Here are the two escalations under `/human_review_escalation`, and the `X-ArcVault-Queue` header." Open #5's body. |
| 3:40 | `output/records.json`, record #3 | Walk through the fields: category, confidence, identifiers, `standard_queue: billing` vs `destination_queue: human_review_escalation`, `triggered_rules` with the detail string, summary. "The reviewer knows exactly why it's here and who owns it next." |
| 4:15 | n8n **Executions**, open one run, click through two nodes | "Every run is inspectable node by node. This is also where the state lives." |
| 4:35 | `output/eval_report.md` | "I also ran 8 edge cases, including prompt injection, French, multi-intent and an empty message, and ran the 5 samples 3 times to check consistency. The main thing I learned: the model reported 0.92 confidence on a three-intent message, so I don't rely on confidence alone. That's in the write-up." |
| 5:00 | end | |

**If something fails live:** a record with `llm_failure` in `triggered_rules` is the system working as designed. Say so: "Rate limit hit. Notice it escalated instead of dropping the message."
