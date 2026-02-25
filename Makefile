.PHONY: install install-backend install-frontend backend frontend dev stop clean docker docker-stop

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

clean:
	rm -rf backend/venv backend/__pycache__ frontend/node_modules

docker:
	docker compose up --build

docker-stop:
	docker compose down
