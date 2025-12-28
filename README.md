# Bounty Go (local dev)

This repository is a small Flask app for posting and claiming bounties.

## Quick start (local)

1. Create and activate virtualenv:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirement.txt
```

3. Set environment variables:

```powershell
$env:SECRET_KEY = 'a_strong_secret_here'
```

4. Run the app:

```powershell
python app.py
```

## Docker (recommended for consistent environment)

Build and run with docker-compose:

```bash
docker compose build
docker compose up -d
```

The app will be available at `http://localhost:5000`.

## Important notes

- Set a strong `SECRET_KEY` in production. Do not commit secrets.
- Consider using an external DB (Postgres) for production, and configure migrations.
- CI workflow was intentionally removed from the branch push; add workflow via GitHub UI or push with a PAT that has `workflow` scope if you want the CI file in the repo.

