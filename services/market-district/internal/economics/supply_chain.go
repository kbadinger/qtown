package economics

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"sync"
	"time"

	kafka "github.com/segmentio/kafka-go"
)

// ─── Resource Types ────────────────────────────────────────────────────────────

// Resource identifies a specific material in the supply chain.
type Resource string

const (
	// RAW resources.
	ResourceWheat   Resource = "wheat"
	ResourceIronOre Resource = "iron_ore"
	ResourceWood    Resource = "wood"
	ResourceStone   Resource = "stone"

	// PROCESSED resources.
	ResourceFlour     Resource = "flour"
	ResourceIronIngot Resource = "iron_ingot"
	ResourceLumber    Resource = "lumber"
	ResourceBrick     Resource = "brick"

	// TRADE goods.
	ResourceBread            Resource = "bread"
	ResourceSword            Resource = "sword"
	ResourceFurniture        Resource = "furniture"
	ResourceBuildingMaterial Resource = "building_material"
)

// ResourceTier classifies a resource within the supply chain.
type ResourceTier string

const (
	TierRAW       ResourceTier = "RAW"
	TierPROCESSED ResourceTier = "PROCESSED"
	TierTRADE     ResourceTier = "TRADE"
)

// ResourceMeta holds metadata for pricing floors.
var ResourceMeta = map[Resource]struct {
	Tier      ResourceTier
	PriceFloor float64
}{
	ResourceWheat:            {TierRAW, 1},
	ResourceIronOre:          {TierRAW, 1},
	ResourceWood:             {TierRAW, 1},
	ResourceStone:            {TierRAW, 1},
	ResourceFlour:            {TierPROCESSED, 5},
	ResourceIronIngot:        {TierPROCESSED, 5},
	ResourceLumber:           {TierPROCESSED, 5},
	ResourceBrick:            {TierPROCESSED, 5},
	ResourceBread:            {TierTRADE, 10},
	ResourceSword:            {TierTRADE, 50},
	ResourceFurniture:        {TierTRADE, 30},
	ResourceBuildingMaterial: {TierTRADE, 20},
}

// ScarcityThresholds defines when a raw resource is considered scarce.
var ScarcityThresholds = map[Resource]float64{
	ResourceWheat:   20,
	ResourceIronOre: 15,
	ResourceWood:    25,
	ResourceStone:   20,
}

// ─── Recipe ───────────────────────────────────────────────────────────────────

// RecipeInput is a single ingredient requirement.
type RecipeInput struct {
	Resource Resource
	Quantity int
}

// Recipe describes how to transform inputs into an output resource.
type Recipe struct {
	Inputs          []RecipeInput
	Output          Resource
	OutputQuantity  int
	ProcessingTicks int64
}

// DefaultRecipes is the canonical recipe book for the supply chain.
var DefaultRecipes = map[Resource]Recipe{
	ResourceFlour: {
		Inputs:          []RecipeInput{{ResourceWheat, 3}},
		Output:          ResourceFlour,
		OutputQuantity:  1,
		ProcessingTicks: 2,
	},
	ResourceIronIngot: {
		Inputs:          []RecipeInput{{ResourceIronOre, 2}},
		Output:          ResourceIronIngot,
		OutputQuantity:  1,
		ProcessingTicks: 3,
	},
	ResourceLumber: {
		Inputs:          []RecipeInput{{ResourceWood, 2}},
		Output:          ResourceLumber,
		OutputQuantity:  1,
		ProcessingTicks: 2,
	},
	ResourceBrick: {
		Inputs:          []RecipeInput{{ResourceStone, 2}},
		Output:          ResourceBrick,
		OutputQuantity:  2,
		ProcessingTicks: 3,
	},
	ResourceBread: {
		Inputs:          []RecipeInput{{ResourceFlour, 2}, {ResourceWood, 1}},
		Output:          ResourceBread,
		OutputQuantity:  4,
		ProcessingTicks: 1,
	},
	ResourceSword: {
		Inputs:          []RecipeInput{{ResourceIronIngot, 3}, {ResourceLumber, 1}},
		Output:          ResourceSword,
		OutputQuantity:  1,
		ProcessingTicks: 5,
	},
	ResourceFurniture: {
		Inputs:          []RecipeInput{{ResourceLumber, 4}},
		Output:          ResourceFurniture,
		OutputQuantity:  1,
		ProcessingTicks: 4,
	},
	ResourceBuildingMaterial: {
		Inputs:          []RecipeInput{{ResourceBrick, 3}, {ResourceLumber, 2}},
		Output:          ResourceBuildingMaterial,
		OutputQuantity:  2,
		ProcessingTicks: 3,
	},
}

// ─── ProcessingJob ────────────────────────────────────────────────────────────

// JobStatus represents the lifecycle state of a processing job.
type JobStatus string

const (
	JobStatusPending    JobStatus = "PENDING"
	JobStatusProcessing JobStatus = "PROCESSING"
	JobStatusComplete   JobStatus = "COMPLETE"
)

// ProcessingJob tracks an in-progress recipe execution.
type ProcessingJob struct {
	ID           string
	NPCID        string
	Recipe       Resource
	StartTick    int64
	CompleteTick int64
	Status       JobStatus
}

// CompletedJob is the output from a finished ProcessingJob.
type CompletedJob struct {
	JobID          string
	OutputResource Resource
	OutputQuantity int
	NPCID          string
}

// ─── SupplyChain ──────────────────────────────────────────────────────────────

// SupplyChain manages multi-tier resource processing.
type SupplyChain struct {
	mu      sync.Mutex
	Recipes map[Resource]Recipe
	jobs    map[string]*ProcessingJob
	jobSeq  uint64
}

// NewSupplyChain creates a SupplyChain pre-loaded with the default recipe book.
func NewSupplyChain() *SupplyChain {
	recipes := make(map[Resource]Recipe, len(DefaultRecipes))
	for k, v := range DefaultRecipes {
		recipes[k] = v
	}
	return &SupplyChain{
		Recipes: recipes,
		jobs:    make(map[string]*ProcessingJob),
	}
}

// ProcessOrder starts a new processing job for the given recipe.
// It verifies that inputInventory contains sufficient quantities and
// deducts them before creating the job.
// Returns an error if the recipe is unknown or inputs are insufficient.
func (sc *SupplyChain) ProcessOrder(
	npcID string,
	recipeOutput Resource,
	inputInventory map[Resource]int,
) (*ProcessingJob, error) {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	recipe, ok := sc.Recipes[recipeOutput]
	if !ok {
		return nil, fmt.Errorf("unknown recipe: %s", recipeOutput)
	}

	// Validate and deduct inputs.
	for _, inp := range recipe.Inputs {
		have := inputInventory[inp.Resource]
		if have < inp.Quantity {
			return nil, fmt.Errorf(
				"insufficient %s: need %d, have %d",
				inp.Resource, inp.Quantity, have,
			)
		}
	}
	for _, inp := range recipe.Inputs {
		inputInventory[inp.Resource] -= inp.Quantity
	}

	sc.jobSeq++
	id := fmt.Sprintf("job-%d-%d", time.Now().UnixNano(), sc.jobSeq)
	job := &ProcessingJob{
		ID:     id,
		NPCID:  npcID,
		Recipe: recipeOutput,
		// StartTick and CompleteTick will be set by the caller or on first Tick.
		Status: JobStatusPending,
	}
	sc.jobs[id] = job
	return job, nil
}

// StartJob marks a pending job as processing starting at currentTick and sets
// its completion time. Call this once the caller knows the current tick.
func (sc *SupplyChain) StartJob(jobID string, currentTick int64) error {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	job, ok := sc.jobs[jobID]
	if !ok {
		return fmt.Errorf("unknown job: %s", jobID)
	}
	recipe := sc.Recipes[job.Recipe]
	job.StartTick = currentTick
	job.CompleteTick = currentTick + recipe.ProcessingTicks
	job.Status = JobStatusProcessing
	return nil
}

// TickProcessing advances simulation time and collects all jobs that have
// completed by currentTick. Completed jobs are removed from the active set.
func (sc *SupplyChain) TickProcessing(currentTick int64) []CompletedJob {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	var completed []CompletedJob
	for id, job := range sc.jobs {
		if job.Status == JobStatusProcessing && currentTick >= job.CompleteTick {
			recipe := sc.Recipes[job.Recipe]
			completed = append(completed, CompletedJob{
				JobID:          id,
				OutputResource: recipe.Output,
				OutputQuantity: recipe.OutputQuantity,
				NPCID:          job.NPCID,
			})
			job.Status = JobStatusComplete
			delete(sc.jobs, id)
		}
	}
	return completed
}

// ─── PriceDiscovery ───────────────────────────────────────────────────────────

// marketWindow holds per-resource supply/demand observations.
type marketWindow struct {
	supplyTotal float64
	demandTotal float64
	observations int
}

// PriceDiscovery computes dynamic prices based on supply and demand.
type PriceDiscovery struct {
	mu         sync.Mutex
	windows    map[Resource]*marketWindow
	basePrices map[Resource]float64
	// dampFactor limits how far price can deviate from base (0 < damp ≤ 1).
	dampFactor float64
}

// NewPriceDiscovery creates a PriceDiscovery with default base prices and
// a damping factor of 0.5 (price can move at most 50% above/below base).
func NewPriceDiscovery(dampFactor float64) *PriceDiscovery {
	if dampFactor <= 0 || dampFactor > 1 {
		dampFactor = 0.5
	}
	basePrices := map[Resource]float64{
		ResourceWheat:            2,
		ResourceIronOre:          3,
		ResourceWood:             2,
		ResourceStone:            2,
		ResourceFlour:            6,
		ResourceIronIngot:        8,
		ResourceLumber:           6,
		ResourceBrick:            7,
		ResourceBread:            12,
		ResourceSword:            60,
		ResourceFurniture:        35,
		ResourceBuildingMaterial: 25,
	}
	return &PriceDiscovery{
		windows:    make(map[Resource]*marketWindow),
		basePrices: basePrices,
		dampFactor: dampFactor,
	}
}

// RecordSupply adds supply to the resource's market window.
func (pd *PriceDiscovery) RecordSupply(resource Resource, quantity float64) {
	pd.mu.Lock()
	defer pd.mu.Unlock()
	w := pd.getOrCreate(resource)
	w.supplyTotal += quantity
	w.observations++
}

// RecordDemand adds demand to the resource's market window.
func (pd *PriceDiscovery) RecordDemand(resource Resource, quantity float64) {
	pd.mu.Lock()
	defer pd.mu.Unlock()
	w := pd.getOrCreate(resource)
	w.demandTotal += quantity
	w.observations++
}

// CalculatePrice returns the current market price for a resource.
// Price = base_price * lerp(1, demand/supply, dampFactor), clamped to the price floor.
func (pd *PriceDiscovery) CalculatePrice(resource Resource) float64 {
	pd.mu.Lock()
	defer pd.mu.Unlock()

	base := pd.basePrices[resource]
	if base == 0 {
		base = 1
	}

	w := pd.getOrCreate(resource)
	if w.supplyTotal == 0 {
		// No supply recorded — price at 2× base (scarcity premium).
		price := base * 2
		return pd.applyFloor(resource, price)
	}

	ratio := w.demandTotal / w.supplyTotal
	// Damped price: base + dampFactor*(base*(ratio-1))
	price := base * (1 + pd.dampFactor*(ratio-1))
	price = math.Max(price, base*0.1) // never below 10% of base
	return pd.applyFloor(resource, price)
}

func (pd *PriceDiscovery) getOrCreate(resource Resource) *marketWindow {
	w, ok := pd.windows[resource]
	if !ok {
		w = &marketWindow{}
		pd.windows[resource] = w
	}
	return w
}

func (pd *PriceDiscovery) applyFloor(resource Resource, price float64) float64 {
	if meta, ok := ResourceMeta[resource]; ok {
		if price < meta.PriceFloor {
			return meta.PriceFloor
		}
	}
	return price
}

// Reset clears all market windows (for a new period).
func (pd *PriceDiscovery) Reset() {
	pd.mu.Lock()
	defer pd.mu.Unlock()
	pd.windows = make(map[Resource]*marketWindow)
}

// ─── Scarcity ─────────────────────────────────────────────────────────────────

// ScarcitySeverity classifies how critical a resource shortage is.
type ScarcitySeverity string

const (
	SeverityLOW      ScarcitySeverity = "LOW"
	SeverityMEDIUM   ScarcitySeverity = "MEDIUM"
	SeverityCRITICAL ScarcitySeverity = "CRITICAL"
)

// ScarcityAlert represents a resource supply warning.
type ScarcityAlert struct {
	Resource       Resource
	CurrentSupply  float64
	Threshold      float64
	Severity       ScarcitySeverity
}

// ScarcityMonitor tracks raw resource supply levels and detects shortages.
type ScarcityMonitor struct {
	mu          sync.Mutex
	supply      map[Resource]float64
	kafkaWriter *kafka.Writer // may be nil in tests
}

// NewScarcityMonitor creates a ScarcityMonitor. Pass nil for kafkaWriter to
// disable Kafka emission (e.g., in unit tests).
func NewScarcityMonitor(kafkaWriter *kafka.Writer) *ScarcityMonitor {
	return &ScarcityMonitor{
		supply:      make(map[Resource]float64),
		kafkaWriter: kafkaWriter,
	}
}

// SetSupply records the current supply level for a resource.
func (sm *ScarcityMonitor) SetSupply(resource Resource, qty float64) {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.supply[resource] = qty
}

// ConsumeSupply deducts qty from the tracked supply for a resource.
func (sm *ScarcityMonitor) ConsumeSupply(resource Resource, qty float64) {
	sm.mu.Lock()
	defer sm.mu.Unlock()
	sm.supply[resource] -= qty
	if sm.supply[resource] < 0 {
		sm.supply[resource] = 0
	}
}

// CheckScarcity inspects all tracked raw resources and returns alerts for those
// below their threshold. If a Kafka writer is configured, each alert is also
// emitted to economy.scarcity.alert.
func (sm *ScarcityMonitor) CheckScarcity(ctx context.Context) []ScarcityAlert {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	var alerts []ScarcityAlert
	for resource, threshold := range ScarcityThresholds {
		supply := sm.supply[resource]
		if supply < threshold {
			sev := computeSeverity(supply, threshold)
			alert := ScarcityAlert{
				Resource:      resource,
				CurrentSupply: supply,
				Threshold:     threshold,
				Severity:      sev,
			}
			alerts = append(alerts, alert)

			if sm.kafkaWriter != nil {
				sm.emitAlert(ctx, alert)
			}
		}
	}
	return alerts
}

func computeSeverity(supply, threshold float64) ScarcitySeverity {
	ratio := supply / threshold
	switch {
	case ratio < 0.25:
		return SeverityCRITICAL
	case ratio < 0.6:
		return SeverityMEDIUM
	default:
		return SeverityLOW
	}
}

func (sm *ScarcityMonitor) emitAlert(ctx context.Context, alert ScarcityAlert) {
	payload, err := json.Marshal(alert)
	if err != nil {
		return
	}
	_ = sm.kafkaWriter.WriteMessages(ctx, kafka.Message{
		Topic: "economy.scarcity.alert",
		Key:   []byte(alert.Resource),
		Value: payload,
	})
}
