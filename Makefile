SHELL := /bin/bash
DB ?= postgres
DBS ?= postgres mysql sqlserver oracle

.PHONY: init-env pull build up down clean shell tpch init bench metrics all save-images load-images \
        up-db stop-db init-db protocol-db protocol-all reset-results validate-db

init-env:
	@test -f .env || cp .env.example .env

pull: init-env
	docker compose pull

build: init-env
	docker compose build runner

# Starts all DBMS. Heavy. Prefer protocol-all, which starts one at a time.
up: init-env
	docker compose up -d postgres mysql sqlserver oracle

up-db: init-env
	docker compose up -d $(DB)

stop-db:
	docker compose stop $(DB)

shell: init-env build
	docker compose run --rm runner bash

tpch: init-env build
	docker compose run --rm runner bash scripts/get_tpch.sh
	docker compose run --rm runner python -m benchmark.prepare_tpch

init: init-env build up
	docker compose run --rm runner python -m benchmark.init_all

init-db: init-env build up-db
	docker compose run --rm -e DBMS=$(DB) runner python -m benchmark.init_all

# Old generic benchmark, kept for compatibility.
bench: init-env build up
	docker compose run --rm runner python -m benchmark.run_benchmark

# Requested protocol for one DBMS.
protocol-db: init-env build up-db
	docker compose run --rm -e DBMS=$(DB) runner python -m benchmark.run_protocol --dbms $(DB)

# Requested protocol: one DBMS at a time.
protocol-all: init-env build
	@for db in $(DBS); do \
		echo "==== Running $$db ===="; \
		$(MAKE) DB=$$db up-db; \
		$(MAKE) DB=$$db init-db; \
		$(MAKE) DB=$$db protocol-db; \
		$(MAKE) DB=$$db stop-db; \
	done
	$(MAKE) metrics

metrics: init-env build
	docker compose run --rm runner python -m benchmark.metrics

all: tpch protocol-all

reset-results:
	rm -f results/*.csv results/*.json

down:
	docker compose down

clean:
	docker compose down -v
	rm -rf data/tpch_raw data/tpch_clean results/*.csv results/*.json queries/q*.sql tools/tpch-dbgen

save-images: init-env
	bash scripts/save_images.sh

load-images:
	bash scripts/load_images.sh
