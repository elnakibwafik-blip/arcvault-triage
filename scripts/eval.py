"""Evaluate the live workflow against tests/golden.json and check run-to-run consistency.

    python scripts/eval.py --runs 3             # 5 samples x 3 runs + edge cases x 1
    python scripts/eval.py --runs 3 --edge-runs 0

Writes output/eval_report.md and output/eval_runs.jsonl (raw records, not the submission file).
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from collections import defaultdict

from common import ROOT, load_env, load_json
from send_samples import send

sys.stdout.reconfigure(encoding="utf-8")


def check(case, rec):
    """Return (list of failed check names) for one record vs its expectations."""
    exp, c, r, e = case["expect"], rec["classification"], rec["routing"], rec["escalation"]
    fails = []
    if exp.get("category") and c["category"] not in exp["category"]:
        fails.append("category")
    if exp.get("priority") and c["priority"] not in exp["priority"]:
        fails.append("priority")
    if exp.get("standard_queue") and r["standard_queue"] != exp["standard_queue"]:
        fails.append("queue")
    if exp.get("escalated") is not None and e["flagged"] != exp["escalated"]:
        fails.append("escalation")
    got_rules = {x["rule"] for x in e["triggered_rules"]}
    if exp.get("expected_rules") and not set(exp["expected_rules"]) <= got_rules:
        fails.append("rules")
    flat = json.dumps(rec["enrichment"]["identifiers"], ensure_ascii=False)
    for needle in exp.get("must_extract", []):
        if needle not in flat:
            fails.append(f"extract:{needle}")
    return fails


def row(case, rec, fails, run):
    c, r, e = rec["classification"], rec["routing"], rec["escalation"]
    exp = case["expect"]
    rules = ", ".join(x["rule"] for x in e["triggered_rules"]) or "-"
    esc_exp = {True: "yes", False: "no", None: "either"}[exp.get("escalated")]
    return (f"| {case['id']} | {run} | {'/'.join(exp.get('category') or ['(none)'])} | {c['category']} | "
            f"{c['priority']} | {c['confidence']} | {exp.get('standard_queue', '-')} | {r['destination_queue']} | "
            f"{esc_exp} | {'yes' if e['flagged'] else 'no'} ({rules}) | {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3, help="runs over the 5 brief samples")
    ap.add_argument("--edge-runs", type=int, default=1, help="runs over the edge cases")
    ap.add_argument("--delay", type=float, default=45.0)
    args = ap.parse_args()

    load_env()
    url = os.environ.get("N8N_WEBHOOK_URL") or sys.exit("N8N_WEBHOOK_URL missing in .env")
    golden = load_json("tests/golden.json")
    plan = [(c, run) for run in range(1, args.runs + 1) for c in golden["samples"]]
    plan += [(c, run) for run in range(1, args.edge_runs + 1) for c in golden["edge_cases"]]

    raw_out = ROOT / "output" / "eval_runs.jsonl"
    results = []
    for i, (case, run) in enumerate(plan):
        if i:
            time.sleep(args.delay)
        rec = send(url, case)
        fails = check(case, rec)
        results.append((case, run, rec, fails))
        print(row(case, rec, fails, run))
        with raw_out.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"case_id": case["id"], "run": run, "record": rec}, ensure_ascii=False) + "\n")

    # Consistency: across runs, did category / priority / destination / escalation change?
    by_case = defaultdict(list)
    for case, run, rec, _ in results:
        by_case[case["id"]].append(rec)
    consistency = []
    for cid, recs in by_case.items():
        if len(recs) < 2:
            continue
        fields = {
            "category": {r["classification"]["category"] for r in recs},
            "priority": {r["classification"]["priority"] for r in recs},
            "destination": {r["routing"]["destination_queue"] for r in recs},
            "escalated": {r["escalation"]["flagged"] for r in recs},
        }
        confs = [r["classification"]["confidence"] for r in recs]
        changed = [k for k, v in fields.items() if len(v) > 1]
        consistency.append(f"| {cid} | {len(recs)} | {min(confs)}-{max(confs)} | "
                           f"{'stable' if not changed else 'CHANGED: ' + ', '.join(changed)} |")

    passed = sum(1 for *_, f in results if not f)
    lat = sorted(r["processing"]["latency_ms"] for _, _, r, _ in results)
    prompts = results[0][2]["processing"]["prompt_versions"] if results else {}
    model = results[0][2]["processing"]["model"] if results else "?"
    header = ("| Case | Run | Expected category | Actual | Priority | Conf. | Expected queue | Destination | "
              "Expect esc. | Escalated (rules) | Result |\n|---|---|---|---|---|---|---|---|---|---|---|")
    report = [
        "# Evaluation report", "",
        f"Generated {dt.datetime.now().isoformat(timespec='seconds')} against the live n8n workflow. "
        f"Model `{model}`, prompts `{json.dumps(prompts)}`.", "",
        f"**{passed}/{len(results)} checks passed.** Latency per message (3 LLM calls): "
        f"median {lat[len(lat) // 2] if lat else 0} ms, max {lat[-1] if lat else 0} ms.", "",
        "Expectations are in `tests/golden.json` (written before running). A category list means more than one answer is acceptable.", "",
        "## Results", "", header, *[row(c, r, f, n) for c, n, r, f in results], "",
        "## Consistency across runs", "",
        "| Case | Runs | Confidence range | Category / priority / destination / escalation |", "|---|---|---|---|",
        *consistency, "",
    ]
    out = ROOT / "output" / "eval_report.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"\n{passed}/{len(results)} passed; wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
