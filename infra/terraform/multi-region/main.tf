###############################################################################
# main.tf — Qtown v2 Multi-Region Deployment
#
# Regions:
#   Primary   (us-east-1): town-core, academy, library, cartographer
#   Secondary (eu-west-1): market-district, fortress, tavern
#
# Global:
#   Route53 latency-based routing
#   Cross-region VPC peering
#   MSK (Managed Kafka) with cross-region replication
###############################################################################

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "s3" {
    bucket         = "qtown-terraform-state"
    key            = "multi-region/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "qtown-terraform-locks"
  }
}

###############################################################################
# Provider configuration — aliased per region
###############################################################################

provider "aws" {
  alias  = "primary"
  region = var.primary_region

  default_tags {
    tags = {
      Project     = "qtown"
      Environment = var.environment
      ManagedBy   = "terraform"
      Region      = "primary"
    }
  }
}

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region

  default_tags {
    tags = {
      Project     = "qtown"
      Environment = var.environment
      ManagedBy   = "terraform"
      Region      = "secondary"
    }
  }
}

###############################################################################
# Variables
###############################################################################

variable "primary_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for primary deployment (town-core, academy, library, cartographer)"
}

variable "secondary_region" {
  type        = string
  default     = "eu-west-1"
  description = "AWS region for secondary deployment (market-district, fortress, tavern)"
}

variable "domain_name" {
  type        = string
  description = "Root domain name for Route53 hosted zone (e.g. qtown.example.com)"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment tag"
}

variable "eks_cluster_version" {
  type        = string
  default     = "1.29"
  description = "EKS Kubernetes version"
}

variable "msk_instance_type" {
  type        = string
  default     = "kafka.m5.large"
  description = "MSK broker instance type"
}

variable "msk_broker_count" {
  type        = number
  default     = 3
  description = "Number of MSK brokers per region (must be a multiple of AZ count)"
}

###############################################################################
# Data sources — availability zones per region
###############################################################################

data "aws_availability_zones" "primary" {
  provider = aws.primary
  state    = "available"
}

data "aws_availability_zones" "secondary" {
  provider = aws.secondary
  state    = "available"
}

###############################################################################
# Route53 — Hosted zone (global, managed once)
###############################################################################

resource "aws_route53_zone" "qtown" {
  provider = aws.primary
  name     = var.domain_name

  tags = {
    Name = "qtown-${var.environment}"
  }
}

# Latency-based routing — primary record (us-east-1)
resource "aws_route53_record" "api_primary" {
  provider = aws.primary
  zone_id  = aws_route53_zone.qtown.zone_id
  name     = "api.${var.domain_name}"
  type     = "A"

  latency_routing_policy {
    region = var.primary_region
  }

  set_identifier = "primary"
  alias {
    name                   = aws_lb.primary_alb.dns_name
    zone_id                = aws_lb.primary_alb.zone_id
    evaluate_target_health = true
  }
}

# Latency-based routing — secondary record (eu-west-1)
resource "aws_route53_record" "api_secondary" {
  provider = aws.secondary
  zone_id  = aws_route53_zone.qtown.zone_id
  name     = "api.${var.domain_name}"
  type     = "A"

  latency_routing_policy {
    region = var.secondary_region
  }

  set_identifier = "secondary"
  alias {
    name                   = aws_lb.secondary_alb.dns_name
    zone_id                = aws_lb.secondary_alb.zone_id
    evaluate_target_health = true
  }
}

###############################################################################
# EKS clusters — one per region
###############################################################################

module "eks_primary" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  providers = {
    aws = aws.primary
  }

  cluster_name    = "qtown-primary"
  cluster_version = var.eks_cluster_version
  vpc_id          = module.vpc_primary.vpc_id
  subnet_ids      = module.vpc_primary.private_subnets

  eks_managed_node_groups = {
    core_services = {
      name           = "core-services"
      instance_types = ["m5.xlarge"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3

      labels = {
        workload = "core"
      }
    }
  }

  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
  }
}

module "eks_secondary" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  providers = {
    aws = aws.secondary
  }

  cluster_name    = "qtown-secondary"
  cluster_version = var.eks_cluster_version
  vpc_id          = module.vpc_secondary.vpc_id
  subnet_ids      = module.vpc_secondary.private_subnets

  eks_managed_node_groups = {
    market_services = {
      name           = "market-services"
      instance_types = ["m5.large"]
      min_size       = 2
      max_size       = 8
      desired_size   = 2

      labels = {
        workload = "market"
      }
    }
  }

  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
  }
}

###############################################################################
# Application Load Balancers — one per region (fronts the EKS ingress)
###############################################################################

resource "aws_lb" "primary_alb" {
  provider           = aws.primary
  name               = "qtown-primary-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = module.vpc_primary.public_subnets
  security_groups    = [module.vpc_primary.default_security_group_id]

  enable_deletion_protection = true

  tags = {
    Name = "qtown-primary-alb"
  }
}

resource "aws_lb" "secondary_alb" {
  provider           = aws.secondary
  name               = "qtown-secondary-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = module.vpc_secondary.public_subnets
  security_groups    = [module.vpc_secondary.default_security_group_id]

  enable_deletion_protection = true

  tags = {
    Name = "qtown-secondary-alb"
  }
}

###############################################################################
# MSK — Managed Kafka with cross-region replication
###############################################################################

resource "aws_msk_cluster" "primary" {
  provider              = aws.primary
  cluster_name          = "qtown-kafka-primary"
  kafka_version         = "3.5.1"
  number_of_broker_nodes = var.msk_broker_count

  broker_node_group_info {
    instance_type  = var.msk_instance_type
    client_subnets = slice(module.vpc_primary.private_subnets, 0, min(var.msk_broker_count, length(module.vpc_primary.private_subnets)))
    storage_info {
      ebs_storage_info {
        volume_size = 500
      }
    }
    security_groups = [aws_security_group.msk_primary.id]
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.qtown.arn
    revision = aws_msk_configuration.qtown.latest_revision
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk_primary.name
      }
    }
  }

  tags = {
    Name = "qtown-kafka-primary"
    Role = "primary"
  }
}

resource "aws_msk_cluster" "secondary" {
  provider              = aws.secondary
  cluster_name          = "qtown-kafka-secondary"
  kafka_version         = "3.5.1"
  number_of_broker_nodes = var.msk_broker_count

  broker_node_group_info {
    instance_type  = var.msk_instance_type
    client_subnets = slice(module.vpc_secondary.private_subnets, 0, min(var.msk_broker_count, length(module.vpc_secondary.private_subnets)))
    storage_info {
      ebs_storage_info {
        volume_size = 500
      }
    }
    security_groups = [aws_security_group.msk_secondary.id]
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.qtown.arn
    revision = aws_msk_configuration.qtown.latest_revision
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk_secondary.name
      }
    }
  }

  tags = {
    Name = "qtown-kafka-secondary"
    Role = "secondary"
  }
}

resource "aws_msk_configuration" "qtown" {
  provider       = aws.primary
  name           = "qtown-kafka-config"
  kafka_versions = ["3.5.1"]

  server_properties = <<-EOT
    auto.create.topics.enable=false
    default.replication.factor=3
    min.insync.replicas=2
    log.retention.hours=168
    log.segment.bytes=1073741824
    num.io.threads=8
    num.network.threads=5
    num.partitions=6
    offsets.topic.replication.factor=3
    transaction.state.log.min.isr=2
    transaction.state.log.replication.factor=3
  EOT
}

# MSK Replicator — primary → secondary
resource "aws_msk_replicator" "primary_to_secondary" {
  provider              = aws.primary
  replicator_name       = "qtown-primary-to-secondary"
  description           = "Replicates all qtown topics from us-east-1 to eu-west-1"
  service_execution_role_arn = aws_iam_role.msk_replicator.arn

  kafka_cluster {
    amazon_msk_cluster {
      msk_cluster_arn = aws_msk_cluster.primary.arn
    }
    vpc_config {
      subnet_ids         = module.vpc_primary.private_subnets
      security_groups_ids = [aws_security_group.msk_primary.id]
    }
  }

  kafka_cluster {
    amazon_msk_cluster {
      msk_cluster_arn = aws_msk_cluster.secondary.arn
    }
    vpc_config {
      subnet_ids         = module.vpc_secondary.private_subnets
      security_groups_ids = [aws_security_group.msk_secondary.id]
    }
  }

  replication_info_list {
    source_kafka_cluster_arn = aws_msk_cluster.primary.arn
    target_kafka_cluster_arn = aws_msk_cluster.secondary.arn
    target_compression_type  = "NONE"

    topic_replication {
      topics_to_replicate     = [".*"]
      topics_to_exclude       = ["__consumer_offsets", "__transaction_state"]
      detect_and_copy_new_topics = true
      copy_access_control_lists_for_topics = true
      copy_topic_configurations  = true
    }

    consumer_group_replication {
      consumer_groups_to_replicate = [".*"]
      consumer_groups_to_exclude   = ["console-consumer-.*"]
      detect_and_copy_new_consumer_groups = true
      synchronise_consumer_group_offsets  = true
    }
  }
}

###############################################################################
# IAM — MSK Replicator role
###############################################################################

resource "aws_iam_role" "msk_replicator" {
  provider = aws.primary
  name     = "qtown-msk-replicator"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "kafka.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "msk_replicator_policy" {
  provider   = aws.primary
  role       = aws_iam_role.msk_replicator.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonMSKFullAccess"
}

###############################################################################
# CloudWatch log groups for MSK
###############################################################################

resource "aws_cloudwatch_log_group" "msk_primary" {
  provider          = aws.primary
  name              = "/aws/msk/qtown-primary"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "msk_secondary" {
  provider          = aws.secondary
  name              = "/aws/msk/qtown-secondary"
  retention_in_days = 14
}
