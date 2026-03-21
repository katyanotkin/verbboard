PYTHON=python
IMAGE_NAME=verbboard
CONTAINER_NAME=verbboard
HOST_PORT?=8001
CONTAINER_PORT=8080

GCP_REGION=us-east1
GCP_SERVICE=verbboard
GCP_REPOSITORY=verbboard
GCP_PROJECT?=knotmem26

IMAGE_TAG=latest
GCP_IMAGE=$(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_REPOSITORY)/$(IMAGE_NAME):$(IMAGE_TAG)

.DEFAULT_GOAL := help

.PHONY: help lexicon \
	local-run local-refresh local-dev \
	docker-build docker-run docker-stop docker-rm docker-dev \
	gcp-check gcp-auth gcp-build gcp-push gcp-deploy gcp-release

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
	@echo "  make gcp-release GCP_PROJECT=my-project"
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

## LOCAL: regenerate lexicons for all languages
lexicon: lexicon-en lexicon-ru lexicon-he lexicon-es ## LOCAL: regenerate lexicons

## LOCAL: run app without Docker
local-run: ## LOCAL: run uvicorn with reload
	$(PYTHON) -m uvicorn app.main:app --reload

## LOCAL: refresh runtime lexicons
local-refresh: lexicon ## LOCAL: refresh lexicons only

## LOCAL: full local dev loop
local-dev: lexicon local-run ## LOCAL: regenerate lexicons and run app

## LOCAL DOCKER: build image
docker-build: lexicon ## LOCAL DOCKER: build image
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

## GCP: show deployed service URL
gcp-open: gcp-check ## GCP: print Cloud Run service URL
	gcloud run services describe $(GCP_SERVICE) \
		--region $(GCP_REGION) \
		--format='value(status.url)'

## GCP: login to gcloud
gcp-login: ## GCP: login with gcloud
	gcloud auth login
	gcloud config set project $(GCP_PROJECT)


## GCP: ensure GCP_PROJECT is set
gcp-check: ## GCP: validate required variables
	@test -n "$(GCP_PROJECT)" || (echo "ERROR: set GCP_PROJECT, e.g. make gcp-release GCP_PROJECT=my-project" && exit 1)

## GCP: configure Docker auth for Artifact Registry
gcp-auth: gcp-check ## GCP: configure docker auth
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev

## GCP: build container using Cloud Build
gcp-build: lexicon gcp-check ## GCP: build image in Cloud Build
	gcloud builds submit \
		--tag $(GCP_IMAGE)

## GCP: push image to Artifact Registry
gcp-push: gcp-check ## GCP: push image
	docker push $(GCP_IMAGE)

## GCP: deploy image to Cloud Run
gcp-deploy: gcp-check ## GCP: deploy to Cloud Run
	gcloud run deploy $(GCP_SERVICE) \
		--image $(GCP_IMAGE) \
		--region $(GCP_REGION) \
		--platform managed \
		--allow-unauthenticated

## GCP: build + push + deploy
gcp-release: gcp-build gcp-deploy ## GCP: release to Cloud Run

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
