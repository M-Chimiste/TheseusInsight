PYTHON ?= /Users/c/miniforge3/envs/theseus/bin/python
COMPOSE ?= docker-compose

.PHONY: test test-db test-down check

test-db:  ## Start the ephemeral test Postgres (port 5434)
	$(COMPOSE) -f docker-compose.test.yml up -d --wait

test: test-db  ## Run the backend characterization suite
	$(PYTHON) -m pytest tests/backend -x -q

test-down:  ## Stop and remove the test database
	$(COMPOSE) -f docker-compose.test.yml down -v

check: test  ## Tests + frontend static checks
	cd theseus-ui && npx tsc -b --noEmit && npm run lint
