package economics

import (
	"testing"
	"time"

	"qtown/market-district/internal/orderbook"
)

// ─── CycleDetector ────────────────────────────────────────────────────────────

func TestBoomDetection(t *testing.T) {
	cd := NewCycleDetector(6)

	// Feed steadily increasing GDP (>5% growth) with rising trade volume.
	baseGDP := 1000.0
	for i := 0; i < 6; i++ {
		gdp := baseGDP * (1 + float64(i)*0.02) // +2% each tick → +10% total
		vol := 500.0 + float64(i)*50             // increasing volume
		cd.AddDataPoint(int64(i), gdp, vol, 10.0)
	}

	phase := cd.DetectPhase()
	if phase != PhaseBOOM {
		t.Errorf("expected BOOM, got %s", phase)
	}
}

func TestGrowthDetection(t *testing.T) {
	cd := NewCycleDetector(4)

	// GDP grows ~3% overall, volume mixed — should be GROWTH not BOOM.
	gdpVals := []float64{1000, 1010, 1025, 1030}
	volVals := []float64{400, 390, 410, 400}
	for i, g := range gdpVals {
		cd.AddDataPoint(int64(i), g, volVals[i], 10.0)
	}

	phase := cd.DetectPhase()
	if phase != PhaseGROWTH {
		t.Errorf("expected GROWTH, got %s", phase)
	}
}

func TestStableDetection(t *testing.T) {
	cd := NewCycleDetector(4)

	// GDP essentially flat — between -2% and 0%.
	gdpVals := []float64{1000, 998, 997, 999}
	for i, g := range gdpVals {
		cd.AddDataPoint(int64(i), g, 300.0, 10.0)
	}

	phase := cd.DetectPhase()
	if phase != PhaseSTABLE {
		t.Errorf("expected STABLE, got %s", phase)
	}
}

func TestContractionDetection(t *testing.T) {
	cd := NewCycleDetector(4)

	// GDP drops ~3.5% — CONTRACTION.
	gdpVals := []float64{1000, 990, 975, 965}
	for i, g := range gdpVals {
		cd.AddDataPoint(int64(i), g, 300.0, 10.0)
	}

	phase := cd.DetectPhase()
	if phase != PhaseCONTRACTION {
		t.Errorf("expected CONTRACTION, got %s", phase)
	}
}

func TestBustDetection(t *testing.T) {
	cd := NewCycleDetector(6)

	// GDP falls >5% and volume decreasing.
	baseGDP := 1000.0
	for i := 0; i < 6; i++ {
		gdp := baseGDP * (1 - float64(i)*0.012) // -6% total
		vol := 500.0 - float64(i)*60              // decreasing volume
		cd.AddDataPoint(int64(i), gdp, vol, 10.0)
	}

	phase := cd.DetectPhase()
	if phase != PhaseBUST {
		t.Errorf("expected BUST, got %s", phase)
	}
}

func TestInsufficientDataReturnsStable(t *testing.T) {
	cd := NewCycleDetector(10)
	cd.AddDataPoint(1, 1000, 500, 10)

	phase := cd.DetectPhase()
	if phase != PhaseSTABLE {
		t.Errorf("expected STABLE with <2 data points, got %s", phase)
	}
}

func TestGetIndicators(t *testing.T) {
	cd := NewCycleDetector(4)
	cd.AddDataPoint(1, 1000, 400, 9.0)
	cd.AddDataPoint(2, 1020, 420, 11.0)
	cd.AddDataPoint(3, 1050, 450, 10.0)
	cd.AddDataPoint(4, 1080, 480, 12.0)

	ind := cd.GetIndicators()
	if ind.DataPoints != 4 {
		t.Errorf("expected 4 data points, got %d", ind.DataPoints)
	}
	if ind.GDPGrowthRate <= 0 {
		t.Errorf("expected positive GDP growth, got %f", ind.GDPGrowthRate)
	}
	if !ind.VolumeIncreasing {
		t.Errorf("expected volume to be increasing")
	}
	if ind.PriceVolatility < 0 {
		t.Errorf("price volatility must be non-negative, got %f", ind.PriceVolatility)
	}
}

func TestWindowEviction(t *testing.T) {
	cd := NewCycleDetector(3)

	// Fill window then overflow — oldest should be evicted.
	for i := 0; i < 5; i++ {
		cd.AddDataPoint(int64(i), float64(i+1)*100, 100, 10)
	}

	ind := cd.GetIndicators()
	if ind.DataPoints != 3 {
		t.Errorf("expected window capped at 3, got %d", ind.DataPoints)
	}
}

// ─── PolicyResponder ──────────────────────────────────────────────────────────

func TestPolicyResponse(t *testing.T) {
	pr := &PolicyResponder{}

	tests := []struct {
		phase    EconomicPhase
		wantType PolicyActionType
		wantLen  int
	}{
		{PhaseBOOM, PolicyADJUST_TAX, 2},
		{PhaseGROWTH, PolicyADJUST_TAX, 1},
		{PhaseSTABLE, "", 0},
		{PhaseCONTRACTION, PolicySTIMULUS, 2},
		{PhaseBUST, PolicyADJUST_TAX, 3},
	}

	for _, tt := range tests {
		actions := pr.RespondToPhase(tt.phase)
		if len(actions) != tt.wantLen {
			t.Errorf("phase %s: expected %d actions, got %d", tt.phase, tt.wantLen, len(actions))
			continue
		}
		if tt.wantLen == 0 {
			continue
		}
		// Verify duration and magnitude are set.
		for _, a := range actions {
			if a.Duration <= 0 {
				t.Errorf("phase %s: action %s has non-positive duration %d", tt.phase, a.Type, a.Duration)
			}
		}
	}
}

func TestBoomPolicyIncrasesTax(t *testing.T) {
	pr := &PolicyResponder{}
	actions := pr.RespondToPhase(PhaseBOOM)

	var found bool
	for _, a := range actions {
		if a.Type == PolicyADJUST_TAX {
			found = true
			if a.Magnitude <= 0 {
				t.Errorf("BOOM policy should increase tax (positive magnitude), got %f", a.Magnitude)
			}
		}
	}
	if !found {
		t.Errorf("expected ADJUST_TAX action in BOOM response")
	}
}

func TestBustPolicyDecreasesTax(t *testing.T) {
	pr := &PolicyResponder{}
	actions := pr.RespondToPhase(PhaseBUST)

	var found bool
	for _, a := range actions {
		if a.Type == PolicyADJUST_TAX {
			found = true
			if a.Magnitude >= 0 {
				t.Errorf("BUST policy should cut tax (negative magnitude), got %f", a.Magnitude)
			}
		}
	}
	if !found {
		t.Errorf("expected ADJUST_TAX action in BUST response")
	}
}

func TestBustPolicyIncludesPriceFloor(t *testing.T) {
	pr := &PolicyResponder{}
	actions := pr.RespondToPhase(PhaseBUST)

	var found bool
	for _, a := range actions {
		if a.Type == PolicyPRICE_FLOOR {
			found = true
		}
	}
	if !found {
		t.Errorf("expected PRICE_FLOOR action in BUST response")
	}
}

// ─── SentimentTracker ─────────────────────────────────────────────────────────

func makeTrade(qty float64) orderbook.Trade {
	return orderbook.Trade{
		ID:          "t1",
		BuyOrderID:  "b1",
		SellOrderID: "s1",
		Resource:    "wheat",
		Price:       10.0,
		Quantity:    qty,
		Timestamp:   time.Now(),
	}
}

func TestSentimentTracking(t *testing.T) {
	st := NewSentimentTracker(100)

	// Feed many normal-size buy-heavy trades.
	for i := 0; i < 20; i++ {
		st.UpdateFromTrade(makeTrade(50))
	}

	mood := st.GetMood()
	// With balanced buy/sell (equal buy+sell each trade) slight buy bias means optimistic.
	if mood == "panic" {
		t.Errorf("unexpected panic mood with small trades")
	}
}

func TestPanicMood(t *testing.T) {
	st := NewSentimentTracker(100)

	// Feed several giant sell trades — each is >= 5× threshold → panic sell.
	for i := 0; i < 5; i++ {
		st.UpdateFromTrade(makeTrade(600)) // 600 >= 5×100
	}

	mood := st.GetMood()
	if mood != "panic" {
		t.Errorf("expected panic mood, got %s", mood)
	}
}

func TestNeutralMoodNoTrades(t *testing.T) {
	st := NewSentimentTracker(100)
	if mood := st.GetMood(); mood != "neutral" {
		t.Errorf("expected neutral with no trades, got %s", mood)
	}
}

func TestSentimentReset(t *testing.T) {
	st := NewSentimentTracker(100)
	st.UpdateFromTrade(makeTrade(600))
	st.UpdateFromTrade(makeTrade(600))
	st.UpdateFromTrade(makeTrade(600))
	st.UpdateFromTrade(makeTrade(600))
	st.UpdateFromTrade(makeTrade(600))

	st.Reset()
	if mood := st.GetMood(); mood != "neutral" {
		t.Errorf("expected neutral after reset, got %s", mood)
	}
}

func TestGetSentimentBullish(t *testing.T) {
	cd := NewCycleDetector(6)
	for i := 0; i < 6; i++ {
		gdp := 1000.0 * (1 + float64(i)*0.02)
		vol := 500.0 + float64(i)*50
		cd.AddDataPoint(int64(i), gdp, vol, 10.0)
	}
	if s := cd.GetSentiment(); s != SentimentBULLISH {
		t.Errorf("expected BULLISH in BOOM phase, got %s", s)
	}
}

func TestGetSentimentBearish(t *testing.T) {
	cd := NewCycleDetector(6)
	for i := 0; i < 6; i++ {
		gdp := 1000.0 * (1 - float64(i)*0.012)
		vol := 500.0 - float64(i)*60
		cd.AddDataPoint(int64(i), gdp, vol, 10.0)
	}
	if s := cd.GetSentiment(); s != SentimentBEARISH {
		t.Errorf("expected BEARISH in BUST phase, got %s", s)
	}
}
