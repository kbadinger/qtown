package grpc

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"qtown/market-district/internal/orderbook"
	pb "qtown/market-district/proto"
)

// MarketServer implements the MarketDistrict gRPC service.
type MarketServer struct {
	pb.UnimplementedMarketDistrictServer

	mu       sync.RWMutex
	books    map[string]*orderbook.OrderBook // resource -> orderbook
	traders  map[int64]*TraderState          // npc_id -> state
	tradeSeq uint64
}

// TraderState tracks an NPC trader visiting the Market District.
type TraderState struct {
	NPCID     int64
	Name      string
	Gold      float64
	ArrivedAt time.Time
}

func NewMarketServer() *MarketServer {
	return &MarketServer{
		books:   make(map[string]*orderbook.OrderBook),
		traders: make(map[int64]*TraderState),
	}
}

func (s *MarketServer) getOrCreateBook(resource string) *orderbook.OrderBook {
	s.mu.Lock()
	defer s.mu.Unlock()
	if book, ok := s.books[resource]; ok {
		return book
	}
	book := orderbook.NewOrderBook(resource)
	s.books[resource] = book
	return book
}

// PlaceOrder handles incoming order requests.
func (s *MarketServer) PlaceOrder(ctx context.Context, req *pb.PlaceOrderRequest) (*pb.PlaceOrderResponse, error) {
	book := s.getOrCreateBook(req.Resource)

	side := orderbook.BID
	if req.Side == pb.OrderSide_ASK {
		side = orderbook.ASK
	}

	s.mu.Lock()
	s.tradeSeq++
	orderID := fmt.Sprintf("ORD-%d-%d", req.NpcId, s.tradeSeq)
	s.mu.Unlock()

	order := orderbook.Order{
		ID:       orderID,
		NPCID:    fmt.Sprintf("%d", req.NpcId),
		Resource: req.Resource,
		Side:     side,
		Price:    float64(req.Price),
		Quantity: float64(req.Quantity),
	}

	book.PlaceOrder(order)

	// Run matching
	trades := book.Match()
	if len(trades) > 0 {
		log.Printf("[market-district] %d trades matched for %s", len(trades), req.Resource)
		// TODO: emit economy.trade.settled to Kafka for each trade
	}

	return &pb.PlaceOrderResponse{
		OrderId:  orderID,
		Accepted: true,
		Message:  fmt.Sprintf("order placed, %d trades matched", len(trades)),
	}, nil
}

// GetOrderBook returns the current state of an order book.
func (s *MarketServer) GetOrderBook(ctx context.Context, req *pb.OrderBookRequest) (*pb.OrderBookSnapshot, error) {
	book := s.getOrCreateBook(req.Resource)
	snap := book.GetSnapshot()

	depth := int(req.Depth)
	if depth <= 0 {
		depth = 20
	}

	var bids []*pb.Order
	for i, b := range snap.Bids {
		if i >= depth {
			break
		}
		bids = append(bids, &pb.Order{
			Id:       b.ID,
			Resource: b.Resource,
			Side:     pb.OrderSide_BID,
			Price:    float32(b.Price),
			Quantity: float32(b.Quantity),
		})
	}

	var asks []*pb.Order
	for i, a := range snap.Asks {
		if i >= depth {
			break
		}
		asks = append(asks, &pb.Order{
			Id:       a.ID,
			Resource: a.Resource,
			Side:     pb.OrderSide_ASK,
			Price:    float32(a.Price),
			Quantity: float32(a.Quantity),
		})
	}

	midPrice := float32(0)
	if len(snap.Bids) > 0 && len(snap.Asks) > 0 {
		midPrice = float32((snap.Bids[0].Price + snap.Asks[0].Price) / 2)
	}

	return &pb.OrderBookSnapshot{
		Resource: req.Resource,
		Bids:     bids,
		Asks:     asks,
		MidPrice: midPrice,
	}, nil
}

// PriceFeed sends real-time price updates for subscribed resources.
func (s *MarketServer) PriceFeed(req *pb.PriceFeedRequest, stream pb.MarketDistrict_PriceFeedServer) error {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-stream.Context().Done():
			return nil
		case <-ticker.C:
			for _, resource := range req.Resources {
				book := s.getOrCreateBook(resource)
				snap := book.GetSnapshot()

				update := &pb.PriceUpdate{
					Resource: resource,
				}
				if len(snap.Bids) > 0 {
					update.BidPrice = float32(snap.Bids[0].Price)
				}
				if len(snap.Asks) > 0 {
					update.AskPrice = float32(snap.Asks[0].Price)
				}
				if update.BidPrice > 0 && update.AskPrice > 0 {
					update.MidPrice = (update.BidPrice + update.AskPrice) / 2
				}

				if err := stream.Send(update); err != nil {
					return err
				}
			}
		}
	}
}

// Health returns the service health status.
func (s *MarketServer) Health(ctx context.Context, req *pb.HealthRequest) (*pb.HealthResponse, error) {
	s.mu.RLock()
	bookCount := len(s.books)
	traderCount := len(s.traders)
	s.mu.RUnlock()

	return &pb.HealthResponse{
		Status:  "ok",
		Service: "market-district",
		Details: map[string]string{
			"order_books":    fmt.Sprintf("%d", bookCount),
			"active_traders": fmt.Sprintf("%d", traderCount),
		},
	}, nil
}

// StressTest runs a synthetic load test and returns latency metrics.
func (s *MarketServer) StressTest(ctx context.Context, req *pb.StressTestRequest) (*pb.StressTestResult, error) {
	numOrders := int(req.NumOrders)
	if numOrders <= 0 {
		numOrders = 10000
	}
	numGoroutines := int(req.NumGoroutines)
	if numGoroutines <= 0 {
		numGoroutines = 100
	}

	book := orderbook.NewOrderBook("stress-test")
	var wg sync.WaitGroup
	start := time.Now()
	ordersPerGoroutine := numOrders / numGoroutines

	latencies := make([]time.Duration, numOrders)
	var latMu sync.Mutex
	latIdx := 0

	for g := 0; g < numGoroutines; g++ {
		wg.Add(1)
		go func(gid int) {
			defer wg.Done()
			for i := 0; i < ordersPerGoroutine; i++ {
				side := orderbook.BID
				if i%2 == 0 {
					side = orderbook.ASK
				}
				price := 100.0 + float64(i%50) - 25.0
				t0 := time.Now()

				book.PlaceOrder(orderbook.Order{
					ID:       fmt.Sprintf("stress-%d-%d", gid, i),
					NPCID:    fmt.Sprintf("%d", gid),
					Resource: "stress-test",
					Side:     side,
					Price:    price,
					Quantity: 1.0,
				})
				book.Match()

				elapsed := time.Since(t0)
				latMu.Lock()
				if latIdx < len(latencies) {
					latencies[latIdx] = elapsed
					latIdx++
				}
				latMu.Unlock()
			}
		}(g)
	}

	wg.Wait()
	totalElapsed := time.Since(start)

	// Calculate percentiles
	validLatencies := latencies[:latIdx]
	sortDurations(validLatencies)

	p50 := float32(0)
	p95 := float32(0)
	p99 := float32(0)
	if len(validLatencies) > 0 {
		p50 = float32(validLatencies[len(validLatencies)*50/100].Microseconds())
		p95 = float32(validLatencies[len(validLatencies)*95/100].Microseconds())
		p99 = float32(validLatencies[len(validLatencies)*99/100].Microseconds())
	}

	snap := book.GetSnapshot()

	return &pb.StressTestResult{
		TotalOrders:    int32(numOrders),
		TotalTrades:    int32(len(snap.Bids) + len(snap.Asks)), // remaining unmatched
		ElapsedMs:      float32(totalElapsed.Milliseconds()),
		P50LatencyUs:   p50,
		P95LatencyUs:   p95,
		P99LatencyUs:   p99,
		GoroutineCount: int32(numGoroutines),
	}, nil
}

func sortDurations(d []time.Duration) {
	// Simple insertion sort — good enough for benchmarks
	for i := 1; i < len(d); i++ {
		key := d[i]
		j := i - 1
		for j >= 0 && d[j] > key {
			d[j+1] = d[j]
			j--
		}
		d[j+1] = key
	}
}
