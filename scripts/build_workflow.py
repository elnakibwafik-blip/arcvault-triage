"""Generate n8n/workflow.arcvault.json from the prompt files, config/rules.json and src/*.js.

Why generate instead of hand-editing in the n8n UI: the prompts in docs/PROMPTS.md,
the rules in config/rules.json and the unit-tested JS in src/ are the single
source of truth. The workflow is a build artifact, so they can't drift apart.

    python scripts/build_workflow.py
"""
import json
import os
import re
import uuid

from common import ROOT, load_env, load_json, load_prompt

WEBHOOK_PATH = "arcvault-intake"
CREDENTIAL_NAME = "Groq API"  # n8n Header Auth credential: Authorization: Bearer <key>


def js_lib(name):
    """Inline a src/*.js file, dropping the Node-only export block."""
    src = (ROOT / "src" / name).read_text(encoding="utf-8")
    return src.split("// @@EXPORTS@@")[0].rstrip() + "\n"


def js_const(name, value):
    return f"const {name} = {json.dumps(value, indent=2, ensure_ascii=False)};\n"


def stable_id(name):
    # Deterministic node ids so rebuilding produces a clean git diff.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "arcvault/" + name))


def code_node(name, js, pos, notes):
    return {"id": stable_id(name), "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2,
            "position": pos, "parameters": {"jsCode": js}, "notes": notes, "notesInFlow": True}


def llm_node(name, request_field, pos, notes):
    return {
        "id": stable_id(name), "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": pos,
        "parameters": {
            "method": "POST",
            "url": "={{ $('Normalize').first().json.ctx.llm_base_url }}/chat/completions",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json." + request_field + ") }}",
            "options": {"timeout": 30000},
        },
        "credentials": {"httpHeaderAuth": {"name": CREDENTIAL_NAME}},
        # Transport retry: Groq JSON mode returns HTTP 400 when the model emits
        # invalid JSON, so this retry also covers the "invalid JSON" case.
        "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 2000,
        # Never crash the execution: the Parse node turns the error into llm_failure.
        "onError": "continueRegularOutput",
        "notes": notes, "notesInFlow": True,
    }


def main():
    load_env()
    rules = load_json("config/rules.json")
    rules_clean = {k: v for k, v in rules.items() if not k.startswith("_")}
    pnames = rules["prompts"]
    prompts = {}
    for step, fname in pnames.items():
        system, user = load_prompt(fname)
        prompts[step] = {"system": system, "user": user}

    ctx = {
        "llm_base_url": rules["llm"]["base_url"],
        "model": rules["llm"]["model"],
        "temperature": rules["llm"]["temperature"],
        "prompt_versions": pnames,
        "workflow_version": rules["workflow_version"],
        "webhook_site_url": os.environ.get("WEBHOOK_SITE_URL", "").rstrip("/"),
    }

    normalize_js = (
        "// Step 1: Ingestion. Normalise the webhook payload and build the two LLM requests.\n"
        + js_const("CTX", ctx)
        + js_const("PROMPTS", {k: prompts[k] for k in ("classification", "enrichment")})
        + r"""
const body = $input.first().json.body || {};
const text = typeof body.message === 'string' ? body.message.trim() : '';
const SOURCES = ['email', 'web_form', 'support_portal'];
const source = SOURCES.includes(body.source) ? body.source : 'unknown';

function uuidv4() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}
// split/join instead of replace so '$' sequences in customer text are not interpreted.
const fill = t => t.split('{{source}}').join(source).split('{{message}}').join(text);
const request = p => ({
  model: CTX.model,
  temperature: CTX.temperature,
  response_format: { type: 'json_object' },
  messages: [{ role: 'system', content: p.system }, { role: 'user', content: fill(p.user) }],
});

return [{ json: {
  record_id: uuidv4(),
  received_at: new Date().toISOString(),
  source,
  raw_message: text,
  has_text: text.length > 0,
  started_ms: Date.now(),
  llm_errors: text.length > 0 ? [] : ['empty message: nothing to classify, LLM not called'],
  classification: null,
  enrichment: null,
  cls_request: request(PROMPTS.classification),
  enr_request: request(PROMPTS.enrichment),
  ctx: CTX,
} }];
""")

    parse_cls_js = (
        "// Step 2b: validate the classification response against the allowed enums.\n"
        + js_lib("validate.js")
        + r"""
const base = $('Normalize').first().json;
const r = parseClassification($input.first().json);
return [{ json: {
  ...base,
  classification: r.ok ? r.value : null,
  llm_errors: base.llm_errors.concat(r.ok ? [] : ['classification: ' + r.error]),
  model_seen: r.model || null,
} }];
""")

    parse_enr_js = (
        "// Step 3b: validate enrichment and drop identifiers that are not literally in the message.\n"
        + js_lib("validate.js")
        + r"""
const base = $('Parse Classification').first().json;
const r = parseEnrichment($input.first().json, base.raw_message);
return [{ json: {
  ...base,
  enrichment: r.ok ? r.value : emptyEnrichment(),
  llm_errors: base.llm_errors.concat(r.ok ? [] : ['enrichment: ' + r.error]),
} }];
""")

    route_js = (
        "// Steps 4 + 6: deterministic routing and escalation. The LLM does not decide this.\n"
        "// ===== CONFIG (generated from config/rules.json - edit there, then rebuild) =====\n"
        + js_const("RULES", rules_clean)
        + "// =================================================================================\n"
        + js_const("SUMMARY_PROMPT", prompts["summary"])
        + js_lib("rules.js")
        + r"""
const b = $input.first().json;
const d = decide({ raw_message: b.raw_message, classification: b.classification, llm_errors: b.llm_errors }, RULES);
const enr = b.enrichment || {};
const triage = {
  category: b.classification ? b.classification.category : null,
  priority: d.priority,
  receiving_queue: d.routing.destination_queue,
  standard_queue: d.routing.standard_queue,
  escalated: d.escalation.flagged,
  escalation_reasons: d.escalation.triggered_rules.map(r => r.rule + ' (' + r.detail + ')'),
  core_issue: enr.core_issue || null,
  identifiers: enr.identifiers || {},
};
const user = SUMMARY_PROMPT.user
  .split('{{triage_json}}').join(JSON.stringify(triage, null, 2))
  .split('{{message}}').join(b.raw_message || '(empty message)');
return [{ json: {
  ...b,
  decision: d,
  sum_request: {
    model: b.ctx.model, temperature: b.ctx.temperature, response_format: { type: 'json_object' },
    messages: [{ role: 'system', content: SUMMARY_PROMPT.system }, { role: 'user', content: user }],
  },
} }];
""")

    assemble_js = (
        "// Step 5: assemble the final structured record (the only shape that leaves the workflow).\n"
        + js_lib("validate.js")
        + r"""
const b = $('Route & Escalate').first().json;
const s = parseSummary($input.first().json);
const d = b.decision;
const c = b.classification;
const enr = b.enrichment || emptyEnrichment();
const errors = b.llm_errors.slice();
if (!s.ok) errors.push('summary: ' + s.error);

// Deterministic fallback so a failed summary call never produces an empty field.
const fallback = (c ? c.category : 'Unclassified message') + ' routed to ' + d.routing.destination_queue + '. '
  + (enr.core_issue || 'Automatic processing failed; read the raw message.')
  + (d.escalation.flagged ? ' Escalated: ' + d.escalation.triggered_rules.map(r => r.rule).join(', ') + '.' : '');

const record = {
  record_id: b.record_id,
  received_at: b.received_at,
  source: b.source,
  raw_message: b.raw_message,
  classification: {
    category: c ? c.category : null,
    priority: d.priority,
    llm_priority: c ? c.priority : null,
    priority_adjusted_by: d.priority_adjusted_by,
    confidence: c ? c.confidence : null,
    rationale: c ? c.rationale : 'classification unavailable',
  },
  enrichment: enr,
  routing: d.routing,
  escalation: d.escalation,
  summary: s.ok ? s.value : fallback,
  processing: {
    model: s.model || b.model_seen || b.ctx.model,
    prompt_versions: b.ctx.prompt_versions,
    latency_ms: Date.now() - b.started_ms,
    workflow_version: b.ctx.workflow_version,
    llm_errors: errors,
  },
};

// Light structural check here; full JSON Schema validation runs in scripts/assemble_output.py.
const missing = ['record_id', 'received_at', 'source', 'classification', 'enrichment', 'routing', 'escalation', 'summary']
  .filter(k => record[k] === undefined || record[k] === null || record[k] === '');
if (missing.length) record.processing.llm_errors.push('record missing fields: ' + missing.join(', '));
return [{ json: record }];
""")

    empty_branch_note = "If false (empty message): skip the LLM and go straight to routing, which escalates it as llm_failure."
    nodes = [
        {"id": stable_id("Webhook"), "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
         "position": [0, 300], "webhookId": stable_id("webhook-id"),
         "parameters": {"httpMethod": "POST", "path": WEBHOOK_PATH, "responseMode": "responseNode", "options": {}},
         "notes": "Step 1: POST {source, message}", "notesInFlow": True},
        code_node("Normalize", normalize_js, [220, 300], "Assigns id/timestamp, validates source, builds LLM requests"),
        {"id": stable_id("Has Text?"), "name": "Has Text?", "type": "n8n-nodes-base.if", "typeVersion": 2,
         "position": [440, 300],
         "parameters": {"conditions": {
             "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
             "conditions": [{"id": stable_id("cond-has-text"), "leftValue": "={{ $json.has_text }}", "rightValue": "",
                             "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
             "combinator": "and"}, "options": {}},
         "notes": empty_branch_note, "notesInFlow": True},
        llm_node("Classify (LLM)", "cls_request", [660, 200], "Step 2: category, priority, confidence"),
        code_node("Parse Classification", parse_cls_js, [880, 200], "Enum + range validation"),
        llm_node("Enrich (LLM)", "enr_request", [1100, 200], "Step 3: core issue, identifiers, urgency"),
        code_node("Parse Enrichment", parse_enr_js, [1320, 200], "Drops identifiers not in the text"),
        code_node("Route & Escalate", route_js, [1540, 300], "Steps 4 + 6: deterministic rules from config/rules.json"),
        llm_node("Summarize (LLM)", "sum_request", [1760, 300], "Step 5: 2-3 sentence handoff for the receiving team"),
        code_node("Assemble Record", assemble_js, [1980, 300], "Final JSON record"),
        {"id": stable_id("Publish to Queue"), "name": "Publish to Queue", "type": "n8n-nodes-base.httpRequest",
         "typeVersion": 4.2, "position": [2200, 300],
         "parameters": {
             "method": "POST",
             "url": "={{ $('Normalize').first().json.ctx.webhook_site_url }}/{{ $json.routing.destination_queue }}",
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "X-ArcVault-Queue", "value": "={{ $json.routing.destination_queue }}"},
                 {"name": "X-ArcVault-Escalated", "value": "={{ String($json.escalation.flagged) }}"}]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify($json) }}",
             "options": {"timeout": 15000}},
         "retryOnFail": True, "maxTries": 2, "waitBetweenTries": 1000,
         "onError": "continueRegularOutput",
         "notes": "Persist: POST record to Webhook.site/<queue>", "notesInFlow": True},
        {"id": stable_id("Respond"), "name": "Respond", "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
         "position": [2420, 300],
         "parameters": {"respondWith": "json",
                        "responseBody": "={{ JSON.stringify($('Assemble Record').first().json) }}",
                        "options": {}},
         "notes": "Return the record to the caller", "notesInFlow": True},
    ]

    def link(*names):
        return [[{"node": n, "type": "main", "index": 0} for n in names]]

    connections = {
        "Webhook": {"main": link("Normalize")},
        "Normalize": {"main": link("Has Text?")},
        "Has Text?": {"main": [[{"node": "Classify (LLM)", "type": "main", "index": 0}],
                               [{"node": "Route & Escalate", "type": "main", "index": 0}]]},
        "Classify (LLM)": {"main": link("Parse Classification")},
        "Parse Classification": {"main": link("Enrich (LLM)")},
        "Enrich (LLM)": {"main": link("Parse Enrichment")},
        "Parse Enrichment": {"main": link("Route & Escalate")},
        "Route & Escalate": {"main": link("Summarize (LLM)")},
        "Summarize (LLM)": {"main": link("Assemble Record")},
        "Assemble Record": {"main": link("Publish to Queue")},
        "Publish to Queue": {"main": link("Respond")},
    }

    workflow = {
        "name": "ArcVault Intake & Triage",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"generatedBy": "scripts/build_workflow.py", "workflow_version": rules["workflow_version"]},
    }
    out = ROOT / "n8n" / "workflow.arcvault.json"
    text = json.dumps(workflow, indent=2, ensure_ascii=False) + "\n"
    if re.search(r"gsk_[A-Za-z0-9]{10,}", text):
        raise SystemExit("refusing to write: workflow contains what looks like a Groq key")
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}  ({len(nodes)} nodes, prompts {pnames}, "
          f"webhook_site_url {'set' if ctx['webhook_site_url'] else 'EMPTY - publish step will be skipped'})")


if __name__ == "__main__":
    main()
