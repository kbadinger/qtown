// Package tournaments implements the NPC Trading Tournament system for
// the Market District service. Tournaments are time-bounded competitions
// where NPCs are ranked by portfolio value (gold + inventory at market prices).
package tournaments

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sort"
	"sync"
	"time"
)

// ─── Kafka topic constants ─────────────────────────────────────────────────────

const (
	TopicTournamentStarted = "qtown.tournament.started"
	TopicTournamentTick    = "qtown.tournament.tick"
	TopicTournamentEnded   = "qtown.tournament.ended"
)

// ─── Types ─────────────────────────────────────────────────────────────────────

// TournamentRules defines the parameters for a tournament run.
type TournamentRules struct {
	// DurationTicks is how many ticks the tournament runs for.
	DurationTicks int `json:"duration_ticks"`

	// StartingGold is the gold amount each participant starts with.
	StartingGold float64 `json:"starting_gold"`

	// AllowedResources lists which resources may be traded.
	// Empty means all resources are allowed.
	AllowedResources []string `json:"allowed_resources"`

	// MaxOrdersPerTick is the maximum orders a participant may place per tick.
	// Zero means unlimited.
	MaxOrdersPerTick int `json:"max_orders_per_tick"`
}

// Standing holds a participant's current ranking within a tournament.
type Standing struct {
	NPCID          string  `json:"npc_id"`
	Rank           int     `json:"rank"`
	Gold           float64 `json:"gold"`
	InventoryValue float64 `json:"inventory_value"`
	TotalValue     float64 `json:"total_value"`
	TradesExecuted int     `json:"trades_executed"`
	ProfitLoss     float64 `json:"profit_loss"`
}

// participantState tracks mutable state for one NPC in a tournament.
type participantState struct {
	npcID          string
	gold           float64
	inventory      map[string]float64 // resource → quantity
	tradesExecuted int
	ordersThisTick int
	initialValue   float64
}

// TickResult is returned after processing each tick.
type TickResult struct {
	TournamentID string     `json:"tournament_id"`
	Tick         int64      `json:"tick"`
	Standings    []Standing `json:"standings"`
}

// TournamentResult is the final outcome of a tournament.
type TournamentResult struct {
	TournamentID  string     `json:"tournament_id"`
	Name          string     `json:"name"`
	WinnerID      string     `json:"winner_id"`
	WinnerProfit  float64    `json:"winner_profit"`
	Standings     []Standing `json:"standings"`
	StartTick     int64      `json:"start_tick"`
	EndTick       int64      `json:"end_tick"`
	TotalTrades   int        `json:"total_trades"`
}

// KafkaProducer is a minimal interface for emitting tournament events.
// This matches the Emit signature of kafka.Producer.
type KafkaProducer interface {
	Emit(ctx context.Context, topic string, key string, value interface{}) error
}

// ─── Tournament ─────────────────────────────────────────────────────────────────

// Tournament is a single time-bounded NPC trading competition.
type Tournament struct {
	mu       sync.RWMutex
	id       string
	name     string
	rules    TournamentRules
	state    map[string]*participantState // keyed by npc_id
	startTick int64
	endTick   int64
	active   bool
	ended    bool
	producer KafkaProducer
}

// NewTournament creates a new tournament. The producer may be nil (disables Kafka emission).
func NewTournament(name string, rules TournamentRules, participants []string, producer KafkaProducer) *Tournament {
	t := &Tournament{
		id:       fmt.Sprintf("tournament-%d", time.Now().UnixNano()),
		name:     name,
		rules:    rules,
		state:    make(map[string]*participantState, len(participants)),
		producer: producer,
	}

	for _, npcID := range participants {
		inv := make(map[string]float64)
		initial := rules.StartingGold
		t.state[npcID] = &participantState{
			npcID:        npcID,
			gold:         initial,
			inventory:    inv,
			initialValue: initial,
		}
	}

	return t
}

// ID returns the tournament's unique identifier.
func (t *Tournament) ID() string { return t.id }

// Name returns the human-readable tournament name.
func (t *Tournament) Name() string { return t.name }

// IsActive reports whether the tournament is currently running.
func (t *Tournament) IsActive() bool {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.active
}

// IsEnded reports whether the tournament has concluded.
func (t *Tournament) IsEnded() bool {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.ended
}

// EndTick returns the tick at which this tournament is scheduled to end.
// Returns 0 if the tournament has not started yet.
func (t *Tournament) EndTick() int64 {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.endTick
}

// Start initialises the tournament at the given simulation tick.
// It publishes a tournament.started event to Kafka.
func (t *Tournament) Start(currentTick int64) {
	t.mu.Lock()
	defer t.mu.Unlock()

	if t.active {
		return
	}

	t.startTick = currentTick
	t.endTick = currentTick + int64(t.rules.DurationTicks)
	t.active = true

	// Snapshot initial participant state.
	for _, ps := range t.state {
		ps.ordersThisTick = 0
	}

	log.Printf("[tournament] started id=%s name=%q start_tick=%d end_tick=%d participants=%d",
		t.id, t.name, t.startTick, t.endTick, len(t.state))

	if t.producer != nil {
		payload := map[string]interface{}{
			"tournament_id": t.id,
			"name":          t.name,
			"start_tick":    t.startTick,
			"end_tick":      t.endTick,
			"rules":         t.rules,
			"participants":  t.participantIDs(),
		}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := t.producer.Emit(ctx, TopicTournamentStarted, t.id, payload); err != nil {
			log.Printf("[tournament] kafka emit error (started): %v", err)
		}
	}
}

// ProcessTick evaluates standings after each tick and publishes a tournament.tick event.
// Returns nil if the tournament is not active.
func (t *Tournament) ProcessTick(currentTick int64, prices map[string]float64) *TickResult {
	t.mu.Lock()
	defer t.mu.Unlock()

	if !t.active || t.ended {
		return nil
	}

	// Reset per-tick order counters.
	for _, ps := range t.state {
		ps.ordersThisTick = 0
	}

	standings := t.computeStandings(prices)

	result := &TickResult{
		TournamentID: t.id,
		Tick:         currentTick,
		Standings:    standings,
	}

	if t.producer != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := t.producer.Emit(ctx, TopicTournamentTick, t.id, result); err != nil {
			log.Printf("[tournament] kafka emit error (tick): %v", err)
		}
	}

	return result
}

// End finalises the tournament, declares a winner, and publishes tournament.ended.
// It returns nil if the tournament was not active.
func (t *Tournament) End(prices map[string]float64) *TournamentResult {
	t.mu.Lock()
	defer t.mu.Unlock()

	if !t.active || t.ended {
		return nil
	}

	t.active = false
	t.ended = true

	standings := t.computeStandings(prices)

	var winnerID string
	var winnerProfit float64
	totalTrades := 0

	if len(standings) > 0 {
		winner := standings[0]
		winnerID = winner.NPCID
		winnerProfit = winner.ProfitLoss
	}

	for _, ps := range t.state {
		totalTrades += ps.tradesExecuted
	}

	result := &TournamentResult{
		TournamentID: t.id,
		Name:         t.name,
		WinnerID:     winnerID,
		WinnerProfit: winnerProfit,
		Standings:    standings,
		StartTick:    t.startTick,
		TotalTrades:  totalTrades,
	}

	log.Printf("[tournament] ended id=%s winner=%s profit=%.2f total_trades=%d",
		t.id, winnerID, winnerProfit, totalTrades)

	if t.producer != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := t.producer.Emit(ctx, TopicTournamentEnded, t.id, result); err != nil {
			log.Printf("[tournament] kafka emit error (ended): %v", err)
		}
	}

	return result
}

// GetStandings returns current standings sorted by total portfolio value.
// prices maps resource name → current market price.
func (t *Tournament) GetStandings(prices map[string]float64) []Standing {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.computeStandings(prices)
}

// RecordTrade updates a participant's inventory and trade count.
// Returns an error if the participant has exceeded MaxOrdersPerTick.
func (t *Tournament) RecordTrade(npcID string, resource string, qty float64, goldDelta float64) error {
	t.mu.Lock()
	defer t.mu.Unlock()

	ps, ok := t.state[npcID]
	if !ok {
		return fmt.Errorf("npc %q is not a tournament participant", npcID)
	}

	if t.rules.MaxOrdersPerTick > 0 && ps.ordersThisTick >= t.rules.MaxOrdersPerTick {
		return fmt.Errorf("npc %q has exceeded max_orders_per_tick (%d)", npcID, t.rules.MaxOrdersPerTick)
	}

	ps.gold += goldDelta
	ps.inventory[resource] += qty
	ps.tradesExecuted++
	ps.ordersThisTick++

	return nil
}

// computeStandings calculates and ranks all participants. Must be called with at least a read lock.
func (t *Tournament) computeStandings(prices map[string]float64) []Standing {
	standings := make([]Standing, 0, len(t.state))

	for _, ps := range t.state {
		invValue := 0.0
		for resource, qty := range ps.inventory {
			if price, ok := prices[resource]; ok {
				invValue += qty * price
			}
		}

		total := ps.gold + invValue
		pl := total - ps.initialValue

		standings = append(standings, Standing{
			NPCID:          ps.npcID,
			Gold:           ps.gold,
			InventoryValue: invValue,
			TotalValue:     total,
			TradesExecuted: ps.tradesExecuted,
			ProfitLoss:     pl,
		})
	}

	// Sort descending by total value; ties broken by profit/loss.
	sort.Slice(standings, func(i, j int) bool {
		if standings[i].TotalValue != standings[j].TotalValue {
			return standings[i].TotalValue > standings[j].TotalValue
		}
		return standings[i].ProfitLoss > standings[j].ProfitLoss
	})

	// Assign ranks.
	for i := range standings {
		standings[i].Rank = i + 1
	}

	return standings
}

func (t *Tournament) participantIDs() []string {
	ids := make([]string, 0, len(t.state))
	for id := range t.state {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

// ─── TournamentScheduler ───────────────────────────────────────────────────────

// scheduledTournament holds the configuration for a recurring tournament.
type scheduledTournament struct {
	name                string
	intervalTicks       int
	rules               TournamentRules
	participantSelector func() []string
	lastStartTick       int64
}

// TournamentScheduler manages recurring tournaments and keeps history.
type TournamentScheduler struct {
	mu         sync.RWMutex
	scheduled  []*scheduledTournament
	active     []*Tournament
	history    []*TournamentResult
	producer   KafkaProducer
}

// NewTournamentScheduler creates a scheduler with an optional Kafka producer.
func NewTournamentScheduler(producer KafkaProducer) *TournamentScheduler {
	return &TournamentScheduler{producer: producer}
}

// ScheduleRecurring registers a tournament that auto-starts every intervalTicks ticks.
func (s *TournamentScheduler) ScheduleRecurring(
	name string,
	intervalTicks int,
	rules TournamentRules,
	participantSelector func() []string,
) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.scheduled = append(s.scheduled, &scheduledTournament{
		name:                name,
		intervalTicks:       intervalTicks,
		rules:               rules,
		participantSelector: participantSelector,
		lastStartTick:       -1,
	})

	log.Printf("[scheduler] registered recurring tournament name=%q interval=%d", name, intervalTicks)
}

// ProcessTick should be called on each simulation tick. It starts new tournaments,
// advances active ones, and ends expired ones.
func (s *TournamentScheduler) ProcessTick(currentTick int64, prices map[string]float64) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Start any due scheduled tournaments.
	for _, st := range s.scheduled {
		due := st.lastStartTick < 0 || (currentTick-st.lastStartTick) >= int64(st.intervalTicks)
		if due {
			participants := st.participantSelector()
			if len(participants) == 0 {
				continue
			}

			t := NewTournament(st.name, st.rules, participants, s.producer)
			t.Start(currentTick)
			s.active = append(s.active, t)
			st.lastStartTick = currentTick
		}
	}

	// Advance active tournaments; collect ended ones.
	var stillActive []*Tournament
	for _, t := range s.active {
		result := t.ProcessTick(currentTick, prices)
		if result == nil {
			continue
		}

		// Check if this tournament should end.
		if currentTick >= t.EndTick() {
			finalResult := t.End(prices)
			if finalResult != nil {
				s.history = append(s.history, finalResult)
			}
		} else {
			stillActive = append(stillActive, t)
		}
	}

	s.active = stillActive
}

// GetActive returns all currently running tournaments.
func (s *TournamentScheduler) GetActive() []*Tournament {
	s.mu.RLock()
	defer s.mu.RUnlock()
	result := make([]*Tournament, len(s.active))
	copy(result, s.active)
	return result
}

// GetHistory returns past tournament results, most recent first.
// limit ≤ 0 returns all history.
func (s *TournamentScheduler) GetHistory(limit int) []*TournamentResult {
	s.mu.RLock()
	defer s.mu.RUnlock()

	n := len(s.history)
	if limit > 0 && limit < n {
		n = limit
	}

	result := make([]*TournamentResult, n)
	// Return most recent first.
	for i := 0; i < n; i++ {
		result[i] = s.history[len(s.history)-1-i]
	}

	return result
}

// ─── JSON helpers ──────────────────────────────────────────────────────────────

// MarshalJSON makes TournamentResult JSON-safe.
func (r *TournamentResult) MarshalJSON() ([]byte, error) {
	type Alias TournamentResult
	return json.Marshal((*Alias)(r))
}
