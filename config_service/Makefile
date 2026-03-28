.PHONY: help venv install test lint typecheck run rds-tunnel rds-tunnel-aws ui-tunnel migrate seed issue-token deploy

VENV ?= .venv
PY   ?= $(VENV)/bin/python3
PIP  ?= $(VENV)/bin/pip

AWS_PROFILE ?= playground
AWS_REGION  ?= us-west-2

help:
	@echo "OpenSRE Config Service — common commands"
	@echo ""
	@echo "Local:"
	@echo "  make venv        - create venv + install deps"
	@echo "  make test        - run tests"
	@echo "  make lint        - ruff check src/"
	@echo "  make typecheck   - mypy src/"
	@echo "  make run         - run API/UI on :8080 (requires .env exported)"
	@echo "  make rds-tunnel  - start SSM tunnel to RDS on localhost:5433 (via ../database/scripts)"
	@echo "  make migrate     - run alembic migrations (uses config_service/.env / DATABASE_URL_TUNNEL)"
	@echo "  make seed        - seed demo data"
	@echo "  make issue-token - issue a demo team token"
	@echo ""
	@echo "AWS:"
	@echo "  make deploy      - terraform + docker build/push + ECS rollout (internal ALB)"
	@echo "  make ui-tunnel   - start SSM tunnel to internal ALB on localhost:8081"

venv:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

install: venv

test:
	$(PY) -m pytest -q

lint:
	$(VENV)/bin/ruff check src/

typecheck:
	$(VENV)/bin/mypy src/

run:
	$(VENV)/bin/uvicorn src.api.main:app --reload --port 8080

rds-tunnel:
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ../database/scripts/rds_tunnel.sh

rds-tunnel-aws: rds-tunnel

ui-tunnel:
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./scripts/ui_tunnel_aws.sh

migrate:
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./scripts/db_migrate.sh

seed:
	$(PY) scripts/seed_demo_data.py

issue-token:
	$(PY) scripts/issue_team_token.py --org-id org1 --team-node-id teamA

deploy:
	AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) ./scripts/deploy_app_ecs.sh


