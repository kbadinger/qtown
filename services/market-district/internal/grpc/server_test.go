package grpc

import (
	"context"
	"encoding/json"
	"sync"
	"testing"

	"qtown/market-district/internal/kafka"
	pb "qtown/proto/qtown"
)

// fakeEmitter is an in-memory tradeEmitter that records every settled message,
// so PlaceOrder's emit path can be unit-tested without a live Kafka broker.
type fakeEmitter struct {
	mu       sync.Mutex
	messages []kafka.TradeSettledMessage
	err      error // optional: force EmitTradeSettled to fail
}

func (f *fakeEmitter) EmitTradeSettled(_ context.Context, settled kafka.TradeSettledMessage) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.messages = append(f.messages, settled)
	return f.err
}

func (f *fakeEmitter) snapshot() []kafka.TradeSettledMessage {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]kafka.TradeSettledMessage, len(f.messages))
	copy(out, f.messages)
	return out
}

// TestPlaceOrder_EmitsSettledPerCounterparty drives a crossing buy+sell and
// asserts exactly two settled messages are emitted with the correct npc_id,
// gold_delta signs, resource, and quantity per the canonical contract.
func TestPlaceOrder_EmitsSettledPerCounterparty(t *testing.T) {
	const (
		buyerNPC  int64   = 1
		sellerNPC int64   = 2
		resource          = "wood"
		price     float32 = 10
		qty       float32 = 5
	)

	fake := &fakeEmitter{}
	srv := NewMarketServer(fake)
	ctx := context.Background()

	// Resting sell order — nothing crosses yet, so nothing settles.
	if _, err := srv.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId:    sellerNPC,
		Resource: resource,
		Side:     pb.OrderSide_ASK,
		Price:    price,
		Quantity: qty,
	}); err != nil {
		t.Fatalf("place sell order: %v", err)
	}
	if got := len(fake.snapshot()); got != 0 {
		t.Fatalf("resting sell should not settle any trade, got %d messages", got)
	}

	// Crossing buy at the same price — one trade, two settled messages.
	if _, err := srv.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId:    buyerNPC,
		Resource: resource,
		Side:     pb.OrderSide_BID,
		Price:    price,
		Quantity: qty,
	}); err != nil {
		t.Fatalf("place buy order: %v", err)
	}

	msgs := fake.snapshot()
	if len(msgs) != 2 {
		t.Fatalf("expected exactly 2 settled messages (buyer+seller), got %d: %+v", len(msgs), msgs)
	}

	notional := float64(price) * float64(qty) // 50

	byNPC := make(map[int64]kafka.TradeSettledMessage, 2)
	for _, m := range msgs {
		byNPC[m.NPCID] = m
	}

	buyer, ok := byNPC[buyerNPC]
	if !ok {
		t.Fatalf("no settled message for buyer npc=%d; got %+v", buyerNPC, msgs)
	}
	seller, ok := byNPC[sellerNPC]
	if !ok {
		t.Fatalf("no settled message for seller npc=%d; got %+v", sellerNPC, msgs)
	}

	// Buyer pays: negative gold_delta. Seller receives: positive gold_delta.
	if buyer.GoldDelta != -notional {
		t.Errorf("buyer gold_delta = %v, want %v", buyer.GoldDelta, -notional)
	}
	if seller.GoldDelta != notional {
		t.Errorf("seller gold_delta = %v, want %v", seller.GoldDelta, notional)
	}

	for label, m := range map[string]kafka.TradeSettledMessage{"buyer": buyer, "seller": seller} {
		if m.Resource != resource {
			t.Errorf("%s resource = %q, want %q", label, m.Resource, resource)
		}
		if m.Price != float64(price) {
			t.Errorf("%s price = %v, want %v", label, m.Price, float64(price))
		}
		if m.Quantity != float64(qty) {
			t.Errorf("%s quantity = %v, want %v", label, m.Quantity, float64(qty))
		}
		if m.TradeID == "" {
			t.Errorf("%s trade_id is empty", label)
		}
	}

	if buyer.TradeID != seller.TradeID {
		t.Errorf("buyer/seller trade_id mismatch: %q vs %q", buyer.TradeID, seller.TradeID)
	}
}

// TestPlaceOrder_NoCrossNoEmit confirms non-crossing orders settle nothing.
func TestPlaceOrder_NoCrossNoEmit(t *testing.T) {
	fake := &fakeEmitter{}
	srv := NewMarketServer(fake)
	ctx := context.Background()

	// Bid below ask — no cross.
	if _, err := srv.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 1, Resource: "iron", Side: pb.OrderSide_BID, Price: 5, Quantity: 1,
	}); err != nil {
		t.Fatalf("place bid: %v", err)
	}
	if _, err := srv.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 2, Resource: "iron", Side: pb.OrderSide_ASK, Price: 9, Quantity: 1,
	}); err != nil {
		t.Fatalf("place ask: %v", err)
	}

	if got := len(fake.snapshot()); got != 0 {
		t.Fatalf("non-crossing orders should emit nothing, got %d", got)
	}
}

// TestPlaceOrder_NilEmitterDoesNotPanic confirms emission is optional: a nil
// emitter (Kafka unavailable) still lets trades match and complete.
func TestPlaceOrder_NilEmitterDoesNotPanic(t *testing.T) {
	srv := NewMarketServer(nil)
	ctx := context.Background()

	if _, err := srv.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 2, Resource: "wood", Side: pb.OrderSide_ASK, Price: 10, Quantity: 5,
	}); err != nil {
		t.Fatalf("place ask with nil emitter: %v", err)
	}
	resp, err := srv.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId: 1, Resource: "wood", Side: pb.OrderSide_BID, Price: 10, Quantity: 5,
	})
	if err != nil {
		t.Fatalf("place crossing bid with nil emitter: %v", err)
	}
	if !resp.Accepted {
		t.Fatalf("crossing order should be accepted even without an emitter")
	}
}

// TestTradeSettledMessage_JSONContractShape locks the on-the-wire shape that
// town-core consumes: exactly npc_id, gold_delta, resource, price, quantity,
// trade_id — no extra fields.
func TestTradeSettledMessage_JSONContractShape(t *testing.T) {
	buyer := kafka.TradeSettledMessage{
		NPCID:     1,
		GoldDelta: -50,
		Resource:  "wood",
		Price:     10,
		Quantity:  5,
		TradeID:   "trade-1",
	}
	seller := kafka.TradeSettledMessage{
		NPCID:     2,
		GoldDelta: 50,
		Resource:  "wood",
		Price:     10,
		Quantity:  5,
		TradeID:   "trade-1",
	}

	buyerJSON, err := json.Marshal(buyer)
	if err != nil {
		t.Fatalf("marshal buyer: %v", err)
	}
	sellerJSON, err := json.Marshal(seller)
	if err != nil {
		t.Fatalf("marshal seller: %v", err)
	}

	const wantBuyer = `{"npc_id":1,"gold_delta":-50,"resource":"wood","price":10,"quantity":5,"trade_id":"trade-1"}`
	const wantSeller = `{"npc_id":2,"gold_delta":50,"resource":"wood","price":10,"quantity":5,"trade_id":"trade-1"}`

	if string(buyerJSON) != wantBuyer {
		t.Errorf("buyer JSON\n got: %s\nwant: %s", buyerJSON, wantBuyer)
	}
	if string(sellerJSON) != wantSeller {
		t.Errorf("seller JSON\n got: %s\nwant: %s", sellerJSON, wantSeller)
	}
}
