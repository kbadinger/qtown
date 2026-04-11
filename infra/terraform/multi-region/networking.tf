###############################################################################
# networking.tf — Cross-region VPC configuration for Qtown
#
# Creates:
#   - VPC in each region with public/private subnets
#   - VPC peering connection (primary → secondary)
#   - Route tables for cross-region traffic via the peering connection
#   - Security groups allowing gRPC (50051-50058) + Kafka (9092, 9094) cross-region
###############################################################################

###############################################################################
# Primary VPC (us-east-1)
###############################################################################

module "vpc_primary" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  providers = {
    aws = aws.primary
  }

  name = "qtown-primary-vpc"
  cidr = "10.10.0.0/16"

  azs = slice(data.aws_availability_zones.primary.names, 0, 3)

  private_subnets = ["10.10.1.0/24", "10.10.2.0/24", "10.10.3.0/24"]
  public_subnets  = ["10.10.101.0/24", "10.10.102.0/24", "10.10.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name   = "qtown-primary-vpc"
    Region = var.primary_region
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "kubernetes.io/cluster/qtown-primary" = "owned"
  }

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
    "kubernetes.io/cluster/qtown-primary" = "owned"
  }
}

###############################################################################
# Secondary VPC (eu-west-1)
###############################################################################

module "vpc_secondary" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  providers = {
    aws = aws.secondary
  }

  name = "qtown-secondary-vpc"
  cidr = "10.20.0.0/16"

  azs = slice(data.aws_availability_zones.secondary.names, 0, 3)

  private_subnets = ["10.20.1.0/24", "10.20.2.0/24", "10.20.3.0/24"]
  public_subnets  = ["10.20.101.0/24", "10.20.102.0/24", "10.20.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name   = "qtown-secondary-vpc"
    Region = var.secondary_region
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "kubernetes.io/cluster/qtown-secondary" = "owned"
  }

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
    "kubernetes.io/cluster/qtown-secondary" = "owned"
  }
}

###############################################################################
# VPC Peering connection — primary (requester) ↔ secondary (accepter)
###############################################################################

# Requester side — created in primary region
resource "aws_vpc_peering_connection" "primary_to_secondary" {
  provider    = aws.primary
  vpc_id      = module.vpc_primary.vpc_id
  peer_vpc_id = module.vpc_secondary.vpc_id
  peer_region = var.secondary_region
  auto_accept = false

  tags = {
    Name = "qtown-primary-to-secondary"
    Side = "requester"
  }
}

# Accepter side — auto-accept in secondary region
resource "aws_vpc_peering_connection_accepter" "secondary" {
  provider                  = aws.secondary
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
  auto_accept               = true

  tags = {
    Name = "qtown-primary-to-secondary"
    Side = "accepter"
  }
}

# DNS resolution across peers
resource "aws_vpc_peering_connection_options" "primary_requester" {
  provider                  = aws.primary
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id

  requester {
    allow_remote_vpc_dns_resolution = true
  }

  depends_on = [aws_vpc_peering_connection_accepter.secondary]
}

resource "aws_vpc_peering_connection_options" "secondary_accepter" {
  provider                  = aws.secondary
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id

  accepter {
    allow_remote_vpc_dns_resolution = true
  }

  depends_on = [aws_vpc_peering_connection_accepter.secondary]
}

###############################################################################
# Route tables — add cross-region routes via VPC peering
###############################################################################

# Primary private subnets → secondary CIDR via peering
resource "aws_route" "primary_to_secondary" {
  provider                  = aws.primary
  count                     = length(module.vpc_primary.private_route_table_ids)
  route_table_id            = module.vpc_primary.private_route_table_ids[count.index]
  destination_cidr_block    = "10.20.0.0/16"
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id

  depends_on = [aws_vpc_peering_connection_accepter.secondary]
}

# Secondary private subnets → primary CIDR via peering
resource "aws_route" "secondary_to_primary" {
  provider                  = aws.secondary
  count                     = length(module.vpc_secondary.private_route_table_ids)
  route_table_id            = module.vpc_secondary.private_route_table_ids[count.index]
  destination_cidr_block    = "10.10.0.0/16"
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id

  depends_on = [aws_vpc_peering_connection_accepter.secondary]
}

###############################################################################
# Security groups — allow cross-region gRPC + Kafka traffic
###############################################################################

# Primary region — accepts inbound from secondary CIDR
resource "aws_security_group" "cross_region_primary" {
  provider    = aws.primary
  name        = "qtown-cross-region-inbound"
  description = "Allow gRPC and Kafka traffic from eu-west-1 (secondary VPC)"
  vpc_id      = module.vpc_primary.vpc_id

  # gRPC services (town-core, academy, library, cartographer)
  ingress {
    description = "gRPC services from secondary region"
    from_port   = 50051
    to_port     = 50058
    protocol    = "tcp"
    cidr_blocks = ["10.20.0.0/16"]
  }

  # Kafka plaintext (within VPC only — MSK uses TLS on 9094)
  ingress {
    description = "Kafka from secondary region"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = ["10.20.0.0/16"]
  }

  # Kafka TLS
  ingress {
    description = "Kafka TLS from secondary region"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = ["10.20.0.0/16"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "qtown-cross-region-inbound-primary"
  }
}

# Secondary region — accepts inbound from primary CIDR
resource "aws_security_group" "cross_region_secondary" {
  provider    = aws.secondary
  name        = "qtown-cross-region-inbound"
  description = "Allow gRPC and Kafka traffic from us-east-1 (primary VPC)"
  vpc_id      = module.vpc_secondary.vpc_id

  ingress {
    description = "gRPC services from primary region"
    from_port   = 50051
    to_port     = 50058
    protocol    = "tcp"
    cidr_blocks = ["10.10.0.0/16"]
  }

  ingress {
    description = "Kafka from primary region"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = ["10.10.0.0/16"]
  }

  ingress {
    description = "Kafka TLS from primary region"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = ["10.10.0.0/16"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "qtown-cross-region-inbound-secondary"
  }
}

# MSK security groups (referenced from main.tf)
resource "aws_security_group" "msk_primary" {
  provider    = aws.primary
  name        = "qtown-msk-primary"
  description = "MSK broker security group — primary region"
  vpc_id      = module.vpc_primary.vpc_id

  ingress {
    description = "Kafka TLS from within primary VPC"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [module.vpc_primary.vpc_cidr_block]
  }

  ingress {
    description = "Kafka TLS from secondary VPC (replication)"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = ["10.20.0.0/16"]
  }

  ingress {
    description = "ZooKeeper (internal MSK cluster communication)"
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "qtown-msk-primary"
  }
}

resource "aws_security_group" "msk_secondary" {
  provider    = aws.secondary
  name        = "qtown-msk-secondary"
  description = "MSK broker security group — secondary region"
  vpc_id      = module.vpc_secondary.vpc_id

  ingress {
    description = "Kafka TLS from within secondary VPC"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [module.vpc_secondary.vpc_cidr_block]
  }

  ingress {
    description = "Kafka TLS from primary VPC (replication)"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = ["10.10.0.0/16"]
  }

  ingress {
    description = "ZooKeeper (internal MSK cluster communication)"
    from_port   = 2181
    to_port     = 2181
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "qtown-msk-secondary"
  }
}
