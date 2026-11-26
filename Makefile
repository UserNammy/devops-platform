SHELL := /bin/bash
.DEFAULT_GOAL := help

APP_DIR   := app
IMAGE     ?= shortener
TAG       ?= dev
TF_DIR    := infra/terraform
ANSIBLE   := infra/ansible
CHART     := k8s/charts/shortener

.PHONY: help
help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

## ---- Application ----

.PHONY: install
install: ## Install app and dev dependencies into the active virtualenv
	pip install -r $(APP_DIR)/requirements-dev.txt

.PHONY: lint
lint: ## Run ruff (lint + format check)
	cd $(APP_DIR) && ruff check . && ruff format --check .

.PHONY: fmt
fmt: ## Auto-format Python and Terraform code
	cd $(APP_DIR) && ruff check --fix . && ruff format .
	terraform -chdir=$(TF_DIR) fmt -recursive

.PHONY: test
test: ## Run the test suite locally (SQLite)
	cd $(APP_DIR) && pytest

## ---- Containers ----

.PHONY: build
build: ## Build the runtime image
	docker build --target runtime -t $(IMAGE):$(TAG) $(APP_DIR)

.PHONY: test-docker
test-docker: ## Run lint + tests inside the Docker test stage
	docker build --target test $(APP_DIR)

.env:
	cp .env.example .env

.PHONY: up
up: .env ## Start the local stack (app + postgres)
	docker compose up --build -d
	@echo "API: http://localhost:8000/docs"

.PHONY: down
down: ## Stop the local stack
	docker compose down

.PHONY: logs
logs: ## Tail application logs
	docker compose logs -f app

## ---- Infrastructure ----

.PHONY: tf-init
tf-init: ## terraform init
	terraform -chdir=$(TF_DIR) init

.PHONY: tf-plan
tf-plan: ## terraform plan (needs HCLOUD_TOKEN and terraform.tfvars)
	terraform -chdir=$(TF_DIR) plan -out=tfplan

.PHONY: tf-apply
tf-apply: ## terraform apply the saved plan
	terraform -chdir=$(TF_DIR) apply tfplan

.PHONY: ansible-bootstrap
ansible-bootstrap: ## First run as root: create the deploy user
	cd $(ANSIBLE) && ansible-galaxy collection install -r requirements.yml && ansible-playbook site.yml -e ansible_user=root --tags base

.PHONY: ansible
ansible: ## Harden the server and install k3s
	cd $(ANSIBLE) && ansible-playbook site.yml

.PHONY: helm-lint
helm-lint: ## Lint and render the Helm chart
	helm lint $(CHART)
	helm template shortener $(CHART) > /dev/null
