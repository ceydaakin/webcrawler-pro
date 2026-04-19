# WebCrawler Pro - Production Deployment Guide

## Overview

This guide covers deploying WebCrawler Pro in production environments, from single-node deployments to large-scale distributed systems. The architecture is designed to scale from development workloads to enterprise-grade operations.

## Deployment Options

### 1. Single Node (Development/Small Scale)

**Recommended for**: Development, testing, small-scale crawling (<10,000 pages)

**Resources**: 2-4 CPU cores, 4-8GB RAM, 100GB storage

```bash
# Local deployment
git clone https://github.com/yourusername/webcrawler-pro.git
cd webcrawler-pro
pip install -r requirements.txt
python scripts/init_db.py
python -m src.main index --origin "https://example.com" --depth 2
```

**Capacity**: 1,000+ pages/minute, suitable for content research and small-scale monitoring.

### 2. Docker Container (Production Ready)

**Recommended for**: Production single-node, CI/CD integration, cloud deployment

```bash
# Build and run with Docker
docker build -t webcrawler-pro .
docker run -d \
  --name webcrawler \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  webcrawler-pro python scripts/init_db.py

# Using Docker Compose
docker-compose up -d
```

**Features**:
- Health checks and auto-restart
- Volume persistence for data and configuration
- Resource limits and monitoring
- Easy scaling with compose

### 3. Kubernetes Cluster (Enterprise Scale)

**Recommended for**: Large-scale production, high availability, auto-scaling

**Capacity**: 50,000+ pages/minute with horizontal scaling

#### Basic Kubernetes Deployment

```yaml
# webcrawler-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webcrawler-pro
  labels:
    app: webcrawler-pro
spec:
  replicas: 3
  selector:
    matchLabels:
      app: webcrawler-pro
  template:
    metadata:
      labels:
        app: webcrawler-pro
    spec:
      containers:
      - name: webcrawler
        image: webcrawler-pro:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        env:
        - name: WEBCRAWLER_MAX_REQUESTS
          value: "100"
        - name: WEBCRAWLER_LOG_LEVEL
          value: "INFO"
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: data
          mountPath: /app/data
      volumes:
      - name: config
        configMap:
          name: webcrawler-config
      - name: data
        persistentVolumeClaim:
          claimName: webcrawler-data
```

#### Horizontal Pod Autoscaling

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: webcrawler-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: webcrawler-pro
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Database Scaling Strategies

### Single Node Database

**Recommended for**: Up to 1 million pages, single geographical region

```yaml
# postgres-single.yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: webcrawler
        - name: POSTGRES_USER
          value: webcrawler
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

### Distributed Database Architecture

**Recommended for**: Multi-million page datasets, global deployment

**Components**:
1. **PostgreSQL Cluster**: Primary for writes, read replicas for search queries
2. **Elasticsearch**: Distributed search index for advanced queries
3. **Redis**: Caching layer for frequently accessed data

```yaml
# elasticsearch-cluster.yaml
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: webcrawler-es
spec:
  version: 8.10.0
  nodeSets:
  - name: default
    count: 3
    config:
      node.store.allow_mmap: false
    volumeClaimTemplates:
    - metadata:
        name: elasticsearch-data
      spec:
        accessModes:
        - ReadWriteOnce
        resources:
          requests:
            storage: 100Gi
        storageClassName: fast-ssd
```

## Cloud Provider Deployments

### AWS Deployment

**Architecture**: EKS cluster with RDS PostgreSQL and OpenSearch

```bash
# Create EKS cluster
eksctl create cluster \
  --name webcrawler-pro \
  --region us-west-2 \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 20 \
  --node-type m5.large

# Deploy with Helm
helm install webcrawler-pro ./helm/webcrawler \
  --set database.host=webcrawler-db.cluster-xxx.us-west-2.rds.amazonaws.com \
  --set elasticsearch.host=vpc-webcrawler-es-xxx.us-west-2.es.amazonaws.com
```

**Cost Optimization**:
- Use Spot instances for crawler workers
- RDS read replicas for search queries
- S3 storage for content archives
- CloudWatch monitoring and alerting

### Google Cloud Deployment

**Architecture**: GKE cluster with Cloud SQL and Elasticsearch Service

```bash
# Create GKE cluster
gcloud container clusters create webcrawler-pro \
  --num-nodes 3 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 20 \
  --machine-type n1-standard-2 \
  --zone us-central1-a

# Deploy application
kubectl apply -f k8s/
```

### Azure Deployment

**Architecture**: AKS cluster with Azure Database for PostgreSQL

```bash
# Create AKS cluster
az aks create \
  --resource-group webcrawler-rg \
  --name webcrawler-pro \
  --node-count 3 \
  --enable-addons monitoring \
  --enable-cluster-autoscaler \
  --min-count 3 \
  --max-count 20
```

## Performance Optimization

### Configuration Tuning

**High Throughput Configuration**:
```yaml
crawler:
  max_concurrent_requests: 100
  request_delay: 0.1
  max_queue_depth: 50000
  batch_size: 500

search:
  index_batch_size: 1000
  max_index_memory: 2147483648  # 2GB

database:
  connection_pool_size: 50
  batch_insert_size: 5000
```

**Memory Optimized Configuration**:
```yaml
crawler:
  max_concurrent_requests: 20
  request_delay: 0.5
  max_queue_depth: 5000
  batch_size: 100

search:
  index_batch_size: 100
  max_index_memory: 536870912  # 512MB
```

### Resource Monitoring

**Prometheus Metrics**:
```yaml
# prometheus-config.yaml
global:
  scrape_interval: 15s
scrape_configs:
- job_name: 'webcrawler'
  static_configs:
  - targets: ['webcrawler-service:8000']
  metrics_path: /metrics
```

**Grafana Dashboard**: Monitor crawler throughput, search latency, queue depth, and resource utilization.

## Security Configuration

### Network Security

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: webcrawler-network-policy
spec:
  podSelector:
    matchLabels:
      app: webcrawler-pro
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: monitoring
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 5432  # Database
```

### Secrets Management

```bash
# Create database secrets
kubectl create secret generic postgres-secret \
  --from-literal=username=webcrawler \
  --from-literal=password=secure-password \
  --from-literal=host=postgres-service.default.svc.cluster.local

# Create TLS certificates
kubectl create secret tls webcrawler-tls \
  --cert=path/to/tls.cert \
  --key=path/to/tls.key
```

## Disaster Recovery

### Backup Strategy

**Database Backups**:
```bash
# Automated PostgreSQL backups
kubectl create cronjob pg-backup \
  --image=postgres:15 \
  --schedule="0 2 * * *" \
  --restart=OnFailure \
  -- pg_dump -h postgres-service -U webcrawler webcrawler > backup.sql
```

**Configuration Backups**:
```bash
# Backup ConfigMaps and Secrets
kubectl get configmap webcrawler-config -o yaml > config-backup.yaml
kubectl get secret postgres-secret -o yaml > secret-backup.yaml
```

### Recovery Procedures

1. **Database Recovery**: Restore from latest backup
2. **Configuration Recovery**: Apply saved ConfigMaps and Secrets
3. **Application Recovery**: Redeploy with health checks
4. **Data Validation**: Verify search index consistency

## Monitoring and Alerting

### Key Metrics to Monitor

**Performance Metrics**:
- Pages crawled per minute
- Search query response time
- Queue depth and processing rate
- Error rates and retry counts

**Resource Metrics**:
- CPU and memory utilization
- Database connection pool usage
- Network throughput
- Storage usage and growth

**Business Metrics**:
- Content discovery rate
- Search accuracy and relevance
- System uptime and availability
- Data freshness and update frequency

### Alerting Rules

```yaml
# prometheus-alerts.yaml
groups:
- name: webcrawler.rules
  rules:
  - alert: HighCrawlerErrorRate
    expr: rate(crawler_errors_total[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High crawler error rate detected"

  - alert: SearchLatencyHigh
    expr: histogram_quantile(0.95, search_duration_seconds_bucket) > 1.0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Search latency is too high"
```

## Cost Optimization

### Resource Right-sizing

**Development Environment**: 1-2 nodes, burstable instances
**Staging Environment**: 2-3 nodes, standard instances  
**Production Environment**: 3+ nodes with auto-scaling

### Cost Monitoring

- Use cloud provider cost management tools
- Implement resource quotas and limits
- Monitor and optimize database query performance
- Use spot/preemptible instances for non-critical workloads

---

This deployment guide provides a comprehensive framework for running WebCrawler Pro at any scale, from development to enterprise production environments.