.DEFAULT_GOAL := help

WEB_DIR  := apps/web
PY_SRC   := packages/stackwarden/src

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

.PHONY: install
install: ## Install all dependencies (Python editable + npm)
	pip install -e ".[dev,wizard,web]"
	npm ci --prefix $(WEB_DIR)

.PHONY: dev-web
dev-web: ## Start the Vue dev server
	npm run dev --prefix $(WEB_DIR)

.PHONY: dev-api
dev-api: ## Start the backend API server
	stackwarden-web

.PHONY: services-up
services-up: ## Stand up backend + frontend services
	ops/scripts/standup_services.sh

.PHONY: services-down
services-down: ## Tear down running services
	ops/scripts/teardown_services.sh

.PHONY: services-recycle
services-recycle: ## Recycle (restart) all services
	ops/scripts/recycle_services.sh

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff linter on Python source and tests
	ruff check $(PY_SRC) tests/

.PHONY: lint-fix
lint-fix: ## Auto-fix ruff lint issues
	ruff check --fix $(PY_SRC) tests/

.PHONY: format
format: ## Format Python source with ruff
	ruff format $(PY_SRC) tests/

.PHONY: typecheck
typecheck: ## Run mypy on Python source
	mypy $(PY_SRC)

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: test-py test-web ## Run all tests

.PHONY: test-py
test-py: ## Run Python backend tests
	pytest tests/ -q --ignore=tests/test_build_integration.py

.PHONY: test-web
test-web: ## Run Vue frontend tests
	npm run test --prefix $(WEB_DIR)

.PHONY: test-stress-e2e
test-stress-e2e: ## Run CLI+API end-to-end stress tests
	pytest tests/test_stress_e2e_cli_web.py -q

.PHONY: test-cov
test-cov: ## Run Python tests with coverage
	pytest tests/ -q --ignore=tests/test_build_integration.py --cov=stackwarden --cov-report=term-missing

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

.PHONY: build-web
build-web: ## Build the Vue frontend for production
	npm run build --prefix $(WEB_DIR)

.PHONY: build
build: build-web ## Build all artifacts

# ---------------------------------------------------------------------------
# CI (mirrors .github/workflows/ci.yml)
# ---------------------------------------------------------------------------

.PHONY: ci
ci: lint test build ## Run the full CI pipeline locally

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	rm -rf $(WEB_DIR)/dist

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
