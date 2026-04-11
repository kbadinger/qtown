package orderbook

import (
	"fmt"
	"sync"
	"testing"
	"time"
)

func TestPlaceOrder_BidSide(t *testing.T) {
	ob := NewOrderBook("wood")
	ob.PlaceOrder(Order{ID: "1", NPCID: "npc1", Resource: "wood", Side: BID, Price: 10.0, Quantity: 5.0})
	snap := ob.GetSnapshot()
	if len(snap.Bids) != 1 {
		t.Fatalf("expected 1 bid, got %d", len(snap.Bids))
	}
	if snap.Bids[0].Price != 10.0 {
		t.Fatalf("expected price 10.0, got %f", snap.Bids[0].Price)
	}
}

func TestPlaceOrder_AskSide(t *testing.T) {
	ob := NewOrderBook("wood")
	ob.PlaceOrder(Order{ID: "1", NPCID: "npc1", Resource: "wood", Side: ASK, Price: 12.0, Quantity: 3.0})
	snap := ob.GetSnapshot()
	if len(snap.Asks) != 1 {
		t.Fatalf("expected 1 ask, got %d", len(snap.Asks))
	}
}

func TestMatch_FullFill(t *testing.T) {
	ob := NewOrderBook("iron")
	ob.PlaceOrder(Order{ID: "b1", NPCID: "buyer", Resource: "iron", Side: BID, Price: 15.0, Quantity: 10.0})
	ob.PlaceOrder(Order{ID: "a1", NPCID: "seller", Resource: "iron", Side: ASK, Price: 14.0, Quantity: 10.0})
	trades := ob.Match()
	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}
	if trades[0].Quantity != 10.0 {
		t.Fatalf("expected fill qty 10, got %f", trades[0].Quantity)
	}
	if trades[0].Price != 14.0 {
		t.Fatalf("expected exec price 14 (ask), got %f", trades[0].Price)
	}
}

func TestMatch_PartialFill(t *testing.T) {
	ob := NewOrderBook("food")
	ob.PlaceOrder(Order{ID: "b1", NPCID: "buyer", Resource: "food", Side: BID, Price: 20.0, Quantity: 100.0})
	ob.PlaceOrder(Order{ID: "a1", NPCID: "seller", Resource: "food", Side: ASK, Price: 18.0, Quantity: 30.0})
	trades := ob.Match()
	if len(trades) != 1 {
		t.Fatalf("expected 1 trade, got %d", len(trades))
	}
	if trades[0].Quantity != 30.0 {
		t.Fatalf("expected partial fill 30, got %f", trades[0].Quantity)
	}
	snap := ob.GetSnapshot()
	if len(snap.Bids) != 1 || snap.Bids[0].Quantity != 70.0 {
		t.Fatalf("expected remaining bid qty 70, got %v", snap.Bids)
	}
}

func TestMatch_NoMatch(t *testing.T) {
	ob := NewOrderBook("gold")
	ob.PlaceOrder(Order{ID: "b1", NPCID: "buyer", Resource: "gold", Side: BID, Price: 10.0, Quantity: 5.0})
	ob.PlaceOrder(Order{ID: "a1", NPCID: "seller", Resource: "gold", Side: ASK, Price: 15.0, Quantity: 5.0})
	trades := ob.Match()
	if len(trades) != 0 {
		t.Fatalf("expected 0 trades, got %d", len(trades))
	}
}

func TestSnapshot_Isolation(t *testing.T) {
	ob := NewOrderBook("stone")
	ob.PlaceOrder(Order{ID: "1", NPCID: "npc1", Resource: "stone", Side: BID, Price: 10.0, Quantity: 5.0})
	snap := ob.GetSnapshot()
	ob.PlaceOrder(Order{ID: "2", NPCID: "npc2", Resource: "stone", Side: BID, Price: 12.0, Quantity: 3.0})
	if len(snap.Bids) != 1 {
		t.Fatalf("snapshot should be isolated, got %d bids", len(snap.Bids))
	}
}

func TestConcurrentOrders(t *testing.T) {
	ob := NewOrderBook("wheat")
	var wg sync.WaitGroup
	numGoroutines := 100
	ordersPerGoroutine := 100

	for g := 0; g < numGoroutines; g++ {
		wg.Add(1)
		go func(gid int) {
			defer wg.Done()
			for i := 0; i < ordersPerGoroutine; i++ {
				side := BID
				if i%2 == 0 {
					side = ASK
				}
				ob.PlaceOrder(Order{
					ID:       fmt.Sprintf("g%d-o%d", gid, i),
					NPCID:    fmt.Sprintf("npc-%d", gid),
					Resource: "wheat",
					Side:     side,
					Price:    100.0 + float64(i%20) - 10.0,
					Quantity: 1.0,
				})
				ob.Match()
			}
		}(g)
	}
	wg.Wait()
	// If we get here without a data race panic, the mutex works
}

// BenchmarkOrderBook measures throughput of concurrent order placement + matching.
func BenchmarkOrderBook(b *testing.B) {
	ob := NewOrderBook("bench-resource")
	var wg sync.WaitGroup

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		wg.Add(2)
		go func() {
			defer wg.Done()
			ob.PlaceOrder(Order{
				ID:       fmt.Sprintf("bid-%d", i),
				NPCID:    "bench-buyer",
				Resource: "bench-resource",
				Side:     BID,
				Price:    100.0 + float64(i%10),
				Quantity: 1.0,
			})
		}()
		go func() {
			defer wg.Done()
			ob.PlaceOrder(Order{
				ID:       fmt.Sprintf("ask-%d", i),
				NPCID:    "bench-seller",
				Resource: "bench-resource",
				Side:     ASK,
				Price:    100.0 + float64(i%10),
				Quantity: 1.0,
			})
		}()
		wg.Wait()
		ob.Match()
	}
}

// BenchmarkConcurrentOrders — the proof test: 10K concurrent orders via goroutines
func BenchmarkConcurrentOrders(b *testing.B) {
	for range b.N {
		ob := NewOrderBook("stress")
		var wg sync.WaitGroup
		numTraders := 100

		start := time.Now()
		for t := 0; t < numTraders; t++ {
			wg.Add(1)
			go func(tid int) {
				defer wg.Done()
				for i := 0; i < 100; i++ {
					side := BID
					if i%2 == 0 {
						side = ASK
					}
					ob.PlaceOrder(Order{
						ID:       fmt.Sprintf("t%d-o%d", tid, i),
						NPCID:    fmt.Sprintf("npc-%d", tid),
						Resource: "stress",
						Side:     side,
						Price:    50.0 + float64(i%30),
						Quantity: 1.0,
					})
					ob.Match()
				}
			}(t)
		}
		wg.Wait()
		_ = time.Since(start)
	}
}
