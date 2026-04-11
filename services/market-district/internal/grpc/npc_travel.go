package grpc

import (
	"context"
	"fmt"
	"log"
	"time"

	pb "qtown/market-district/proto"
)

// NPCArrive handles an NPC arriving at the Market District.
func (s *MarketServer) NPCArrive(ctx context.Context, req *pb.TravelRequest) (*pb.TravelResponse, error) {
	npcState := req.NpcState
	if npcState == nil {
		return &pb.TravelResponse{
			Accepted: false,
			Reason:   "missing NPC state",
		}, nil
	}

	s.mu.Lock()
	s.traders[npcState.Id] = &TraderState{
		NPCID:     npcState.Id,
		Name:      npcState.Name,
		Gold:      float64(npcState.Gold),
		ArrivedAt: time.Now(),
	}
	s.mu.Unlock()

	log.Printf("[market-district] NPC %d (%s) arrived with %.0f gold",
		npcState.Id, npcState.Name, npcState.Gold)

	return &pb.TravelResponse{
		Accepted: true,
		EtaTicks: 0,
	}, nil
}

// NPCDepart handles an NPC leaving the Market District.
func (s *MarketServer) NPCDepart(ctx context.Context, req *pb.TravelRequest) (*pb.TravelResponse, error) {
	npcID := req.NpcId

	s.mu.Lock()
	trader, exists := s.traders[npcID]
	if exists {
		delete(s.traders, npcID)
	}
	s.mu.Unlock()

	if !exists {
		return &pb.TravelResponse{
			Accepted: false,
			Reason:   fmt.Sprintf("NPC %d not found in Market District", npcID),
		}, nil
	}

	log.Printf("[market-district] NPC %d (%s) departing after %.0fs",
		npcID, trader.Name, time.Since(trader.ArrivedAt).Seconds())

	return &pb.TravelResponse{
		Accepted: true,
	}, nil
}
