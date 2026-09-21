// Parsing + validation of LLM responses. Inlined into the Parse/Assemble Code
// nodes by build_workflow.py; unit-tested in tests/validate.test.js.
// Every function returns { ok, value, error } and never throws, so a bad model
// response turns into an llm_failure escalation instead of a crashed execution.

const CATEGORIES = ['Bug Report', 'Feature Request', 'Billing Issue', 'Technical Question', 'Incident/Outage'];
const LEVELS = ['Low', 'Medium', 'High'];
const ID_KEYS = ['account_ids', 'invoice_numbers', 'error_codes', 'urls', 'monetary_amounts', 'products_or_features', 'other'];

// Pull the model's JSON out of an OpenAI-compatible chat completion response
// (or the error object n8n emits when the HTTP node fails with continueOnFail).
function extractContent(resp) {
  if (!resp || resp.error) {
    const e = resp && resp.error;
    return { ok: false, error: 'HTTP/LLM error: ' + (typeof e === 'string' ? e : JSON.stringify(e || 'empty response')).slice(0, 300) };
  }
  const content = resp.choices && resp.choices[0] && resp.choices[0].message && resp.choices[0].message.content;
  if (typeof content !== 'string') return { ok: false, error: 'no message content in LLM response' };
  try {
    return { ok: true, value: JSON.parse(content), model: resp.model || null };
  } catch (e) {
    return { ok: false, error: 'invalid JSON from LLM: ' + content.slice(0, 200) };
  }
}

function parseClassification(resp) {
  const r = extractContent(resp);
  if (!r.ok) return r;
  const v = r.value;
  const errs = [];
  if (!CATEGORIES.includes(v.category)) errs.push('category not in enum: ' + JSON.stringify(v.category));
  if (!LEVELS.includes(v.priority)) errs.push('priority not in enum: ' + JSON.stringify(v.priority));
  const conf = typeof v.confidence === 'string' ? parseFloat(v.confidence) : v.confidence;
  if (typeof conf !== 'number' || isNaN(conf) || conf < 0 || conf > 1) errs.push('confidence not a number in [0,1]: ' + JSON.stringify(v.confidence));
  if (errs.length) return { ok: false, error: 'classification schema: ' + errs.join('; ') };
  // Tolerant: unknown values and the primary category are dropped rather than failing the record.
  const secondary = (Array.isArray(v.secondary_categories) ? v.secondary_categories : [])
    .filter((x, i, a) => CATEGORIES.includes(x) && x !== v.category && a.indexOf(x) === i);
  return {
    ok: true, model: r.model,
    value: {
      category: v.category, secondary_categories: secondary, priority: v.priority,
      confidence: Math.round(conf * 100) / 100, rationale: String(v.rationale || ''),
    },
  };
}

const norm = s => String(s).toLowerCase().replace(/\s+/g, ' ').trim();

// Keeps only identifiers that literally occur in the message. Anything else is
// moved to `dropped` so hallucinations are visible rather than silently kept.
function parseEnrichment(resp, rawMessage) {
  const r = extractContent(resp);
  if (!r.ok) return r;
  const v = r.value;
  const text = norm(rawMessage);
  const ids = {};
  const dropped = [];
  const src = (v.identifiers && typeof v.identifiers === 'object') ? v.identifiers : {};
  for (const k of ID_KEYS) {
    const list = Array.isArray(src[k]) ? src[k] : [];
    ids[k] = [];
    for (const item of list) {
      if (item === null || item === undefined || String(item).trim() === '') continue;
      if (text.includes(norm(item))) {
        if (!ids[k].includes(String(item))) ids[k].push(String(item));
      } else {
        dropped.push(k + ': ' + String(item));
      }
    }
  }
  const u = v.urgency_signal || {};
  const level = LEVELS.includes(u.level) ? u.level : null;
  const evidence = (Array.isArray(u.evidence) ? u.evidence : []).map(String).filter(e => text.includes(norm(e)));
  if (typeof v.core_issue !== 'string' || !v.core_issue.trim() || !level) {
    return { ok: false, error: 'enrichment schema: core_issue or urgency_signal.level missing/invalid' };
  }
  return {
    ok: true, model: r.model,
    value: { core_issue: v.core_issue.trim(), identifiers: ids, dropped_identifiers: dropped, urgency_signal: { level, evidence } },
  };
}

function emptyEnrichment() {
  const ids = {};
  for (const k of ID_KEYS) ids[k] = [];
  return { core_issue: '', identifiers: ids, dropped_identifiers: [], urgency_signal: { level: 'Low', evidence: [] } };
}

function parseSummary(resp) {
  const r = extractContent(resp);
  if (!r.ok) return r;
  const s = typeof r.value.summary === 'string' ? r.value.summary.trim() : '';
  if (!s) return { ok: false, error: 'summary missing' };
  return { ok: true, value: s, model: r.model };
}

// @@EXPORTS@@ (stripped by build_workflow.py)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { extractContent, parseClassification, parseEnrichment, parseSummary, emptyEnrichment };
}
