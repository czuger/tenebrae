# Ave Tenebrae - running the test suite.
#
# `make test` brings up a test MongoDB in a container, waits for it to answer, then runs pytest
# pointing it at it. That is the way to check the repository: everything one wants to verify is
# written as a test and replayed by this command - the application is not launched by hand.
#
# The container is separate from the game's: it listens on another port (27018) and works in its
# own database, `tenebrae_test`. It stays up between two `make test`, which makes series fast;
# `make mongo-stop` removes it.
#
# Without Docker, `make test-fast` runs the same suite without a database: the tests that require
# a real MongoDB skip themselves, all the others run (mongomock covers in-memory persistence).

CONTAINER ?= tenebrae-mongo-test
IMAGE     ?= mongo:7
PORT      ?= 27018
DATABASE  ?= tenebrae_test
URI       := mongodb://localhost:$(PORT)/$(DATABASE)

# Arguments passed to pytest: `make test ARGS="-k persistence -v"`.
ARGS ?=

.PHONY: test test-fast test-browser coverage coverage-fast mongo mongo-stop browser help

help:
	@echo "make test          — brings up MongoDB and runs the whole suite"
	@echo "make test-fast     — the suite without MongoDB (the tests that need it skip themselves)"
	@echo "make test-browser  — the Chromium tests only"
	@echo "make coverage      — the whole suite, measuring what it covers of tenebrae/"
	@echo "make coverage-fast — the same measurement without MongoDB"
	@echo "make mongo         — brings up the test MongoDB and waits for it"
	@echo "make mongo-stop    — removes the container"
	@echo "make browser       — installs Chromium for Playwright"
	@echo ""
	@echo "ARGS passes arguments to pytest:  make test ARGS='-k persistence -v'"

test: mongo
	MONGODB_URI_TEST=$(URI) python3 -m pytest $(ARGS)

test-fast:
	python3 -m pytest $(ARGS)

test-browser: mongo
	MONGODB_URI_TEST=$(URI) python3 -m pytest tests/application/test_board_browser.py \
		tests/application/test_map_fix_browser.py \
		tests/application/test_resume_browser.py \
		tests/application/test_connection_browser.py \
		tests/application/test_ai_browser.py \
		tests/application/test_stream_browser.py \
		tests/application/test_view_browser.py \
		tests/application/test_log_browser.py $(ARGS)

# What the suite covers of the `tenebrae` package. What is measured and what is left out is set
# out in `.coveragerc`, beside the reasons: `tests/` is not its own subject, and the map extraction
# script is not code a test may run.
#
# Two reports at once, because they are not read for the same thing: the terminal one names the
# lines nobody reached, and the HTML one — `htmlcov/index.html`, not versioned — colours them in
# the source, which is what one wants when the missing lines are a branch rather than a block.
#
# It is the whole suite that measures, Chromium included: dropping the browser tests can only lower
# the figure, and a report is worth reading only if what it calls unreached really is. It therefore
# costs the seven minutes the browser tests cost.
coverage: mongo
	MONGODB_URI_TEST=$(URI) python3 -m pytest --cov --cov-report=term-missing \
		--cov-report=html $(ARGS)
	@echo "HTML report: htmlcov/index.html"

# The same measurement without a base, as `test-fast` is to `test`: the tests requiring a real
# MongoDB skip themselves, and the lines only they reach are then reported as missed.
#
# For the quick pass one wants while writing a test, drop Chromium through ARGS - seconds instead
# of minutes, at the cost of a figure lower still:
#
#     make coverage-fast ARGS="--ignore-glob=*browser*"
coverage-fast:
	python3 -m pytest --cov --cov-report=term-missing $(ARGS)

# Brings the container up if it is not already there, then waits for the database to really answer:
# a container that is "Up" is not yet a server accepting connections, and pytest would then start
# and skip the tests that require it.
mongo:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "Docker is missing: use \"make test-fast\" (the MongoDB tests will skip)."; \
		exit 1; \
	fi
	@if [ -z "$$(docker ps -q -f name=^/$(CONTAINER)$$)" ]; then \
		if [ -n "$$(docker ps -aq -f name=^/$(CONTAINER)$$)" ]; then \
			echo "Restarting container $(CONTAINER)..."; \
			docker start $(CONTAINER) >/dev/null; \
		else \
			echo "Creating container $(CONTAINER) on port $(PORT)..."; \
			docker run -d --name $(CONTAINER) -p $(PORT):27017 $(IMAGE) >/dev/null; \
		fi; \
	fi
	@printf "Waiting for MongoDB on port $(PORT)"
	@for i in $$(seq 1 60); do \
		if docker exec $(CONTAINER) mongosh --quiet --eval "db.runCommand({ping:1})" \
			>/dev/null 2>&1; then \
			echo " — ready."; exit 0; \
		fi; \
		printf "."; sleep 1; \
	done; \
	echo " — no answer after 60 s."; exit 1

mongo-stop:
	@docker rm -f $(CONTAINER) >/dev/null 2>&1 && echo "Container $(CONTAINER) removed." \
		|| echo "No container $(CONTAINER)."

browser:
	python3 -m playwright install chromium
