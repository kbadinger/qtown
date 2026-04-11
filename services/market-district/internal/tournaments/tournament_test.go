package tournaments_test

import (
	"context"
	"sync"
	"testing"

	"qtown/market-district/internal/tournaments"
)

// ─── Mock Kafka Producer ───────────────────────────────────────────────────────

// mockProducer records emitted events for assertion.
type mockProducer struct {
	mu     sync.Mutex
	events []mockEvent
}

type mockEvent struct {
	topic string
	key   string
	value interface{}
}

func (m *mockProducer) Emit(_ context.Context, topic, key string, value interface{}) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.events = append(m.events, mockEvent{topic: topic, key: key, value: value})
	return nil
}

func (m *mockProducer) EventsByTopic(topic string) []mockEvent {
	m.mu.Lock()
	defer m.mu.Unlock()
	var out []mockEvent
	for _, e := range m.events {
		if e.topic == topic {
			out = append(out, e)
		}
	}
	return out
}

func (m *mockProducer) Reset() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.events = nil
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

func defaultRules() tournaments.TournamentRules {
	return tournaments.TournamentRules{
		DurationTicks:    10,
		StartingGold:     1000.0,
		AllowedResources: []string{"wheat", "iron"},
		MaxOrdersPerTick: 5,
	}
}

func samplePrices() map[string]float64 {
	return map[string]float64{
		"wheat": 10.0,
		"iron":  25.0,
	}
}

// ─── TestTournamentLifecycle ───────────────────────────────────────────────────

func TestTournamentLifecycle(t *testing.T) {
	prod := &mockProducer{}
	rules := defaultRules()
	participants := []string{"npc-alice", "npc-bob", "npc-carol"}

	tourney := tournaments.NewTournament("Weekly Showdown", rules, participants, prod)

	// Not active before Start.
	if tourney.IsActive() {
		t.Fatal("expected tournament to be inactive before Start")
	}

	// Start the tournament.
	tourney.Start(100)

	if !tourney.IsActive() {
		t.Fatal("expected tournament to be active after Start")
	}

	startedEvents := prod.EventsByTopic(tournaments.TopicTournamentStarted)
	if len(startedEvents) != 1 {
		t.Fatalf("expected 1 tournament.started event, got %d", len(startedEvents))
	}

	prices := samplePrices()

	// Process several ticks — no trades yet.
	for tick := int64(101); tick <= 105; tick++ {
		result := tourney.ProcessTick(tick, prices)
		if result == nil {
			t.Fatalf("ProcessTick returned nil at tick %d", tick)
		}
		if result.TournamentID != tourney.ID() {
			t.Errorf("tick result has wrong tournament ID: %s", result.TournamentID)
		}
		if len(result.Standings) != len(participants) {
			t.Errorf("expected %d standings, got %d at tick %d", len(participants), len(result.Standings), tick)
		}
	}

	tickEvents := prod.EventsByTopic(tournaments.TopicTournamentTick)
	if len(tickEvents) != 5 {
		t.Errorf("expected 5 tournament.tick events, got %d", len(tickEvents))
	}

	// Simulate a trade — alice buys 10 wheat.
	err := tourney.RecordTrade("npc-alice", "wheat", 10.0, -100.0) // paid 10*10=100
	if err != nil {
		t.Fatalf("RecordTrade failed: %v", err)
	}

	// End the tournament.
	result := tourney.End(prices)
	if result == nil {
		t.Fatal("End returned nil")
	}

	if result.TournamentID != tourney.ID() {
		t.Errorf("wrong tournament ID in result: %s", result.TournamentID)
	}

	if !tourney.IsEnded() {
		t.Fatal("expected tournament to be ended after End()")
	}

	endedEvents := prod.EventsByTopic(tournaments.TopicTournamentEnded)
	if len(endedEvents) != 1 {
		t.Fatalf("expected 1 tournament.ended event, got %d", len(endedEvents))
	}

	if result.WinnerID == "" {
		t.Error("expected a non-empty winner ID")
	}

	t.Logf("Winner: %s (profit=%.2f)", result.WinnerID, result.WinnerProfit)
}

// ─── TestStandingsCalculation ─────────────────────────────────────────────────

func TestStandingsCalculation(t *testing.T) {
	rules := tournaments.TournamentRules{
		DurationTicks: 10,
		StartingGold:  1000.0,
	}
	participants := []string{"npc-x", "npc-y"}
	tourney := tournaments.NewTournament("Calc Test", rules, participants, nil)
	tourney.Start(1)

	prices := map[string]float64{"wheat": 10.0}

	// npc-x buys 50 wheat for 500 gold → gold=500, inventory=50*10=500 → total=1000
	if err := tourney.RecordTrade("npc-x", "wheat", 50.0, -500.0); err != nil {
		t.Fatalf("RecordTrade npc-x: %v", err)
	}

	// npc-y stays all cash → gold=1000, inventory=0 → total=1000
	standings := tourney.GetStandings(prices)

	if len(standings) != 2 {
		t.Fatalf("expected 2 standings, got %d", len(standings))
	}

	// Verify total value formula: gold + inventory * price
	for _, s := range standings {
		switch s.NPCID {
		case "npc-x":
			expectedTotal := 500.0 + 50.0*10.0
			if s.TotalValue != expectedTotal {
				t.Errorf("npc-x total value: want %.2f, got %.2f", expectedTotal, s.TotalValue)
			}
			if s.InventoryValue != 500.0 {
				t.Errorf("npc-x inventory value: want 500.00, got %.2f", s.InventoryValue)
			}
			if s.Gold != 500.0 {
				t.Errorf("npc-x gold: want 500.00, got %.2f", s.Gold)
			}
		case "npc-y":
			if s.TotalValue != 1000.0 {
				t.Errorf("npc-y total value: want 1000.00, got %.2f", s.TotalValue)
			}
			if s.Gold != 1000.0 {
				t.Errorf("npc-y gold: want 1000.00, got %.2f", s.Gold)
			}
		}
	}

	// Both tied at 1000 total; rank ordering is deterministic but either can be first.
	if standings[0].Rank != 1 {
		t.Errorf("first standing rank should be 1, got %d", standings[0].Rank)
	}
	if standings[1].Rank != 2 {
		t.Errorf("second standing rank should be 2, got %d", standings[1].Rank)
	}

	// Now price rises to 20; npc-x should pull ahead.
	prices["wheat"] = 20.0
	standings = tourney.GetStandings(prices)
	if standings[0].NPCID != "npc-x" {
		t.Errorf("expected npc-x to lead after price rise, got %s", standings[0].NPCID)
	}
	expectedXTotal := 500.0 + 50.0*20.0 // 1500
	if standings[0].TotalValue != expectedXTotal {
		t.Errorf("npc-x total with higher price: want %.2f, got %.2f", expectedXTotal, standings[0].TotalValue)
	}

	t.Logf("Standings at price=20: %v", standings)
}

// ─── TestTournamentRulesEnforced ──────────────────────────────────────────────

func TestTournamentRulesEnforced(t *testing.T) {
	rules := tournaments.TournamentRules{
		DurationTicks:    5,
		StartingGold:     1000.0,
		MaxOrdersPerTick: 2,
	}
	participants := []string{"npc-trader"}
	tourney := tournaments.NewTournament("Rules Test", rules, participants, nil)
	tourney.Start(1)

	prices := samplePrices()

	// First order: should succeed.
	if err := tourney.RecordTrade("npc-trader", "wheat", 1.0, -10.0); err != nil {
		t.Errorf("first order should succeed: %v", err)
	}

	// Second order: should succeed.
	if err := tourney.RecordTrade("npc-trader", "wheat", 1.0, -10.0); err != nil {
		t.Errorf("second order should succeed: %v", err)
	}

	// Third order this tick: should be REJECTED (limit is 2).
	if err := tourney.RecordTrade("npc-trader", "wheat", 1.0, -10.0); err == nil {
		t.Error("third order this tick should have been rejected by MaxOrdersPerTick rule")
	}

	// After ProcessTick, the counter resets; next order should succeed.
	result := tourney.ProcessTick(2, prices)
	if result == nil {
		t.Fatal("ProcessTick returned nil")
	}

	if err := tourney.RecordTrade("npc-trader", "wheat", 1.0, -10.0); err != nil {
		t.Errorf("order after tick reset should succeed: %v", err)
	}

	t.Logf("Rules enforced correctly: max_orders_per_tick=%d", rules.MaxOrdersPerTick)
}

// ─── TestSchedulerRecurrence ──────────────────────────────────────────────────

func TestSchedulerRecurrence(t *testing.T) {
	prod := &mockProducer{}
	scheduler := tournaments.NewTournamentScheduler(prod)

	participantSelector := func() []string {
		return []string{"npc-a", "npc-b", "npc-c"}
	}

	rules := tournaments.TournamentRules{
		DurationTicks: 5,
		StartingGold:  500.0,
	}

	// Register a tournament that should run every 10 ticks.
	scheduler.ScheduleRecurring("Recurring Cup", 10, rules, participantSelector)

	prices := samplePrices()

	// Tick 1 — first tournament should start immediately.
	scheduler.ProcessTick(1, prices)

	active := scheduler.GetActive()
	if len(active) != 1 {
		t.Fatalf("expected 1 active tournament at tick 1, got %d", len(active))
	}

	startedEvents := prod.EventsByTopic(tournaments.TopicTournamentStarted)
	if len(startedEvents) < 1 {
		t.Fatal("expected at least 1 tournament.started event after tick 1")
	}
	firstTournamentID := active[0].ID()

	// Advance ticks 2–5 (tournament ends at tick 6 = start(1) + duration(5)).
	for tick := int64(2); tick <= 5; tick++ {
		scheduler.ProcessTick(tick, prices)
	}

	// Tick 6 — tournament should end (duration = 5 ticks from start tick 1).
	scheduler.ProcessTick(6, prices)

	history := scheduler.GetHistory(0)
	if len(history) < 1 {
		t.Fatal("expected at least 1 completed tournament in history after tick 6")
	}
	if history[0].TournamentID != firstTournamentID {
		t.Errorf("history[0] tournament ID mismatch: got %s", history[0].TournamentID)
	}

	// At tick 11 (1 + 10 interval) a new tournament should start.
	prod.Reset()
	for tick := int64(7); tick <= 11; tick++ {
		scheduler.ProcessTick(tick, prices)
	}

	// A second tournament.started event should have been emitted.
	newStarted := prod.EventsByTopic(tournaments.TopicTournamentStarted)
	if len(newStarted) < 1 {
		t.Error("expected a second tournament to start at tick 11")
	}

	t.Logf("Recurrence verified: history=%d, active=%d", len(scheduler.GetHistory(0)), len(scheduler.GetActive()))
}

// ─── TestNonParticipantTrade ───────────────────────────────────────────────────

func TestNonParticipantTrade(t *testing.T) {
	rules := defaultRules()
	tourney := tournaments.NewTournament("Participant Check", rules, []string{"npc-1"}, nil)
	tourney.Start(1)

	err := tourney.RecordTrade("npc-not-in-tournament", "wheat", 5.0, -50.0)
	if err == nil {
		t.Error("expected error when trading as non-participant, got nil")
	}
}
