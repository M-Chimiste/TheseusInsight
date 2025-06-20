"""
Prompts Module for Research Agent

Contains all prompt functions used by the LangGraph nodes for:
- Query planning and decomposition
- Evidence selection and sufficiency evaluation
- Context compression
- Answer generation with citations
"""

from typing import List, Optional


def planner_prompt(question: str, n: int = 5) -> str:
    """
    Generate prompt for query planning and decomposition.
    
    Args:
        question: The main research question
        n: Number of sub-queries to generate
        
    Returns:
        Formatted prompt for query planning
    """
    return f"""You are a research query planner. Your task is to break down a research question into {n} simple, diverse search queries that will find the maximum number of relevant papers.

RESEARCH QUESTION: {question}

Create {n} simple search queries that:
1. Use different core keywords from the main question
2. Are broad enough to capture many relevant papers
3. Cover different aspects or angles of the topic
4. Use simple, clear language that papers would likely contain
5. Avoid overly complex academic jargon

Guidelines for effective queries:
- Keep queries short and focused (3-8 words typically)
- Use common terminology that appears in paper titles and abstracts
- Include both broad and specific aspects
- Consider synonyms and related terms
- Think about how researchers would title papers on this topic

Examples for "What are the current trends in LLM Agents?":
- "LLM agents trends"
- "large language model agents"
- "AI agent architectures"
- "conversational AI systems"
- "autonomous language agents"

RESPONSE FORMAT:
Please respond with a JSON object containing:
- sub_queries: Array of {n} simple sub-query strings
- planning_rationale: Brief explanation of your query planning strategy
- estimated_difficulty: Assessment of research difficulty ("low", "medium", or "high")

Example format:
{{
  "sub_queries": [
    "LLM agents",
    "language model applications",
    "AI assistant systems"
  ],
  "planning_rationale": "I focused on using different core terms that would appear in relevant papers...",
  "estimated_difficulty": "medium"
}}

Generate your JSON response:"""


def evidence_selector_prompt(question: str, passages: List[str]) -> str:
    """
    Generate prompt for evidence selection and relevance evaluation.
    
    Args:
        question: The main research question
        passages: List of evidence passages to evaluate
        
    Returns:
        Formatted prompt for evidence evaluation
    """
    evidence_text = "\n\n---\n\n".join(passages)
    
    return f"""You are a research evidence evaluator. Your task is to assess the RELEVANCE of each piece of evidence to the research question and determine if we have sufficient coverage.

RESEARCH QUESTION: {question}

EVIDENCE TO EVALUATE:
{evidence_text}

Focus on RELEVANCE ASSESSMENT:

1. RELEVANCE EVALUATION:
   - How directly does each piece of evidence address the research question?
   - Which aspects of the question are well-covered by the evidence?
   - Which aspects need more evidence?
   - Rate relevance on a scale of 0.0 (not relevant) to 1.0 (highly relevant)

2. COVERAGE ASSESSMENT:
   - Is the evidence sufficient to provide a comprehensive answer?
   - Do we have enough diverse perspectives and sources?
   - Are there obvious gaps in coverage?

3. RECOMMENDATION:
   - Should we proceed with answer generation? (YES/NO)
   - Or should we search for additional evidence?
   - What specific areas need more research if any?

IMPORTANT: Assume all sources are from trusted academic databases and are high quality. 
Focus ONLY on relevance to the research question, not source quality.

RESPONSE FORMAT:
Please respond with a JSON object containing:
- evidence_assessments: Array of assessments for each piece of evidence
- sufficiency_assessment: Overall sufficiency evaluation
- selection_summary: Summary of your evaluation process

Example format:
{{
  "evidence_assessments": [
    {{
      "source_id": "source_1",
      "quality_score": 0.8,
      "relevance_score": 0.9,
      "key_findings": ["Finding 1", "Finding 2"],
      "include_in_synthesis": true
    }}
  ],
  "sufficiency_assessment": {{
    "is_sufficient": true,
    "coverage_score": 0.85,
    "well_covered_aspects": ["Aspect 1", "Aspect 2"],
    "missing_aspects": ["Aspect 3"],
    "confidence_level": "high",
    "recommendation": "proceed"
  }},
  "selection_summary": "The evidence provides good coverage of the main question..."
}}

Generate your JSON response:"""


def scratchpad_compress_prompt(
    research_question: str,
    evidence_pieces: List[str],
    target_tokens: int,
    preserve_citations: bool = True
) -> str:
    """
    Generate prompt for evidence compression.
    
    Args:
        research_question: The main research question
        evidence_pieces: List of evidence pieces to compress
        target_tokens: Target token count for compression
        preserve_citations: Whether to preserve citation information
        
    Returns:
        Formatted prompt for compression
    """
    evidence_text = "\n\n---\n\n".join(evidence_pieces)
    
    citation_instruction = """
IMPORTANT: Preserve all citation information including:
- Paper titles and authors
- URLs and source identifiers
- Relevance scores
- Source types (local/external)
""" if preserve_citations else ""
    
    return f"""You are a research content compressor. Your task is to compress the following evidence while preserving the most important information for answering the research question.

RESEARCH QUESTION: {research_question}

TARGET: Compress to approximately {target_tokens} tokens while maintaining all key information.

{citation_instruction}

EVIDENCE TO COMPRESS:
{evidence_text}

COMPRESSION GUIDELINES:
1. Preserve all key findings and conclusions
2. Maintain the logical flow of arguments
3. Keep essential details and data points
4. Preserve citation information and source attribution
5. Remove redundant information and verbose explanations
6. Focus on information directly relevant to the research question

RESPONSE FORMAT:
Please respond with a JSON object containing:
- compressed_content: The compressed evidence text
- compression_ratio: Actual compression ratio achieved (0.0-1.0)
- preserved_citations: Array of citation identifiers that were preserved
- key_points_preserved: Array of key points maintained in compression
- compression_notes: Notes about the compression process

Example format:
{{
  "compressed_content": "Compressed evidence maintaining key findings...",
  "compression_ratio": 0.3,
  "preserved_citations": ["source_1", "source_2"],
  "key_points_preserved": ["Key finding 1", "Key finding 2"],
  "compression_notes": "Focused on primary findings while preserving all citations..."
}}

Generate your JSON response:"""


def answer_instructions(
    current_date: str,
    research_topic: str,
    evidence_summaries: str,
    citation_style: str = "academic",
    include_methodology: bool = False,
    include_limitations: bool = False
) -> str:
    """
    Generate prompt for final answer generation.
    
    Args:
        current_date: Current date for the report
        research_topic: The research question/topic
        evidence_summaries: Compiled evidence text
        citation_style: Citation style to use
        include_methodology: Whether to include methodology section
        include_limitations: Whether to include limitations section
        
    Returns:
        Formatted prompt for answer generation
    """
    methodology_instruction = """
Include a brief methodology section explaining:
- How the research was conducted
- Search strategies used
- Evidence selection criteria
- Any limitations of the approach
""" if include_methodology else ""
    
    limitations_instruction = """
Include a limitations section that acknowledges:
- Scope limitations of the search
- Potential biases in source selection
- Temporal limitations of the evidence
- Recommendations for further research
""" if include_limitations else ""
    
    citation_format = {
        "academic": "Use numbered citations [1], [2], etc. with a reference list",
        "numbered": "Use numbered references throughout the text",
        "apa": "Use APA-style in-text citations and references"
    }.get(citation_style, "Use numbered citations [1], [2], etc.")
    
    return f"""You are a senior research analyst tasked with producing a comprehensive, analytical research report. Your goal is to create a deep, thoughtful analysis that goes beyond surface-level summaries.

RESEARCH QUESTION: {research_topic}

DATE: {current_date}

EVIDENCE BASE:
{evidence_summaries}

ANALYTICAL REQUIREMENTS:

1. **DEEP ANALYTICAL STRUCTURE**:
   - **Introduction**: Provide context, scope, and significance of the research question
   - **Thematic Analysis**: Organize findings into 3-4 major themes or trends with detailed exploration
   - **Critical Synthesis**: Analyze relationships, contradictions, and patterns across sources
   - **Implications & Future Directions**: Discuss broader impacts and emerging questions
   - **Conclusion**: Synthesize insights and provide clear answers to the research question

2. **ANALYTICAL DEPTH REQUIREMENTS**:
   - **CRITICAL**: Use ALL provided evidence sources - each source should contribute meaningfully to the analysis
   - **SYNTHESIS**: Don't just summarize - analyze patterns, contradictions, and connections between sources
   - **DEPTH**: Each paragraph should explore one specific theme/trend in detail (150-200 words minimum)
   - **EVIDENCE INTEGRATION**: Weave multiple sources together within paragraphs, showing relationships
   - **CRITICAL THINKING**: Identify gaps, limitations, conflicting findings, and areas needing further research
   - **IMPLICATIONS**: Discuss what findings mean for the field, practitioners, and future research

3. **WRITING EXCELLENCE**:
   - **Paragraph Structure**: Each paragraph = One major point + Multiple supporting sources + Analysis of implications
   - **Transitions**: Use clear topic sentences and logical flow between paragraphs
   - **Voice**: Analytical, authoritative, but accessible to educated readers
   - **Specificity**: Use specific examples, data points, and concrete findings from sources
   - **Avoid**: Generic phrases like "comprehensive analysis reveals" - be specific about what you found

4. **CITATION INTEGRATION**:
   - {citation_format}
   - **NATURAL INTEGRATION**: Citations should support specific claims, not be listed in clusters
   - **DIVERSE SOURCING**: Each paragraph should reference 3-5 different sources
   - **NO REPETITION**: Each citation number should appear only once in the analysis
   - **ALL SOURCES**: Every provided source must be meaningfully integrated into the analysis

{methodology_instruction}

{limitations_instruction}

**QUALITY STANDARDS**:
- Detailed Analysis section should be 800-1200 words minimum
- Each major theme/trend should be explored in 2-3 substantive paragraphs
- Clear, specific topic sentences that preview the analytical point
- Evidence from multiple sources integrated naturally within each analytical point
- Explicit discussion of implications, significance, and future directions

RESPONSE FORMAT:
Please respond with a JSON object containing:
- executive_summary: Concise 2-3 paragraph summary highlighting key insights and implications
- thematic_findings: Array of 3-4 major themes/trends identified, each with detailed explanation
- detailed_analysis: Comprehensive analytical discussion (800-1200 words) organized by themes with deep synthesis
- implications_analysis: Analysis of broader implications for the field and future research directions
- citations_used: Array of citation objects with id, title, url, source_type, relevance_score
- confidence_score: Your confidence in the answer quality (0.0-1.0)
- limitations: Array of limitations and recommendations for further research
- methodology_notes: Brief notes on research methodology

Example format:
{{
  "executive_summary": "This analysis of [topic] reveals three major trends that are reshaping the field... The implications suggest...",
  "thematic_findings": [
    {{
      "theme": "Technology Advancement Patterns",
      "description": "Detailed explanation of this theme with key insights",
      "supporting_evidence": ["Key evidence point 1", "Key evidence point 2"]
    }}
  ],
  "detailed_analysis": "### Technology Advancement Patterns\n\nThe emerging landscape of [topic] is characterized by several distinct technological advancement patterns. [Detailed analytical paragraph with multiple citations and synthesis]...\n\n### Application Domain Evolution\n\n[Second major theme with detailed analysis]...",
  "implications_analysis": "These findings have significant implications for... Future research should focus on...",
  "citations_used": [
    {{
      "id": "1",
      "title": "Title of Source",
      "url": "https://example.com",
      "source_type": "arxiv",
      "relevance_score": 0.9
    }}
  ],
  "confidence_score": 0.85,
  "limitations": [
    "Analysis limited to peer-reviewed sources",
    "Temporal scope may miss very recent developments"
  ],
  "methodology_notes": "Systematic thematic analysis with cross-source synthesis"
}}

Generate your JSON response:"""


def coverage_route_prompt(state_summary: str) -> str:
    """
    Generate prompt for coverage routing decisions.
    
    Args:
        state_summary: Summary of current research state
        
    Returns:
        Formatted prompt for routing decisions
    """
    return f"""You are a research workflow coordinator. Based on the current research state, determine the next appropriate action.

CURRENT STATE:
{state_summary}

ROUTING OPTIONS:
1. CONTINUE_RESEARCH - If evidence is insufficient and more research is needed
2. COMPRESS_EVIDENCE - If evidence is sufficient but exceeds token limits
3. GENERATE_ANSWER - If evidence is sufficient and within token limits

Consider:
- Quality and quantity of evidence gathered
- Coverage of the research question
- Token budget constraints
- Research loop count (avoid infinite loops)

Provide your routing decision with a brief explanation:

DECISION:"""


def query_refinement_prompt(
    original_question: str,
    previous_results: str,
    gaps_identified: str
) -> str:
    """
    Generate prompt for query refinement in subsequent research loops.
    
    Args:
        original_question: The original research question
        previous_results: Summary of previous search results
        gaps_identified: Identified gaps in coverage
        
    Returns:
        Formatted prompt for query refinement
    """
    return f"""You are a research query refiner. Based on previous search results and identified gaps, generate refined sub-queries for additional research.

ORIGINAL RESEARCH QUESTION: {original_question}

PREVIOUS RESULTS SUMMARY:
{previous_results}

IDENTIFIED GAPS:
{gaps_identified}

Generate 3-5 refined sub-queries that:
1. Target the identified gaps specifically
2. Use different terminology or approaches than previous queries
3. Focus on underexplored aspects of the research question
4. Are likely to find additional relevant sources

REFINED SUB-QUERIES:"""


 