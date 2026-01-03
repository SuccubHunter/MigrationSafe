# Makefile example with migsafe integration
#
# Usage:
#   make check-migrations      - check all migrations (strict mode)
#   make check-migrations-soft - check with warnings (soft mode)
#   make migration-report      - generate HTML report

.PHONY: check-migrations check-migrations-soft migration-report help

# Path to migrations directory (configure for your project)
MIGRATIONS_DIR ?= migrations
ALEMBIC_VERSIONS_DIR ?= alembic/versions

# Report format
REPORT_FORMAT ?= junit
REPORT_FILE ?= migsafe-report.xml

help:
	@echo "Available commands:"
	@echo "  make check-migrations      - strict migration check (fails on critical issues)"
	@echo "  make check-migrations-soft - soft check (warnings only)"
	@echo "  make migration-report      - generate HTML report"
	@echo ""
	@echo "Variables:"
	@echo "  MIGRATIONS_DIR=$(MIGRATIONS_DIR)"
	@echo "  REPORT_FORMAT=$(REPORT_FORMAT)"
	@echo "  REPORT_FILE=$(REPORT_FILE)"

# Strict mode: fails on critical issues
check-migrations:
	@echo "🔍 Checking migrations (strict mode)..."
	@migsafe lint \
		--format $(REPORT_FORMAT) \
		--output $(REPORT_FILE) \
		--no-color \
		$(MIGRATIONS_DIR) $(ALEMBIC_VERSIONS_DIR)
	@echo "✅ Check completed. Report: $(REPORT_FILE)"

# Soft mode: shows issues but doesn't fail
check-migrations-soft:
	@echo "🔍 Checking migrations (soft mode)..."
	@migsafe analyze \
		--format text \
		--no-color \
		--severity warning \
		$(MIGRATIONS_DIR) $(ALEMBIC_VERSIONS_DIR) || true
	@echo "✅ Check completed (soft mode)"

# Generate HTML report
migration-report:
	@echo "📊 Generating HTML report..."
	@migsafe analyze \
		--format html \
		--output migsafe-report.html \
		--no-color \
		$(MIGRATIONS_DIR) $(ALEMBIC_VERSIONS_DIR)
	@echo "✅ HTML report created: migsafe-report.html"

# Check specific file
check-migration:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Specify file: make check-migration FILE=path/to/migration.py"; \
		exit 1; \
	fi
	@echo "🔍 Checking file: $(FILE)"
	@migsafe lint --no-color $(FILE)

# Integration into existing testing process
test: check-migrations
	@echo "🧪 Running tests..."
	# Your commands to run tests
	@pytest

# CI mode: for use in CI/CD
ci-check-migrations:
	@migsafe lint \
		--format junit \
		--output migsafe-report.xml \
		--no-color \
		$(MIGRATIONS_DIR) $(ALEMBIC_VERSIONS_DIR)
