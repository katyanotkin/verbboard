PYTHON=python
IMAGE_NAME=verbboard
GCP_REGION=us-central1
GCP_SERVICE=verbboard
GCP_REPOSITORY=verbboard
GCP_PROJECT?=your-gcp-project-id

.DEFAULT_GOAL := help

## Show available commands
help:
	@echo ""
	@echo "VerbBoard commands"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'
	@echo ""

## LOCAL: regenerate lexicons for all languages
lexicon:
	$(PYTHON) -m tools.generate_lexicon --language en
	$(PYTHON) -m tools.generate_lexicon --language ru
	$(PYTHON) -m tools.generate_lexicon --language he

## LOCAL: run uvicorn directly
local-run: ## LOCAL: run app without Docker
	$(PYTHON) -m uvicorn app.main:app --reload

## LOCAL: regenerate lexicons only
local-refresh: lexicon ## LOCAL: refresh runtime lexicons

## LOCAL: regenerate lexicons and run app
local-dev: lexicon local-run ## LOCAL: full local dev loop

## DOCKER LOCAL: build image on this machine
docker-build: lexicon ## LOCAL DOCKER: build image
	docker build -t $(IMAGE_NAME) .

## DOCKER LOCAL: run image on this machine
docker-run: ## LOCAL DOCKER: run local image
	docker run --rm -p 8000:8080 $(IMAGE_NAME)

## DOCKER LOCAL: rebuild then run
docker-dev: docker-build docker-run ## LOCAL DOCKER: rebuild and run

## GCP: configure docker auth for Artifact Registry
gcp-auth: ## GCP: configure Docker auth for Artifact Registry
	gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev

## GCP: build image tagged for Artifact Registry
gcp-build: lexicon ## GCP: build image tagged for Artifact Registry
	docker build -t $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_REPOSITORY)/$(IMAGE_NAME):latest .

## GCP: push image to Artifact Registry
gcp-push: ## GCP: push image to Artifact Registry
	docker push $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_REPOSITORY)/$(IMAGE_NAME):latest

## GCP: deploy pushed image to Cloud Run
gcp-deploy: ## GCP: deploy image to Cloud Run
	gcloud run deploy $(GCP_SERVICE) \
		--image $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_REPOSITORY)/$(IMAGE_NAME):latest \
		--region $(GCP_REGION) \
		--platform managed \
		--allow-unauthenticated

## GCP: build + push + deploy
gcp-release: gcp-build gcp-push gcp-deploy ## GCP: release to Cloud Run
