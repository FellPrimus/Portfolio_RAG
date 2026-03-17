# RAG Microservices System

Kubernetes 기반 RAG(Retrieval-Augmented Generation) 마이크로서비스 아키텍처

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Traefik Ingress                       │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│   RAG API Service   │       │     Web UI          │
│   (통합 서비스)       │       │   (Nginx Static)    │
└──────────┬──────────┘       └─────────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌─────────────┐
│Embedding│  │ LLM Gateway │
│ Service │  │   (CLOVA)   │
└────┬────┘  └─────────────┘
     │
┌────┴────────────────────────────────┐
│           Data Layer                 │
├─────────────┬───────────────────────┤
│   Qdrant    │      Redis            │
│  (Vectors)  │  (Cache/Queue/Meta)   │
└─────────────┴───────────────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| RAG API | 8000 | Query, Document, Admin, Crawl endpoints |
| Embedding Service | 8001 | E5 multilingual-e5-large embeddings |
| LLM Gateway | 8002 | CLOVA Studio HCX-007 abstraction |
| Web UI | 80 | Static web interface |
| Qdrant | 6333/6334 | Vector database |
| Redis | 6379 | Cache, queue, metadata |

## Quick Start

### Prerequisites

- Docker
- Kubernetes (K3s/K8s)
- kubectl configured

### Local Development (Docker Compose)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Kubernetes Deployment

```bash
# Build and import images
make build
make import

# Deploy infrastructure first
make deploy-infra

# Deploy services
make deploy-services

# Or deploy everything at once
make deploy

# Check status
make status

# View logs
make logs
```

## API Endpoints

### Query API

```bash
# RAG Query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "서버 생성 방법은?",
    "collection": "documents",
    "top_k": 5
  }'
```

### Document API

```bash
# Upload document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@document.txt" \
  -F "category=guide"

# List documents
curl http://localhost:8000/api/v1/documents

# Delete document
curl -X DELETE http://localhost:8000/api/v1/documents/{doc_id}
```

### Admin API

```bash
# System status
curl http://localhost:8000/api/v1/admin/status

# List categories
curl http://localhost:8000/api/v1/admin/categories

# List collections
curl http://localhost:8000/api/v1/admin/collections
```

### Crawl API

```bash
# Start crawl
curl -X POST http://localhost:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "depth": 2,
    "category": "web"
  }'

# Check status
curl http://localhost:8000/api/v1/crawl/{task_id}
```

## Resource Requirements

| Component | CPU Request | Memory Request | Storage |
|-----------|-------------|----------------|---------|
| RAG API (x2) | 500m | 1Gi | - |
| Embedding Service | 2000m | 6Gi | 10Gi |
| LLM Gateway | 250m | 256Mi | - |
| Web UI | 100m | 128Mi | - |
| Qdrant | 1000m | 2Gi | 50Gi |
| Redis | 250m | 512Mi | 10Gi |

**Total**: ~6 vCPU, ~14GB Memory, ~70GB Storage

## Configuration

### Environment Variables

See `k8s/configmap.yaml` and `k8s/secrets.yaml` for configuration.

Key settings:
- `EMBEDDING_MODEL`: E5 model name
- `LLM_MODEL`: CLOVA model (HCX-007)
- `RAG_RETRIEVAL_K`: Number of documents to retrieve
- `RAG_MIN_QUALITY_SCORE`: Minimum quality threshold

## Monitoring

```bash
# Pod resource usage
kubectl top pods -n rag-system

# Service logs
kubectl logs -f deployment/rag-api -n rag-system

# Port forward for local access
make port-forward
```
