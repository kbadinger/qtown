## ---------------------------------------------------------------------------
## Qtown Terraform — Input Variables
## ---------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region where all resources are deployed"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (e.g. production, staging, dev)"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["production", "staging", "dev"], var.environment)
    error_message = "environment must be one of: production, staging, dev."
  }
}

variable "project_name" {
  description = "Project name prefix used for all resource names"
  type        = string
  default     = "qtown"
}

## ---------------------------------------------------------------------------
## Kubernetes
## ---------------------------------------------------------------------------

variable "k8s_cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

variable "k8s_node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  type        = string
  default     = "m5.xlarge"
}

variable "k8s_node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 3
}

variable "k8s_node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "k8s_node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 10
}

## ---------------------------------------------------------------------------
## Postgres (RDS Aurora Serverless v2)
## ---------------------------------------------------------------------------

variable "postgres_instance_class" {
  description = "RDS instance class for the Postgres writer instance"
  type        = string
  default     = "db.r7g.large"
}

variable "postgres_engine_version" {
  description = "Aurora PostgreSQL-compatible engine version"
  type        = string
  default     = "15.5"
}

variable "postgres_database_name" {
  description = "Initial database name"
  type        = string
  default     = "qtown"
}

variable "postgres_master_username" {
  description = "Master username for the RDS cluster"
  type        = string
  default     = "qtown_admin"
  sensitive   = true
}

variable "postgres_backup_retention_days" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}

## ---------------------------------------------------------------------------
## Kafka (Amazon MSK)
## ---------------------------------------------------------------------------

variable "kafka_instance_type" {
  description = "MSK broker instance type"
  type        = string
  default     = "kafka.m5.large"
}

variable "kafka_broker_count" {
  description = "Number of Kafka broker nodes (must be a multiple of the number of AZs)"
  type        = number
  default     = 3
}

variable "kafka_kafka_version" {
  description = "Apache Kafka version for MSK"
  type        = string
  default     = "3.6.0"
}

variable "kafka_volume_size_gb" {
  description = "EBS storage per Kafka broker in GB"
  type        = number
  default     = 100
}

## ---------------------------------------------------------------------------
## Redis (ElastiCache Serverless)
## ---------------------------------------------------------------------------

variable "redis_engine_version" {
  description = "ElastiCache Redis engine version"
  type        = string
  default     = "7.1"
}

variable "redis_node_type" {
  description = "ElastiCache node type (used if not serverless)"
  type        = string
  default     = "cache.r7g.large"
}

variable "redis_num_cache_nodes" {
  description = "Number of Redis cache nodes"
  type        = number
  default     = 2
}

## ---------------------------------------------------------------------------
## Elasticsearch (AWS OpenSearch)
## ---------------------------------------------------------------------------

variable "elasticsearch_instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "r6g.large.search"
}

variable "elasticsearch_instance_count" {
  description = "Number of OpenSearch data nodes"
  type        = number
  default     = 2
}

variable "elasticsearch_volume_size_gb" {
  description = "EBS volume size per OpenSearch node in GB"
  type        = number
  default     = 50
}

variable "elasticsearch_engine_version" {
  description = "OpenSearch engine version"
  type        = string
  default     = "OpenSearch_2.13"
}

## ---------------------------------------------------------------------------
## Networking
## ---------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AWS AZs to use for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
