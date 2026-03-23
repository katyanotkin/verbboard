PYTHON=python
IMAGE_NAME=verbboard
CONTAINER_NAME=verbboard
HOST_PORT?=8001
CONTAINER_PORT=8080

GCP_REGION=us-east1
GCP_SERVICE=verbboard
GCP_STAGE_SERVICE=verbboard-stage
GCP_REPOSITORY=verbboard
GCP_PROJECT?=knotmem26

ADMIN_LOG_BUCKET_STAGE=verbboard-verb-signal-stage
ADMIN_LOG_BUCKET_PROD=verbboard-verb-signal-prod

GCP_RUNTIME_SERVICE_ACCOUNT?=$(shell gcloud projects describe $(GCP_PROJECT) --format='value(projectNumber)')-compute@developer.gserviceaccount.com

IMAGE_TAG=$(shell git rev-parse --short HEAD)
GCP_IMAGE=$(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_REPOSITORY)/$(IMAGE_NAME):$(IMAGE_TAG)

.DEFAULT_GOAL := help

.PHONY: help lexicon \
	local-run local-refresh local-dev \
	docker-build docker-run docker-stop docker-rm docker-dev docker-url \
	gcp-check gcp-login gcp-auth gcp-build gcp-push \
	gcp-image gcp-open gcp-open-stage gcp-open-prod \
	gcp-deploy-stage \
	gcp-release-stage gcp-release-prod \
	gcp-map-stage gcp-map-prod gcp-domain-status \
	gcp-ensure-bucket gcp-grant-bucket-writer \
        gcp-setup-stage-verb-signal gcp-setup-prod-verb-signal \
	audit-examples audit-en audit-ru audit-he audit-es

## Show available commands
help:
	@echo ""
	@echo "VerbBoard commands"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make local-dev"
	@echo "  make docker-dev"
	@echo "  make docker-run HOST_PORT=8001"
	@echo "  make gcp-release-stage"
	@echo ""

## LOCAL: regenerate English lexicon
lexicon-en: ## LOCAL: regenerate English lexicon
	$(PYTHON) -m tools.generate_lexicon --language en

## LOCAL: regenerate Russian lexicon
lexicon-ru: ## LOCAL: regenerate Russian lexicon
	$(PYTHON) -m tools.generate_lexicon --language ru

## LOCAL: regenerate Hebrew lexicon
lexicon-he: ## LOCAL: regenerate Hebrew lexicon
	$(PYTHON) -m tools.generate_lexicon --language he

## LOCAL: regenerate Spanish lexicon
lexicon-es: ## LOCAL: regenerate Spanish lexicon
	$(PYTHON) -m tools.generate_lexicon --language es

lexicon: ## LOCAL: regenerate lexicons for all languages
	$(PYTHON) -m tools.generate_lexicon --language all

## LOCAL: run app without Docker
local-run: ## LOCAL: run uvicorn with reload
	$(PYTHON) -m uvicorn app.main:app --reload

## LOCAL: refresh runtime lexicons
local-refresh: lexicon ## LOCAL: refresh lexicons only

## LOCAL: full local dev loop
local-dev: lexicon local-run ## LOCAL: regenerate lexicons and run app

## LOCAL DOCKER: build image
docker-build: ## LOCAL DOCKER: build image
	docker build -t $(IMAGE_NAME) .

## LOCAL DOCKER: run local image
docker-run: ## LOCAL DOCKER: run container on HOST_PORT -> CONTAINER_PORT
	docker run --rm --name $(CONTAINER_NAME) -p $(HOST_PORT):$(CONTAINER_PORT) $(IMAGE_NAME)

## LOCAL DOCKER: stop running container
docker-stop: ## LOCAL DOCKER: stop named container
	-docker stop $(CONTAINER_NAME)

## LOCAL DOCKER: remove stopped container
docker-rm: ## LOCAL DOCKER: remove named container if present
	-docker rm -f $(CONTAINER_NAME)

## LOCAL DOCKER: rebuild and run
docker-dev: docker-rm docker-build docker-run ## LOCAL DOCKER: rebuild image and run container

## LOCAL DOCKER: print local docker URL
docker-url: ## LOCAL DOCKER: show browser URL
	@echo http://localhost:$(HOST_PORT)

## GCP: print resolved image URL
gcp-image: ## GCP: show image reference
	@echo $(GCP_IMAGE)

## GCP: ensure GCP_PROJECT is set
gcp-check: ## GCP: validate required variables
	@test -n "$(GCP_PROJECT)" || (echo "ERROR: set GCP_PROJECT, e.g. make gcp-release-stage GCP_PROJECT=my-project" && exit 1)

## GCP: login to gcloud
gcp-login: gcp-check ## GCP: login with gcloud
	gcloud auth login
	gcloud config set project $(GCP_PROJECT)

## GCP: configure Docker auth for Artifact Registry
gcp-auth: gcp-check ## GCP: configure docker auth
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev

## GCP: build container using Cloud Build
gcp-build: gcp-check ## GCP: build image in Cloud Build
	gcloud builds submit --tag $(GCP_IMAGE)

## GCP: push image to Artifact Registry
gcp-push: gcp-check ## GCP: push local image
	docker push $(GCP_IMAGE)

## GCP: show deployed prod service URL
gcp-open-prod: gcp-check ## GCP: print prod Cloud Run service URL
	gcloud run services describe $(GCP_SERVICE) \
		--region $(GCP_REGION) \
		--format='value(status.url)'

## GCP: show deployed stage service URL
gcp-open-stage: gcp-check ## GCP: print stage Cloud Run service URL
	gcloud run services describe $(GCP_STAGE_SERVICE) \
		--region $(GCP_REGION) \
		--format='value(status.url)'

## GCP: backward-compatible alias for prod URL
gcp-open: gcp-open-prod ## GCP: print Cloud Run service URL

## GCP: deploy image to stage Cloud Run service
gcp-deploy-stage: gcp-check ## GCP: deploy current image tag to stage
	gcloud run deploy $(GCP_STAGE_SERVICE) \
		--image $(GCP_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--set-env-vars ADMIN_LOG_BUCKET=$(ADMIN_LOG_BUCKET_STAGE) \
		--allow-unauthenticated

## GCP: build + deploy to stage
gcp-release-stage: gcp-build gcp-setup-stage-verb-signal gcp-deploy-stage ## GCP: build and release to stage

## GCP: map stage domain to stage service
gcp-map-stage: gcp-check ## GCP: create domain mapping for stage.verbboard.com
	gcloud beta run domain-mappings create \
		--service $(GCP_STAGE_SERVICE) \
		--domain stage.verbboard.com \
		--region $(GCP_REGION)

## GCP: map prod domain to prod service
gcp-map-prod: gcp-check ## GCP: create domain mapping for verbboard.com
	gcloud beta run domain-mappings create \
		--service $(GCP_SERVICE) \
		--domain verbboard.com \
		--region $(GCP_REGION)

## GCP: list domain mappings
gcp-domain-status: gcp-check ## GCP: list domain mappings
	gcloud beta run domain-mappings list \
		--region $(GCP_REGION)

## GCP: show image currently deployed to stage
gcp-stage-image: gcp-check ## GCP: print stage image reference
	@gcloud run services describe $(GCP_STAGE_SERVICE) \
		--region $(GCP_REGION) \
		--format='value(spec.template.spec.containers[0].image)'

## GCP: promote currently deployed stage image to prod
gcp-promote-stage-to-prod: gcp-check gcp-setup-prod-verb-signal ## GCP: promote deployed stage image to prod
	$(eval STAGE_IMAGE := $(shell gcloud run services describe $(GCP_STAGE_SERVICE) --region $(GCP_REGION) --format='value(spec.template.spec.containers[0].image)'))
	@test -n "$(STAGE_IMAGE)" || (echo "ERROR: could not determine stage image" && exit 1)
	@echo "Promoting stage image to prod:"
	@echo "  $(STAGE_IMAGE)"
	gcloud run deploy $(GCP_SERVICE) \
		--image $(STAGE_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--set-env-vars ADMIN_LOG_BUCKET=$(ADMIN_LOG_BUCKET_PROD) \
		--allow-unauthenticated

## GCP: create bucket if missing
gcp-ensure-bucket: gcp-check
	@test -n "$(BUCKET)" || (echo "ERROR: BUCKET is required" && exit 1)
	@if ! gcloud storage buckets describe gs://$(BUCKET) --format='value(name)' >/dev/null 2>&1; then \
		echo "Creating bucket gs://$(BUCKET)"; \
		gcloud storage buckets create gs://$(BUCKET) \
			--location=$(GCP_REGION) \
			--uniform-bucket-level-access; \
	else \
		echo "Bucket gs://$(BUCKET) already exists"; \
	fi

## GCP: grant runtime service account write access to bucket
gcp-grant-bucket-writer: gcp-check
	@test -n "$(BUCKET)" || (echo "ERROR: BUCKET is required" && exit 1)
	@test -n "$(SERVICE_ACCOUNT)" || (echo "ERROR: SERVICE_ACCOUNT is required" && exit 1)
	gcloud storage buckets add-iam-policy-binding gs://$(BUCKET) \
		--member="serviceAccount:$(SERVICE_ACCOUNT)" \
		--role="roles/storage.objectCreator"

## GCP: ensure stage verb-signal bucket exists and grant access
gcp-setup-stage-verb-signal: gcp-check
	$(MAKE) gcp-ensure-bucket BUCKET=$(ADMIN_LOG_BUCKET_STAGE)
	$(MAKE) gcp-grant-bucket-writer BUCKET=$(ADMIN_LOG_BUCKET_STAGE) SERVICE_ACCOUNT=$(GCP_RUNTIME_SERVICE_ACCOUNT)

## GCP: ensure prod verb-signal bucket exists and grant access
gcp-setup-prod-verb-signal: gcp-check
	$(MAKE) gcp-ensure-bucket BUCKET=$(ADMIN_LOG_BUCKET_PROD)
	$(MAKE) gcp-grant-bucket-writer BUCKET=$(ADMIN_LOG_BUCKET_PROD) SERVICE_ACCOUNT=$(GCP_RUNTIME_SERVICE_ACCOUNT)

## QA: audit examples for all languages
audit-examples: ## QA: run example audit for all languages
	$(PYTHON) -m tools.audit_examples --language all

## QA: audit English examples
audit-en: ## QA: run example audit for English
	$(PYTHON) -m tools.audit_examples --language en

## QA: audit Russian examples
audit-ru: ## QA: run example audit for Russian
	$(PYTHON) -m tools.audit_examples --language ru

## QA: audit Hebrew examples
audit-he: ## QA: run example audit for Hebrew
	$(PYTHON) -m tools.audit_examples --language he

## QA: audit Spanish examples
audit-es: ## QA: run example audit for Spanish
	$(PYTHON) -m tools.audit_examples --language es
