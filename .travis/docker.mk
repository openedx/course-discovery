.PHONY: travis_down travis_start travis_stop travis_test travis_up

travis_up: ## Create containers used to run tests on Travis CI
	docker-compose -f .travis/docker-compose-travis.yml up -d

travis_start: ## Start containers stopped by `travis_stop`
	docker-compose -f .travis/docker-compose-travis.yml start

travis_test: ## Run tests on Docker containers, as on Travis CI
	docker exec -it discovery env TERM=$(TERM) /edx/app/discovery/discovery/.travis/run_tests.sh

travis_stop: ## Stop running containers created by `travis_up` without removing them
	docker-compose -f .travis/docker-compose-travis.yml stop

travis_down: ## Stop and remove containers and other resources created by `travis_up`
	docker-compose -f .travis/docker-compose-travis.yml down
