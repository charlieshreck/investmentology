"""Tests for Qdrant semantic memory (memory/semantic.py).

Verifies:
1. _build_embedding_text() produces meaningful text
2. store_analysis_memory() sends a real vector (not None) to Qdrant
3. find_similar_situations() sends a vector query (not raw text)
4. Graceful fallback when sentence-transformers is unavailable
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from investmentology.memory.semantic import (
    EMBED_DIM,
    _build_embedding_text,
    _compute_embedding,
    find_similar_situations,
    store_analysis_memory,
)


# ---------------------------------------------------------------------------
# _build_embedding_text tests
# ---------------------------------------------------------------------------

class TestBuildEmbeddingText:
    def test_basic_fields(self):
        text = _build_embedding_text(
            ticker="AAPL", verdict="BUY", reasoning="Strong moat",
            position_type="long", thesis_health="healthy",
            market_context=None, agent_stances=None,
        )
        assert "AAPL" in text
        assert "BUY" in text
        assert "Strong moat" in text
        assert "long" in text
        assert "healthy" in text

    def test_none_optional_fields(self):
        text = _build_embedding_text(
            ticker="TSLA", verdict="HOLD", reasoning="Uncertain outlook",
            position_type=None, thesis_health=None,
            market_context=None, agent_stances=None,
        )
        assert "none" in text
        assert "unknown" in text

    def test_market_context_included(self):
        text = _build_embedding_text(
            ticker="MSFT", verdict="BUY", reasoning="Cloud growth",
            position_type="long", thesis_health="strong",
            market_context={"vix": 18.5, "spy_price": 520.0},
            agent_stances=None,
        )
        assert "VIX: 18.5" in text
        assert "SPY: 520.0" in text

    def test_agent_stances_included(self):
        stances = [
            {"name": "Warren", "sentiment": 0.8},
            {"name": "Simons", "sentiment": -0.5},
            {"name": "Soros", "sentiment": 0.0},
        ]
        text = _build_embedding_text(
            ticker="GOOG", verdict="BUY", reasoning="AI leadership",
            position_type="long", thesis_health="healthy",
            market_context=None, agent_stances=stances,
        )
        assert "Warren=bullish" in text
        assert "Simons=bearish" in text
        assert "Soros=neutral" in text

    def test_reasoning_truncated(self):
        long_reasoning = "x" * 1000
        text = _build_embedding_text(
            ticker="X", verdict="SELL", reasoning=long_reasoning,
            position_type=None, thesis_health=None,
            market_context=None, agent_stances=None,
        )
        # Reasoning should be truncated to 500 chars
        reasoning_part = text.split("Reasoning: ")[1]
        assert len(reasoning_part) == 500

    def test_returns_nonempty_string(self):
        text = _build_embedding_text(
            ticker="A", verdict="V", reasoning="R",
            position_type=None, thesis_health=None,
            market_context=None, agent_stances=None,
        )
        assert isinstance(text, str)
        assert len(text) > 10


# ---------------------------------------------------------------------------
# _compute_embedding tests
# ---------------------------------------------------------------------------

class TestComputeEmbedding:
    def test_returns_list_of_floats(self):
        """When model is available, embedding should be a list of 768 floats."""
        fake_embedding = np.random.randn(EMBED_DIM).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embedding

        with patch("investmentology.memory.semantic._get_embed_model", return_value=mock_model):
            result = _compute_embedding("test text")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == EMBED_DIM
        assert all(isinstance(v, float) for v in result)

    def test_returns_none_when_model_unavailable(self):
        with patch("investmentology.memory.semantic._get_embed_model", return_value=None):
            result = _compute_embedding("test text")
        assert result is None

    def test_passes_search_document_prefix(self):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros(EMBED_DIM, dtype=np.float32)

        with patch("investmentology.memory.semantic._get_embed_model", return_value=mock_model):
            _compute_embedding("my text here")

        call_args = mock_model.encode.call_args
        assert call_args[0][0].startswith("search_document: ")


# ---------------------------------------------------------------------------
# store_analysis_memory tests
# ---------------------------------------------------------------------------

class TestStoreAnalysisMemory:
    @pytest.mark.asyncio
    async def test_sends_real_vector_not_none(self):
        """The upsert payload must contain a real vector, never None."""
        fake_vector = [0.1] * EMBED_DIM

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("investmentology.memory.semantic._compute_embedding", return_value=fake_vector),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await store_analysis_memory(
                ticker="AAPL", verdict="BUY", confidence=0.85,
                reasoning="Strong fundamentals and growing services revenue",
            )

        assert result is True
        # Inspect the JSON payload sent to Qdrant
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        point = body["points"][0]

        assert point["vector"] is not None
        assert isinstance(point["vector"], list)
        assert len(point["vector"]) == EMBED_DIM
        assert point["payload"]["ticker"] == "AAPL"
        assert point["payload"]["verdict"] == "BUY"

    @pytest.mark.asyncio
    async def test_returns_false_when_no_model(self):
        """Should return False and not call Qdrant if embedding model is unavailable."""
        with patch("investmentology.memory.semantic._compute_embedding", return_value=None):
            result = await store_analysis_memory(
                ticker="AAPL", verdict="BUY", confidence=0.85,
                reasoning="test",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_qdrant_error(self):
        """Should return False if Qdrant returns non-200."""
        fake_vector = [0.1] * EMBED_DIM

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("investmentology.memory.semantic._compute_embedding", return_value=fake_vector),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result = await store_analysis_memory(
                ticker="AAPL", verdict="BUY", confidence=0.85,
                reasoning="test",
            )
        assert result is False


# ---------------------------------------------------------------------------
# find_similar_situations tests
# ---------------------------------------------------------------------------

class TestFindSimilarSituations:
    @pytest.mark.asyncio
    async def test_sends_vector_query_not_text(self):
        """Search must send a real vector, not raw text."""
        fake_vector = np.random.randn(EMBED_DIM).astype(np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vector

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("investmentology.memory.semantic._get_embed_model", return_value=mock_model),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            await find_similar_situations(
                ticker="AAPL", verdict="BUY", reasoning="Strong fundamentals",
            )

        # Verify the search payload uses "vector" (list of floats), not "query" (text)
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

        assert "vector" in body
        assert "query" not in body
        assert isinstance(body["vector"], list)
        assert len(body["vector"]) == EMBED_DIM

    @pytest.mark.asyncio
    async def test_uses_search_query_prefix(self):
        """Search should use search_query: prefix (not search_document:)."""
        fake_vector = np.zeros(EMBED_DIM, dtype=np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vector

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("investmentology.memory.semantic._get_embed_model", return_value=mock_model),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            await find_similar_situations(
                ticker="AAPL", verdict="BUY", reasoning="test",
            )

        encode_arg = mock_model.encode.call_args[0][0]
        assert encode_arg.startswith("search_query: ")

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_model(self):
        with patch("investmentology.memory.semantic._get_embed_model", return_value=None):
            results = await find_similar_situations(
                ticker="AAPL", verdict="BUY", reasoning="test",
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_parses_qdrant_results(self):
        """Should parse Qdrant search results into SimilarSituation objects."""
        fake_vector = np.zeros(EMBED_DIM, dtype=np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_vector

        qdrant_result = {
            "result": [
                {
                    "score": 0.92,
                    "payload": {
                        "ticker": "MSFT",
                        "verdict": "BUY",
                        "position_type": "long",
                        "thesis_health": "strong",
                        "market_snapshot": {"regime": "bull"},
                        "confidence": 0.88,
                        "reasoning": "Cloud dominance continues",
                        "outcome": "profitable",
                        "timestamp": "2024-06-15T10:00:00",
                    },
                },
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = qdrant_result

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("investmentology.memory.semantic._get_embed_model", return_value=mock_model),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            results = await find_similar_situations(
                ticker="AAPL", verdict="BUY", reasoning="test",
            )

        assert len(results) == 1
        assert results[0].ticker == "MSFT"
        assert results[0].verdict == "BUY"
        assert results[0].similarity_score == 0.92
        assert results[0].outcome == "profitable"
        assert results[0].market_regime == "bull"
