"""Run the classification + enrichment prompts directly against Groq, outside n8n.

Used for prompt iteration: faster than round-tripping through the workflow.
The n8n workflow sends exactly the same system/user messages (build_workflow.py
reads the same prompt files).

    python scripts/check_groq.py                 # 5 golden samples
    python scripts/check_groq.py --edge          # edge cases too
    python scripts/check_groq.py --only S3 --runs 3
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error

from common import load_env, load_json, load_prompt, post_json

sys.stdout.reconfigure(encoding="utf-8")


def call(cfg, system, user):
    body = {
        "model": cfg["model"],
        "temperature": cfg["temperature"],
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if cfg.get("reasoning_effort"):
        body["reasoning_effort"] = cfg["reasoning_effort"]
    t0 = time.time()
    for attempt in range(4):
        try:
            resp = post_json(cfg["base_url"] + "/chat/completions", body,
                             {"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]})
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            m = re.search(r"try again in ([\d.]+)s", e.read().decode())
            wait = float(m.group(1)) + 1 if m else 20
            print(f"   (429 tokens-per-minute limit, waiting {wait:.0f}s)")
            time.sleep(wait)
            t0 = time.time()
    return json.loads(resp["choices"][0]["message"]["content"]), int((time.time() - t0) * 1000), resp.get("model")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--cls", help="prompt file name, default from config/rules.json")
    ap.add_argument("--enr", help="prompt file name, default from config/rules.json")
    args = ap.parse_args()

    load_env()
    if not os.environ.get("GROQ_API_KEY"):
        sys.exit("GROQ_API_KEY missing in .env")
    rules = load_json("config/rules.json")
    cfg = rules["llm"]
    args.cls = args.cls or rules["prompts"]["classification"]
    args.enr = args.enr or rules["prompts"]["enrichment"]
    golden = load_json("tests/golden.json")
    cases = golden["samples"] + (golden["edge_cases"] if args.edge else [])
    if args.only:
        cases = [c for c in cases if c["id"].startswith(args.only)]

    cls_sys, cls_user = load_prompt(args.cls)
    enr_sys, enr_user = load_prompt(args.enr)
    for c in cases:
        if not c["message"].strip():
            print(f"\n=== {c['id']}: empty, skipped (Normalize short-circuits it)")
            continue
        for run in range(args.runs):
            fill = lambda t: t.replace("{{source}}", c["source"]).replace("{{message}}", c["message"])
            try:
                cls, ms1, model = call(cfg, cls_sys, fill(cls_user))
                enr, ms2, _ = call(cfg, enr_sys, fill(enr_user))
            except urllib.error.HTTPError as e:
                print(f"\n=== {c['id']} HTTP {e.code}: {e.read().decode()[:400]}")
                continue
            print(f"\n=== {c['id']} run {run + 1} ({model}, {ms1}+{ms2} ms) expect={c['expect'].get('category')}")
            print("CLS", json.dumps(cls, ensure_ascii=False))
            print("ENR", json.dumps(enr, ensure_ascii=False))


if __name__ == "__main__":
    main()
