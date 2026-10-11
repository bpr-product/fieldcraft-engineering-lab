# Publish FieldCraft to GitHub

Suggested new public repository: `BALA-PRADEEP/fieldcraft-engineering-lab`.

This is a standalone portfolio demo with invented records and mock external providers. Do not add employer-owned code, client data, credentials or internal documents.

## Option A: GitHub Desktop (Windows/macOS; easiest)

1. Extract `fieldcraft-engineering-lab-github-ready.zip`.
2. Sign in to GitHub Desktop as `BALA-PRADEEP`.
3. Select **File > Add local repository**, then choose the extracted `fieldcraft-engineering-lab` folder.
4. Select **Publish repository**; name it `fieldcraft-engineering-lab` and UNCHECK **Keep this code private**.
5. Verify `https://github.com/BALA-PRADEEP/fieldcraft-engineering-lab` now displays the README.

## Option B: Terminal

1. Extract the archive, enter the folder and sign in to GitHub with Git/GitHub CLI.
2. Create a new empty **public** GitHub repository named `fieldcraft-engineering-lab` at https://github.com/new. Do not initialize it with README, .gitignore or license.
3. Run:

```bash
git remote add origin https://github.com/BALA-PRADEEP/fieldcraft-engineering-lab.git
git push -u origin main
```

## Review before sharing

- Run `python -m pytest -q` and `python scripts/check_public_safe.py`.
- Manually check for sensitive terms, credentials, proprietary assets, and employer-owned content. A text scan cannot verify intellectual property ownership.
- Confirm the repository is public and its README accurately describes synthetic and mocked capabilities.
- Only share a link after the public page is verified.

The attached archive contains a freshly created Git commit history, not the history of any private employer repository.
