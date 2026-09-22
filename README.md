# ArcVault Intake & Triage

An n8n workflow that takes unstructured customer messages from a webhook, classifies and enriches them with an LLM, routes them with deterministic rules, flags the ones a human should see, and writes one structured JSON record per message.

Built for the Valsoft AI Engineer take-home (`brief/`).

```
Webhook -> Normalize -> Classify (LLM) -> Enrich (LLM) -> Route & Escalate (code) -> Summarize (LLM) -> Assemble -> Webhook.site/<queue> -> HTTP response
```

The LLM classifies, extracts and summarises. Code decides routing and escalation. Details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Deliverables

[SUBMISSION.md](SUBMISSION.md) maps each item in section 4 of the brief to its file. `python scripts/build_submission.py` packages them as PDFs + JSON in `submission/` (plus `ArcVault_Submission.zip` for emailing).

| Brief item | Where |
|---|---|
| Working workflow (exported JSON) | [n8n/workflow.arcvault.json](n8n/workflow.arcvault.json), screenshots listed in [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md) |
| Structured output for the 5 samples | [output/records.json](output/records.json) |
| Prompts + rationale | [docs/PROMPTS.md](docs/PROMPTS.md) (prompt files in [prompts/](prompts/), history in [docs/CHANGELOG_PROMPTS.md](docs/CHANGELOG_PROMPTS.md)) |
| Architecture write-up | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Evaluation and 3-run consistency | [output/eval_report.md](output/eval_report.md) |
| Demo script (Loom) | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| What the AI got wrong | [docs/AI_ASSISTANCE_LOG.md](docs/AI_ASSISTANCE_LOG.md) |

## Stack

- **n8n Cloud** for orchestration. Self-hosted n8n works the same way; see the note at the end.
- **Groq**, `openai/gpt-oss-120b`, through its OpenAI-compatible API from plain HTTP Request nodes. The base URL and model are set in `config/rules.json`, so Ollama or another compatible endpoint can be swapped in.
- **Webhook.site** stands in for the downstream queue system.
- Python 3.11+ (stdlib + `jsonschema`) for the helper scripts. Node 18+ only for the offline tests.

## Quickstart (about 10 minutes)

1. **Get the keys and URLs**
   - Groq API key: https://console.groq.com/keys
   - A Webhook.site URL: open https://webhook.site and copy "Your unique URL".
   - `cp .env.example .env` and fill in `GROQ_API_KEY` and `WEBHOOK_SITE_URL`.
   - `pip install -r requirements.txt`

2. **Build the workflow JSON.** `--local` bakes in your own Webhook.site URL; without it the file keeps the placeholder `https://webhook.site/YOUR-UNIQUE-ID`, which is what's committed here:
   ```
   python scripts/build_workflow.py --local
   ```

3. **In n8n Cloud**
   1. *Create workflow -> ... menu -> Import from File ->* `n8n/workflow.arcvault.json`. If you are re-importing, delete or unpublish the old copy first; two active workflows can't share a webhook path.
   2. Open **Classify (LLM)**. Authentication is already `Generic Credential Type` / `Bearer Auth`. In the **Bearer Auth** credential field, choose *Create new credential* and paste the raw Groq key (`gsk_...`, without the word "Bearer") as the Token.
   3. Open **Enrich (LLM)** and **Summarize (LLM)** and select the same credential in their **Bearer Auth** field. Any LLM node without a credential fails with `Credentials not found`, and the record is escalated as `llm_failure`.
   4. **Save**, then **Publish** (n8n 2.x) or toggle **Active** (n8n 1.x), top right. After later edits, publish again; saving only updates the draft.
   5. Open the **Webhook** node, switch to **Production URL**, and copy it into `.env` as `N8N_WEBHOOK_URL`. It must contain `/webhook/`, not `/webhook-test/`.

4. **Send the 5 sample messages**
   ```
   python scripts/send_samples.py            # prints each record, appends to output/records.jsonl
   python scripts/assemble_output.py         # validates against the schema, writes output/records.json
   ```
   Each record also arrives at Webhook.site under `/<destination_queue>`.

   To send your own message: `python scripts/send_samples.py --message "Our whole team is locked out since 9am" --source email`. On Windows PowerShell, prefer this over `curl.exe -d "{\"...\"}"`: PowerShell 5.1 strips the escaped quotes and the JSON breaks.

5. **Evaluate (optional, about 25 minutes because of free-tier rate limits)**
   ```
   python scripts/eval.py --runs 3           # writes output/eval_report.md
   ```

## Offline checks (no n8n or LLM needed)

```
node tests/rules.test.js           # routing + escalation rules
node tests/validate.test.js        # LLM response validation
node tests/workflow_smoke.test.js  # runs the generated Code nodes with fake LLM responses
python scripts/check_groq.py       # prompt iteration straight against Groq (needs GROQ_API_KEY)
```

## Changing things

- **Rules, queues, thresholds, keywords, model:** edit `config/rules.json`.
- **Prompts:** add `prompts/<step>.vN.md` and point `config/rules.json` at it.
- **Routing logic:** edit `src/rules.js`.

After any of these, run `python scripts/build_workflow.py` and re-import. I don't edit the workflow JSON by hand; it's a build artifact.

## Limits and notes

- Groq's free tier for `gpt-oss-120b` allows 8,000 tokens/minute, and one message uses about 6k across 3 calls. The scripts pace requests; if you fire them faster, the workflow records `llm_failure` and escalates instead of dropping the message.
- Webhook.site URLs expire after 7 days on the free plan. The durable copy of the output is `output/records.json`.
- **Self-hosted n8n:** `docker run -it --rm -p 5678:5678 n8nio/n8n`, then the same import steps. The webhook URL becomes `http://localhost:5678/webhook/arcvault-intake`. I haven't tested this path; I used n8n Cloud.
