FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod go.sum* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /market-district ./cmd/server/

FROM alpine:3.20

RUN apk add --no-cache ca-certificates && adduser -D -u 10001 appuser
COPY --from=builder /market-district /market-district
# Run as a non-root user (Trivy DS-0002).
USER appuser

EXPOSE 50051 6060

ENTRYPOINT ["/market-district"]
