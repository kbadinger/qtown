"""Async Elasticsearch client for the Qtown Library service."""

from __future__ import annotations

import logging
import os
from typing import Any

from elasticsearch import AsyncElasticsearch, helpers

from library.index_templates import ALL_TEMPLATES, INDEX_NAMES

logger = logging.getLogger(__name__)

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ES_USERNAME = os.getenv("ELASTICSEARCH_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD", "changeme")


class ElasticsearchClient:
    """Thin async wrapper around the official elasticsearch-py client."""

    def __init__(self) -> None:
        self._client: AsyncElasticsearch | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the async client and apply index templates."""
        self._client = AsyncElasticsearch(
            hosts=[ES_URL],
            http_auth=(ES_USERNAME, ES_PASSWORD),
            retry_on_timeout=True,
            max_retries=3,
            request_timeout=30,
        )
        await self._apply_templates()
        logger.info("Elasticsearch client connected to %s", ES_URL)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            logger.info("Elasticsearch client closed")

    @property
    def client(self) -> AsyncElasticsearch:
        if self._client is None:
            raise RuntimeError("ElasticsearchClient not connected — call connect() first")
        return self._client

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    async def _apply_templates(self) -> None:
        """Register or update all index component templates in Elasticsearch."""
        for name, template in ALL_TEMPLATES.items():
            try:
                await self.client.indices.put_index_template(name=name, body=template)
                logger.debug("Applied index template: %s", name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not apply template %s: %s", name, exc)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        indices: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Multi-index full-text search with highlighting.

        Parameters
        ----------
        query:
            The user-provided search string.
        indices:
            List of index names to search.  Defaults to all four qtown indices.
        limit:
            Maximum number of hits to return.
        offset:
            Pagination offset.

        Returns
        -------
        dict with keys: total, hits, took_ms
        """
        target = indices or INDEX_NAMES

        body: dict[str, Any] = {
            "from": offset,
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "description^2",
                        "description.autocomplete",
                        "headline^3",
                        "headline.autocomplete",
                        "lead^2",
                        "body",
                        "editorial",
                        "text^2",
                        "npc_name",
                        "resource",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
            "highlight": {
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
                "fields": {
                    "description": {"number_of_fragments": 2},
                    "headline": {"number_of_fragments": 1},
                    "lead": {"number_of_fragments": 2},
                    "body": {"number_of_fragments": 3},
                    "text": {"number_of_fragments": 2},
                },
            },
            "sort": [{"_score": "desc"}],
        }

        response = await self.client.search(index=",".join(target), body=body)

        hits = []
        for hit in response["hits"]["hits"]:
            hits.append(
                {
                    "_index": hit["_index"],
                    "_id": hit["_id"],
                    "_score": hit["_score"],
                    "_source": hit["_source"],
                    "highlight": hit.get("highlight", {}),
                }
            )

        return {
            "total": response["hits"]["total"]["value"],
            "hits": hits,
            "took_ms": response["took"],
        }

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------

    async def aggregate(
        self,
        index: str,
        agg_type: str,
        field: str,
        interval: str = "1d",
    ) -> dict[str, Any]:
        """
        Run an aggregation against an index.

        Parameters
        ----------
        index:
            Target index name.
        agg_type:
            One of: ``date_histogram``, ``terms``, ``stats``.
        field:
            The document field to aggregate on.
        interval:
            Calendar/fixed interval (only used for date_histogram).

        Returns
        -------
        Aggregation result dict.
        """
        if agg_type == "date_histogram":
            agg_body: dict[str, Any] = {
                "date_histogram": {
                    "field": field,
                    "calendar_interval": interval,
                    "min_doc_count": 0,
                }
            }
        elif agg_type == "terms":
            agg_body = {"terms": {"field": field, "size": 100}}
        elif agg_type == "stats":
            agg_body = {"stats": {"field": field}}
        else:
            raise ValueError(f"Unsupported agg_type: {agg_type!r}")

        body: dict[str, Any] = {
            "size": 0,
            "aggs": {"result": agg_body},
        }

        response = await self.client.search(index=index, body=body)
        return response["aggregations"]["result"]

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    async def index_document(
        self,
        index: str,
        doc_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Index a single document."""
        response = await self.client.index(index=index, id=doc_id, document=body)
        return {
            "result": response["result"],
            "_id": response["_id"],
            "_index": response["_index"],
        }

    async def bulk_index(
        self,
        index: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Bulk index a list of documents.

        Each document dict must contain an ``_id`` key (used as the document id)
        plus the actual document payload under all other keys.
        """
        actions = []
        for doc in documents:
            doc_id = doc.get("_id") or doc.get("event_id") or doc.get("trade_id") or doc.get("dialogue_id")
            source = {k: v for k, v in doc.items() if k != "_id"}
            action: dict[str, Any] = {
                "_op_type": "index",
                "_index": index,
                "_source": source,
            }
            if doc_id:
                action["_id"] = str(doc_id)
            actions.append(action)

        success, errors = await helpers.async_bulk(
            self.client,
            actions,
            stats_only=False,
            raise_on_error=False,
        )

        return {"success": success, "errors": errors}

    # ------------------------------------------------------------------
    # Aggregation helpers used by the API layer
    # ------------------------------------------------------------------

    async def events_per_day(self, days: int = 30) -> list[dict[str, Any]]:
        """Return daily event counts for the last *days* days."""
        body: dict[str, Any] = {
            "size": 0,
            "query": {
                "range": {
                    "timestamp": {
                        "gte": f"now-{days}d/d",
                        "lte": "now/d",
                    }
                }
            },
            "aggs": {
                "per_day": {
                    "date_histogram": {
                        "field": "timestamp",
                        "calendar_interval": "1d",
                        "min_doc_count": 0,
                        "extended_bounds": {
                            "min": f"now-{days}d/d",
                            "max": "now/d",
                        },
                    }
                }
            },
        }
        response = await self.client.search(index="qtown-events", body=body)
        buckets = response["aggregations"]["per_day"]["buckets"]
        return [{"date": b["key_as_string"], "count": b["doc_count"]} for b in buckets]

    async def resource_trends(
        self, resource: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Return price and volume trends for a given resource over the last *days* days."""
        body: dict[str, Any] = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"resource": resource}},
                        {"range": {"settled_at": {"gte": f"now-{days}d/d", "lte": "now/d"}}},
                    ]
                }
            },
            "aggs": {
                "per_day": {
                    "date_histogram": {
                        "field": "settled_at",
                        "calendar_interval": "1d",
                        "min_doc_count": 0,
                    },
                    "aggs": {
                        "avg_price": {"avg": {"field": "price"}},
                        "total_volume": {"sum": {"field": "quantity"}},
                        "max_price": {"max": {"field": "price"}},
                        "min_price": {"min": {"field": "price"}},
                    },
                }
            },
        }
        response = await self.client.search(index="qtown-transactions", body=body)
        buckets = response["aggregations"]["per_day"]["buckets"]
        return [
            {
                "date": b["key_as_string"],
                "avg_price": b["avg_price"]["value"],
                "max_price": b["max_price"]["value"],
                "min_price": b["min_price"]["value"],
                "total_volume": b["total_volume"]["value"],
                "trade_count": b["doc_count"],
            }
            for b in buckets
        ]

    async def economic_indicators(self) -> dict[str, Any]:
        """Return current economic indicators: gold supply, trade volume, GDP proxy."""
        gold_body: dict[str, Any] = {
            "size": 0,
            "query": {"term": {"resource": "gold"}},
            "aggs": {
                "total_volume": {"sum": {"field": "quantity"}},
                "avg_price": {"avg": {"field": "price"}},
                "trade_count": {"value_count": {"field": "trade_id"}},
            },
        }
        trade_body: dict[str, Any] = {
            "size": 0,
            "aggs": {
                "total_value": {
                    "sum": {
                        "script": {
                            "source": "doc['price'].value * doc['quantity'].value",
                            "lang": "painless",
                        }
                    }
                },
                "by_resource": {"terms": {"field": "resource", "size": 50}},
            },
        }

        gold_resp, trade_resp = await asyncio.gather(
            self.client.search(index="qtown-transactions", body=gold_body),
            self.client.search(index="qtown-transactions", body=trade_body),
        )

        gold_aggs = gold_resp["aggregations"]
        trade_aggs = trade_resp["aggregations"]

        return {
            "gold_supply": gold_aggs["total_volume"]["value"] or 0.0,
            "gold_avg_price": gold_aggs["avg_price"]["value"] or 0.0,
            "total_trade_volume": trade_aggs["total_value"]["value"] or 0.0,
            "trade_count": trade_resp["hits"]["total"]["value"],
            "top_resources": [
                {"resource": b["key"], "trade_count": b["doc_count"]}
                for b in trade_aggs["by_resource"]["buckets"]
            ],
            # GDP proxy: total value of all settled trades in the last 30 days
            "gdp_proxy_30d": trade_aggs["total_value"]["value"] or 0.0,
        }


import asyncio  # noqa: E402 — must come after class definition to avoid circular


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_client: ElasticsearchClient | None = None


def get_es_client() -> ElasticsearchClient:
    global _client
    if _client is None:
        _client = ElasticsearchClient()
    return _client
