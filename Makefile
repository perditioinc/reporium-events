# Root passthrough to the local OSS substrate (see local/).
# These targets are additive and local-only; they never touch production/cloud.

.PHONY: local-up local-down local-seed local-smoke local-logs local-clean

local-up:
	$(MAKE) -C local up

local-down:
	$(MAKE) -C local down

local-seed:
	$(MAKE) -C local seed

local-smoke:
	$(MAKE) -C local smoke

local-logs:
	$(MAKE) -C local logs

local-clean:
	$(MAKE) -C local clean
