## ---------------------------------------------------------------------------
## Elasticsearch Module — Amazon OpenSearch Service
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
variable "instance_type"     { type = string }
variable "instance_count"    { type = number }
variable "volume_size_gb"    { type = number }
variable "engine_version"    { type = string }

locals {
  name        = "${var.project_name}-${var.environment}"
  domain_name = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Master password
# ---------------------------------------------------------------------------

resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>"
}

resource "aws_secretsmanager_secret" "opensearch" {
  name                    = "${local.name}/opensearch/credentials"
  description             = "Qtown OpenSearch master credentials"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "opensearch" {
  secret_id = aws_secretsmanager_secret.opensearch.id
  secret_string = jsonencode({
    ELASTICSEARCH_USERNAME = "admin"
    ELASTICSEARCH_PASSWORD = random_password.master.result
    ELASTICSEARCH_URL      = "https://${aws_opensearch_domain.this.endpoint}"
  })
}

# ---------------------------------------------------------------------------
# IAM service-linked role (required for VPC access)
# ---------------------------------------------------------------------------

resource "aws_iam_service_linked_role" "opensearch" {
  aws_service_name = "opensearchservice.amazonaws.com"

  lifecycle {
    ignore_errors = true  # Role may already exist
  }
}

# ---------------------------------------------------------------------------
# OpenSearch Domain
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_opensearch_domain" "this" {
  domain_name    = local.domain_name
  engine_version = var.engine_version

  cluster_config {
    instance_type            = var.instance_type
    instance_count           = var.instance_count
    zone_awareness_enabled   = var.instance_count > 1
    dedicated_master_enabled = var.instance_count >= 3 && var.environment == "production"
    dedicated_master_type    = var.instance_count >= 3 && var.environment == "production" ? "r6g.large.search" : null
    dedicated_master_count   = var.instance_count >= 3 && var.environment == "production" ? 3 : null

    dynamic "zone_awareness_config" {
      for_each = var.instance_count > 1 ? [1] : []
      content {
        availability_zone_count = min(var.instance_count, 3)
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.volume_size_gb
    throughput  = 250
    iops        = 3000
  }

  vpc_options {
    subnet_ids         = slice(var.subnet_ids, 0, min(var.instance_count, length(var.subnet_ids)))
    security_group_ids = [var.security_group_id]
  }

  advanced_security_options {
    enabled                        = true
    anonymous_auth_enabled         = false
    internal_user_database_enabled = true

    master_user_options {
      master_user_name     = "admin"
      master_user_password = random_password.master.result
    }
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_index.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_search.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_error.arn
    log_type                 = "ES_APPLICATION_LOGS"
  }

  auto_tune_options {
    desired_state = "ENABLED"
    rollback_on_disable = "NO_ROLLBACK"
  }

  tags = {
    Name = "${local.name}-opensearch"
  }

  depends_on = [aws_iam_service_linked_role.opensearch]

  lifecycle {
    ignore_changes = [advanced_security_options[0].master_user_options[0].master_user_password]
  }
}

# ---------------------------------------------------------------------------
# Access Policy — allow intra-VPC access
# ---------------------------------------------------------------------------

resource "aws_opensearch_domain_policy" "this" {
  domain_name = aws_opensearch_domain.this.domain_name

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = "*" }
        Action    = "es:*"
        Resource  = "${aws_opensearch_domain.this.arn}/*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "opensearch_index" {
  name              = "/qtown/${var.environment}/opensearch/index-slow"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "opensearch_search" {
  name              = "/qtown/${var.environment}/opensearch/search-slow"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "opensearch_error" {
  name              = "/qtown/${var.environment}/opensearch/application"
  retention_in_days = 30
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "endpoint" {
  description = "OpenSearch domain endpoint (without protocol)"
  value       = aws_opensearch_domain.this.endpoint
}

output "kibana_endpoint" {
  description = "OpenSearch Dashboards endpoint"
  value       = aws_opensearch_domain.this.kibana_endpoint
}

output "domain_arn" {
  value = aws_opensearch_domain.this.arn
}

output "secret_arn" {
  description = "Secrets Manager ARN for OpenSearch credentials"
  value       = aws_secretsmanager_secret.opensearch.arn
}
