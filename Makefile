# Makefile for Python project

# Create or update requirements.txt
freeze:
	pip freeze > requirements.txt

# Run the server with uvicorn
run:
	uvicorn login:app --host 0.0.0.0 --port 8000 --reload

# Format code using black
prettier:
	black .

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests using pytest
test:
	pytest

# Clean up cache and temporary files
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} +
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .coverage

# Run type checking using mypy
typecheck:
	mypy .