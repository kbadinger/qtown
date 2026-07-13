package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	_ "net/http/pprof"
	"os"
	"os/signal"
	"syscall"
	"time"

	"google.golang.org/grpc"

	marketgrpc "qtown/market-district/internal/grpc"
	"qtown/market-district/internal/kafka"
	pb "qtown/market-district/proto"
)

const (
	grpcPort = ":50051"
	httpPort = ":6060"
)

func main() {
	log.Println("[market-district] starting up")

	// --- gRPC server ---
	lis, err := net.Listen("tcp", grpcPort)
	if err != nil {
		log.Fatalf("[market-district] failed to listen on %s: %v", grpcPort, err)
	}

	grpcServer := grpc.NewServer()

	// --- Kafka producer (best-effort) ---
	// NewProducer only builds a writer; it doesn't dial, so a missing/unreachable
	// broker won't crash startup. Publish failures are logged and swallowed
	// inside MarketServer — a settled-trade event is never allowed to fail a trade.
	producer := kafka.NewProducer()
	defer producer.Close()

	marketSrv := marketgrpc.NewMarketServer(producer)

	// NOTE: gRPC service registration is still blocked on proto codegen —
	// proto/ is a placeholder with no Register* function. Once `buf generate`
	// runs, register the fully-wired server with:
	//   pb.RegisterMarketDistrictServer(grpcServer, marketSrv)

	go func() {
		log.Printf("[market-district] gRPC server listening on %s", grpcPort)
		if err := grpcServer.Serve(lis); err != nil {
			log.Printf("[market-district] gRPC server stopped: %v", err)
		}
	}()

	// --- HTTP server (health + pprof) ---
	mux := http.NewServeMux()

	// pprof endpoints are registered on DefaultServeMux by the net/http/pprof import
	mux.Handle("/debug/pprof/", http.DefaultServeMux)

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		resp, err := marketSrv.Health(r.Context(), &pb.HealthRequest{})
		w.Header().Set("Content-Type", "application/json")
		if err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			if encErr := json.NewEncoder(w).Encode(map[string]string{
				"status":  "error",
				"service": "market-district",
			}); encErr != nil {
				log.Printf("[market-district] health encode error: %v", encErr)
			}
			return
		}
		w.WriteHeader(http.StatusOK)
		payload := map[string]interface{}{
			"status":  resp.Status,
			"service": resp.Service,
			"details": resp.Details,
		}
		if err := json.NewEncoder(w).Encode(payload); err != nil {
			log.Printf("[market-district] health encode error: %v", err)
		}
	})

	httpServer := &http.Server{
		Addr:         httpPort,
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	go func() {
		log.Printf("[market-district] HTTP server listening on %s", httpPort)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("[market-district] HTTP server error: %v", err)
		}
	}()

	// --- Kafka consumer placeholder ---
	go runKafkaConsumer()

	// --- Graceful shutdown ---
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	sig := <-quit
	log.Printf("[market-district] received signal %s, shutting down", sig)

	grpcServer.GracefulStop()
	log.Println("[market-district] gRPC server stopped")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("[market-district] HTTP shutdown error: %v", err)
	}
	log.Println("[market-district] shutdown complete")
}

// runKafkaConsumer is a placeholder for the Kafka consumer loop.
// Replace with a real kafka-go reader once topics are defined.
func runKafkaConsumer() {
	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}
	topic := os.Getenv("KAFKA_TOPIC")
	if topic == "" {
		topic = "qtown.market.orders"
	}

	log.Printf("[market-district] kafka consumer placeholder — broker=%s topic=%s", brokers, topic)

	// Example usage once real consumer is wired in:
	//
	// r := kafka.NewReader(kafka.ReaderConfig{
	//     Brokers:  []string{brokers},
	//     Topic:    topic,
	//     GroupID:  "market-district-consumer",
	//     MinBytes: 1e3,
	//     MaxBytes: 10e6,
	// })
	// defer r.Close()
	// for {
	//     m, err := r.ReadMessage(context.Background())
	//     if err != nil { break }
	//     fmt.Printf("kafka message at offset %d: %s = %s\n", m.Offset, m.Key, m.Value)
	// }

	fmt.Println("[market-district] kafka consumer: not yet connected (placeholder)")
}
