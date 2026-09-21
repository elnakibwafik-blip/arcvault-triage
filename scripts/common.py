"""Small shared helpers for the scripts (stdlib only)."""
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Minimal .env reader so no python-dotenv dependency is needed."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_prompt(name):
    """Split prompts/<name>.md into (system, user_template) on '## System' / '## User'."""
    text = (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    m = re.search(r"^## System\s*$(.*?)^## User\s*$(.*)", text, re.S | re.M)
    if not m:
        raise ValueError(f"prompt {name} missing '## System' / '## User' sections")
    return m.group(1).strip(), m.group(2).strip()


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def post_json(url, payload, headers=None, timeout=90):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json",
                                          # Some edges (Cloudflare) reject urllib's default UA.
                                          "User-Agent": "arcvault-triage-scripts/1.0",
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
