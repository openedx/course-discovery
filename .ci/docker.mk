ci_up: ## Create containers used to run tests on CI
	docker-compose -f .ci/docker-compose-ci.yml up -d
.PHONY: ci_up

ci_start: ## Start containers stopped by `ci_stop`
	docker-compose -f .ci/docker-compose-ci.yml start
.PHONY: ci_start

ci_test: ## Run tests on Docker containers, as on CI
	# Can restrict run like so: make ci_test TOXENV=py38-django30
	.ci/run-in-docker.sh -f .ci/run-tests.sh
.PHONY: ci_test

ci_quality: ## Run quality on Docker containers, as on CI
	.ci/run-in-docker.sh -f .ci/run-quality.sh
.PHONY: ci_quality

ci_stop: ## Stop running containers created by `ci_up` without removing them
	docker-compose -f .ci/docker-compose-ci.yml stop
.PHONY: ci_stop

ci_down: ## Stop and remove containers and other resources created by `ci_up`
	docker-compose -f .ci/docker-compose-ci.yml down
.PHONY: ci_down
