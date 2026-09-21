"""Build the submission file output/records.json from output/records.jsonl.

Takes the most recent record for each of the 5 brief samples (matched on the
raw message text), validates each against schema/record.schema.json, and writes
them in sample order as a pretty-printed array. Records are copied as-is and
never edited by hand.

    python scripts/assemble_output.py
"""
import json
import sys

from jsonschema import Draft202012Validator, FormatChecker

from common import ROOT, load_json

sys.stdout.reconfigure(encoding="utf-8")


def main():
    src = ROOT / "output" / "records.jsonl"
    if not src.exists():
        sys.exit("output/records.jsonl not found - run scripts/send_samples.py first")
    records = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    samples = load_json("tests/golden.json")["samples"]
    validator = Draft202012Validator(load_json("schema/record.schema.json"), format_checker=FormatChecker())

    chosen, ok = [], True
    for s in samples:
        matches = [r for r in records if r.get("raw_message") == s["message"].strip()]
        if not matches:
            print(f"{s['id']}: MISSING (no record for this sample yet)")
            ok = False
            continue
        rec = max(matches, key=lambda r: r["received_at"])
        errors = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
        status = "valid" if not errors else f"{len(errors)} schema error(s)"
        print(f"{s['id']}: {status}  record_id={rec['record_id']}")
        for e in errors:
            print(f"    {'/'.join(map(str, e.path))}: {e.message}")
        ok = ok and not errors
        chosen.append(rec)

    out = ROOT / "output" / "records.json"
    out.write_text(json.dumps(chosen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)} with {len(chosen)} record(s); all valid: {ok}")
    sys.exit(0 if ok and len(chosen) == len(samples) else 1)


if __name__ == "__main__":
    main()
