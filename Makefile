.PHONY: install install-backend install-frontend backend frontend dev stop clean \
       test test-install \
       docker docker-stop infra-init infra-plan infra-apply infra-destroy deploy

install: install-backend install-frontend

install-backend:
	cd backend && python -m venv venv && venv/bin/pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

backend:
	cd backend && venv/bin/uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) backend & $(MAKE) frontend & wait

stop:
	-lsof -ti :8000 | xargs -r kill
	-lsof -ti :5173 | xargs -r kill

test-install:
	cd backend && venv/bin/pip install pytest pytest-asyncio httpx

test: test-install
	cd backend && venv/bin/pytest tests/ -v

clean:
	rm -rf backend/venv backend/__pycache__ frontend/node_modules

docker:
	docker compose up --build

docker-stop:
	docker compose down

# --- Infrastructure ---

infra-init:
	cd infra && terraform init

infra-plan:
	cd infra && terraform plan

infra-apply:
	cd infra && terraform apply

infra-destroy:
	cd infra && terraform destroy

# --- Deploy (build, push image, restart ECS) ---

deploy:
	$(eval AWS_REGION := $(shell cd infra && terraform output -raw aws_region))
	$(eval ECR_URL    := $(shell cd infra && terraform output -raw ecr_repository_url))
	$(eval CLUSTER    := $(shell cd infra && terraform output -raw ecs_cluster_name))
	$(eval SERVICE    := $(shell cd infra && terraform output -raw ecs_service_name))
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_URL)
	docker build -t $(ECR_URL):latest .
	docker push $(ECR_URL):latest
	aws ecs update-service --cluster $(CLUSTER) --service $(SERVICE) --force-new-deployment
