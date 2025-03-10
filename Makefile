IMAGE_NAME=cupcake-s3
CONTAINER_NAME=cupcake-s3
VERSION_FILE := VERSION

show-version:
	@current_version="$$(cat $(VERSION_FILE))"; \
		echo "Current Version: $$current_version";

update-version:
	@current_date="$$(date +'%y.%-m.%-d')"; \
		current_version="$$(cat $(VERSION_FILE))"; \
		echo "Current Version: $$current_version"; \
		[[ "$$current_version" == "$$current_date"* ]] && \
			new_version="$$(echo "$$current_version" | awk -F'.' '{print $$1"."$$2"."$$3+1}')" || \
			new_version="$${current_date}000"; \
		echo $$new_version > VERSION; \
		echo "New Version: $$new_version";

update-dependencies:
	@echo ">> Updating dependencies"
	curl -sL https://cdn.jsdelivr.net/npm/bootstrap@5/dist/js/bootstrap.bundle.min.js -o cupcake/js/bootstrap.bundle.min.js
	curl -sL https://cdn.jsdelivr.net/npm/bootstrap@5/dist/js/bootstrap.bundle.min.js.map -o cupcake/js/bootstrap.bundle.min.js.map
	curl -sL https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js -o cupcake/js/vue.global.prod.js
	curl -sL https://cdn.jsdelivr.net/npm/cronstrue@2/dist/cronstrue.min.js -o cupcake/js/cronstrue.min.js
	@pipenv update

lint:
	@echo ">> Linting cupcake/cupcake.py"
	@pylint --output-format json2 --fail-under 10 cupcake/cupcake.py
	@echo ">> Linting yaml"
	@yamllint --strict -f github . \
		&& echo ">> Linting yaml: OK"
	@echo ">> Linting cloudformation"
	@cfn-lint --info cupcake/cloudformation/cupcake.yml

build: update-version
	@echo ">> Generating requirements.txt"
	@pipenv requirements > requirements.txt
	@echo ">> Building ${IMAGE_NAME}"
	@docker compose build

run:
	@echo ">> Starting the container"
	@docker compose up --force-recreate

stop:
	@echo ">> Stopping the container $(CONTAINER_NAME)"
	@docker compose stop

clean:
	@echo ">> Cleaning up requirements.txt"
	@rm -f requirements.txt
	@echo ">> Stopping $(CONTAINER_NAME)"
	@docker stop $(CONTAINER_NAME) || true
	@echo ">> Removing $(CONTAINER_NAME)"
	@docker rm $(CONTAINER_NAME) || true
	@echo ">> Removing $(IMAGE_NAME)"
	@docker rmi $(IMAGE_NAME) || true
	@echo ">> Removing run logs"
	@sudo rm -rf _run/logs

prune:
	@echo ">> Removing all stopped containers"
	@docker container prune -f
	@echo ">> Removing all dangling images"
	@docker image prune -f
	@echo ">> Removing all unused volumes"
	@docker volume prune -f
	@echo ">> Removing all unused networks"
	@docker network prune -f
	@echo ">> Removing all unused build cache"
	@docker builder prune -f

ps:
	@docker ps

ps-all:
	@docker ps --all
