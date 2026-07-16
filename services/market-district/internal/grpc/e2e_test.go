//go:build e2e

// End-to-end test for the market trade path (W1-M6). Exercises the REAL
// distributed flow: gRPC PlaceOrder over TCP -> in-memory match -> real Kafka
// produce -> consume the two single-sided trade.settled messages off the bus.
//
// Requires a running Kafka broker (docker-compose.deps.yml). Excluded from the
// normal unit-test build; run with:  go test -tags e2e ./internal/grpc/...
package grpc

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/segmentio/kafka-go"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	mkafka "qtown/market-district/internal/kafka"
	pb "qtown/proto/qtown"
)

func e2eBrokers() string {
	if b := os.Getenv("KAFKA_BROKERS"); b != "" {
		return b
	}
	return "localhost:9092"
}

// ensureTopic idempotently creates a topic, mirroring infra/kafka-init.sh in the
// real stack (kafka-go's Writer does not request auto-creation, so producing to
// a missing topic fails).
func ensureTopic(ctx context.Context, t *testing.T, brokers, topic string) {
	t.Helper()
	conn, err := kafka.DialContext(ctx, "tcp", brokers)
	if err != nil {
		t.Fatalf("dial for topic create: %v", err)
	}
	defer conn.Close()
	controller, err := conn.Controller()
	if err != nil {
		t.Fatalf("controller lookup: %v", err)
	}
	cc, err := kafka.DialContext(ctx, "tcp",
		net.JoinHostPort(controller.Host, strconv.Itoa(controller.Port)))
	if err != nil {
		t.Fatalf("dial controller: %v", err)
	}
	defer cc.Close()
	err = cc.CreateTopics(kafka.TopicConfig{
		Topic: topic, NumPartitions: 6, ReplicationFactor: 1,
	})
	if err != nil && !strings.Contains(err.Error(), "already exists") {
		t.Fatalf("create topic %s: %v", topic, err)
	}
}

// TestE2E_OrderMatch_EmitsTradeSettledToKafka proves the systems core end-to-end:
// a crossing order placed over gRPC produces two single-sided settlement events
// (buyer debit, seller credit) onto the real Kafka topic.
func TestE2E_OrderMatch_EmitsTradeSettledToKafka(t *testing.T) {
	brokers := e2eBrokers()
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()

	// Skip (not fail) if no broker is reachable — keeps the tag runnable anywhere.
	if conn, err := kafka.DialContext(ctx, "tcp", brokers); err != nil {
		t.Skipf("kafka not reachable at %s: %v", brokers, err)
	} else {
		_ = conn.Close()
	}

	// Topics are pre-created in the real stack (kafka-init.sh); do the same here.
	ensureTopic(ctx, t, brokers, mkafka.TopicTradeSettled)

	// Unique resource so we can filter our two messages from anything else on the
	// shared topic (and from prior runs when Kafka isn't ephemeral).
	resource := fmt.Sprintf("e2e-wood-%d", time.Now().UnixNano())

	// Real Kafka producer as the server's emitter.
	producer := mkafka.NewProducer()
	defer producer.Close()

	// Real gRPC server on a TCP port, wired exactly like cmd/server/main.go.
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	srv := grpc.NewServer()
	pb.RegisterMarketDistrictServer(srv, NewMarketServer(producer))
	go func() { _ = srv.Serve(lis) }()
	defer srv.Stop()

	conn, err := grpc.NewClient(
		lis.Addr().String(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer conn.Close()
	client := pb.NewMarketDistrictClient(conn)

	// Consumer group across all partitions (buyer/seller keys hash to different
	// partitions). Unique group + FirstOffset avoids any offset/join race.
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     []string{brokers},
		Topic:       mkafka.TopicTradeSettled,
		GroupID:     fmt.Sprintf("e2e-market-%d", time.Now().UnixNano()),
		StartOffset: kafka.FirstOffset,
		MaxWait:     250 * time.Millisecond,
	})
	defer reader.Close()

	// Place a resting ask (seller npc 2) then a crossing bid (buyer npc 1).
	if _, err := client.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 2, Resource: resource, Side: pb.OrderSide_ASK, Price: 10, Quantity: 5,
	}); err != nil {
		t.Fatalf("place ask: %v", err)
	}
	if _, err := client.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 1, Resource: resource, Side: pb.OrderSide_BID, Price: 10, Quantity: 5,
	}); err != nil {
		t.Fatalf("place bid: %v", err)
	}

	// Collect our two counterparties (keyed by npc_id) off the bus.
	got := map[int64]mkafka.TradeSettledMessage{}
	deadline := time.Now().Add(35 * time.Second)
	for len(got) < 2 && time.Now().Before(deadline) {
		rctx, rcancel := context.WithTimeout(ctx, 5*time.Second)
		m, err := reader.ReadMessage(rctx)
		rcancel()
		if err != nil {
			continue
		}
		var msg mkafka.TradeSettledMessage
		if json.Unmarshal(m.Value, &msg) != nil {
			continue
		}
		if msg.Resource != resource {
			continue // not ours (other runs / other resources)
		}
		got[msg.NPCID] = msg
	}

	if len(got) != 2 {
		t.Fatalf("expected 2 settled messages (buyer+seller), got %d: %+v", len(got), got)
	}
	buyer, seller := got[1], got[2]
	if buyer.GoldDelta >= 0 {
		t.Errorf("buyer gold_delta should be negative, got %v", buyer.GoldDelta)
	}
	if seller.GoldDelta <= 0 {
		t.Errorf("seller gold_delta should be positive, got %v", seller.GoldDelta)
	}
	if buyer.TradeID == "" || buyer.TradeID != seller.TradeID {
		t.Errorf("counterparties should share a non-empty trade_id, got %q / %q",
			buyer.TradeID, seller.TradeID)
	}
	if buyer.Quantity != 5 || buyer.Price != 10 {
		t.Errorf("unexpected buyer price/qty: %+v", buyer)
	}
	t.Logf("e2e OK: buyer=%+v seller=%+v", buyer, seller)
}
