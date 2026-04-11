// Package orderbook implements a price-time priority order book for the
// Market District service. It supports BID and ASK sides, continuous
// matching, and partial fills.
package orderbook

import (
	"fmt"
	"sort"
	"sync"
	"time"
)

// Side represents whether an order is a buy (BID) or sell (ASK).
type Side string

const (
	BID Side = "BID"
	ASK Side = "ASK"
)

// Order represents a single resting order in the book.
type Order struct {
	ID        string
	NPCID     string
	Resource  string
	Side      Side
	Price     float64
	Quantity  float64
	Timestamp time.Time
}

// Trade represents a matched transaction between a buyer and seller.
type Trade struct {
	ID          string
	BuyOrderID  string
	SellOrderID string
	Resource    string
	Price       float64
	Quantity    float64
	Timestamp   time.Time
}

// Snapshot is a point-in-time view of the order book.
type Snapshot struct {
	Bids []Order
	Asks []Order
}

// OrderBook holds all resting orders for a single resource and performs
// continuous matching using price-time priority.
type OrderBook struct {
	mu       sync.RWMutex
	Resource string
	Bids     []Order // sorted descending by price, then ascending by timestamp
	Asks     []Order // sorted ascending by price, then ascending by timestamp
	tradeSeq uint64
}

// NewOrderBook creates an empty order book for the given resource.
func NewOrderBook(resource string) *OrderBook {
	return &OrderBook{Resource: resource}
}

// PlaceOrder appends the order to the correct side without matching.
// Call Match after PlaceOrder to execute any crosses.
func (ob *OrderBook) PlaceOrder(o Order) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	o.Timestamp = time.Now()
	if o.Side == BID {
		ob.Bids = append(ob.Bids, o)
		sortBids(ob.Bids)
	} else {
		ob.Asks = append(ob.Asks, o)
		sortAsks(ob.Asks)
	}
}

// Match runs one full matching cycle and returns all generated trades.
// It removes fully filled orders and updates quantities for partial fills.
func (ob *OrderBook) Match() []Trade {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	var trades []Trade

	for len(ob.Bids) > 0 && len(ob.Asks) > 0 {
		best := ob.Bids[0]
		offer := ob.Asks[0]

		// No cross — best bid is below the best ask.
		if best.Price < offer.Price {
			break
		}

		// Determine fill price (maker price = the resting side's price).
		// The bid arrived first if best.Timestamp < offer.Timestamp,
		// otherwise the ask is the maker. For simplicity we use the ask
		// price (offer price) as the execution price.
		execPrice := offer.Price

		// Determine fill quantity.
		fillQty := min(best.Quantity, offer.Quantity)

		ob.tradeSeq++
		trades = append(trades, Trade{
			ID:          fmt.Sprintf("trade-%d", ob.tradeSeq),
			BuyOrderID:  best.ID,
			SellOrderID: offer.ID,
			Resource:    ob.Resource,
			Price:       execPrice,
			Quantity:    fillQty,
			Timestamp:   time.Now(),
		})

		// Update or remove the bid.
		ob.Bids[0].Quantity -= fillQty
		if ob.Bids[0].Quantity <= 0 {
			ob.Bids = ob.Bids[1:]
		}

		// Update or remove the ask.
		ob.Asks[0].Quantity -= fillQty
		if ob.Asks[0].Quantity <= 0 {
			ob.Asks = ob.Asks[1:]
		}
	}

	return trades
}

// GetSnapshot returns a copy of the current book state (safe for concurrent use).
func (ob *OrderBook) GetSnapshot() Snapshot {
	ob.mu.RLock()
	defer ob.mu.RUnlock()

	bids := make([]Order, len(ob.Bids))
	copy(bids, ob.Bids)

	asks := make([]Order, len(ob.Asks))
	copy(asks, ob.Asks)

	return Snapshot{Bids: bids, Asks: asks}
}

// --- sorting helpers ---

// sortBids sorts bids descending by price, then ascending by timestamp
// (best bid = highest price, earliest arrival at that price).
func sortBids(bids []Order) {
	sort.SliceStable(bids, func(i, j int) bool {
		if bids[i].Price != bids[j].Price {
			return bids[i].Price > bids[j].Price
		}
		return bids[i].Timestamp.Before(bids[j].Timestamp)
	})
}

// sortAsks sorts asks ascending by price, then ascending by timestamp
// (best ask = lowest price, earliest arrival at that price).
func sortAsks(asks []Order) {
	sort.SliceStable(asks, func(i, j int) bool {
		if asks[i].Price != asks[j].Price {
			return asks[i].Price < asks[j].Price
		}
		return asks[i].Timestamp.Before(asks[j].Timestamp)
	})
}

func min(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}
