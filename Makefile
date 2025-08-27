# Makefile for testing Docker Experiment Manager API
# Usage examples:
#   make build-analysing_pii_leakage
#   make run-analysing_pii_leakage
#   make remove-analysing_pii_leakage
#   make logs-analysing_pii_leakage

SERVER ?= http://localhost:8000
JSON_HEADER = -H "Content-Type: application/json"

.PHONY: help build-% run-% remove-% logs-%

help:
	@echo "Usage:"
	@echo "  make get"
	@echo "  make build-<experiment_name>"
	@echo "  make run-<experiment_name>"
	@echo "  make remove-<experiment_name>"
	@echo "  make logs-<experiment_name>"

get:
	@echo "Availavle experiments:"
	curl -s $(SERVER)/experiments | jq

build-%:
	@echo "Building image for experiment '$*'..."
	curl -s -X POST $(SERVER)/build \
	     $(JSON_HEADER) \
	     -d '{"experiment_name":"'$*'"}' | jq .

run-%:
	@echo "Running container for experiment '$*'..."
	curl -s -X POST $(SERVER)/run \
	     $(JSON_HEADER) \
	     -d '{"experiment_name":"'$*'"}' | jq .

remove-%:
	@echo "Removing container for experiment '$*'..."
	curl -s -X POST $(SERVER)/remove \
	     $(JSON_HEADER) \
	     -d '{"experiment_name":"'$*'"}' | jq .

logs-%:
	@echo "To stream logs for '$*', connect via WebSocket:"
	@echo "  wscat -c ws://localhost:8000/ws/logs/$*"
