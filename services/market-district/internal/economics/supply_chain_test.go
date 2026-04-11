package economics

import (
	"context"
	"testing"
)

// ─── Recipe Processing ────────────────────────────────────────────────────────

func TestRecipeProcessing(t *testing.T) {
	sc := NewSupplyChain()

	inv := map[Resource]int{
		ResourceWheat: 6, // enough for 2 flour recipes
	}

	job, err := sc.ProcessOrder("npc-1", ResourceFlour, inv)
	if err != nil {
		t.Fatalf("ProcessOrder failed: %v", err)
	}
	if job == nil {
		t.Fatal("expected non-nil ProcessingJob")
	}
	if job.Recipe != ResourceFlour {
		t.Errorf("expected recipe=flour, got %s", job.Recipe)
	}

	// Inputs should have been deducted.
	if inv[ResourceWheat] != 3 {
		t.Errorf("expected 3 wheat remaining, got %d", inv[ResourceWheat])
	}
}

func TestRecipeInsufficientInputs(t *testing.T) {
	sc := NewSupplyChain()

	inv := map[Resource]int{
		ResourceWheat: 1, // need 3 for flour
	}

	_, err := sc.ProcessOrder("npc-1", ResourceFlour, inv)
	if err == nil {
		t.Fatal("expected error for insufficient inputs")
	}
}

func TestRecipeUnknown(t *testing.T) {
	sc := NewSupplyChain()
	_, err := sc.ProcessOrder("npc-1", Resource("dragon_scale"), map[Resource]int{})
	if err == nil {
		t.Fatal("expected error for unknown recipe")
	}
}

func TestMultipleInputRecipe(t *testing.T) {
	sc := NewSupplyChain()

	// Bread requires flour×2 + wood×1.
	inv := map[Resource]int{
		ResourceFlour: 4,
		ResourceWood:  2,
	}

	job, err := sc.ProcessOrder("npc-2", ResourceBread, inv)
	if err != nil {
		t.Fatalf("ProcessOrder failed: %v", err)
	}
	if job.Recipe != ResourceBread {
		t.Errorf("expected bread recipe, got %s", job.Recipe)
	}
	// 4 flour - 2 = 2 remaining; 2 wood - 1 = 1 remaining.
	if inv[ResourceFlour] != 2 {
		t.Errorf("expected 2 flour remaining, got %d", inv[ResourceFlour])
	}
	if inv[ResourceWood] != 1 {
		t.Errorf("expected 1 wood remaining, got %d", inv[ResourceWood])
	}
}

// ─── Processing Time ──────────────────────────────────────────────────────────

func TestProcessingTime(t *testing.T) {
	sc := NewSupplyChain()

	inv := map[Resource]int{ResourceWheat: 3}
	job, err := sc.ProcessOrder("npc-1", ResourceFlour, inv)
	if err != nil {
		t.Fatalf("ProcessOrder failed: %v", err)
	}

	// Start the job at tick 10; flour has ProcessingTicks=2, so completes at 12.
	err = sc.StartJob(job.ID, 10)
	if err != nil {
		t.Fatalf("StartJob failed: %v", err)
	}

	// Tick 11 — job not yet complete.
	completed := sc.TickProcessing(11)
	if len(completed) != 0 {
		t.Errorf("expected no completions at tick 11, got %d", len(completed))
	}

	// Tick 12 — job completes.
	completed = sc.TickProcessing(12)
	if len(completed) != 1 {
		t.Fatalf("expected 1 completion at tick 12, got %d", len(completed))
	}
	if completed[0].OutputResource != ResourceFlour {
		t.Errorf("expected flour output, got %s", completed[0].OutputResource)
	}
	if completed[0].OutputQuantity != 1 {
		t.Errorf("expected quantity=1, got %d", completed[0].OutputQuantity)
	}
	if completed[0].NPCID != "npc-1" {
		t.Errorf("expected npc-1, got %s", completed[0].NPCID)
	}
}

func TestJobCompletesExactlyOnTime(t *testing.T) {
	sc := NewSupplyChain()

	inv := map[Resource]int{ResourceIronOre: 2}
	job, _ := sc.ProcessOrder("npc-3", ResourceIronIngot, inv)
	_ = sc.StartJob(job.ID, 0)

	// Iron ingot has ProcessingTicks=3.
	for tick := int64(1); tick < 3; tick++ {
		c := sc.TickProcessing(tick)
		if len(c) != 0 {
			t.Errorf("expected no completion at tick %d", tick)
		}
	}
	c := sc.TickProcessing(3)
	if len(c) != 1 {
		t.Errorf("expected completion at tick 3, got %d", len(c))
	}
}

func TestMultipleJobsComplete(t *testing.T) {
	sc := NewSupplyChain()

	inv1 := map[Resource]int{ResourceWheat: 3}
	inv2 := map[Resource]int{ResourceWheat: 3}
	j1, _ := sc.ProcessOrder("npc-1", ResourceFlour, inv1)
	j2, _ := sc.ProcessOrder("npc-2", ResourceFlour, inv2)
	_ = sc.StartJob(j1.ID, 0)
	_ = sc.StartJob(j2.ID, 0)

	c := sc.TickProcessing(2)
	if len(c) != 2 {
		t.Errorf("expected 2 completions at tick 2, got %d", len(c))
	}
}

// ─── Price Discovery ──────────────────────────────────────────────────────────

func TestPriceDiscoveryIncreasesWithDemand(t *testing.T) {
	pd := NewPriceDiscovery(0.5)

	// Record equal supply and demand → price at base.
	pd.RecordSupply(ResourceWheat, 100)
	pd.RecordDemand(ResourceWheat, 100)
	basePrice := pd.CalculatePrice(ResourceWheat)

	// Reset and now record high demand relative to supply.
	pd.Reset()
	pd.RecordSupply(ResourceWheat, 50)
	pd.RecordDemand(ResourceWheat, 200)
	highDemandPrice := pd.CalculatePrice(ResourceWheat)

	if highDemandPrice <= basePrice {
		t.Errorf("expected price to increase with higher demand: base=%f, highDemand=%f", basePrice, highDemandPrice)
	}
}

func TestPriceFloorRaw(t *testing.T) {
	pd := NewPriceDiscovery(0.5)

	// Record massive supply, no demand — price would collapse, but floor=1.
	pd.RecordSupply(ResourceWheat, 10000)
	pd.RecordDemand(ResourceWheat, 0)

	price := pd.CalculatePrice(ResourceWheat)
	if price < 1 {
		t.Errorf("raw resource price must not go below 1 gold, got %f", price)
	}
}

func TestPriceFloorProcessed(t *testing.T) {
	pd := NewPriceDiscovery(0.5)

	pd.RecordSupply(ResourceFlour, 10000)
	pd.RecordDemand(ResourceFlour, 0)

	price := pd.CalculatePrice(ResourceFlour)
	if price < 5 {
		t.Errorf("processed resource price must not go below 5 gold, got %f", price)
	}
}

func TestPriceNoSupply(t *testing.T) {
	pd := NewPriceDiscovery(0.5)

	// No supply recorded → should return 2× base (scarcity premium).
	price := pd.CalculatePrice(ResourceWood)
	base := 2.0 // wood base price
	if price < base {
		t.Errorf("price with no supply should be at or above base (%f), got %f", base, price)
	}
}

// ─── Scarcity Detection ───────────────────────────────────────────────────────

func TestScarcityDetection(t *testing.T) {
	sm := NewScarcityMonitor(nil) // nil = no Kafka

	// Set wheat supply below its threshold of 20.
	sm.SetSupply(ResourceWheat, 5)

	alerts := sm.CheckScarcity(context.Background())
	if len(alerts) == 0 {
		t.Fatal("expected at least one scarcity alert")
	}

	var found bool
	for _, a := range alerts {
		if a.Resource == ResourceWheat {
			found = true
			if a.CurrentSupply != 5 {
				t.Errorf("expected current supply=5, got %f", a.CurrentSupply)
			}
			if a.Threshold != 20 {
				t.Errorf("expected threshold=20, got %f", a.Threshold)
			}
		}
	}
	if !found {
		t.Error("no scarcity alert for wheat")
	}
}

func TestScarcitySeverityCritical(t *testing.T) {
	sm := NewScarcityMonitor(nil)
	// Supply is 4 (<25% of threshold 20).
	sm.SetSupply(ResourceWheat, 4)

	alerts := sm.CheckScarcity(context.Background())
	for _, a := range alerts {
		if a.Resource == ResourceWheat {
			if a.Severity != SeverityCRITICAL {
				t.Errorf("expected CRITICAL severity, got %s", a.Severity)
			}
			return
		}
	}
	t.Error("no alert for wheat")
}

func TestScarcitySeverityMedium(t *testing.T) {
	sm := NewScarcityMonitor(nil)
	// Supply is 10 (50% of threshold 20 → MEDIUM).
	sm.SetSupply(ResourceWheat, 10)

	alerts := sm.CheckScarcity(context.Background())
	for _, a := range alerts {
		if a.Resource == ResourceWheat {
			if a.Severity != SeverityMEDIUM {
				t.Errorf("expected MEDIUM severity, got %s", a.Severity)
			}
			return
		}
	}
	t.Error("no alert for wheat")
}

func TestNoScarcityAboveThreshold(t *testing.T) {
	sm := NewScarcityMonitor(nil)

	// Set all resources well above their thresholds.
	sm.SetSupply(ResourceWheat, 100)
	sm.SetSupply(ResourceIronOre, 100)
	sm.SetSupply(ResourceWood, 100)
	sm.SetSupply(ResourceStone, 100)

	alerts := sm.CheckScarcity(context.Background())
	if len(alerts) != 0 {
		t.Errorf("expected no alerts when supply is abundant, got %d", len(alerts))
	}
}

func TestConsumeSupplyTriggersScarcity(t *testing.T) {
	sm := NewScarcityMonitor(nil)
	sm.SetSupply(ResourceIronOre, 30)

	// Consume enough to drop below threshold of 15.
	sm.ConsumeSupply(ResourceIronOre, 20)

	alerts := sm.CheckScarcity(context.Background())
	var found bool
	for _, a := range alerts {
		if a.Resource == ResourceIronOre {
			found = true
		}
	}
	if !found {
		t.Error("expected scarcity alert for iron_ore after consumption")
	}
}
