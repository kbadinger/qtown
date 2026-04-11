package kafka

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"time"

	"github.com/segmentio/kafka-go"
)

// Producer wraps kafka-go writer for emitting events.
type Producer struct {
	writer *kafka.Writer
}

func NewProducer() *Producer {
	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}

	return &Producer{
		writer: &kafka.Writer{
			Addr:         kafka.TCP(brokers),
			Balancer:     &kafka.LeastBytes{},
			BatchTimeout: 10 * time.Millisecond,
			RequiredAcks: kafka.RequireAll,
		},
	}
}

func (p *Producer) Emit(ctx context.Context, topic string, key string, value interface{}) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}

	msg := kafka.Message{
		Topic: topic,
		Key:   []byte(key),
		Value: data,
	}

	if err := p.writer.WriteMessages(ctx, msg); err != nil {
		log.Printf("[market-district] kafka produce error topic=%s: %v", topic, err)
		return err
	}
	return nil
}

func (p *Producer) EmitTradeSettled(ctx context.Context, settled TradeSettledMessage) error {
	return p.Emit(ctx, TopicTradeSettled, string(rune(settled.NPCID)), settled)
}

func (p *Producer) EmitTravelComplete(ctx context.Context, npcID int64, status string, goldDelta int, neighborhood string) error {
	msg := map[string]interface{}{
		"npc_id":       npcID,
		"status":       status,
		"gold_delta":   goldDelta,
		"neighborhood": neighborhood,
	}
	return p.Emit(ctx, TopicNPCTravelComplete, string(rune(npcID)), msg)
}

func (p *Producer) Close() {
	p.writer.Close()
}
