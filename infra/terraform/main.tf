## ---------------------------------------------------------------------------
## Qtown Terraform — Root Module
## Provider config + VPC + module wiring
## ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    # Configure via -backend-config or a backend.hcl file
    # bucket         = "qtown-terraform-state"
    # key            = "qtown/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "qtown-terraform-locks"
    # encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Kubernetes provider is configured after the EKS cluster is created
provider "kubernetes" {
  host                   = module.kubernetes.cluster_endpoint
  cluster_ca_certificate = base64decode(module.kubernetes.cluster_ca_certificate)
  token                  = module.kubernetes.cluster_auth_token
}

provider "helm" {
  kubernetes {
    host                   = module.kubernetes.cluster_endpoint
    cluster_ca_certificate = base64decode(module.kubernetes.cluster_ca_certificate)
    token                  = module.kubernetes.cluster_auth_token
  }
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.5"

  name = "${var.project_name}-${var.environment}"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + 10)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # Tags required for EKS cluster auto-discovery
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"                           = "1"
    "kubernetes.io/cluster/${var.project_name}-${var.environment}" = "shared"
  }
  public_subnet_tags = {
    "kubernetes.io/role/elb"                                    = "1"
    "kubernetes.io/cluster/${var.project_name}-${var.environment}" = "shared"
  }
}

# ---------------------------------------------------------------------------
# Security Groups
# ---------------------------------------------------------------------------

resource "aws_security_group" "services" {
  name        = "${var.project_name}-${var.environment}-services"
  description = "Allow intra-cluster traffic between Qtown services"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "All intra-VPC traffic"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-services"
  }
}

# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

module "kubernetes" {
  source = "./modules/kubernetes"

  project_name     = var.project_name
  environment      = var.environment
  aws_region       = var.aws_region
  vpc_id           = module.vpc.vpc_id
  private_subnets  = module.vpc.private_subnets
  cluster_version  = var.k8s_cluster_version
  node_instance_type = var.k8s_node_instance_type
  node_desired_size  = var.k8s_node_desired_size
  node_min_size      = var.k8s_node_min_size
  node_max_size      = var.k8s_node_max_size
  security_group_ids = [aws_security_group.services.id]
}

module "postgres" {
  source = "./modules/postgres"

  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnets
  security_group_id = aws_security_group.services.id
  instance_class    = var.postgres_instance_class
  engine_version    = var.postgres_engine_version
  database_name     = var.postgres_database_name
  master_username   = var.postgres_master_username
  backup_retention_days = var.postgres_backup_retention_days
}

module "kafka" {
  source = "./modules/kafka"

  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnets
  security_group_id = aws_security_group.services.id
  instance_type     = var.kafka_instance_type
  broker_count      = var.kafka_broker_count
  kafka_version     = var.kafka_kafka_version
  volume_size_gb    = var.kafka_volume_size_gb
}

module "redis" {
  source = "./modules/redis"

  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnets
  security_group_id = aws_security_group.services.id
  engine_version    = var.redis_engine_version
  node_type         = var.redis_node_type
  num_cache_nodes   = var.redis_num_cache_nodes
}

module "elasticsearch" {
  source = "./modules/elasticsearch"

  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = slice(module.vpc.private_subnets, 0, min(2, length(module.vpc.private_subnets)))
  security_group_id = aws_security_group.services.id
  instance_type     = var.elasticsearch_instance_type
  instance_count    = var.elasticsearch_instance_count
  volume_size_gb    = var.elasticsearch_volume_size_gb
  engine_version    = var.elasticsearch_engine_version
}
