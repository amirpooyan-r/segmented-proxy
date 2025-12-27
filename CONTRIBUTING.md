# Contributing

Thanks for contributing to SegmentedProxy.
This project is for learning, so clear and small changes help a lot.

## Requirements
- Python 3.10+

## Setup
```bash
python -m venv .venv
```

Activate the environment:

- Linux/macOS:
  ```bash
  source .venv/bin/activate
  ```
- Windows:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

Install dev dependencies:
```bash
pip install -e .[dev]
```

## Checks
```bash
ruff check .
ruff format .
pytest -q
```

## Pull Requests
- Keep PRs small and focused.
- Explain why the change is needed, not only what changed.
