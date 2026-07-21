# Market District (Go/gRPC + JSON read-model).
#
# IMPORTANT: build from the REPO ROOT, not this directory:
#   docker build -f services/market-district/Dockerfile -t qtown-market .
#
# go.mod pins `replace qtown/proto => ../../gen/go` (the buf-generated, committed
# cross-service contract). That module lives outside this dir, so the build
# context must include gen/go — hence the repo-root context. The compose file
# sets `context: .` + this dockerfile for the same reason.
FROM golang:1.25-alpine AS builder

WORKDIR /src

# Bring in the generated proto module (the replace target) first so its layer
# caches independently of service source churn. The path mirrors the repo layout
# so go.mod's `../../gen/go` relative replace resolves from the service dir.
COPY gen/go/ ./gen/go/

# Service sources (module qtown/market-district).
COPY services/market-district/ ./services/market-district/

WORKDIR /src/services/market-district
RUN go mod download
# Two binaries from one module: the service, and the demo order-driver (synthetic
# NPC traders) used by the live exhibit. The driver container overrides the
# entrypoint to /market-driver; the default is the service itself.
RUN CGO_ENABLED=0 GOOS=linux go build -o /market-district ./cmd/server/
RUN CGO_ENABLED=0 GOOS=linux go build -o /market-driver   ./cmd/driver/

FROM alpine:3.20

# ca-certificates for outbound TLS; wget (busybox) backs the compose healthcheck
# on :6060/health.
RUN apk add --no-cache ca-certificates && adduser -D -u 10001 appuser
COPY --from=builder /market-district /market-district
COPY --from=builder /market-driver   /market-driver
# Run as a non-root user (Trivy DS-0002).
USER appuser

EXPOSE 50051 6060

ENTRYPOINT ["/market-district"]
