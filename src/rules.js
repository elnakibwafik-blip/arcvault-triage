// Deterministic routing + escalation. No LLM calls in here: the model classifies
// and extracts, this function decides. build_workflow.py inlines this file into
// the "Route & Escalate" Code node, with RULES taken from config/rules.json.

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Word-boundary, case-insensitive phrase match. Returns the phrases that hit.
function matchPhrases(text, phrases) {
  const hits = [];
  for (const p of phrases) {
    const re = new RegExp('(^|[^a-z0-9])' + escapeRegex(p.toLowerCase()) + '($|[^a-z0-9])', 'i');
    if (re.test(text)) hits.push(p);
  }
  return hits;
}

// Dollar amounts read straight from the raw text (not from the LLM), so the
// billing threshold can't be tripped by a hallucinated number.
function parseUsdAmounts(text) {
  const re = /(?:\$\s?|USD\s?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?/gi;
  const out = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    out.push(parseFloat(m[0].replace(/[^0-9.]/g, '')));
  }
  return out;
}

function decide(input, RULES) {
  const text = input.raw_message || '';
  const c = input.classification || {};
  const t = RULES.thresholds;
  const triggered = [];
  const advisory = [];

  const llmErrors = input.llm_errors || [];
  // Classification is the only LLM output routing depends on. If it is missing,
  // there is no standard queue. If only enrichment failed, keep the standard
  // queue but still escalate, because the record is incomplete.
  const llmOk = RULES.categories.includes(c.category);
  const standardQueue = llmOk ? RULES.category_to_queue[c.category] : 'unassigned';
  let priority = RULES.priorities.includes(c.priority) ? c.priority : 'High';
  let priorityAdjustedBy = null;

  if (llmErrors.length || !llmOk) {
    triggered.push({ rule: 'llm_failure', detail: llmErrors.join(' | ') || 'classification missing or invalid' });
  }
  if (llmOk) {
    if (typeof c.confidence !== 'number' || c.confidence < t.min_confidence) {
      triggered.push({ rule: 'low_confidence', detail: `confidence ${c.confidence} < ${t.min_confidence}` });
    }
    if (c.category === 'Incident/Outage') {
      triggered.push({ rule: 'incident_category', detail: 'category is Incident/Outage' });
    }
    if (c.category === 'Billing Issue') {
      const amounts = parseUsdAmounts(text);
      if (amounts.length) {
        const maxAmt = Math.max(...amounts);
        const disc = amounts.length > 1 ? maxAmt - Math.min(...amounts) : 0;
        const basis = t.billing_threshold_basis;
        const over = basis === 'discrepancy' ? disc > t.billing_escalation_usd : maxAmt > t.billing_escalation_usd;
        if (over) {
          triggered.push({
            rule: 'billing_amount_over_threshold',
            detail: `basis=${basis}; largest amount $${maxAmt}, discrepancy $${disc}, threshold $${t.billing_escalation_usd}`,
          });
        }
      }
    }
  }

  // Keyword rules run even when the LLM failed: they only need the raw text.
  const outageHits = matchPhrases(text, RULES.keywords.outage_language);
  if (outageHits.length) {
    triggered.push({ rule: 'outage_language', detail: 'matched: ' + outageHits.join(', ') });
  }

  const securityHits = matchPhrases(text, RULES.keywords.security_signal);
  if (securityHits.length) {
    advisory.push({ rule: 'security_signal', detail: 'matched: ' + securityHits.join(', ') + '; priority raised to High, not escalated on its own' });
    if (priority !== 'High') {
      priorityAdjustedBy = 'security_signal';
      priority = 'High';
    }
  }

  const flagged = triggered.length > 0;
  const destination = flagged ? RULES.escalation_queue : standardQueue;
  const routingReason = flagged
    ? `Escalated for human review (${triggered.map(r => r.rule).join(', ')}); standard owner would be ${standardQueue}.`
    : `${c.category} -> ${standardQueue} (category mapping, confidence ${c.confidence}).`;

  return {
    priority,
    priority_adjusted_by: priorityAdjustedBy,
    routing: { standard_queue: standardQueue, destination_queue: destination, routing_reason: routingReason },
    escalation: { flagged, triggered_rules: triggered, advisory_signals: advisory },
  };
}

// @@EXPORTS@@ (stripped by build_workflow.py)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { decide, matchPhrases, parseUsdAmounts };
}
