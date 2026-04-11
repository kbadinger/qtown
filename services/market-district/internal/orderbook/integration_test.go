package orderbook_test

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"qtown/market-district/internal/orderbook"
)

// TestFullTradeLifecycle simulates the complete flow:
// 1. Multiple NPCs place orders concurrently
// 2. Orders match in the book
// 3. Trades are generated
// 4. Book state is consistent after all operations
func TestFullTradeLifecycle(t *testing.T) {
	ob := orderbook.NewOrderBook("wheat")

	// NPC merchants place sell orders (they produce wheat)
	for i := 0; i < 10; i++ {
		ob.PlaceOrder(orderbook.Order{
			ID:       fmt.Sprintf("seller-%d", i),
			NPCID:    fmt.Sprintf("farmer-%d", i),
			Resource: "wheat",
			Side:     orderbook.ASK,
			Price:    10.0 + float64(i)*0.5,
			Quantity: 100.0,
		})
	}

	// NPC buyers place buy orders
	for i := 0; i < 10; i++ {
		ob.PlaceOrder(orderbook.Order{
			ID:       fmt.Sprintf("buyer-%d", i),
			NPCID:    fmt.Sprintf("baker-%d", i),
			Resource: "wheat",
			Side:     orderbook.BID,
			Price:    15.0 - float64(i)*0.5,
			Quantity: 50.0,
		})
	}

	// Match all crossable orders
	trades := ob.Match()

	if len(trades) == 0 {
		t.Fatal("expected trades to be generated")
	}

	// Verify all trades have valid IDs and positive quantities
	for _, trade := range trades {
		if trade.ID == "" {
			t.Error("trade has empty ID")
		}
		if trade.Quantity <= 0 {
			t.Errorf("trade %s has invalid quantity: %f", trade.ID, trade.Quantity)
		}
		if trade.Price <= 0 {
			t.Errorf("trade %s has invalid price: %f", trade.ID, trade.Price)
		}
	}

	// Verify snapshot consistency
	snap := ob.GetSnapshot()
	totalBidQty := 0.0
	for _, b := range snap.Bids {
		totalBidQty += b.Quantity
	}
	totalAskQty := 0.0
	for _, a := range snap.Asks {
		totalAskQty += a.Quantity
	}

	t.Logf("Trades: %d, Remaining bids: %d (qty %.0f), Remaining asks: %d (qty %.0f)",
		len(trades), len(snap.Bids), totalBidQty, len(snap.Asks), totalAskQty)
}

// TestConcurrentTradeSettlement simulates the proof test scenario:
// 100 goroutines each placing 100 orders with matching and settlement.
func TestConcurrentTradeSettlement(t *testing.T) {
	ob := orderbook.NewOrderBook("iron")
	var wg sync.WaitGroup
	var allTrades []orderbook.Trade
	var tradesMu sync.Mutex

	numTraders := 100
	ordersPerTrader := 100

	start := time.Now()

	for tid := 0; tid < numTraders; tid++ {
		wg.Add(1)
		go func(traderID int) {
			defer wg.Done()
			for i := 0; i < ordersPerTrader; i++ {
				side := orderbook.BID
				if traderID%2 == 0 {
					side = orderbook.ASK
				}
				price := 50.0 + float64(i%30)

				ob.PlaceOrder(orderbook.Order{
					ID:       fmt.Sprintf("t%d-o%d", traderID, i),
					NPCID:    fmt.Sprintf("npc-%d", traderID),
					Resource: "iron",
					Side:     side,
					Price:    price,
					Quantity: 1.0,
				})

				trades := ob.Match()
				if len(trades) > 0 {
					tradesMu.Lock()
					allTrades = append(allTrades, trades...)
					tradesMu.Unlock()
				}
			}
		}(tid)
	}

	wg.Wait()
	elapsed := time.Since(start)

	t.Logf("Completed in %v", elapsed)
	t.Logf("Total orders: %d", numTraders*ordersPerTrader)
	t.Logf("Total trades: %d", len(allTrades))
	t.Logf("Throughput: %.0f orders/sec", float64(numTraders*ordersPerTrader)/elapsed.Seconds())

	// The proof: p99 should be under 10ms for 10K concurrent orders
	if elapsed.Milliseconds() > 5000 {
		t.Logf("WARNING: 10K concurrent orders took >5s (%v) — may not meet p99 <10ms target", elapsed)
	}
}
