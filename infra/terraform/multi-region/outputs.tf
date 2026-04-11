###############################################################################
# outputs.tf — Connection strings, VPC IDs, peering IDs, Route53 record names
###############################################################################

###############################################################################
# VPC outputs
###############################################################################

output "primary_vpc_id" {
  description = "VPC ID in the primary region (us-east-1)"
  value       = module.vpc_primary.vpc_id
}

output "primary_vpc_cidr" {
  description = "CIDR block of the primary VPC"
  value       = module.vpc_primary.vpc_cidr_block
}

output "primary_private_subnet_ids" {
  description = "Private subnet IDs in the primary region"
  value       = module.vpc_primary.private_subnets
}

output "primary_public_subnet_ids" {
  description = "Public subnet IDs in the primary region"
  value       = module.vpc_primary.public_subnets
}

output "secondary_vpc_id" {
  description = "VPC ID in the secondary region (eu-west-1)"
  value       = module.vpc_secondary.vpc_id
}

output "secondary_vpc_cidr" {
  description = "CIDR block of the secondary VPC"
  value       = module.vpc_secondary.vpc_cidr_block
}

output "secondary_private_subnet_ids" {
  description = "Private subnet IDs in the secondary region"
  value       = module.vpc_secondary.private_subnets
}

output "secondary_public_subnet_ids" {
  description = "Public subnet IDs in the secondary region"
  value       = module.vpc_secondary.public_subnets
}

###############################################################################
# VPC Peering outputs
###############################################################################

output "vpc_peering_connection_id" {
  description = "ID of the VPC peering connection between primary and secondary"
  value       = aws_vpc_peering_connection.primary_to_secondary.id
}

output "vpc_peering_status" {
  description = "Status of the VPC peering connection"
  value       = aws_vpc_peering_connection.primary_to_secondary.accept_status
}

###############################################################################
# EKS cluster outputs
###############################################################################

output "eks_primary_cluster_name" {
  description = "EKS cluster name in the primary region"
  value       = module.eks_primary.cluster_name
}

output "eks_primary_cluster_endpoint" {
  description = "EKS API server endpoint in the primary region"
  value       = module.eks_primary.cluster_endpoint
  sensitive   = true
}

output "eks_primary_cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the primary EKS cluster"
  value       = module.eks_primary.cluster_certificate_authority_data
  sensitive   = true
}

output "eks_secondary_cluster_name" {
  description = "EKS cluster name in the secondary region"
  value       = module.eks_secondary.cluster_name
}

output "eks_secondary_cluster_endpoint" {
  description = "EKS API server endpoint in the secondary region"
  value       = module.eks_secondary.cluster_endpoint
  sensitive   = true
}

output "eks_secondary_cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the secondary EKS cluster"
  value       = module.eks_secondary.cluster_certificate_authority_data
  sensitive   = true
}

###############################################################################
# MSK / Kafka connection strings
###############################################################################

output "msk_primary_bootstrap_brokers_tls" {
  description = "TLS bootstrap brokers for the primary MSK cluster (use port 9094)"
  value       = aws_msk_cluster.primary.bootstrap_brokers_tls
  sensitive   = true
}

output "msk_primary_bootstrap_brokers" {
  description = "Plaintext bootstrap brokers for the primary MSK cluster (dev/testing only)"
  value       = aws_msk_cluster.primary.bootstrap_brokers
  sensitive   = true
}

output "msk_primary_zookeeper_connection_string" {
  description = "ZooKeeper connection string for the primary MSK cluster"
  value       = aws_msk_cluster.primary.zookeeper_connect_string
  sensitive   = true
}

output "msk_secondary_bootstrap_brokers_tls" {
  description = "TLS bootstrap brokers for the secondary MSK cluster"
  value       = aws_msk_cluster.secondary.bootstrap_brokers_tls
  sensitive   = true
}

output "msk_secondary_bootstrap_brokers" {
  description = "Plaintext bootstrap brokers for the secondary MSK cluster (dev/testing only)"
  value       = aws_msk_cluster.secondary.bootstrap_brokers
  sensitive   = true
}

output "msk_replicator_arn" {
  description = "ARN of the MSK cross-region replicator"
  value       = aws_msk_replicator.primary_to_secondary.arn
}

###############################################################################
# Route53 outputs
###############################################################################

output "route53_zone_id" {
  description = "Route53 hosted zone ID for the domain"
  value       = aws_route53_zone.qtown.zone_id
}

output "route53_zone_name" {
  description = "Route53 hosted zone name (the domain)"
  value       = aws_route53_zone.qtown.name
}

output "route53_name_servers" {
  description = "Name servers for the hosted zone — configure these at your registrar"
  value       = aws_route53_zone.qtown.name_servers
}

output "route53_api_record_primary" {
  description = "Route53 latency record pointing to primary ALB (us-east-1)"
  value       = aws_route53_record.api_primary.fqdn
}

output "route53_api_record_secondary" {
  description = "Route53 latency record pointing to secondary ALB (eu-west-1)"
  value       = aws_route53_record.api_secondary.fqdn
}

output "api_endpoint" {
  description = "Global API endpoint (latency-routed via Route53)"
  value       = "https://api.${var.domain_name}"
}

###############################################################################
# ALB connection strings
###############################################################################

output "primary_alb_dns_name" {
  description = "DNS name of the Application Load Balancer in the primary region"
  value       = aws_lb.primary_alb.dns_name
}

output "primary_alb_arn" {
  description = "ARN of the ALB in the primary region"
  value       = aws_lb.primary_alb.arn
}

output "secondary_alb_dns_name" {
  description = "DNS name of the Application Load Balancer in the secondary region"
  value       = aws_lb.secondary_alb.dns_name
}

output "secondary_alb_arn" {
  description = "ARN of the ALB in the secondary region"
  value       = aws_lb.secondary_alb.arn
}

###############################################################################
# Monitoring outputs
###############################################################################

output "cloudwatch_dashboard_url" {
  description = "URL to the cross-region latency CloudWatch dashboard"
  value       = "https://${var.primary_region}.console.aws.amazon.com/cloudwatch/home?region=${var.primary_region}#dashboards:name=${aws_cloudwatch_dashboard.cross_region.dashboard_name}"
}

output "canary_name" {
  description = "Name of the CloudWatch Synthetics canary for cross-region latency"
  value       = aws_synthetics_canary.cross_region_latency.name
}

output "canary_artifact_bucket" {
  description = "S3 bucket storing canary artifacts (screenshots, logs)"
  value       = aws_s3_bucket.canary_artifacts.bucket
}

output "ops_alerts_sns_topic_arn" {
  description = "SNS topic ARN for operational alerts (subscribe PagerDuty/email here)"
  value       = aws_sns_topic.ops_alerts.arn
}

output "latency_alarm_high_arn" {
  description = "ARN of the CloudWatch alarm for p95 latency > 100ms"
  value       = aws_cloudwatch_metric_alarm.cross_region_latency_high.arn
}

output "latency_alarm_critical_arn" {
  description = "ARN of the CloudWatch alarm for p95 latency > 250ms"
  value       = aws_cloudwatch_metric_alarm.cross_region_latency_critical.arn
}

###############################################################################
# Security group IDs
###############################################################################

output "sg_cross_region_primary_id" {
  description = "Security group ID allowing cross-region traffic in the primary region"
  value       = aws_security_group.cross_region_primary.id
}

output "sg_cross_region_secondary_id" {
  description = "Security group ID allowing cross-region traffic in the secondary region"
  value       = aws_security_group.cross_region_secondary.id
}

output "sg_msk_primary_id" {
  description = "Security group ID for the primary MSK cluster"
  value       = aws_security_group.msk_primary.id
}

output "sg_msk_secondary_id" {
  description = "Security group ID for the secondary MSK cluster"
  value       = aws_security_group.msk_secondary.id
}

###############################################################################
# Convenience: kubectl config commands
###############################################################################

output "kubectl_config_primary" {
  description = "Command to configure kubectl for the primary EKS cluster"
  value       = "aws eks update-kubeconfig --region ${var.primary_region} --name ${module.eks_primary.cluster_name}"
}

output "kubectl_config_secondary" {
  description = "Command to configure kubectl for the secondary EKS cluster"
  value       = "aws eks update-kubeconfig --region ${var.secondary_region} --name ${module.eks_secondary.cluster_name}"
}
