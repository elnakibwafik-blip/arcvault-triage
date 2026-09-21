// Offline smoke test of the GENERATED workflow: runs every Code node's jsCode
// from n8n/workflow.arcvault.json in order, with a fake $input / $() and canned
// LLM responses. Catches glue bugs (wrong node names, missing fields) before
// importing into n8n. Run after build: node tests/workflow_smoke.test.js
const assert = require('assert');
const path = require('path');
const wf = require(path.join(__dirname, '..', 'n8n', 'workflow.arcvault.json'));

const code = name => wf.nodes.find(n => n.name === name).parameters.jsCode;
const llm = obj => ({ model: 'fake-model', choices: [{ message: { content: JSON.stringify(obj) } }] });

function runCode(name, input, outputs) {
  const fn = new Function('$input', '$', 'return (function(){' + code(name) + '\n})();');
  const $input = { first: () => ({ json: input }) };
  const $ = n => { if (!(n in outputs)) throw new Error(`${name} referenced $('${n}') which has not run`); return { first: () => ({ json: outputs[n] }) }; };
  const res = fn($input, $);
  outputs[name] = res[0].json;
  return res[0].json;
}

function pipeline(body, fakes) {
  const out = {};
  const norm = runCode('Normalize', { body }, out);
  let routeIn = norm;
  if (norm.has_text) {
    runCode('Parse Classification', fakes.cls, out);
    routeIn = runCode('Parse Enrichment', fakes.enr, out);
  }
  runCode('Route & Escalate', routeIn, out);
  return runCode('Assemble Record', fakes.sum, out);
}

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('ok   ' + name); }
  catch (e) { console.log('FAIL ' + name + '\n     ' + e.stack.split('\n').slice(0, 3).join('\n     ')); process.exitCode = 1; }
}

test('happy path: billing message escalates with full record', () => {
  const rec = pipeline(
    { source: 'support_portal', message: 'Invoice #8821 shows a charge of $1,240 but our contract rate is $980/month.' },
    {
      cls: llm({ category: 'Billing Issue', priority: 'Medium', confidence: 0.95, rationale: 'invoice dispute' }),
      enr: llm({ core_issue: 'Invoice #8821 overcharged.', identifiers: { invoice_numbers: ['#8821'], monetary_amounts: ['$1,240', '$980/month'] }, urgency_signal: { level: 'Medium', evidence: ['charge of $1,240'] } }),
      sum: llm({ summary: 'Invoice #8821 billed $1,240 vs $980/month contract.' }),
    });
  assert.strictEqual(rec.routing.destination_queue, 'human_review_escalation');
  assert.strictEqual(rec.routing.standard_queue, 'billing');
  assert.strictEqual(rec.escalation.flagged, true);
  assert.deepStrictEqual(rec.enrichment.identifiers.invoice_numbers, ['#8821']);
  assert.deepStrictEqual(rec.processing.llm_errors, []);
  assert.strictEqual(rec.processing.model, 'fake-model');
  assert.ok(!('cls_request' in rec) && !('ctx' in rec), 'internal fields must not leak into the record');
});

test('empty message skips LLM and escalates as llm_failure', () => {
  const rec = pipeline({ source: 'email', message: '   ' }, { sum: { error: { message: 'not called' } } });
  assert.strictEqual(rec.routing.destination_queue, 'human_review_escalation');
  assert.strictEqual(rec.routing.standard_queue, 'unassigned');
  assert.deepStrictEqual(rec.escalation.triggered_rules.map(r => r.rule), ['llm_failure']);
  assert.ok(rec.summary.length > 0, 'fallback summary used');
});

test('LLM HTTP failure escalates instead of crashing', () => {
  const rec = pipeline({ source: 'web_form', message: 'The reports page errors out.' },
    { cls: { error: { message: '429 Too Many Requests' } }, enr: { error: { message: '429' } }, sum: { error: { message: '429' } } });
  assert.strictEqual(rec.escalation.flagged, true);
  assert.strictEqual(rec.processing.llm_errors.length, 3);
});

test('unknown source becomes "unknown"', () => {
  const rec = pipeline({ source: 'fax', message: 'hi' }, {
    cls: llm({ category: 'Technical Question', priority: 'Low', confidence: 0.5, rationale: 'x' }),
    enr: llm({ core_issue: 'Greeting only.', identifiers: {}, urgency_signal: { level: 'Low', evidence: [] } }),
    sum: llm({ summary: 'A greeting with no request.' }),
  });
  assert.strictEqual(rec.source, 'unknown');
  assert.deepStrictEqual(rec.escalation.triggered_rules.map(r => r.rule), ['low_confidence']);
});

test('customer text with $& does not corrupt prompt fill', () => {
  const out = {};
  const n = runCode('Normalize', { body: { source: 'email', message: 'charged $& and $1 twice' } }, out);
  assert.ok(n.cls_request.messages[1].content.includes('charged $& and $1 twice'));
});

console.log(`\n${passed} passed`);
