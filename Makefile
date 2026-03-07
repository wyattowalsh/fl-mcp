.PHONY: test quality

test:
	python -m pytest

quality: test
