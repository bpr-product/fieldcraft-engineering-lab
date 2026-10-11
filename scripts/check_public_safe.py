"""Conservative public-content scan; not a substitute for manual source review."""
from __future__ import annotations
from pathlib import Path
import re
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', '__pycache__', '.pytest_cache', 'data', 'artifacts', 'output'}
TEXT_EXTS = {'.py', '.js', '.css', '.html', '.md', '.toml', '.txt', '.example', '.ipynb', '.gitignore', '.yml', '.yaml'}
# Supply organization-specific blocked terms at review time without placing
# private identifiers into the public repository itself.
BLOCKED_TERMS = [x.strip() for x in os.getenv("PUBLIC_BLOCKLIST", "").split(",") if x.strip()]
FORBIDDEN = [re.compile(re.escape(s), re.IGNORECASE) for s in BLOCKED_TERMS]
# Avoid checking the scan rule definitions against themselves.
issues = []
for f in ROOT.rglob('*'):
    if not f.is_file() or set(f.relative_to(ROOT).parts).intersection(SKIP):
        continue
    if f.name in ('check_public_safe.py',):
        continue
    if f.suffix not in TEXT_EXTS and f.name not in ('.gitignore',):
        continue
    if f.stat().st_size > 2_000_000:
        issues.append(f'{f.relative_to(ROOT)}: unexpectedly large text file')
        continue
    content = f.read_text(encoding='utf-8', errors='replace')
    for rule in FORBIDDEN:
        if rule.search(content):
            issues.append(f'{f.relative_to(ROOT)}: forbidden employer reference')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', content):
        issues.append(f'{f.relative_to(ROOT)}: private key material')
    if re.search(r'(?im)^\s*(?:LLM_API_KEY|AWS_SECRET_ACCESS_KEY|AZURE_CLIENT_SECRET)\s*=\s*[^\s#]+', content):
        issues.append(f'{f.relative_to(ROOT)}: possible hardcoded secret')
if issues:
    print('PUBLIC CONTENT REVIEW FAILED:')
    for issue in issues: print(' -', issue)
    sys.exit(1)
print('Pass: no listed blocked terms or obvious key patterns in published text files.')
print('Reminder: human review for licenses, embedded values and intellectual property is still required.')
