"""Simplified LangGraph workflow for the Theseus Insight research agent."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

from .graph_configuration import AgentConfiguration
from .graph_state import OverallState
from .local_search import LocalSearchTool
from .external_search import ExternalSearchTool
from .unified_model_router import load_unified_router, UnifiedModelRouter
from .graph_utils import get_research_topic
from ..utils.common_utils import cosine_similarity
from ..prompt.research_agent_prompts import (
    planner_prompt,
    evidence_selector_prompt,
    scratchpad_compress_prompt,
    answer_instructions,
    get_current_date,
)
from ..data_model.data_handling import PaperDatabase
from ..inference.llm import SentenceTransformerInference

logger = logging.getLogger(__name__)

MAX_TOKENS = 15000


def count_tokens(text: str) -> int:
    """Very small utility for approximate token counting."""
    import tiktoken

    if not text:
        return 0

    try:
        enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def coverage_route(state: OverallState) -> str:
    """Routing logic after evidence selection."""
    if not state.is_sufficient:
        return "query_planner"
    if count_tokens("\n".join(state.evidence)) > MAX_TOKENS:
        return "scratchpad_compress"
    return "answer_generator"


class ResearchAgent:
    """Retrieval-centric research agent built with LangGraph."""

    def __init__(
        self,
        db: PaperDatabase,
        embedding_model: SentenceTransformerInference,
        config: Optional[AgentConfiguration] = None,
    ) -> None:
        self.db = db
        self.embedding_model = embedding_model
        self.config = config or AgentConfiguration()

        self.local_tool = LocalSearchTool(
            db=db,
            embedding_model=embedding_model,
            semantic_weight=self.config.semantic_weight,
            keyword_weight=self.config.keyword_weight,
            similarity_threshold=self.config.similarity_threshold,
            enable_pdf_download=self.config.enable_pdf_download,
        )
        self.external_tool = ExternalSearchTool(
            enable_pdf_download=self.config.enable_pdf_download
        )
        self.model_router = load_unified_router(db)
        self.graph = self._build_graph()
        self._source_counter = 0
        self._url_mapping: Dict[str, str] = {}

    # ------------------------------------------------------------------
    def _generate_short_url(self, original_url: str) -> str:
        self._source_counter += 1
        short = f"[source_{self._source_counter}]"
        self._url_mapping[short] = original_url
        return short

    # ------------------------------------------------------------------
    def _query_planner(self, state: OverallState, config: RunnableConfig) -> Dict:
        question = get_research_topic(state.messages)
        n = self.config.number_of_initial_queries
        try:
            llm = self.model_router.get_model("generate_query")
            prompt = planner_prompt(question=question, n=n)
            result = llm.invoke(prompt)
            queries = []
            try:
                data = json.loads(result)
                if isinstance(data, list):
                    queries = [str(q) for q in data if q]
            except Exception:
                queries = [q.strip() for q in result.split("\n") if q.strip()]
            if not queries:
                queries = [question]
        except Exception as e:  # pragma: no cover - llm failure
            logger.error("planner failed: %s", e)
            queries = [question]
        return {"sub_queries": queries, "research_loop_count": state.research_loop_count}

    # ------------------------------------------------------------------
    def _retriever_local(self, state: OverallState, config: RunnableConfig) -> Dict:
        limit = self.config.local_search_limit
        results = []
        for q in state.sub_queries:
            for paper in self.local_tool.search_local_only(q, limit=limit):
                url = paper.get("url") or f"paper_{paper.get('id')}"
                short = self._generate_short_url(url)
                results.append({
                    "short_url": short,
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract", ""),
                    "url": url,
                    "source_type": "local",
                })
        return {"sources_gathered": state.sources_gathered + results}

    # ------------------------------------------------------------------
    def _retriever_external(self, state: OverallState, config: RunnableConfig) -> Dict:
        limit = self.config.external_search_limit
        results = []
        for q in state.sub_queries:
            for paper in self.external_tool.search_and_rank(q, limit=limit):
                url = paper.get("pdf_url") or paper.get("url", "")
                short = self._generate_short_url(url)
                results.append({
                    "short_url": short,
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract", ""),
                    "url": url,
                    "source_type": "external",
                })
        return {"sources_gathered": state.sources_gathered + results}

    # ------------------------------------------------------------------
    def _merger(self, state: OverallState, config: RunnableConfig) -> Dict:
        unique = {}
        for src in state.sources_gathered:
            key = (src.get("title", "").lower(), src.get("url", ""))
            if key not in unique:
                unique[key] = src
        return {"sources_gathered": list(unique.values())}

    # ------------------------------------------------------------------
    def _rerank(self, state: OverallState, config: RunnableConfig) -> Dict:
        question = get_research_topic(state.messages)
        q_emb = self.embedding_model.invoke(question, to_list=True)
        scored = []
        for src in state.sources_gathered:
            text = src.get("title", "") + " " + src.get("abstract", "")
            d_emb = self.embedding_model.invoke(text, to_list=True)
            score = cosine_similarity(q_emb, d_emb)
            src["score"] = float(score)
            scored.append(src)
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_k = scored[: self.config.initial_rerank_top_k]
        return {"judged_sources": top_k}

    # ------------------------------------------------------------------
    def _evidence_selector(self, state: OverallState, config: RunnableConfig) -> Dict:
        passages = []
        for src in state.judged_sources:
            snippet = f"{src['title']} ({src['short_url']})\n{src.get('abstract','')}"
            passages.append(snippet)
        summary_text = "\n\n".join(passages)
        llm = self.model_router.get_model("reflection")
        prompt = evidence_selector_prompt(question=get_research_topic(state.messages), passages=summary_text)
        try:
            result = llm.invoke(prompt)
            data = json.loads(result)
            is_sufficient = bool(data.get("is_sufficient"))
        except Exception:
            is_sufficient = False
        return {"evidence": passages, "is_sufficient": is_sufficient}

    # ------------------------------------------------------------------
    def _scratchpad_compress(self, state: OverallState, config: RunnableConfig) -> Dict:
        try:
            llm = self.model_router.get_model("reflection")
            text = "\n\n".join(state.evidence)
            prompt = scratchpad_compress_prompt(max_tokens=int(self.config.max_research_context_tokens * self.config.compress_to_ratio)) + "\n" + text
            compressed = llm.invoke(prompt)
            return {"compressed_notes": compressed}
        except Exception as e:
            logger.error("compression failed: %s", e)
            return {"compressed_notes": state.compressed_notes}

    # ------------------------------------------------------------------
    def _answer_generator(self, state: OverallState, config: RunnableConfig) -> Dict:
        notes = state.compressed_notes or "\n\n".join(state.evidence)
        llm = self.model_router.get_model("finalize_answer")
        prompt = answer_instructions(
            current_date=get_current_date(),
            research_topic=get_research_topic(state.messages),
            summaries=notes,
        )
        answer = llm.invoke(prompt)
        state.messages.append(AIMessage(content=answer))
        return {"messages": state.messages}

    # ------------------------------------------------------------------
    def _build_graph(self) -> StateGraph:
        builder = StateGraph(OverallState, config_schema=AgentConfiguration)
        builder.add_node("query_planner", self._query_planner)
        builder.add_node("retriever_local", self._retriever_local)
        builder.add_node("retriever_external", self._retriever_external)
        builder.add_node("merger", self._merger)
        builder.add_node("rerank", self._rerank)
        builder.add_node("evidence_selector", self._evidence_selector)
        builder.add_node("scratchpad_compress", self._scratchpad_compress)
        builder.add_node("answer_generator", self._answer_generator)

        builder.set_entry_point("query_planner")
        builder.add_edge("query_planner", "retriever_local")
        builder.add_edge("query_planner", "retriever_external")
        builder.add_edge("retriever_local", "merger")
        builder.add_edge("retriever_external", "merger")
        builder.add_edge("merger", "rerank")
        builder.add_edge("rerank", "evidence_selector")
        builder.add_conditional_edges(
            "evidence_selector",
            coverage_route,
            {"query_planner": "query_planner", "scratchpad_compress": "scratchpad_compress", "answer_generator": "answer_generator"},
        )
        builder.add_edge("scratchpad_compress", "answer_generator")
        builder.add_edge("answer_generator", END)
        return builder.compile()

    # ------------------------------------------------------------------
    async def arun(
        self,
        research_question: str,
        config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[BaseMessage]] = None,
    ) -> Dict[str, Any]:
        messages = conversation_history or []
        messages.append(HumanMessage(content=research_question))
        initial_state = OverallState(messages=messages)
        result = await self.graph.ainvoke(initial_state, config=config)
        return result

    def run(
        self,
        research_question: str,
        config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[BaseMessage]] = None,
    ) -> Dict[str, Any]:
        messages = conversation_history or []
        messages.append(HumanMessage(content=research_question))
        initial_state = OverallState(messages=messages)
        result = self.graph.invoke(initial_state, config=config)
        return result

    async def astream(
        self,
        research_question: str,
        config: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[BaseMessage]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        messages = conversation_history or []
        messages.append(HumanMessage(content=research_question))
        initial_state = OverallState(messages=messages)
        async for output in self.graph.astream(initial_state, config=config):
            yield output


# ------------------------------------------------------------------------------

def create_research_agent(
    db: PaperDatabase,
    embedding_model: Optional[SentenceTransformerInference] = None,
    config: Optional[AgentConfiguration] = None,
) -> ResearchAgent:
    if embedding_model is None:
        embedding_model = SentenceTransformerInference()
    return ResearchAgent(db=db, embedding_model=embedding_model, config=config)
