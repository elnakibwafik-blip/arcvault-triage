// Unit tests for src/validate.js. Run: node tests/validate.test.js
const assert = require('assert');
const V = require('../src/validate.js');

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('ok   ' + name); }
  catch (e) { console.log('FAIL ' + name + '\n     ' + e.message); process.exitCode = 1; }
}
const wrap = obj => ({ model: 'm', choices: [{ message: { content: typeof obj === 'string' ? obj : JSON.stringify(obj) } }] });

test('valid classification passes, confidence rounded', () => {
  const r = V.parseClassification(wrap({ category: 'Bug Report', priority: 'High', confidence: 0.923, rationale: 'x' }));
  assert.ok(r.ok);
  assert.strictEqual(r.value.confidence, 0.92);
});

test('category outside enum fails', () => {
  const r = V.parseClassification(wrap({ category: 'Question', priority: 'High', confidence: 0.9 }));
  assert.ok(!r.ok);
  assert.match(r.error, /category/);
});

test('confidence as percentage fails (not silently rescaled)', () => {
  assert.ok(!V.parseClassification(wrap({ category: 'Bug Report', priority: 'High', confidence: 85 })).ok);
});

test('non-JSON content fails', () => {
  assert.ok(!V.parseClassification(wrap('Sure! Here is the JSON...')).ok);
});

test('n8n HTTP error object fails cleanly', () => {
  const r = V.parseClassification({ error: { message: '429 rate limited' } });
  assert.ok(!r.ok);
  assert.match(r.error, /429/);
});

test('enrichment drops identifiers not present in the message', () => {
  const msg = 'Invoice #8821 shows a charge of $1,240 but our contract rate is $980/month.';
  const r = V.parseEnrichment(wrap({
    core_issue: 'The customer disputes invoice #8821.',
    identifiers: { invoice_numbers: ['#8821'], monetary_amounts: ['$1,240', '$980/month', '$260'], account_ids: ['ACME-1'] },
    urgency_signal: { level: 'Medium', evidence: ['charge of $1,240', 'made-up quote'] },
  }), msg);
  assert.ok(r.ok);
  assert.deepStrictEqual(r.value.identifiers.monetary_amounts, ['$1,240', '$980/month']);
  assert.deepStrictEqual(r.value.identifiers.error_codes, []);
  assert.deepStrictEqual(r.value.dropped_identifiers, ['account_ids: ACME-1', 'monetary_amounts: $260']);
  assert.deepStrictEqual(r.value.urgency_signal.evidence, ['charge of $1,240']);
});

test('enrichment without urgency level fails', () => {
  assert.ok(!V.parseEnrichment(wrap({ core_issue: 'x', identifiers: {} }), 'x').ok);
});

test('summary parse', () => {
  assert.strictEqual(V.parseSummary(wrap({ summary: ' Hello. ' })).value, 'Hello.');
  assert.ok(!V.parseSummary(wrap({ text: 'x' })).ok);
});

console.log(`\n${passed} passed`);
