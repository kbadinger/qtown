// Package proto is a placeholder for generated protobuf code.
// Run `buf generate` from the repo root to populate this package
// with generated Go types from proto/qtown/market.proto.
package proto

import "context"

// Placeholder types — these will be replaced by buf-generated code.
// They exist so the gRPC server package compiles before codegen.

type HealthRequest struct{}
type HealthResponse struct {
	Status  string
	Service string
	Details map[string]string
}

type PlaceOrderRequest struct {
	NpcId    int64
	Resource string
	Side     OrderSide
	Price    float32
	Quantity float32
}

type PlaceOrderResponse struct {
	OrderId  string
	Accepted bool
	Message  string
}

type CancelOrderRequest struct {
	OrderId string
}

type CancelOrderResponse struct {
	Success bool
	Message string
}

type OrderBookRequest struct {
	Resource string
	Depth    int32
}

type OrderBookSnapshot struct {
	Resource string
	Bids     []*Order
	Asks     []*Order
	MidPrice float32
}

type Order struct {
	Id       string
	NpcId    int64
	Resource string
	Side     OrderSide
	Price    float32
	Quantity float32
}

type OrderSide int32

const (
	OrderSide_ORDER_SIDE_UNSPECIFIED OrderSide = 0
	OrderSide_BID                   OrderSide = 1
	OrderSide_ASK                   OrderSide = 2
)

type PriceFeedRequest struct {
	Resources []string
}

type PriceUpdate struct {
	Resource string
	BidPrice float32
	AskPrice float32
	MidPrice float32
}

type StressTestRequest struct {
	NumOrders     int32
	NumGoroutines int32
}

type StressTestResult struct {
	TotalOrders    int32
	TotalTrades    int32
	ElapsedMs      float32
	P50LatencyUs   float32
	P95LatencyUs   float32
	P99LatencyUs   float32
	GoroutineCount int32
}

type TravelRequest struct {
	NpcId    int64
	NpcState *NPCState
}

type TravelResponse struct {
	Accepted bool
	Reason   string
	EtaTicks int64
}

type NPCState struct {
	Id   int64
	Name string
	Gold float32
}

// MarketDistrictServer is the interface that the gRPC server must implement.
type MarketDistrictServer interface {
	PlaceOrder(context.Context, *PlaceOrderRequest) (*PlaceOrderResponse, error)
	GetOrderBook(context.Context, *OrderBookRequest) (*OrderBookSnapshot, error)
	PriceFeed(*PriceFeedRequest, MarketDistrict_PriceFeedServer) error
	Health(context.Context, *HealthRequest) (*HealthResponse, error)
	StressTest(context.Context, *StressTestRequest) (*StressTestResult, error)
	NPCArrive(context.Context, *TravelRequest) (*TravelResponse, error)
	NPCDepart(context.Context, *TravelRequest) (*TravelResponse, error)
}

// UnimplementedMarketDistrictServer can be embedded to have forward compatible implementations.
type UnimplementedMarketDistrictServer struct{}

func (UnimplementedMarketDistrictServer) PlaceOrder(context.Context, *PlaceOrderRequest) (*PlaceOrderResponse, error) {
	return nil, nil
}
func (UnimplementedMarketDistrictServer) GetOrderBook(context.Context, *OrderBookRequest) (*OrderBookSnapshot, error) {
	return nil, nil
}
func (UnimplementedMarketDistrictServer) PriceFeed(*PriceFeedRequest, MarketDistrict_PriceFeedServer) error {
	return nil
}
func (UnimplementedMarketDistrictServer) Health(context.Context, *HealthRequest) (*HealthResponse, error) {
	return nil, nil
}
func (UnimplementedMarketDistrictServer) StressTest(context.Context, *StressTestRequest) (*StressTestResult, error) {
	return nil, nil
}
func (UnimplementedMarketDistrictServer) NPCArrive(context.Context, *TravelRequest) (*TravelResponse, error) {
	return nil, nil
}
func (UnimplementedMarketDistrictServer) NPCDepart(context.Context, *TravelRequest) (*TravelResponse, error) {
	return nil, nil
}

// MarketDistrict_PriceFeedServer is the server-side streaming interface for PriceFeed.
type MarketDistrict_PriceFeedServer interface {
	Send(*PriceUpdate) error
	Context() context.Context
}
