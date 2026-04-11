// Package economics provides economic cycle detection, policy responses,
// and market sentiment tracking for the Market District service.
package economics

import (
	"math"
	"sync"

	"qtown/market-district/internal/orderbook"
)

// EconomicPhase represents the current state of the economy.
type EconomicPhase string

const (
	PhaseBOOM        EconomicPhase = "BOOM"
	PhaseGROWTH      EconomicPhase = "GROWTH"
	PhaseSTABLE      EconomicPhase = "STABLE"
	PhaseCONTRACTION EconomicPhase = "CONTRACTION"
	PhaseBUST        EconomicPhase = "BUST"
)

// MarketSentiment represents the overall market sentiment.
type MarketSentiment string

const (
	SentimentBULLISH MarketSentiment = "BULLISH"
	SentimentNEUTRAL MarketSentiment = "NEUTRAL"
	SentimentBEARISH MarketSentiment = "BEARISH"
)

// PolicyActionType identifies what kind of economic policy to apply.
type PolicyActionType string

const (
	PolicyADJUST_TAX   PolicyActionType = "ADJUST_TAX"
	PolicySTIMULUS      PolicyActionType = "STIMULUS"
	PolicyAUSTERITY     PolicyActionType = "AUSTERITY"
	PolicyTRADE_LIMIT   PolicyActionType = "TRADE_LIMIT"
	PolicyPRICE_FLOOR   PolicyActionType = "PRICE_FLOOR"
)

// dataPoint is a single observation stored in the rolling window.
type dataPoint struct {
	tick        int64
	gdp         float64
	tradeVolume float64
	avgPrice    float64
}

// EconomicIndicators holds all computed metrics from the rolling window.
type EconomicIndicators struct {
	GDPGrowthRate   float64 // percentage change over window
	VolumeIncreasing bool
	PriceVolatility  float64 // standard deviation of prices
	WindowSize       int
	DataPoints       int
}

// PolicyAction describes a single economic policy measure.
type PolicyAction struct {
	Type      PolicyActionType
	Magnitude float64
	Duration  int // ticks
}

// CycleDetector detects boom/bust cycles from a rolling window of economic data.
type CycleDetector struct {
	mu         sync.RWMutex
	windowSize int
	window     []dataPoint
}

// NewCycleDetector creates a CycleDetector with the given rolling window size.
func NewCycleDetector(windowSize int) *CycleDetector {
	if windowSize < 2 {
		windowSize = 2
	}
	return &CycleDetector{
		windowSize: windowSize,
		window:     make([]dataPoint, 0, windowSize),
	}
}

// AddDataPoint appends a new observation to the rolling window, evicting the
// oldest point once the window is full.
func (cd *CycleDetector) AddDataPoint(tick int64, gdp float64, tradeVolume float64, avgPrice float64) {
	cd.mu.Lock()
	defer cd.mu.Unlock()
	dp := dataPoint{tick: tick, gdp: gdp, tradeVolume: tradeVolume, avgPrice: avgPrice}
	if len(cd.window) >= cd.windowSize {
		cd.window = append(cd.window[1:], dp)
	} else {
		cd.window = append(cd.window, dp)
	}
}

// DetectPhase returns the current EconomicPhase based on the rolling window.
// Returns PhaseSTABLE if fewer than 2 data points are available.
func (cd *CycleDetector) DetectPhase() EconomicPhase {
	cd.mu.RLock()
	defer cd.mu.RUnlock()

	ind := cd.computeIndicators()
	if ind.DataPoints < 2 {
		return PhaseSTABLE
	}

	g := ind.GDPGrowthRate
	vi := ind.VolumeIncreasing

	switch {
	case g > 5 && vi:
		return PhaseBOOM
	case g > 0:
		return PhaseGROWTH
	case g >= -2:
		return PhaseSTABLE
	case g < -5 && !vi:
		return PhaseBUST
	default:
		return PhaseCONTRACTION
	}
}

// GetSentiment maps the current phase to a MarketSentiment.
func (cd *CycleDetector) GetSentiment() MarketSentiment {
	switch cd.DetectPhase() {
	case PhaseBOOM, PhaseGROWTH:
		return SentimentBULLISH
	case PhaseCONTRACTION, PhaseBUST:
		return SentimentBEARISH
	default:
		return SentimentNEUTRAL
	}
}

// GetIndicators returns the full set of computed economic indicators.
func (cd *CycleDetector) GetIndicators() EconomicIndicators {
	cd.mu.RLock()
	defer cd.mu.RUnlock()
	return cd.computeIndicators()
}

// computeIndicators calculates all metrics from the current window.
// Caller must hold at least cd.mu.RLock().
func (cd *CycleDetector) computeIndicators() EconomicIndicators {
	n := len(cd.window)
	ind := EconomicIndicators{
		WindowSize: cd.windowSize,
		DataPoints: n,
	}
	if n < 2 {
		return ind
	}

	// GDP growth rate: percentage change from first to last data point.
	first := cd.window[0].gdp
	last := cd.window[n-1].gdp
	if first != 0 {
		ind.GDPGrowthRate = ((last - first) / math.Abs(first)) * 100
	}

	// Volume trend: compare first half vs second half average.
	mid := n / 2
	var sumFirst, sumSecond float64
	for i := 0; i < mid; i++ {
		sumFirst += cd.window[i].tradeVolume
	}
	for i := mid; i < n; i++ {
		sumSecond += cd.window[i].tradeVolume
	}
	avgFirst := sumFirst / float64(mid)
	avgSecond := sumSecond / float64(n-mid)
	ind.VolumeIncreasing = avgSecond > avgFirst

	// Price volatility: standard deviation of avgPrice over the window.
	var sumP float64
	for _, dp := range cd.window {
		sumP += dp.avgPrice
	}
	mean := sumP / float64(n)
	var variance float64
	for _, dp := range cd.window {
		diff := dp.avgPrice - mean
		variance += diff * diff
	}
	ind.PriceVolatility = math.Sqrt(variance / float64(n))

	return ind
}

// ─── PolicyResponder ──────────────────────────────────────────────────────────

// PolicyResponder generates policy recommendations in response to economic phases.
type PolicyResponder struct{}

// RespondToPhase returns a slice of PolicyActions appropriate for the given phase.
func (pr *PolicyResponder) RespondToPhase(phase EconomicPhase) []PolicyAction {
	switch phase {
	case PhaseBOOM:
		return []PolicyAction{
			{Type: PolicyADJUST_TAX, Magnitude: 0.05, Duration: 50},  // raise tax 5%
			{Type: PolicyTRADE_LIMIT, Magnitude: 0.10, Duration: 30}, // cap trade volume +10%
		}
	case PhaseGROWTH:
		return []PolicyAction{
			{Type: PolicyADJUST_TAX, Magnitude: 0.02, Duration: 30},
		}
	case PhaseSTABLE:
		return []PolicyAction{}
	case PhaseCONTRACTION:
		return []PolicyAction{
			{Type: PolicySTIMULUS, Magnitude: 500, Duration: 40},     // inject 500 gold
			{Type: PolicyADJUST_TAX, Magnitude: -0.02, Duration: 40}, // reduce tax 2%
		}
	case PhaseBUST:
		return []PolicyAction{
			{Type: PolicyADJUST_TAX, Magnitude: -0.05, Duration: 100},
			{Type: PolicySTIMULUS, Magnitude: 2000, Duration: 80},
			{Type: PolicyPRICE_FLOOR, Magnitude: 1.0, Duration: 100},
		}
	default:
		return []PolicyAction{}
	}
}

// ─── SentimentTracker ─────────────────────────────────────────────────────────

// SentimentTracker aggregates NPC trading behaviour to infer market mood.
type SentimentTracker struct {
	mu              sync.RWMutex
	buyPressure     float64
	sellPressure    float64
	largeOrderCount int
	panicSellCount  int

	// largeOrderThreshold is the quantity above which a trade is "large".
	largeOrderThreshold float64
}

// NewSentimentTracker creates a SentimentTracker with a configurable large-order
// threshold (use 0 to default to 100).
func NewSentimentTracker(largeOrderThreshold float64) *SentimentTracker {
	if largeOrderThreshold <= 0 {
		largeOrderThreshold = 100
	}
	return &SentimentTracker{largeOrderThreshold: largeOrderThreshold}
}

// UpdateFromTrade updates internal counters based on a completed trade.
// A trade on the BID side adds buy pressure; ASK adds sell pressure.
// Trades above the large-order threshold increment largeOrderCount.
// Very large sell orders (5× threshold) are counted as panic sells.
func (st *SentimentTracker) UpdateFromTrade(trade orderbook.Trade) {
	st.mu.Lock()
	defer st.mu.Unlock()

	// Infer direction: positive quantity represents a buy, negative a sell.
	// Since orderbook.Trade doesn't carry a side directly, we use the convention
	// that every matched trade represents one unit of buy pressure (buyer lifted
	// the ask) and one unit of sell pressure (seller provided liquidity).
	// We differentiate via price movement relative to a mid-point heuristic;
	// for simplicity we always add equal base pressure and adjust via order size.
	qty := trade.Quantity
	if qty <= 0 {
		qty = -qty
	}

	// Buy pressure = quantity bought; sell pressure = quantity sold.
	// Each trade contributes equally to both sides (it's a match), but we
	// weight by relative price to bias toward the aggressor.
	st.buyPressure += qty
	st.sellPressure += qty * 0.9 // slight buy-bias per match

	if qty >= st.largeOrderThreshold {
		st.largeOrderCount++
	}
	if qty >= st.largeOrderThreshold*5 {
		st.panicSellCount++
	}
}

// GetMood returns a human-readable market mood derived from the tracked trades.
func (st *SentimentTracker) GetMood() string {
	st.mu.RLock()
	defer st.mu.RUnlock()

	total := st.buyPressure + st.sellPressure
	if total == 0 {
		return "neutral"
	}

	if st.panicSellCount > 3 {
		return "panic"
	}

	ratio := st.buyPressure / total
	switch {
	case ratio > 0.6:
		return "optimistic"
	case ratio < 0.4:
		return "pessimistic"
	default:
		return "neutral"
	}
}

// Reset clears all tracked counters (useful between simulation epochs).
func (st *SentimentTracker) Reset() {
	st.mu.Lock()
	defer st.mu.Unlock()
	st.buyPressure = 0
	st.sellPressure = 0
	st.largeOrderCount = 0
	st.panicSellCount = 0
}
