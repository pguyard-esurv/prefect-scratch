.PHONY: help install install-dev clean lint format test run run-rpa1 run-rpa2 run-rpa3 run-all check pre-commit activate test-unit test-integration test-coverage test-watch info setup-dev setup-staging setup-prod setup-all list-config run-dev run-staging run-prod run-rpa1-dev run-rpa1-staging run-rpa1-prod run-rpa2-dev run-rpa2-staging run-rpa2-prod run-rpa3-dev run-rpa3-staging run-rpa3-prod dev-setup dev-status dev-rebuild dev-test dev-logs dev-debug dev-watch dev-stop dev-clean docker-build docker-up docker-down docker-logs serve-flows serve-rpa1 serve-rpa2 serve-rpa3 discover-flows build-deployments deploy-python deploy-containers deploy-all clean-deployments deploy-dev deploy-staging deploy-prod validate-deployments deployment-status deploy-dev-python deploy-dev-containers deploy-staging-python deploy-staging-containers deploy-prod-python deploy-prod-containers

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install production dependencies
	uv sync --no-dev

install-dev: ## Install development dependencies
	uv sync

# Development
clean: ## Clean up temporary files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf flows/rpa1/data/*.csv
	rm -rf flows/rpa1/data/*.json
	rm -rf flows/rpa1/output/*.json
	rm -rf flows/rpa2/data/*.csv
	rm -rf flows/rpa2/data/*.json
	rm -rf flows/rpa2/output/*.json

lint: ## Run linting with ruff
	uv run ruff check .

format: ## Format code with ruff
	uv run ruff format .

check: lint ## Run all checks (linting)

# Testing
test: ## Run all tests
	uv run pytest

test-ultra-fast: ## Run ultra-fast unit tests only (exclude workflows, docker, filesystem)
	uv run pytest -m "not slow" --ignore=flows/ --ignore=core/test/test_base_image_build.py --ignore=core/test/test_base_image_health.py --ignore=core/test/test_container_config.py --ignore=core/test/test_container_lifecycle_manager.py --ignore=core/test/test_container_lifecycle_validation.py --ignore=core/test/test_automated_container_framework.py --maxfail=5

test-fast: ## Run fast tests only (skip slow tests)
	uv run pytest -m "not slow" --maxfail=10

test-slow: ## Run slow tests only
	uv run pytest -m slow -v

test-unit: ## Run unit tests only
	uv run pytest -m unit

test-integration: ## Run integration tests only
	uv run pytest -m integration

test-coverage: ## Run tests with coverage report
	uv run pytest --cov=core --cov=flows --cov-report=html --cov-report=term-missing

test-coverage-fast: ## Run fast tests with coverage report
	uv run pytest -m "not slow" --cov=core --cov=flows --cov-report=html --cov-report=term-missing

test-watch: ## Run tests in watch mode
	uv run pytest-watch

test-watch-fast: ## Run fast tests in watch mode
	uv run pytest-watch --args="-m 'not slow'"

# Running workflows
run: ## Run all RPA workflows
	uv run python main.py

run-rpa1: ## Run RPA1 workflow only
	uv run python main.py rpa1

run-rpa2: ## Run RPA2 workflow only
	uv run python main.py rpa2

run-all: ## Run all RPA workflows (same as run)
	uv run python main.py all

# Flow registration and deployment (makes flows appear in Prefect UI)
serve-flows: ## Register all flows with Prefect server (makes them appear in UI)
	export PREFECT_API_URL=http://localhost:4200/api && uv run python register_flows.py

serve-deployments: ## Serve flows as deployments (allows running from UI)
	export PREFECT_API_URL=http://localhost:4200/api && uv run python deploy_all_flows.py

serve-rpa1: ## Register RPA1 flow with Prefect server
	export PREFECT_API_URL=http://localhost:4200/api && uv run python -c "from flows.rpa1.workflow import rpa1_workflow; print(f'Registered flow: {rpa1_workflow.name}')"

serve-rpa2: ## Register RPA2 flow with Prefect server
	export PREFECT_API_URL=http://localhost:4200/api && uv run python -c "from flows.rpa2.workflow import rpa2_workflow; print(f'Registered flow: {rpa2_workflow.name}')"

serve-rpa3: ## Register RPA3 flow with Prefect server
	export PREFECT_API_URL=http://localhost:4200/api && uv run python -c "from flows.rpa3.workflow import rpa3_workflow; print(f'Registered flow: {rpa3_workflow.name}')"

# Pre-commit checks
pre-commit: format lint test-ultra-fast ## Run pre-commit checks (ultra-fast tests only)

pre-commit-full: format lint test ## Run complete pre-commit checks (including slow tests)

# Development setup
setup: install-dev ## Set up development environment
	@echo "Development environment set up successfully!"
	@echo "Run 'make help' to see available commands"

activate: ## Activate the virtual environment
	@echo "To activate the virtual environment, run:"
	@echo "  source .venv/bin/activate"
	@echo ""
	@echo "Or use uv to run commands directly:"
	@echo "  uv run python main.py"
	@echo "  uv run pytest"

# Environment setup
setup-dev: ## Set up development environment configuration
	uv run python scripts/setup_environments.py development

setup-staging: ## Set up staging environment configuration
	uv run python scripts/setup_environments.py staging

setup-prod: ## Set up production environment configuration
	uv run python scripts/setup_environments.py production

setup-all: setup-dev setup-staging setup-prod ## Set up all environments

list-config: ## List current configurations
	uv run python scripts/setup_environments.py list

# Environment-specific runs
run-dev: ## Run workflows in development mode
	PREFECT_ENVIRONMENT=development uv run python main.py

run-staging: ## Run workflows in staging mode
	PREFECT_ENVIRONMENT=staging uv run python main.py

run-prod: ## Run workflows in production mode
	PREFECT_ENVIRONMENT=production uv run python main.py

run-rpa1-dev: ## Run RPA1 workflow in development mode
	PREFECT_ENVIRONMENT=development uv run python main.py rpa1

run-rpa1-staging: ## Run RPA1 workflow in staging mode
	PREFECT_ENVIRONMENT=staging uv run python main.py rpa1

run-rpa1-prod: ## Run RPA1 workflow in production mode
	PREFECT_ENVIRONMENT=production uv run python main.py rpa1

run-rpa2-dev: ## Run RPA2 workflow in development mode
	PREFECT_ENVIRONMENT=development uv run python main.py rpa2

run-rpa2-staging: ## Run RPA2 workflow in staging mode
	PREFECT_ENVIRONMENT=staging uv run python main.py rpa2

run-rpa2-prod: ## Run RPA2 workflow in production mode
	PREFECT_ENVIRONMENT=production uv run python main.py rpa2

run-rpa3: ## Run RPA3 workflow only
	uv run python main.py rpa3

run-rpa3-dev: ## Run RPA3 workflow in development mode
	PREFECT_ENVIRONMENT=development uv run python main.py rpa3

run-rpa3-staging: ## Run RPA3 workflow in staging mode
	PREFECT_ENVIRONMENT=staging uv run python main.py rpa3

run-rpa3-prod: ## Run RPA3 workflow in production mode
	PREFECT_ENVIRONMENT=production uv run python main.py rpa3

# Development Workflow Commands
dev-setup: ## Set up complete development environment
	uv run python scripts/dev_workflow.py env setup

dev-status: ## Show development environment status
	uv run python scripts/dev_workflow.py dashboard status

dev-rebuild: ## Rebuild and restart all containers
	uv run python scripts/dev_workflow.py containers rebuild

dev-test: ## Run smart tests based on recent changes
	uv run python scripts/dev_workflow.py test smart

dev-logs: ## Show logs from all containers
	uv run python scripts/dev_workflow.py utils logs

dev-debug: ## Open debugging dashboard
	uv run python scripts/debug_toolkit.py dashboard status

dev-watch: ## Start file watcher for hot reloading
	docker-compose --profile development up -d file-watcher

dev-stop: ## Stop all development containers
	docker-compose down

dev-clean: ## Clean up development environment
	docker-compose down -v
	docker system prune -f

# Docker Container Commands
docker-build: ## Build all container images
	./scripts/build_all.sh

docker-up: ## Start all containers
	docker-compose up -d

docker-down: ## Stop all containers
	docker-compose down

docker-logs: ## Show logs from all containers
	docker-compose logs -f

# Fast Test Commands
test-smart: ## Run smart tests (changed files only)
	uv run python scripts/fast_test_runner.py smart

test-suite: ## Run specific test suite (usage: make test-suite SUITE=unit)
	uv run python scripts/fast_test_runner.py suite --suite $(SUITE)

test-all: ## Run all test suites
	uv run python scripts/fast_test_runner.py all

# Container Testing Commands
test-container: ## Run container-specific tests
	uv run python scripts/dev_workflow.py test container

test-distributed: ## Run distributed processing tests
	docker-compose run --rm test-runner python -m pytest core/test/test_distributed_*.py -v

test-performance: ## Run performance tests
	docker-compose run --rm test-runner python -m pytest -m performance -v

# Database Commands
db-inspect: ## Open database inspector (pgAdmin)
	docker-compose --profile development up -d db-inspector
	@echo "Database inspector available at http://localhost:8080"
	@echo "Email: dev@rpa.local, Password: dev_password"

db-query: ## Run database query (usage: make db-query QUERY="SELECT * FROM table")
	uv run python scripts/debug_toolkit.py database query --query "$(QUERY)"

db-status: ## Show database status
	uv run python scripts/debug_toolkit.py database test

# Log Analysis Commands
logs-search: ## Search logs for pattern (usage: make logs-search PATTERN="error")
	uv run python scripts/debug_toolkit.py logs search --pattern "$(PATTERN)"

logs-tail: ## Tail specific log file (usage: make logs-tail FILE="rpa1/workflow.log")
	uv run python scripts/debug_toolkit.py logs tail --file "$(FILE)"

logs-list: ## List all log files
	uv run python scripts/debug_toolkit.py logs list

# Container Management Commands
containers-list: ## List all containers
	uv run python scripts/debug_toolkit.py containers list

containers-stats: ## Show container resource usage
	uv run python scripts/debug_toolkit.py containers stats --name rpa-rpa1-worker

containers-exec: ## Execute command in container (usage: make containers-exec CONTAINER=rpa-rpa1-worker CMD="ls -la")
	uv run python scripts/debug_toolkit.py containers exec --name $(CONTAINER) --command "$(CMD)"

# Project info
info: ## Show project information
	@echo "Project: prefect-rpa-solution"
	@echo "Python version: $(shell python --version)"
	@echo "UV version: $(shell uv --version)"
	@echo "Ruff version: $(shell uv run ruff --version)"
	@echo ""
	@echo "Available workflows:"
	@echo "  - RPA1: File processing and data transformation"
	@echo "  - RPA2: Data validation and reporting"
	@echo "  - RPA3: Concurrent data processing demo using .map()"
	@echo ""
	@echo "Environment configuration:"
	@echo "  - Development: Local development with debug settings"
	@echo "  - Staging: Testing environment with production-like settings"
	@echo "  - Production: Production environment with optimized settings"
	@echo ""
	@echo "Development workflow commands:"
	@echo "  - make dev-setup: Set up complete development environment"
	@echo "  - make dev-status: Show development environment status"
	@echo "  - make dev-test: Run smart tests based on recent changes"
	@echo "  - make test-ultra-fast: Run ultra-fast unit tests only (~20s, recommended for development)"
	@echo "  - make test-fast: Run fast tests only (skip slow tests)"
	@echo "  - make test-slow: Run slow tests only"
	@echo "  - make test-smart: Run tests for changed files only"
	@echo "  - make db-inspect: Open database inspector"
	@echo "  - make dev-logs: Show container logs"
	@echo ""
	@echo "Flow registration and deployment commands:"
	@echo "  - make serve-flows: Register all flows with Prefect server"
	@echo "  - make serve-deployments: Serve flows as deployments (allows running from UI)"
	@echo "  - make serve-rpa1: Register RPA1 flow only"
	@echo "  - make serve-rpa2: Register RPA2 flow only"
	@echo "  - make serve-rpa3: Register RPA3 flow only"
	@echo ""
	@echo "Deployment system commands:"
	@echo "  - make discover-flows: Discover and list all available flows"
	@echo "  - make build-deployments: Build deployments for all flows"
	@echo "  - make deploy-python: Deploy Python-based deployments"
	@echo "  - make deploy-containers: Deploy container-based deployments"
	@echo "  - make deploy-all: Deploy all deployments (Python and Docker)"
	@echo "  - make clean-deployments: Remove existing deployments"
	@echo "  - make deploy-dev: Deploy to development environment"
	@echo "  - make deploy-staging: Deploy to staging environment"
	@echo "  - make deploy-prod: Deploy to production environment"
	@echo "  - make validate-deployments: Validate deployment configurations"
	@echo "  - make deployment-status: Show deployment system status"


# Deployment System Commands
discover-flows: ## Discover and list all available flows
	uv run python -m deployment_system.cli.main discover-flows

build-deployments: ## Build deployments for all flows
	uv run python -m deployment_system.cli.main build-deployments --environment development

deploy-python: ## Deploy Python-based deployments
	uv run python -m deployment_system.cli.main deploy-python --environment development

deploy-containers: ## Deploy container-based deployments
	uv run python -m deployment_system.cli.main deploy-containers --environment development

deploy-all: ## Deploy all deployments (Python and Docker)
	uv run python -m deployment_system.cli.main deploy-all --environment development

clean-deployments: ## Remove existing deployments
	uv run python -m deployment_system.cli.main clean-deployments --confirm

deploy-dev: ## Deploy to development environment
	uv run python -m deployment_system.cli.main deploy-dev --type all

deploy-staging: ## Deploy to staging environment
	uv run python -m deployment_system.cli.main deploy-staging --type all

deploy-prod: ## Deploy to production environment
	uv run python -m deployment_system.cli.main deploy-prod --type all

validate-deployments: ## Validate deployment configurations
	uv run python -m deployment_system.cli.main validate-deployments --environment development

deployment-status: ## Show deployment system status
	uv run python -m deployment_system.cli.main status

# Environment-specific deployment commands with type options
deploy-dev-python: ## Deploy Python deployments to development
	uv run python -m deployment_system.cli.main deploy-dev --type python

deploy-dev-containers: ## Deploy container deployments to development
	uv run python -m deployment_system.cli.main deploy-dev --type docker

deploy-staging-python: ## Deploy Python deployments to staging
	uv run python -m deployment_system.cli.main deploy-staging --type python

deploy-staging-containers: ## Deploy container deployments to staging
	uv run python -m deployment_system.cli.main deploy-staging --type docker

deploy-prod-python: ## Deploy Python deployments to production
	uv run python -m deployment_system.cli.main deploy-prod --type python

deploy-prod-containers: ## Deploy container deployments to production
	uv run python -m deployment_system.cli.main deploy-prod --type docker

# UI Integration and Verification Commands
check-ui: ## Check Prefect UI connectivity and accessibility
	uv run python -m deployment_system.cli.main check-ui

verify-deployment-ui: ## Verify specific deployment appears in UI (requires DEPLOYMENT_NAME and FLOW_NAME)
	@if [ -z "$(DEPLOYMENT_NAME)" ] || [ -z "$(FLOW_NAME)" ]; then \
		echo "Error: Please specify DEPLOYMENT_NAME and FLOW_NAME"; \
		echo "Usage: make verify-deployment-ui DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow"; \
		exit 1; \
	fi
	uv run python -m deployment_system.cli.main verify-deployment-ui --deployment-name "$(DEPLOYMENT_NAME)" --flow-name "$(FLOW_NAME)"

check-deployment-health: ## Check health of specific deployment (requires DEPLOYMENT_NAME and FLOW_NAME)
	@if [ -z "$(DEPLOYMENT_NAME)" ] || [ -z "$(FLOW_NAME)" ]; then \
		echo "Error: Please specify DEPLOYMENT_NAME and FLOW_NAME"; \
		echo "Usage: make check-deployment-health DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow"; \
		exit 1; \
	fi
	uv run python -m deployment_system.cli.main check-deployment-health --deployment-name "$(DEPLOYMENT_NAME)" --flow-name "$(FLOW_NAME)"

deployment-status-report: ## Generate comprehensive deployment status report
	uv run python -m deployment_system.cli.main deployment-status-report

validate-ui: ## Validate all deployments visibility in UI
	uv run python -m deployment_system.cli.main validate-ui

troubleshoot-ui: ## Run UI connectivity troubleshooting
	uv run python -m deployment_system.cli.main troubleshoot-ui

troubleshoot-deployment: ## Troubleshoot specific deployment visibility (requires DEPLOYMENT_NAME and FLOW_NAME)
	@if [ -z "$(DEPLOYMENT_NAME)" ] || [ -z "$(FLOW_NAME)" ]; then \
		echo "Error: Please specify DEPLOYMENT_NAME and FLOW_NAME"; \
		echo "Usage: make troubleshoot-deployment DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow"; \
		exit 1; \
	fi
	uv run python -m deployment_system.cli.main troubleshoot-deployment --deployment-name "$(DEPLOYMENT_NAME)" --flow-name "$(FLOW_NAME)"

wait-deployment-ready: ## Wait for deployment to become ready (requires DEPLOYMENT_NAME and FLOW_NAME)
	@if [ -z "$(DEPLOYMENT_NAME)" ] || [ -z "$(FLOW_NAME)" ]; then \
		echo "Error: Please specify DEPLOYMENT_NAME and FLOW_NAME"; \
		echo "Usage: make wait-deployment-ready DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow"; \
		exit 1; \
	fi
	uv run python -m deployment_system.cli.main wait-deployment-ready --deployment-name "$(DEPLOYMENT_NAME)" --flow-name "$(FLOW_NAME)"

list-deployments-ui: ## List all deployments with UI status
	uv run python -m deployment_system.cli.main list-deployments-ui

get-deployment-url: ## Get UI URL for specific deployment (requires DEPLOYMENT_NAME and FLOW_NAME)
	@if [ -z "$(DEPLOYMENT_NAME)" ] || [ -z "$(FLOW_NAME)" ]; then \
		echo "Error: Please specify DEPLOYMENT_NAME and FLOW_NAME"; \
		echo "Usage: make get-deployment-url DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow"; \
		exit 1; \
	fi
	uv run python -m deployment_system.cli.main get-deployment-url --deployment-name "$(DEPLOYMENT_NAME)" --flow-name "$(FLOW_NAME)"