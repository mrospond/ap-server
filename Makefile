# Makefile for testing Docker Experiment Manager API
# Usage examples:
#   make build-analysing_pii_leakage
#   make run-analysing_pii_leakage
#   make remove-analysing_pii_leakage
#   make logs-analysing_pii_leakage

SERVER ?= http://localhost:8000
JSON_HEADER = -H "Content-Type: application/json"

.PHONY: help get build-% run-% remove-% logs-%

help:
	@echo "Usage:"
	@echo "  make get\t\t\t:Get available experiments"
	@echo "  make build-<experiment_name>\t:Build docker image"
	@echo "  make run-<experiment_name>\t:Run docker container"
	@echo "  make remove-<experiment_name>\t:Remove docker container"
	@echo "  make logs-<experiment_name>\t:Stream docker logs"

get:
	@curl -s $(SERVER)/experiments | jq

build-%:
	@echo "Building image for experiment '$*'..."
	curl -s -X POST $(SERVER)/build \
	     $(JSON_HEADER) \
	     -d '{"experiment_name":"'$*'"}'

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
	@echo "\twscat -c ws://localhost:8000/ws/logs/$*"
