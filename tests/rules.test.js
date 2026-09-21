// Unit tests for src/rules.js. Run: node tests/rules.test.js
const assert = require('assert');
const path = require('path');
const { decide, matchPhrases, parseUsdAmounts } = require('../src/rules.js');
const RULES = require(path.join(__dirname, '..', 'config', 'rules.json'));

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('ok   ' + name); }
  catch (e) { console.log('FAIL ' + name + '\n     ' + e.message); process.exitCode = 1; }
}
const cls = (category, priority, confidence) => ({ category, priority, confidence });
const rules = r => r.escalation.triggered_rules.map(x => x.rule);

test('#1 403 login -> engineering, priority raised, not escalated', () => {
  const r = decide({ raw_message: 'I tried logging in this morning and keep getting a 403 error.', classification: cls('Bug Report', 'Medium', 0.9) }, RULES);
  assert.strictEqual(r.routing.destination_queue, 'engineering');
  assert.strictEqual(r.priority, 'High');
  assert.strictEqual(r.priority_adjusted_by, 'security_signal');
  assert.strictEqual(r.escalation.flagged, false);
  assert.match(r.escalation.advisory_signals[0].detail, /raised from Medium to High/);
});

test('#1 when LLM already said High, detail does not claim a raise', () => {
  const r = decide({ raw_message: 'keep getting a 403 error', classification: cls('Bug Report', 'High', 0.94) }, RULES);
  assert.strictEqual(r.priority_adjusted_by, null);
  assert.match(r.escalation.advisory_signals[0].detail, /already High, no change/);
  assert.doesNotMatch(r.escalation.advisory_signals[0].detail, /raised/);
});

test('#2 feature request -> product', () => {
  const r = decide({ raw_message: "We'd love to see a bulk export feature for our audit logs.", classification: cls('Feature Request', 'Low', 0.95) }, RULES);
  assert.strictEqual(r.routing.destination_queue, 'product');
  assert.deepStrictEqual(rules(r), []);
});

test('#3 invoice $1,240 vs $980 -> escalated under any_amount', () => {
  const r = decide({ raw_message: 'Invoice #8821 shows a charge of $1,240 but our contract rate is $980/month.', classification: cls('Billing Issue', 'Medium', 0.95) }, RULES);
  assert.strictEqual(r.routing.destination_queue, 'human_review_escalation');
  assert.strictEqual(r.routing.standard_queue, 'billing');
  assert.deepStrictEqual(rules(r), ['billing_amount_over_threshold']);
});

test('#3 under discrepancy basis ($260) -> not escalated', () => {
  const alt = JSON.parse(JSON.stringify(RULES));
  alt.thresholds.billing_threshold_basis = 'discrepancy';
  const r = decide({ raw_message: 'Invoice #8821 shows a charge of $1,240 but our contract rate is $980/month.', classification: cls('Billing Issue', 'Medium', 0.95) }, alt);
  assert.strictEqual(r.escalation.flagged, false);
});

test('#4 SSO question -> technical_support, no security signal', () => {
  const r = decide({ raw_message: 'is there a way to set up SSO with Okta?', classification: cls('Technical Question', 'Low', 0.85) }, RULES);
  assert.strictEqual(r.routing.destination_queue, 'technical_support');
  assert.strictEqual(r.priority, 'Low');
  assert.deepStrictEqual(r.escalation.advisory_signals, []);
});

test('#5 dashboard stopped loading -> escalated, two rules', () => {
  const r = decide({ raw_message: 'Your dashboard stopped loading for us around 2pm EST. Multiple users affected.', classification: cls('Incident/Outage', 'High', 0.9) }, RULES);
  assert.strictEqual(r.routing.destination_queue, 'human_review_escalation');
  assert.strictEqual(r.routing.standard_queue, 'incident_response');
  assert.deepStrictEqual(rules(r).sort(), ['incident_category', 'outage_language']);
});

test('low confidence -> escalated, keeps standard queue', () => {
  const r = decide({ raw_message: 'it does not work', classification: cls('Bug Report', 'Medium', 0.5) }, RULES);
  assert.deepStrictEqual(rules(r), ['low_confidence']);
  assert.strictEqual(r.routing.standard_queue, 'engineering');
});

test('multi-intent -> escalated even with high confidence', () => {
  const c = { ...cls('Billing Issue', 'Medium', 0.92), secondary_categories: ['Bug Report', 'Feature Request'] };
  const r = decide({ raw_message: 'invoice too high and reports page errors', classification: c }, RULES);
  assert.deepStrictEqual(rules(r), ['multi_intent']);
  assert.strictEqual(r.routing.standard_queue, 'billing');
});

test('confidence exactly 0.70 is not low', () => {
  const r = decide({ raw_message: 'x', classification: cls('Bug Report', 'Medium', 0.7) }, RULES);
  assert.strictEqual(r.escalation.flagged, false);
});

test('llm failure -> escalated, unassigned', () => {
  const r = decide({ raw_message: 'hello', classification: null, llm_errors: ['invalid JSON after retry'] }, RULES);
  assert.deepStrictEqual(rules(r), ['llm_failure']);
  assert.strictEqual(r.routing.standard_queue, 'unassigned');
  assert.strictEqual(r.routing.destination_queue, 'human_review_escalation');
});

test('enrichment-only failure -> escalated but keeps standard queue', () => {
  const r = decide({ raw_message: 'feature idea', classification: cls('Feature Request', 'Low', 0.9), llm_errors: ['enrichment schema'] }, RULES);
  assert.deepStrictEqual(rules(r), ['llm_failure']);
  assert.strictEqual(r.routing.standard_queue, 'product');
});

test('small billing complaint ($120) -> billing, not escalated', () => {
  const r = decide({ raw_message: 'You overcharged me $120, this is outrageous!', classification: cls('Billing Issue', 'High', 0.9) }, RULES);
  assert.strictEqual(r.routing.destination_queue, 'billing');
});

test('phrase matching respects word boundaries', () => {
  assert.deepStrictEqual(matchPhrases('error 4030 in log', ['403']), []);
  assert.deepStrictEqual(matchPhrases('Got a 403.', ['403']), ['403']);
});

test('parseUsdAmounts handles commas, decimals, USD prefix', () => {
  assert.deepStrictEqual(parseUsdAmounts('$1,240 and $980/month and USD 12.50'), [1240, 980, 12.5]);
});

console.log(`\n${passed} passed`);
