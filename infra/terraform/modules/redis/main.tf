## ---------------------------------------------------------------------------
## Redis Module — Amazon ElastiCache for Redis (Cluster Mode Disabled)
## ---------------------------------------------------------------------------

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

variable "project_name"      { type = string }
variable "environment"       { type = string }
variable "vpc_id"            { type = string }
variable "subnet_ids"        { type = list(string) }
variable "security_group_id" { type = string }
variable "engine_version"    { type = string }
variable "node_type"         { type = string }
variable "num_cache_nodes"   { type = number }

locals {
  name = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Subnet group
# ---------------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "this" {
  name        = "${local.name}-redis"
  subnet_ids  = var.subnet_ids
  description = "Subnet group for ${local.name} Redis cluster"

  tags = {
    Name = "${local.name}-redis"
  }
}

# ---------------------------------------------------------------------------
# Parameter group
# ---------------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "this" {
  name        = "${local.name}-redis7"
  family      = "redis7"
  description = "Qtown Redis 7 parameter group"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "activerehashing"
    value = "yes"
  }

  parameter {
    name  = "lazyfree-lazy-eviction"
    value = "yes"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"  # Expired key notifications
  }
}

# ---------------------------------------------------------------------------
# Auth token in Secrets Manager
# ---------------------------------------------------------------------------

resource "random_password" "redis_auth" {
  length  = 64
  special = false  # Redis auth tokens must be alphanumeric + some symbols
}

resource "aws_secretsmanager_secret" "redis" {
  name                    = "${local.name}/redis/credentials"
  description             = "Qtown Redis auth token"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({
    REDIS_PASSWORD = random_password.redis_auth.result
    REDIS_HOST     = aws_elasticache_replication_group.this.primary_endpoint_address
    REDIS_PORT     = "6379"
  })
}

# ---------------------------------------------------------------------------
# Replication Group (supports read replicas + Multi-AZ)
# ---------------------------------------------------------------------------

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = "${local.name}-redis"
  description                = "Qtown ${var.environment} Redis cluster"
  node_type                  = var.node_type
  engine_version             = var.engine_version
  parameter_group_name       = aws_elasticache_parameter_group.this.name
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [var.security_group_id]
  num_cache_clusters         = var.num_cache_nodes
  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.num_cache_nodes > 1 && var.environment == "production"
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result
  auto_minor_version_upgrade = true
  maintenance_window         = "sun:05:00-sun:06:00"
  snapshot_retention_limit   = var.environment == "production" ? 5 : 1
  snapshot_window            = "04:00-05:00"

  log_delivery_configuration {
    destination      = "/qtown/${var.environment}/redis/slow-log"
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  tags = {
    Name = "${local.name}-redis"
  }

  lifecycle {
    ignore_changes = [auth_token]
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group for slow log
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "redis_slow" {
  name              = "/qtown/${var.environment}/redis/slow-log"
  retention_in_days = 14
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "primary_endpoint_address" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "Redis reader endpoint"
  value       = aws_elasticache_replication_group.this.reader_endpoint_address
}

output "port" {
  value = 6379
}

output "secret_arn" {
  description = "Secrets Manager ARN for Redis credentials"
  value       = aws_secretsmanager_secret.redis.arn
}

output "replication_group_id" {
  value = aws_elasticache_replication_group.this.id
}
