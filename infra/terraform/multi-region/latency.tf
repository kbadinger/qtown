###############################################################################
# latency.tf — Cross-region latency measurement infrastructure
#
# Creates:
#   - CloudWatch Synthetics canary (us-east-1 → eu-west-1 gRPC probe)
#   - Custom CloudWatch metric: qtown/cross-region / CrossRegionGrpcLatencyMs
#   - CloudWatch dashboard showing real-time cross-region latency
#   - CloudWatch alarm for p95 latency > 100ms
###############################################################################

###############################################################################
# IAM role for Synthetics canary
###############################################################################

resource "aws_iam_role" "canary" {
  provider = aws.primary
  name     = "qtown-canary-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "canary" {
  provider = aws.primary
  name     = "qtown-canary-policy"
  role     = aws_iam_role.canary.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:GetBucketLocation",
          "s3:ListAllMyBuckets",
          "s3:GetObjectVersion",
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "qtown/cross-region"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments"]
        Resource = "*"
      },
    ]
  })
}

###############################################################################
# S3 bucket for canary artifacts (screenshots, logs)
###############################################################################

resource "aws_s3_bucket" "canary_artifacts" {
  provider      = aws.primary
  bucket        = "qtown-canary-artifacts-${data.aws_caller_identity.primary.account_id}"
  force_destroy = false

  tags = {
    Name    = "qtown-canary-artifacts"
    Purpose = "synthetics-canary"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "canary_artifacts" {
  provider = aws.primary
  bucket   = aws_s3_bucket.canary_artifacts.id

  rule {
    id     = "expire-old-artifacts"
    status = "Enabled"
    filter { prefix = "" }
    expiration { days = 30 }
  }
}

data "aws_caller_identity" "primary" {
  provider = aws.primary
}

###############################################################################
# CloudWatch Synthetics canary — gRPC latency probe every 5 minutes
###############################################################################

resource "aws_synthetics_canary" "cross_region_latency" {
  provider             = aws.primary
  name                 = "qtown-cross-region-latency"
  artifact_s3_location = "s3://${aws_s3_bucket.canary_artifacts.bucket}/canary/"
  execution_role_arn   = aws_iam_role.canary.arn
  handler              = "latency_probe.handler"
  runtime_version      = "syn-nodejs-puppeteer-6.2"
  start_canary         = true

  schedule {
    expression          = "rate(5 minutes)"
    duration_in_seconds = 0
  }

  run_config {
    timeout_in_seconds    = 60
    memory_in_mb          = 960
    active_tracing        = true
    environment_variables = {
      TARGET_HOST       = "api.${var.domain_name}"
      TARGET_GRPC_PORT  = "50051"
      SECONDARY_REGION  = var.secondary_region
      METRIC_NAMESPACE  = "qtown/cross-region"
    }
  }

  success_retention_period = 7
  failure_retention_period = 30

  # Inline canary script — Node.js that measures gRPC ping latency
  zip_file = filebase64("${path.module}/canary/latency_probe.zip")

  tags = {
    Name    = "qtown-cross-region-latency"
    Purpose = "latency-measurement"
  }
}

# Canary source code lives in canary/latency_probe.js (included via zip)
# The canary:
#   1. Calls town-core's /health endpoint in us-east-1 (baseline)
#   2. Calls market-district's /health endpoint in eu-west-1 via the peered VPC
#   3. Publishes CrossRegionGrpcLatencyMs to qtown/cross-region namespace
#   4. Publishes CrossRegionHttpLatencyMs for ALB round-trip

###############################################################################
# CloudWatch custom metric alarm — p95 > 100ms
###############################################################################

resource "aws_cloudwatch_metric_alarm" "cross_region_latency_high" {
  provider            = aws.primary
  alarm_name          = "qtown-cross-region-latency-high"
  alarm_description   = "Cross-region gRPC p95 latency exceeded 100ms"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 100

  metric_name = "CrossRegionGrpcLatencyMs"
  namespace   = "qtown/cross-region"
  statistic   = "p95"
  period      = 300   # 5-minute intervals (matches canary schedule)
  unit        = "Milliseconds"

  dimensions = {
    Route = "us-east-1-to-eu-west-1"
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]

  treat_missing_data = "breaching"

  tags = {
    Name    = "qtown-cross-region-latency-high"
    Severity = "warning"
  }
}

resource "aws_cloudwatch_metric_alarm" "cross_region_latency_critical" {
  provider            = aws.primary
  alarm_name          = "qtown-cross-region-latency-critical"
  alarm_description   = "Cross-region gRPC p95 latency exceeded 250ms — SLA breach risk"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 250

  metric_name = "CrossRegionGrpcLatencyMs"
  namespace   = "qtown/cross-region"
  statistic   = "p95"
  period      = 300
  unit        = "Milliseconds"

  dimensions = {
    Route = "us-east-1-to-eu-west-1"
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]

  treat_missing_data = "breaching"

  tags = {
    Name    = "qtown-cross-region-latency-critical"
    Severity = "critical"
  }
}

# SNS topic for alarms
resource "aws_sns_topic" "ops_alerts" {
  provider = aws.primary
  name     = "qtown-ops-alerts"

  tags = {
    Name = "qtown-ops-alerts"
  }
}

###############################################################################
# CloudWatch Dashboard — real-time cross-region latency
###############################################################################

resource "aws_cloudwatch_dashboard" "cross_region" {
  provider       = aws.primary
  dashboard_name = "qtown-cross-region-latency"

  dashboard_body = jsonencode({
    widgets = [
      # ── Cross-region gRPC latency (line chart) ─────────────────────────────
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Cross-Region gRPC Latency (ms)"
          view   = "timeSeries"
          stacked = false
          metrics = [
            ["qtown/cross-region", "CrossRegionGrpcLatencyMs",
              "Route", "us-east-1-to-eu-west-1",
              { stat = "p50", label = "p50", color = "#20808D" }],
            ["...", { stat = "p95", label = "p95", color = "#A84B2F" }],
            ["...", { stat = "p99", label = "p99", color = "#944454" }],
          ]
          period = 60
          yAxis  = { left = { min = 0, label = "Latency (ms)" } }
          annotations = {
            horizontal = [
              { label = "Warning (100ms)",  value = 100, color = "#FFC553" },
              { label = "Critical (250ms)", value = 250, color = "#A84B2F" },
            ]
          }
        }
      },

      # ── Cross-region HTTP ALB latency ──────────────────────────────────────
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Cross-Region HTTP Latency (ms)"
          view   = "timeSeries"
          stacked = false
          metrics = [
            ["qtown/cross-region", "CrossRegionHttpLatencyMs",
              "Route", "us-east-1-to-eu-west-1",
              { stat = "p50", label = "p50", color = "#20808D" }],
            ["...", { stat = "p95", label = "p95", color = "#A84B2F" }],
          ]
          period = 60
          yAxis  = { left = { min = 0, label = "Latency (ms)" } }
        }
      },

      # ── Canary success rate ────────────────────────────────────────────────
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 4
        properties = {
          title  = "Canary Success Rate (%)"
          view   = "timeSeries"
          metrics = [
            ["CloudWatchSynthetics", "SuccessPercent",
              "CanaryName", "qtown-cross-region-latency",
              { stat = "Average", color = "#437A22", label = "Success %" }]
          ]
          period = 300
          yAxis  = { left = { min = 0, max = 100 } }
        }
      },

      # ── Alarm status widget ────────────────────────────────────────────────
      {
        type   = "alarm"
        x      = 8
        y      = 6
        width  = 8
        height = 4
        properties = {
          title = "Latency Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.cross_region_latency_high.arn,
            aws_cloudwatch_metric_alarm.cross_region_latency_critical.arn,
          ]
        }
      },

      # ── MSK cross-region replication lag ──────────────────────────────────
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 4
        properties = {
          title  = "MSK Replication Lag (ms)"
          view   = "timeSeries"
          metrics = [
            ["AWS/Kafka", "ReplicationBytesOutPerSec",
              "ClusterName", "qtown-kafka-primary",
              { stat = "Average", label = "Bytes out/s", color = "#20808D" }]
          ]
          period = 60
        }
      },
    ]
  })
}
