package kafka

import (
	"context"
	"encoding/json"
	"log"
	"os"

	"github.com/segmentio/kafka-go"
)

const (
	TopicNPCTravel        = "qtown.npc.travel"
	TopicEconomyTrade     = "qtown.economy.trade"
	TopicTradeSettled     = "qtown.economy.trade.settled"
	TopicPriceUpdate      = "qtown.economy.price.update"
	TopicNPCTravelComplete = "qtown.npc.travel.complete"
)

// NPCTravelMessage is the Kafka message for NPC travel events.
type NPCTravelMessage struct {
	Tick     int64           `json:"tick"`
	NPCID    int64           `json:"npc_id"`
	From     string          `json:"from"`
	To       string          `json:"to"`
	NPCState json.RawMessage `json:"npc_state"`
}

// TradeSettledMessage is emitted when a trade matches in the order book.
type TradeSettledMessage struct {
	Tick      int64   `json:"tick"`
	TradeID   string  `json:"trade_id"`
	NPCID     int64   `json:"npc_id"`
	GoldDelta int     `json:"gold_delta"`
	Resource  string  `json:"resource"`
	Price     float64 `json:"price"`
	Quantity  float64 `json:"quantity"`
}

type MessageHandler func(ctx context.Context, msg []byte) error

// Consumer wraps kafka-go reader with handler dispatch.
type Consumer struct {
	readers  []*kafka.Reader
	handlers map[string]MessageHandler
}

func NewConsumer() *Consumer {
	return &Consumer{
		handlers: make(map[string]MessageHandler),
	}
}

func (c *Consumer) RegisterHandler(topic string, handler MessageHandler) {
	c.handlers[topic] = handler

	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{brokers},
		Topic:    topic,
		GroupID:  "market-district",
		MinBytes: 1e3,
		MaxBytes: 10e6,
	})
	c.readers = append(c.readers, reader)
}

func (c *Consumer) Start(ctx context.Context) {
	for _, reader := range c.readers {
		go c.consumeLoop(ctx, reader)
	}
}

func (c *Consumer) consumeLoop(ctx context.Context, reader *kafka.Reader) {
	topic := reader.Config().Topic
	handler := c.handlers[topic]
	log.Printf("[market-district] kafka consumer started for topic=%s", topic)

	for {
		msg, err := reader.ReadMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return // context cancelled
			}
			log.Printf("[market-district] kafka read error topic=%s: %v", topic, err)
			continue
		}

		if err := handler(ctx, msg.Value); err != nil {
			log.Printf("[market-district] handler error topic=%s offset=%d: %v",
				topic, msg.Offset, err)
		}
	}
}

func (c *Consumer) Close() {
	for _, r := range c.readers {
		r.Close()
	}
}
