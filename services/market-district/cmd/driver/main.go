// market-driver — synthetic NPC traders for the live Market exhibit.
//
// It places REAL orders into the REAL matching engine over gRPC, producing a
// live, moving order book and a genuine trade tape. It fabricates nothing:
// per-resource prices come from a random walk, but every order is a real
// PlaceOrder RPC and every resulting trade + latency is whatever the engine
// actually produces. In qtown's world these are the town's NPCs trading — the
// simulation IS the product, not a fake overlay on it.
//
// Config (all optional, env-driven):
//
//	MARKET_GRPC_ADDR    gRPC target            (default "localhost:50051")
//	DRIVER_RESOURCES    comma-separated list   (default "gold,wood,grain,stone")
//	DRIVER_TRADERS      distinct NPC ids        (default 8)
//	DRIVER_INTERVAL_MS  ms between order waves  (default 800)
//	DRIVER_SEED         PRNG seed               (default 42 — deterministic)
package main

import (
	"context"
	"log"
	"math"
	"math/rand"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "qtown/proto/qtown"
)

func main() {
	addr := env("MARKET_GRPC_ADDR", "localhost:50051")
	resources := splitCSV(env("DRIVER_RESOURCES", "gold,wood,grain,stone"))
	traders := envInt("DRIVER_TRADERS", 8)
	interval := time.Duration(envInt("DRIVER_INTERVAL_MS", 800)) * time.Millisecond
	seed := int64(envInt("DRIVER_SEED", 42))

	log.Printf("[market-driver] starting — target=%s resources=%v traders=%d interval=%s",
		addr, resources, traders, interval)

	conn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("[market-driver] failed to create client for %s: %v", addr, err)
	}
	defer conn.Close()
	client := pb.NewMarketDistrictClient(conn)

	rng := rand.New(rand.NewSource(seed))

	// Per-resource fair value (a random walk). Seeded with plausible-but-arbitrary
	// starting prices; the walk, not the seed, is what makes the book move.
	fair := make(map[string]float64, len(resources))
	for i, r := range resources {
		fair[r] = 40 + float64(i*15) + rng.Float64()*10
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	var placed, accepted int
	for {
		select {
		case <-stop:
			log.Printf("[market-driver] shutting down — placed=%d accepted=%d", placed, accepted)
			return
		case <-ticker.C:
			for _, res := range resources {
				// Random-walk the fair value (±1.5%), floored so it never goes silly.
				fair[res] *= 1 + (rng.Float64()-0.5)*0.03
				fair[res] = math.Max(1, fair[res])
				f := fair[res]

				// Lay down depth: a few resting makers on each side around fair.
				for i := 0; i < 3; i++ {
					off := (float64(i) + 1) * f * 0.004 // 0.4% per level
					place(client, &placed, &accepted, npc(rng, traders), res, pb.OrderSide_BID, round2(f-off), qty(rng))
					place(client, &placed, &accepted, npc(rng, traders), res, pb.OrderSide_ASK, round2(f+off), qty(rng))
				}

				// ~55% of waves, send a marketable taker that crosses the spread to
				// print a real trade against resting depth.
				if rng.Float64() < 0.55 {
					if rng.Intn(2) == 0 {
						place(client, &placed, &accepted, npc(rng, traders), res, pb.OrderSide_BID, round2(f*1.01), qty(rng))
					} else {
						place(client, &placed, &accepted, npc(rng, traders), res, pb.OrderSide_ASK, round2(f*0.99), qty(rng))
					}
				}
			}
			if placed%50 < 8 { // periodic heartbeat without flooding logs
				log.Printf("[market-driver] placed=%d accepted=%d", placed, accepted)
			}
		}
	}
}

func place(c pb.MarketDistrictClient, placed, accepted *int, npcID int64, res string, side pb.OrderSide, price, quantity float64) {
	*placed++
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	resp, err := c.PlaceOrder(ctx, &pb.PlaceOrderRequest{
		NpcId:    npcID,
		Resource: res,
		Side:     side,
		Price:    float32(price),
		Quantity: float32(quantity),
	})
	if err != nil {
		// Best-effort: a down or slow engine must not crash the driver.
		return
	}
	if resp.Accepted {
		*accepted++
	}
}

func npc(rng *rand.Rand, traders int) int64 { return int64(rng.Intn(traders) + 1) }
func qty(rng *rand.Rand) float64            { return round2(1 + rng.Float64()*9) }
func round2(v float64) float64              { return math.Round(v*100) / 100 }

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func envInt(k string, def int) int {
	if v := os.Getenv(k); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return def
}

func splitCSV(s string) []string {
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if t := strings.TrimSpace(p); t != "" {
			out = append(out, t)
		}
	}
	return out
}
