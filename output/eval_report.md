# Evaluation report

Generated 2026-09-21T22:52:07 against the live n8n workflow. Model `openai/gpt-oss-120b`, prompts `{"classification": "classification.v2", "enrichment": "enrichment.v2", "summary": "summary.v1"}`.

**21/23 checks passed.** Latency per message (3 LLM calls): median 1987 ms, max 4080 ms.

Expectations are in `tests/golden.json` (written before running). A category list means more than one answer is acceptable.

## Results

| Case | Run | Expected category | Actual | Priority | Conf. | Expected queue | Destination | Expect esc. | Escalated (rules) | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 1 | Bug Report | Bug Report | High | 0.94 | engineering | engineering | no | no (-) | PASS |
| S2 | 1 | Feature Request | Feature Request | Low | 0.94 | product | product | no | no (-) | PASS |
| S3 | 1 | Billing Issue | Billing Issue | Medium | 0.95 | billing | human_review_escalation | yes | yes (billing_amount_over_threshold) | PASS |
| S4 | 1 | Technical Question | Technical Question | Low | 0.94 | technical_support | technical_support | either | no (-) | PASS |
| S5 | 1 | Incident/Outage | Incident/Outage | High | 0.96 | incident_response | human_review_escalation | yes | yes (incident_category, outage_language) | PASS |
| S1 | 2 | Bug Report | Bug Report | High | 0.94 | engineering | engineering | no | no (-) | PASS |
| S2 | 2 | Feature Request | Feature Request | Low | 0.94 | product | product | no | no (-) | PASS |
| S3 | 2 | Billing Issue | Billing Issue | Medium | 0.95 | billing | human_review_escalation | yes | yes (billing_amount_over_threshold) | PASS |
| S4 | 2 | Technical Question | Technical Question | Low | 0.94 | technical_support | technical_support | either | no (-) | PASS |
| S5 | 2 | Incident/Outage | Incident/Outage | High | 0.96 | incident_response | human_review_escalation | yes | yes (incident_category, outage_language) | PASS |
| S1 | 3 | Bug Report | Bug Report | High | 0.94 | engineering | engineering | no | no (-) | PASS |
| S2 | 3 | Feature Request | Feature Request | Low | 0.94 | product | product | no | no (-) | PASS |
| S3 | 3 | Billing Issue | Billing Issue | Medium | 0.95 | billing | human_review_escalation | yes | yes (billing_amount_over_threshold) | PASS |
| S4 | 3 | Technical Question | Technical Question | Low | 0.94 | technical_support | technical_support | either | no (-) | PASS |
| S5 | 3 | Incident/Outage | Incident/Outage | High | 0.96 | incident_response | human_review_escalation | yes | yes (incident_category, outage_language) | PASS |
| E1-multi-intent | 1 | Billing Issue/Bug Report | Billing Issue | Medium | 0.92 | - | human_review_escalation | yes | yes (multi_intent) | PASS |
| E2-vague | 1 | Bug Report/Incident/Outage | Bug Report | Medium | 0.78 | - | engineering | yes | no (-) | FAIL: escalation, rules |
| E3-prompt-injection | 1 | Technical Question | Technical Question | Low | 0.92 | - | technical_support | either | no (-) | PASS |
| E4-french | 1 | Incident/Outage | Incident/Outage | High | 0.96 | - | human_review_escalation | yes | yes (incident_category) | PASS |
| E5-angry-small-billing | 1 | Billing Issue | Billing Issue | High | 0.94 | billing | billing | no | no (-) | FAIL: priority |
| E6-feature-sounds-like-bug | 1 | Feature Request/Bug Report | Bug Report | Medium | 0.94 | - | engineering | either | no (-) | PASS |
| E7-empty | 1 | (none) | None | High | None | - | human_review_escalation | yes | yes (llm_failure) | PASS |
| E8-long | 1 | Bug Report | Bug Report | Medium | 0.94 | engineering | engineering | no | no (-) | PASS |

## Consistency across runs

| Case | Runs | Confidence range | Category / priority / destination / escalation |
|---|---|---|---|
| S1 | 3 | 0.94-0.94 | stable |
| S2 | 3 | 0.94-0.94 | stable |
| S3 | 3 | 0.95-0.95 | stable |
| S4 | 3 | 0.94-0.94 | stable |
| S5 | 3 | 0.96-0.96 | stable |
