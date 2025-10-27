# Repository Guidelines

## Project Structure & Module Organization
Application code lives in `app/`, with API routers under `app/api`, orchestration logic in `app/services`, and database layers split between `app/models`, `app/crud`, and `app/db`. Templates and static assets are in `app/templates` and `app/static`, while automation scripts sit in `scripts/`. Integration and API tests reside in `tests/`, and reference material is collected under `docs/` for architecture, API, and Playwright details.

## Build, Test, and Development Commands
Use Docker for parity with production: `docker-compose up --build -d` starts the web, worker, and backing services; follow with `docker-compose exec web alembic upgrade head` to apply migrations. For local iteration without containers, activate the venv, install requirements, then run `uvicorn app.main:app --reload --port 8000`. Celery tasks run via `celery -A app.worker worker --loglevel=info`. Execute end-to-end tests with `docker-compose exec web pytest` or `pytest tests/` when running locally.

## Coding Style & Naming Conventions
Default to PEP 8 with four-space indentation. Follow the existing scheme: PascalCase classes, snake_case functions and variables, and UPPER_SNAKE_CASE constants. Type hints are required on public functions and methods; add Google-style docstrings when logic is non-trivial. Keep imports sorted as stdlib, third-party, then local. Before opening a pull request, run `black app/`, `flake8 app/`, and `mypy app/` to match the automation.

## Testing Guidelines
Pytest is the standard framework; name files `test_*.py` and mirror the module under test (for example, `tests/api/test_tasks.py`). Prioritize fixture reuse for Playwright-heavy flows to keep runs fast. Aim to maintain or improve coverage by running `pytest --cov=app tests/` and add assertions for regression-prone Celery and Playwright paths. Include screenshots or logs in `uploads/` when diagnosing failures.

## Commit & Pull Request Guidelines
Commits follow concise, imperative headlines similar to `Enhance robot detection and improve error handling in style posting process`; separate body paragraphs explain rationale and side effects. Each pull request should summarize user-facing impact, list key changes, and link issues or task IDs. Provide testing notes (`pytest`, `docker-compose up`, etc.) and screenshots for UI adjustments. Keep branches rebased to avoid noisy history during review.

## Security & Configuration Tips
Secrets are injected through `.env`; copy from `.env.example`, then replace `SECRET_KEY`, `ENCRYPTION_KEY`, and service credentials before deploying. Protect user and SALON BOARD credentials by using the bundled `scripts/create_admin.py` helper instead of manual inserts. When working on browser automation, scrub sensitive data from logs before committing and verify encrypted fields via the Fernet helpers in `app/core/security.py`.
