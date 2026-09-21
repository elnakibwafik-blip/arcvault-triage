# Prompt changelog

Every change came from an observed output, found with `scripts/check_groq.py` (same prompts, called outside n8n). No output record was edited by hand.

## classification v2 / enrichment v2 (2026-09-21)

Model: `openai/gpt-oss-120b` on Groq, temperature 0, reasoning_effort low.

| Observed with v1 | Case | Change in v2 |
|---|---|---|
| A message with three separate asks (invoice too high, reports page error, Slack integration) came back as Billing Issue with **confidence 0.92**. The calibration guide says multi-intent should be 0.50–0.69; the model ignored it. It would have gone straight to billing, and the bug and the feature request would have been lost. | E1 | Added a `secondary_categories` output field and a "Several intents" section. **Code** now escalates on it (`multi_intent` rule in `config/rules.json`) instead of relying on self-reported confidence. After v2 the model returned `["Bug Report", "Feature Request"]`, still with confidence 0.92. That confirms confidence alone is not a usable signal for this. |
| "This is RIDICULOUS. You charged us $45... Fix it NOW or we cancel" got priority **High**. | E5 | Added "judge by business impact, never by tone", defined High financial error as "hundreds of dollars or more", and made the third few-shot example angry but Medium. **Still High after v2.** The model seems to treat "or we cancel" as churn risk. I left it: it doesn't affect routing (under $500, so it goes to billing and isn't escalated), and a churn threat is arguably worth High. I didn't want to overfit the prompt to one test case. Recorded as a known disagreement in the eval. |
| Single user who can't log in (403) got urgency **Medium**, although the brief's own priority definition treats being blocked as High. | S1 | Enrichment v2 spells out urgency levels: "a single user who can't log in counts" as High. Now High. |
| `products_or_features` missed "bulk export" (S2) and "SSO" (S4). The v1 definition said "named features", so the model skipped capabilities. | S2, S4 | Broadened the definition to "features, pages or capabilities mentioned or requested", with SSO and bulk export as examples. Both are now extracted. |
| Rationale for S5 said the dashboard "stopped loading for all", which the message doesn't say. | S5 | Rationale must "quote the exact words that decided it; don't overstate them". Now it quotes "Multiple users affected". |

v1 files are kept in `prompts/` so the diff can be reviewed.
