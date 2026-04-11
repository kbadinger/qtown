## ---------------------------------------------------------------------------
## Postgres Module — Amazon RDS Aurora PostgreSQL Serverless v2
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

variable "project_name"             { type = string }
variable "environment"              { type = string }
variable "vpc_id"                   { type = string }
variable "subnet_ids"               { type = list(string) }
variable "security_group_id"        { type = string }
variable "instance_class"           { type = string }
variable "engine_version"           { type = string }
variable "database_name"            { type = string }
variable "master_username"          { type = string ; sensitive = true }
variable "backup_retention_days"    { type = number ; default = 7 }

locals {
  name = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Subnet group
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "this" {
  name        = "${local.name}-postgres"
  subnet_ids  = var.subnet_ids
  description = "Subnet group for ${local.name} Postgres cluster"

  tags = {
    Name = "${local.name}-postgres"
  }
}

# ---------------------------------------------------------------------------
# Cluster parameter group
# ---------------------------------------------------------------------------

resource "aws_rds_cluster_parameter_group" "this" {
  name        = "${local.name}-postgres15"
  family      = "aurora-postgresql15"
  description = "Qtown cluster parameter group for Aurora PostgreSQL 15"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries slower than 1s
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
    apply_method = "pending-reboot"
  }
}

# ---------------------------------------------------------------------------
# Master password in Secrets Manager
# ---------------------------------------------------------------------------

resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "postgres" {
  name                    = "${local.name}/postgres/credentials"
  description             = "Qtown Postgres master credentials"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "postgres" {
  secret_id = aws_secretsmanager_secret.postgres.id
  secret_string = jsonencode({
    POSTGRES_USER     = var.master_username
    POSTGRES_PASSWORD = random_password.master.result
    POSTGRES_HOST     = aws_rds_cluster.this.endpoint
    POSTGRES_PORT     = "5432"
    POSTGRES_DB       = var.database_name
    connection_string = "postgresql://${var.master_username}:${random_password.master.result}@${aws_rds_cluster.this.endpoint}:5432/${var.database_name}?sslmode=require"
  })
}

# ---------------------------------------------------------------------------
# Aurora Cluster
# ---------------------------------------------------------------------------

resource "aws_rds_cluster" "this" {
  cluster_identifier              = "${local.name}-postgres"
  engine                          = "aurora-postgresql"
  engine_version                  = var.engine_version
  engine_mode                     = "provisioned"
  database_name                   = var.database_name
  master_username                 = var.master_username
  master_password                 = random_password.master.result
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [var.security_group_id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.this.name
  backup_retention_period         = var.backup_retention_days
  preferred_backup_window         = "03:00-04:00"
  preferred_maintenance_window    = "sun:04:30-sun:05:30"
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-postgres-final"
  deletion_protection             = var.environment == "production"
  storage_encrypted               = true
  enabled_cloudwatch_logs_exports = ["postgresql"]
  apply_immediately               = var.environment != "production"

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 16
  }

  tags = {
    Name = "${local.name}-postgres"
  }

  lifecycle {
    ignore_changes = [master_password]
  }
}

# ---------------------------------------------------------------------------
# Aurora Instances (writer + optional reader)
# ---------------------------------------------------------------------------

resource "aws_rds_cluster_instance" "writer" {
  identifier         = "${local.name}-postgres-writer"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version
  auto_minor_version_upgrade = true

  tags = {
    Name = "${local.name}-postgres-writer"
    Role = "writer"
  }
}

resource "aws_rds_cluster_instance" "reader" {
  count              = var.environment == "production" ? 1 : 0
  identifier         = "${local.name}-postgres-reader"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version
  auto_minor_version_upgrade = true

  tags = {
    Name = "${local.name}-postgres-reader"
    Role = "reader"
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "endpoint" {
  description = "Aurora cluster writer endpoint"
  value       = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  description = "Aurora cluster reader endpoint"
  value       = aws_rds_cluster.this.reader_endpoint
}

output "secret_arn" {
  description = "Secrets Manager ARN for Postgres credentials"
  value       = aws_secretsmanager_secret.postgres.arn
}

output "cluster_identifier" {
  value = aws_rds_cluster.this.cluster_identifier
}
