# Public repository review checklist

Do not publish the original archives or any private employer source files. This independent codebase should contain only invented example data and newly written illustrative logic.

- [ ] No employer or customer names, identifiers, tickets, URLs, or brand assets.
- [ ] No private schema migrations, test fixtures, screenshots, API responses or internal docs.
- [ ] No `.env`, API tokens, session cookies, signing keys, certificates or production endpoints.
- [ ] No committed local `.sqlite3` files or run artifacts.
- [ ] No descriptions claiming this is a real provider-integrated production system.
- [ ] Every user/record/company shown in a screenshot is fictional.
- [ ] Tests pass: `python -m pytest`.
- [ ] Public-content check passes: `python scripts/check_public_safe.py`.
- [ ] README and case studies reflect what the repository actually runs.
- [ ] Choose a repository license and review employer IP/confidentiality terms before publication.

Before publishing to GitHub, inspect `git status`, review every file, and push this new standalone directory only. Never add files directly from an employer archive, even if identifiers have been renamed.

Git commands to run after you have reviewed and approved the files:

```bash
git init
git add .
git diff --cached --stat
git commit -m "Build independent engineering systems showcase"
# Create a new repository in your own GitHub account, then add its URL:
git remote add origin <YOUR_NEW_GITHUB_REPO_URL>
git branch -M main
git push -u origin main
```

The placeholder remote URL is intentional; no external account is connected or modified as part of this local package.
