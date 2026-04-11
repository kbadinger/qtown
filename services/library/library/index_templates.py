"""Elasticsearch index template definitions for all Qtown indices."""

from typing import Any

# ---------------------------------------------------------------------------
# Shared settings used by all indices
# ---------------------------------------------------------------------------

SHARED_SETTINGS: dict[str, Any] = {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
        "filter": {
            "edge_ngram_filter": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 20,
            }
        },
        "analyzer": {
            "standard_analyzer": {
                "type": "standard",
                "stopwords": "_english_",
            },
            "autocomplete_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "edge_ngram_filter"],
            },
            "autocomplete_search_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase"],
            },
        },
    },
}


def _text_with_keyword(analyzer: str = "standard_analyzer") -> dict[str, Any]:
    """Return a mapping for a field that supports both full-text and exact-value search."""
    return {
        "type": "text",
        "analyzer": analyzer,
        "fields": {
            "keyword": {"type": "keyword", "ignore_above": 512},
            "autocomplete": {
                "type": "text",
                "analyzer": "autocomplete_analyzer",
                "search_analyzer": "autocomplete_search_analyzer",
            },
        },
    }


# ---------------------------------------------------------------------------
# qtown-events
# ---------------------------------------------------------------------------

EVENTS_TEMPLATE: dict[str, Any] = {
    "index_patterns": ["qtown-events*"],
    "template": {
        "settings": SHARED_SETTINGS,
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "event_id": {"type": "keyword"},
                "type": {"type": "keyword"},
                "description": _text_with_keyword(),
                "tick": {"type": "long"},
                "timestamp": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
                "npc_ids": {"type": "keyword"},
                "neighborhood": {"type": "keyword"},
                "metadata": {"type": "object", "dynamic": True, "enabled": True},
            },
        },
    },
    "priority": 100,
    "_meta": {"description": "Qtown broadcast events index template"},
}

# ---------------------------------------------------------------------------
# qtown-newspapers
# ---------------------------------------------------------------------------

NEWSPAPERS_TEMPLATE: dict[str, Any] = {
    "index_patterns": ["qtown-newspapers*"],
    "template": {
        "settings": SHARED_SETTINGS,
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "day": {"type": "integer"},
                "headline": _text_with_keyword(),
                "lead": {
                    "type": "text",
                    "analyzer": "standard_analyzer",
                    "term_vector": "with_positions_offsets",
                },
                "body": {
                    "type": "text",
                    "analyzer": "standard_analyzer",
                    "term_vector": "with_positions_offsets",
                },
                "editorial": {
                    "type": "text",
                    "analyzer": "standard_analyzer",
                },
                "generated_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
            },
        },
    },
    "priority": 100,
    "_meta": {"description": "Qtown AI-generated newspaper index template"},
}

# ---------------------------------------------------------------------------
# qtown-dialogues
# ---------------------------------------------------------------------------

DIALOGUES_TEMPLATE: dict[str, Any] = {
    "index_patterns": ["qtown-dialogues*"],
    "template": {
        "settings": SHARED_SETTINGS,
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "dialogue_id": {"type": "keyword"},
                "npc_id": {"type": "keyword"},
                "npc_name": _text_with_keyword(),
                "text": {
                    "type": "text",
                    "analyzer": "standard_analyzer",
                    "term_vector": "with_positions_offsets",
                },
                "context": {"type": "object", "dynamic": True, "enabled": True},
                "generated_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
            },
        },
    },
    "priority": 100,
    "_meta": {"description": "Qtown NPC dialogue index template"},
}

# ---------------------------------------------------------------------------
# qtown-transactions
# ---------------------------------------------------------------------------

TRANSACTIONS_TEMPLATE: dict[str, Any] = {
    "index_patterns": ["qtown-transactions*"],
    "template": {
        "settings": SHARED_SETTINGS,
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "trade_id": {"type": "keyword"},
                "buyer_id": {"type": "keyword"},
                "seller_id": {"type": "keyword"},
                "resource": {"type": "keyword"},
                "price": {"type": "float"},
                "quantity": {"type": "float"},
                "settled_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
            },
        },
    },
    "priority": 100,
    "_meta": {"description": "Qtown market transaction index template"},
}

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TEMPLATES: dict[str, dict[str, Any]] = {
    "qtown-events": EVENTS_TEMPLATE,
    "qtown-newspapers": NEWSPAPERS_TEMPLATE,
    "qtown-dialogues": DIALOGUES_TEMPLATE,
    "qtown-transactions": TRANSACTIONS_TEMPLATE,
}

INDEX_NAMES: list[str] = [
    "qtown-events",
    "qtown-newspapers",
    "qtown-dialogues",
    "qtown-transactions",
]
