.PHONY: all build push deploy clean help

# Docker registry (local for now)
REGISTRY ?= localhost
VERSION ?= latest

# K3s containerd socket (MUST use this path, not the default ctr socket)
K3S_CTR = sudo ctr --address /run/k3s/containerd/containerd.sock -n k8s.io

# Service images
SERVICES = embedding-service llm-gateway rag-api web-ui

help:
	@echo "RAG Microservices Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make build              - Build all Docker images"
	@echo "  make build-<service>    - Build specific service image"
	@echo "  make import             - Import all images to k3s containerd"
	@echo "  make import-web-ui      - Build + import + restart web-ui only (fast path)"
	@echo "  make deploy-infra       - Deploy infrastructure (Redis, Qdrant)"
	@echo "  make deploy-services    - Deploy all services"
	@echo "  make deploy             - Deploy everything"
	@echo "  make status             - Show deployment status"
	@echo "  make logs               - Show logs for all services"
	@echo "  make clean              - Remove all deployments"
	@echo ""

# Build all images
build: build-embedding-service build-llm-gateway build-rag-api build-web-ui

build-embedding-service:
	@echo "Building embedding-service..."
	docker build -t embedding-service:$(VERSION) services/embedding-service/

build-llm-gateway:
	@echo "Building llm-gateway..."
	docker build -t llm-gateway:$(VERSION) services/llm-gateway/

build-rag-api:
	@echo "Building rag-api..."
	docker build -t rag-api:$(VERSION) services/rag-api/

build-web-ui:
	@echo "Building web-ui..."
	docker build --no-cache -t web-ui:$(VERSION) services/web-ui/

# Import images to containerd (for K3s)
# NOTE: Must use K3s-specific containerd socket (/run/k3s/containerd/containerd.sock)
#       NOT the default ctr socket. Using wrong socket silently imports to a different
#       namespace that kubelet does not read, causing pods to run stale images.
import: build
	@echo "Importing images to containerd (k3s socket)..."
	docker save embedding-service:$(VERSION) | $(K3S_CTR) images import -
	docker save llm-gateway:$(VERSION) | $(K3S_CTR) images import -
	docker save rag-api:$(VERSION) | $(K3S_CTR) images import -
	docker save web-ui:$(VERSION) | $(K3S_CTR) images import -
	@echo "Images imported successfully"

# Import only web-ui (fast path for frontend-only changes)
import-web-ui:
	@echo "Building and importing web-ui only..."
	docker build --no-cache -t web-ui:$(VERSION) services/web-ui/
	docker save web-ui:$(VERSION) | $(K3S_CTR) images import -
	kubectl rollout restart deployment/web-ui -n rag-system
	kubectl rollout status deployment/web-ui -n rag-system --timeout=60s
	@echo "web-ui deployed successfully"

# Deploy infrastructure
deploy-infra:
	@echo "Creating namespace..."
	kubectl apply -f k8s/namespace.yaml
	@echo "Creating secrets and configmap..."
	kubectl apply -f k8s/secrets.yaml
	kubectl apply -f k8s/configmap.yaml
	@echo "Creating PVCs..."
	kubectl apply -f k8s/pvc.yaml
	@echo "Deploying Redis..."
	kubectl apply -f k8s/redis-statefulset.yaml
	@echo "Deploying Qdrant..."
	kubectl apply -f k8s/qdrant-statefulset.yaml
	@echo "Waiting for infrastructure to be ready..."
	kubectl wait --for=condition=ready pod -l app=redis -n rag-system --timeout=120s
	kubectl wait --for=condition=ready pod -l app=qdrant -n rag-system --timeout=120s
	@echo "Infrastructure deployed successfully"

# Deploy services
deploy-services:
	@echo "Deploying Embedding Service..."
	kubectl apply -f k8s/embedding-deployment.yaml
	@echo "Deploying LLM Gateway..."
	kubectl apply -f k8s/llm-gateway-deployment.yaml
	@echo "Deploying RAG API..."
	kubectl apply -f k8s/rag-api-deployment.yaml
	@echo "Deploying Web UI..."
	kubectl apply -f k8s/web-ui-deployment.yaml
	@echo "Deploying Ingress..."
	kubectl apply -f k8s/ingress.yaml
	@echo "Services deployed successfully"

# Deploy everything
deploy: deploy-infra deploy-services
	@echo "Deployment complete!"
	@echo ""
	@make status

# Show status
status:
	@echo "=== Namespace: rag-system ==="
	@kubectl get all -n rag-system
	@echo ""
	@echo "=== PVCs ==="
	@kubectl get pvc -n rag-system
	@echo ""
	@echo "=== Ingress ==="
	@kubectl get ingress -n rag-system

# Show logs
logs:
	@echo "=== Redis logs ==="
	@kubectl logs -l app=redis -n rag-system --tail=20
	@echo ""
	@echo "=== Qdrant logs ==="
	@kubectl logs -l app=qdrant -n rag-system --tail=20
	@echo ""
	@echo "=== Embedding Service logs ==="
	@kubectl logs -l app=embedding-service -n rag-system --tail=20
	@echo ""
	@echo "=== LLM Gateway logs ==="
	@kubectl logs -l app=llm-gateway -n rag-system --tail=20
	@echo ""
	@echo "=== RAG API logs ==="
	@kubectl logs -l app=rag-api -n rag-system --tail=20

# Clean up
clean:
	@echo "Removing all deployments..."
	kubectl delete -f k8s/ingress.yaml --ignore-not-found
	kubectl delete -f k8s/web-ui-deployment.yaml --ignore-not-found
	kubectl delete -f k8s/rag-api-deployment.yaml --ignore-not-found
	kubectl delete -f k8s/llm-gateway-deployment.yaml --ignore-not-found
	kubectl delete -f k8s/embedding-deployment.yaml --ignore-not-found
	kubectl delete -f k8s/qdrant-statefulset.yaml --ignore-not-found
	kubectl delete -f k8s/redis-statefulset.yaml --ignore-not-found
	@echo "Cleanup complete"

# Delete everything including PVCs
clean-all: clean
	@echo "Removing PVCs and namespace..."
	kubectl delete -f k8s/pvc.yaml --ignore-not-found
	kubectl delete -f k8s/secrets.yaml --ignore-not-found
	kubectl delete -f k8s/configmap.yaml --ignore-not-found
	kubectl delete -f k8s/namespace.yaml --ignore-not-found
	@echo "Full cleanup complete"

# Port forward for local access
port-forward:
	@echo "Port forwarding services..."
	@echo "Web UI: http://localhost:8080"
	@echo "RAG API: http://localhost:8000"
	@echo "Qdrant: http://localhost:6333"
	kubectl port-forward -n rag-system svc/web-ui 8080:80 &
	kubectl port-forward -n rag-system svc/rag-api 8000:8000 &
	kubectl port-forward -n rag-system svc/qdrant 6333:6333 &
