# Datacebo Backend

FastAPI app with SQLite, Pydantic v2, and pytest.

## Install

Create a venv and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run

```bash
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```
