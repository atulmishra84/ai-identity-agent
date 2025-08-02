install:
	pyenv local 3.11.9 || true
	python3 -m venv .venv && \
	source .venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt

run:
	source .venv/bin/activate && \
	uvicorn main:app --reload

setup:
	make install && make run

lint:
	ruff check . --fix

format:
	black .

typecheck:
	mypy .

