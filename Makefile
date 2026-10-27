.PHONY: all install lint test format migrate run seed check collectstatic deploy-check

.DEFAULT_GOAL := all

VENV := .venv
ifeq ($(OS),Windows_NT)
PYTHON ?= python
VENV_PY := $(VENV)/Scripts/python.exe
else
PYTHON ?= python3
VENV_PY := $(VENV)/bin/python
endif

PY := $(VENV_PY)
BLACK_TARGETS := EduXJY AIQandA manage.py
PYLINT_TARGETS := EduXJY AIQandA manage.py

all: install lint test

install:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

lint:
	$(PY) -m black --check $(BLACK_TARGETS)
	$(PY) -m pylint --persistent=n $(PYLINT_TARGETS)

test:
	$(PY) -m pytest

format:
	$(PY) -m black $(BLACK_TARGETS)

migrate:
	$(PY) manage.py migrate

run:
	$(PY) manage.py runserver 127.0.0.1:8000

seed:
	$(PY) manage.py seed_demo

check:
	$(PY) manage.py check
	$(PY) manage.py makemigrations --check --dry-run

collectstatic:
	$(PY) manage.py collectstatic --noinput

deploy-check:
	$(PY) manage.py check --deploy
