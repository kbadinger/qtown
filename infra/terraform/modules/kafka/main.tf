## ---------------------------------------------------------------------------
## Kafka Module — Amazon MSK (Managed Streaming for Apache Kafka)
## ---------------------------------------------------------------------------

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

variable "project_name"      { type = string }
variable "environment"       { type = string }
variable "vpc_id"            { type = string }
variable "subnet_ids"        { type = list(string) }
variable "security_group_id" { type = string }
variable "instance_type"     { type = string }
variable "broker_count"      { type = number }
variable "kafka_version"     { type = string }
variable "volume_size_gb"    { type = number }

locals {
  name = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# MSK Configuration
# ---------------------------------------------------------------------------

resource "aws_msk_configuration" "this" {
  name              = "${local.name}-kafka"
  kafka_versions    = [var.kafka_version]
  description       = "Qtown Kafka broker configuration"

  server_properties = <<-EOT
    auto.create.topics.enable=false
    default.replication.factor=3
    min.insync.replicas=2
    num.io.threads=8
    num.network.threads=5
    num.partitions=12
    num.replica.fetchers=2
    replica.lag.time.max.ms=30000
    socket.receive.buffer.bytes=102400
    socket.request.max.bytes=104857600
    socket.send.buffer.bytes=102400
    unclean.leader.election.enable=false
    zookeeper.session.timeout.ms=18000
    log.retention.hours=168
    log.segment.bytes=1073741824
    log.retention.check.interval.ms=300000
  EOT
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "msk_broker" {
  name              = "/qtown/${var.environment}/kafka/broker"
  retention_in_days = 30
}

# ---------------------------------------------------------------------------
# MSK Cluster
# ---------------------------------------------------------------------------

resource "aws_msk_cluster" "this" {
  cluster_name           = "${local.name}-kafka"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  broker_node_group_info {
    instance_type   = var.instance_type
    client_subnets  = slice(var.subnet_ids, 0, min(var.broker_count, length(var.subnet_ids)))
    security_groups = [var.security_group_id]

    storage_info {
      ebs_storage_info {
        volume_size = var.volume_size_gb

        provisioned_throughput {
          enabled           = var.environment == "production"
          volume_throughput = 250
        }
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.this.arn
    revision = aws_msk_configuration.this.latest_revision
  }

  client_authentication {
    unauthenticated = true  # Allow unauthenticated within VPC; add SASL/TLS for internet-facing

    sasl {
      scram = false
      iam   = true  # IAM-based authentication
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS_PLAINTEXT"
      in_cluster    = true
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk_broker.name
      }
    }
  }

  tags = {
    Name = "${local.name}-kafka"
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "bootstrap_brokers" {
  description = "MSK plaintext bootstrap broker list"
  value       = aws_msk_cluster.this.bootstrap_brokers
}

output "bootstrap_brokers_tls" {
  description = "MSK TLS bootstrap broker list"
  value       = aws_msk_cluster.this.bootstrap_brokers_tls
}

output "bootstrap_brokers_sasl_iam" {
  description = "MSK SASL/IAM bootstrap broker list"
  value       = aws_msk_cluster.this.bootstrap_brokers_sasl_iam
}

output "zookeeper_connect_string" {
  description = "MSK ZooKeeper connection string"
  value       = aws_msk_cluster.this.zookeeper_connect_string
}

output "cluster_arn" {
  value = aws_msk_cluster.this.arn
}
