# Repository Guidelines

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, standard-library imports before third-party imports, and clear snake_case names for functions, variables, and modules. Keep path handling based on `pathlib.Path` and resolve repository-relative paths through the existing helper pattern. Prefer explicit data field names such as `trade_date`, `total_margin_balance_yuan`, and `top5pct_concentration` over abbreviated names. Keep user-facing dashboard text in Chinese where the existing script does.

## Testing Guidelines

Tests use `pytest` and `unittest` style test cases. Add tests under `tests/` with names like `test_security_market_pulse.py` and test methods beginning with `test`_. Prefer temporary SQLite databases via `tempfile.TemporaryDirectory()` so tests do not mutate `data/market_data.sqlite`. Cover database schema changes, payload generation, HTML output, and fetch/update edge cases.

## Commit & Pull Request Guidelines

Recent history uses concise imperative messages, with optional Conventional Commit prefixes, for example `chore: ignore .workbuddy and PRD.md` and `Add A-share top concentration dashboard`. Keep commits focused on one behavior or documentation change. Pull requests should include a short summary, commands run (`python3 -m pytest`), affected dashboards, linked issues when applicable, and screenshots or generated HTML notes for visual changes.

## Security & Configuration Tips

Do not commit `.env`, API tokens, or private database snapshots. `TUSHARE_TOKEN` should be supplied through the environment or `.env`. Use `--skip-fetch` when validating rendering without external network calls.

## **重要提示**

- 写任何代码前必须完整阅读 memory-bank/architecture.md
- 写任何代码前必须完整阅读 memory-bank/design-document.md
- 每完成一个重大功能或里程碑后，必须更新 memory-bank/architecture.md 和 memory-bank/progress.md