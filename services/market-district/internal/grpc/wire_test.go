package grpc

import (
	"context"
	"net"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"

	pb "qtown/proto/qtown"
)

// TestPlaceOrder_ReachableOverGRPC proves the service is actually REGISTERED and
// callable over a real gRPC connection. This is the wiring W1-M1 restores:
// cmd/server/main.go previously never called RegisterMarketDistrictServer, so
// every gRPC call to :50051 failed with "unknown service". It stands up an
// in-memory gRPC server (the same registration path main.go uses), dials it with
// the generated client, places two crossing orders, and asserts a fill.
func TestPlaceOrder_ReachableOverGRPC(t *testing.T) {
	lis := bufconn.Listen(1024 * 1024)
	srv := grpc.NewServer()
	pb.RegisterMarketDistrictServer(srv, NewMarketServer(&fakeEmitter{}))
	go func() { _ = srv.Serve(lis) }()
	t.Cleanup(srv.Stop)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	conn, err := grpc.NewClient(
		"passthrough:///bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return lis.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("dial bufnet: %v", err)
	}
	defer conn.Close()

	client := pb.NewMarketDistrictClient(conn)

	// Resting ask — nothing to cross yet.
	if _, err := client.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 2, Resource: "wood", Side: pb.OrderSide_ASK, Price: 10, Quantity: 5,
	}); err != nil {
		t.Fatalf("place ask over gRPC: %v", err)
	}

	// Crossing bid at the same price — should fill.
	resp, err := client.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 1, Resource: "wood", Side: pb.OrderSide_BID, Price: 10, Quantity: 5,
	})
	if err != nil {
		t.Fatalf("place crossing bid over gRPC: %v", err)
	}
	if !resp.Accepted {
		t.Fatalf("expected crossing bid to be accepted, got %+v", resp)
	}

	// A full cross leaves an empty book on both sides — proof the order matched.
	book, err := client.GetOrderBook(ctx, &pb.OrderBookRequest{Resource: "wood"})
	if err != nil {
		t.Fatalf("get order book over gRPC: %v", err)
	}
	if len(book.Bids) != 0 || len(book.Asks) != 0 {
		t.Fatalf("expected empty book after full cross, got bids=%d asks=%d", len(book.Bids), len(book.Asks))
	}
}
