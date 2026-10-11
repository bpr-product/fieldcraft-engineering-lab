.PHONY: install test demo check
install:
	python -m pip install -e '.[dev]'
test:
	python -m pytest
check:
	python scripts/check_public_safe.py
demo:
	uvicorn fieldcraft.api:app --reload --app-dir src --port 8000
