## ---------------------------------------------------------------------------
## Qtown Terraform — Outputs
## Connection strings and endpoints for all managed services
## ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Kubernetes
# ---------------------------------------------------------------------------

output "k8s_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.kubernetes.cluster_name
}

output "k8s_cluster_endpoint" {
  description = "API server endpoint of the EKS cluster"
  value       = module.kubernetes.cluster_endpoint
  sensitive   = false
}

output "k8s_kubeconfig_command" {
  description = "AWS CLI command to update local kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.kubernetes.cluster_name}"
}

# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------

output "postgres_connection_string" {
  description = "PostgreSQL connection string (password redacted)"
  value       = "postgresql://${var.postgres_master_username}:***@${module.postgres.endpoint}:5432/${var.postgres_database_name}?sslmode=require"
}

output "postgres_host" {
  description = "RDS cluster writer endpoint"
  value       = module.postgres.endpoint
}

output "postgres_reader_host" {
  description = "RDS cluster reader endpoint"
  value       = module.postgres.reader_endpoint
}

output "postgres_secret_arn" {
  description = "Secrets Manager ARN containing Postgres credentials"
  value       = module.postgres.secret_arn
}

# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------

output "kafka_bootstrap_brokers" {
  description = "MSK broker list (plaintext, intra-VPC)"
  value       = module.kafka.bootstrap_brokers
}

output "kafka_bootstrap_brokers_tls" {
  description = "MSK broker list (TLS)"
  value       = module.kafka.bootstrap_brokers_tls
}

output "kafka_zookeeper_connection" {
  description = "MSK ZooKeeper connection string"
  value       = module.kafka.zookeeper_connect_string
}

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

output "redis_primary_endpoint" {
  description = "ElastiCache Redis primary endpoint address"
  value       = module.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "ElastiCache Redis reader endpoint address"
  value       = module.redis.reader_endpoint_address
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = module.redis.port
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "redis://${module.redis.primary_endpoint_address}:${module.redis.port}"
}

# ---------------------------------------------------------------------------
# Elasticsearch / OpenSearch
# ---------------------------------------------------------------------------

output "elasticsearch_endpoint" {
  description = "OpenSearch cluster endpoint"
  value       = module.elasticsearch.endpoint
}

output "elasticsearch_kibana_endpoint" {
  description = "OpenSearch Dashboards (Kibana) endpoint"
  value       = module.elasticsearch.kibana_endpoint
}

output "elasticsearch_domain_arn" {
  description = "OpenSearch domain ARN"
  value       = module.elasticsearch.domain_arn
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}
