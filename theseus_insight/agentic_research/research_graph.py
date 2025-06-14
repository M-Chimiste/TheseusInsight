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
    def _query_refinement(self, state: OverallState, config: RunnableConfig) -> Dict:
        question = get_research_topic(state.messages)
        result = {
            "needs_clarification": False,
            "clarifying_questions": [],
            "refined_query": question,
            "original_query": question,
        }
        state.needs_clarification = result["needs_clarification"]
        state.clarifying_questions = result["clarifying_questions"]
        return result

    # ------------------------------------------------------------------
    def _generate_query(self, state: OverallState, config: RunnableConfig) -> Dict:
        result = self._query_planner(state, config)
        queries = result.get("sub_queries", [])
        state.sub_queries = queries
        return {"query_list": [{"query": q} for q in queries]}

    # ------------------------------------------------------------------
    def _query_planner(self, state: OverallState, config: RunnableConfig) -> Dict:
        question = get_research_topic(state.messages)
        n = self.config.number_of_initial_queries
        try:
            llm = self.model_router.get_model("generate_query")
            prompt = planner_prompt(question=question, n=n)
            messages = [{"role": "user", "content": prompt}]
            result = llm.invoke(messages=messages, system_prompt="You are a helpful research assistant.")
            if hasattr(result, "content"):
                result = result.content
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
        return {
            "sub_queries": queries,
            "research_loop_count": state.research_loop_count,
        }

    # ------------------------------------------------------------------
    def _retriever_local(self, state: OverallState, config: RunnableConfig) -> Dict:
        limit = self.config.local_search_limit
        results = []
        for q in state.sub_queries:
            for paper in self.local_tool.search_local_only(q, limit=limit):
                url = paper.get("url") or f"paper_{paper.get('id')}"
                short = self._generate_short_url(url)
                results.append(
                    {
                        "short_url": short,
                        "title": paper.get("title", ""),
                        "abstract": paper.get("abstract", ""),
                        "url": url,
                        "source_type": "local",
                    }
                )
        state.sources_gathered.extend(results)
        return {
            "sources_gathered": results,
            "search_query": state.sub_queries,
            "web_research_result": [],
        }

    # ------------------------------------------------------------------
    def _retriever_external(self, state: OverallState, config: RunnableConfig) -> Dict:
        limit = self.config.external_search_limit
        results = []
        for q in state.sub_queries:
            for paper in self.external_tool.search_and_rank(q, limit=limit):
                url = paper.get("pdf_url") or paper.get("url", "")
                short = self._generate_short_url(url)
                results.append(
                    {
                        "short_url": short,
                        "title": paper.get("title", ""),
                        "abstract": paper.get("abstract", ""),
                        "url": url,
                        "source_type": "external",
                    }
                )
        state.sources_gathered.extend(results)
        return {
            "sources_gathered": results,
            "search_query": state.sub_queries,
            "web_research_result": [],
        }

    # ------------------------------------------------------------------
    def _local_research(self, state: OverallState, config: RunnableConfig) -> Dict:
        return self._retriever_local(state, config)

    # ------------------------------------------------------------------
    def _external_research(self, state: OverallState, config: RunnableConfig) -> Dict:
        return self._retriever_external(state, config)

    # ------------------------------------------------------------------
    def _merger(self, state: OverallState, config: RunnableConfig) -> Dict:
        unique = {}
        for src in state.sources_gathered:
            key = (src.get("title", "").lower(), src.get("url", ""))
            if key not in unique:
                unique[key] = src
        state.sources_gathered = list(unique.values())
        return {"sources_gathered": state.sources_gathered}

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
        state.judged_sources = top_k
        return {
            "judged_papers": top_k,
            "rejected_papers": [],
            "judged_sources": top_k,
        }

    # ------------------------------------------------------------------
    def _evidence_selector(self, state: OverallState, config: RunnableConfig) -> Dict:
        passages = []
        for src in state.judged_sources:
            snippet = f"{src['title']} ({src['short_url']})\n{src.get('abstract','')}"
            passages.append(snippet)
        summary_text = "\n\n".join(passages)
        llm = self.model_router.get_model("reflection")
        prompt = evidence_selector_prompt(
            question=get_research_topic(state.messages), passages=summary_text
        )
        try:
            messages = [{"role": "user", "content": prompt}]
            result = llm.invoke(messages=messages, system_prompt="You are a helpful research assistant analyzing evidence.")
            if hasattr(result, "content"):
                result = result.content
            data = json.loads(result)
            is_sufficient = bool(data.get("is_sufficient"))
        except Exception:
            is_sufficient = False
        state.evidence = passages
        state.is_sufficient = is_sufficient
        return {
            "research_loop_count": state.research_loop_count,
            "is_sufficient": is_sufficient,
        }

    # ------------------------------------------------------------------
    def _scratchpad_compress(self, state: OverallState, config: RunnableConfig) -> Dict:
        try:
            llm = self.model_router.get_model("reflection")
            text = "\n\n".join(state.evidence)
            prompt = (
                scratchpad_compress_prompt(
                    max_tokens=int(
                        self.config.max_research_context_tokens
                        * self.config.compress_to_ratio
                    )
                )
                + "\n"
                + text
            )
            messages = [{"role": "user", "content": prompt}]
            compressed = llm.invoke(messages=messages, system_prompt="You are a helpful assistant compressing notes.")
            if hasattr(compressed, "content"):
                compressed = compressed.content
            state.compressed_notes = compressed
            return {"compressed_notes": compressed}
        except Exception as e:
            logger.error("compression failed: %s", e)
            return {"compressed_notes": state.compressed_notes}

    # ------------------------------------------------------------------
    def _judge_all_papers(self, state: OverallState, config: RunnableConfig) -> Dict:
        merge_state = self._merger(state, config)
        state.sources_gathered = merge_state["sources_gathered"]
        rank_state = self._rerank(state, config)
        return rank_state

    # ------------------------------------------------------------------
    def _process_pdfs(self, state: OverallState, config: RunnableConfig) -> Dict:
        # Placeholder for backward compatibility
        return {"judged_sources": state.judged_sources}

    # ------------------------------------------------------------------
    def _compile_outline(self, state: OverallState, config: RunnableConfig) -> Dict:
        text = "\n\n".join(state.evidence)
        if count_tokens(text) > self.config.max_research_context_tokens:
            comp_state = self._scratchpad_compress(state, config)
            notes = comp_state.get("compressed_notes", "")
        else:
            notes = text
            state.compressed_notes = notes
        return {"outline": notes, "paper_contexts": state.evidence}

    # ------------------------------------------------------------------
    def _reflection(self, state: OverallState, config: RunnableConfig) -> Dict:
        sel = self._evidence_selector(state, config)
        state.research_loop_count += 1
        follow_up = []
        if not state.is_sufficient:
            plan = self._query_planner(state, config)
            follow_up = plan.get("sub_queries", [])
            state.sub_queries = follow_up
        state.follow_up_queries = follow_up
        return {
            "research_loop_count": state.research_loop_count,
            "is_sufficient": state.is_sufficient,
            "follow_up_queries": follow_up,
            "knowledge_gap": "",
        }

    # ------------------------------------------------------------------
    def _follow_up_research(self, state: OverallState, config: RunnableConfig) -> Dict:
        # Use the retrieval steps again with the new queries
        local = self._retriever_local(state, config)
        external = self._retriever_external(state, config)
        # Merge outputs
        combined = {
            "sources_gathered": local["sources_gathered"]
            + external["sources_gathered"],
            "search_query": state.sub_queries,
            "web_research_result": [],
        }
        return combined

    # ------------------------------------------------------------------
    def _answer_generator(self, state: OverallState, config: RunnableConfig) -> Dict:
        notes = state.compressed_notes or "\n\n".join(state.evidence)
        llm = self.model_router.get_model("finalize_answer")
        prompt = answer_instructions(
            current_date=get_current_date(),
            research_topic=get_research_topic(state.messages),
            summaries=notes,
        )
        messages = [{"role": "user", "content": prompt}]
        answer = llm.invoke(messages=messages, system_prompt="You are a helpful assistant generating a research summary.")
        if hasattr(answer, "content"):
            answer = answer.content
        state.messages.append(AIMessage(content=answer))
        return {
            "messages": state.messages,
            "sources_gathered": state.sources_gathered,
        }

    # ------------------------------------------------------------------
    def _reflection_route(self, state: OverallState) -> str:
        if (
            not state.is_sufficient
            and state.research_loop_count < self.config.max_research_loops
        ):
            return "follow_up_research"
        if (
            count_tokens("\n".join(state.evidence))
            > self.config.max_research_context_tokens
        ):
            return "compile_outline"
        return "finalize_answer"

    # ------------------------------------------------------------------
    def _build_graph(self) -> StateGraph:
        builder = StateGraph(OverallState, config_schema=AgentConfiguration)

        # Legacy node names for UI compatibility
        builder.add_node("query_refinement", self._query_refinement)
        builder.add_node("generate_query", self._generate_query)
        builder.add_node("local_research", self._local_research)
        builder.add_node("external_research", self._external_research)
        builder.add_node("judge_all_papers", self._judge_all_papers)
        builder.add_node("process_pdfs", self._process_pdfs)
        builder.add_node("compile_outline", self._compile_outline)
        builder.add_node("reflection", self._reflection)
        builder.add_node("follow_up_research", self._follow_up_research)
        builder.add_node("finalize_answer", self._answer_generator)

        builder.add_edge(START, "query_refinement")
        builder.add_conditional_edges(
            "query_refinement",
            lambda s: (
                END if getattr(s, "needs_clarification", False) else "generate_query"
            ),
            {END: END, "generate_query": "generate_query"},
        )

        builder.add_edge("generate_query", "local_research")
        builder.add_edge("generate_query", "external_research")
        builder.add_edge("local_research", "judge_all_papers")
        builder.add_edge("external_research", "judge_all_papers")
        builder.add_edge("judge_all_papers", "process_pdfs")
        builder.add_edge("process_pdfs", "reflection")

        builder.add_conditional_edges(
            "reflection",
            self._reflection_route,
            {
                "follow_up_research": "follow_up_research",
                "compile_outline": "compile_outline",
                "finalize_answer": "finalize_answer",
            },
        )

        builder.add_edge("compile_outline", "finalize_answer")
        builder.add_edge("follow_up_research", "judge_all_papers")
        builder.add_edge("finalize_answer", END)

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
