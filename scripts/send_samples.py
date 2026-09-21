"""POST the sample messages to the live n8n webhook, one at a time, like real arrivals.

Every returned record is printed and appended to output/records.jsonl.
This is also the demo script.

    python scripts/send_samples.py              # the 5 brief samples
    python scripts/send_samples.py --edge       # plus the 8 edge cases
    python scripts/send_samples.py --only S5    # a single sample
"""
import argparse
import json
import os
import sys
import time
import urllib.error

from common import ROOT, load_env, load_json, post_json

sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "output" / "records.jsonl"


def send(url, case, retries=2):
    """POST one case. Retries only on transport errors; the workflow itself never 5xx's by design."""
    for attempt in range(retries + 1):
        try:
            return post_json(url, {"source": case["source"], "message": case["message"]}, timeout=120)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries:
                raise
            print(f"  transport error ({e}); retrying in 5s")
            time.sleep(5)


def brief(rec):
    c, r, e = rec["classification"], rec["routing"], rec["escalation"]
    rules = ",".join(x["rule"] for x in e["triggered_rules"]) or "-"
    return (f"{c['category']} | {c['priority']} | conf {c['confidence']} | "
            f"{r['standard_queue']} -> {r['destination_queue']} | escalated={e['flagged']} [{rules}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge", action="store_true", help="include edge cases")
    ap.add_argument("--only", help="id prefix, e.g. S3 or E2")
    ap.add_argument("--delay", type=float, default=6.0,
                    help="seconds between messages (Groq free-tier tokens-per-minute limit)")
    ap.add_argument("--quiet", action="store_true", help="one line per record instead of full JSON")
    args = ap.parse_args()

    load_env()
    url = os.environ.get("N8N_WEBHOOK_URL")
    if not url:
        sys.exit("N8N_WEBHOOK_URL missing in .env (the Production URL from the Webhook node)")
    golden = load_json("tests/golden.json")
    cases = golden["samples"] + (golden["edge_cases"] if args.edge else [])
    if args.only:
        cases = [c for c in cases if c["id"].startswith(args.only)]

    OUT.parent.mkdir(exist_ok=True)
    for i, case in enumerate(cases):
        if i:
            time.sleep(args.delay)
        print(f"\n>>> {case['id']} [{case['source']}] {case['message'][:90]!r}")
        t0 = time.time()
        rec = send(url, case)
        print(f"<<< {time.time() - t0:.1f}s  {brief(rec)}")
        if not args.quiet:
            print(json.dumps(rec, indent=2, ensure_ascii=False))
        if rec["processing"].get("llm_errors"):
            print(f"  !! llm_errors: {rec['processing']['llm_errors']}")
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\nappended {len(cases)} record(s) to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
