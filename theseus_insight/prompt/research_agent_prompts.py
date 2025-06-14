from datetime import datetime
from  .prompting import prompt


def get_current_date():
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")


@prompt
def planner_prompt(question: str, n: int = 5):
    """Rewrite the user question into {{n}} diverse academic sub-queries."""
    pass


@prompt
def evidence_selector_prompt(question: str, passages: str):
    """Assess whether the passages answer the research question and return JSON with 'is_sufficient'."""
    pass


@prompt
def scratchpad_compress_prompt(max_tokens: int):
    """Compress the notes to fit within {{max_tokens}} tokens."""
    pass

@prompt
def query_refinement_instructions(current_date: str, research_question: str):
    """You are an expert research assistant helping to refine and clarify research questions for optimal academic literature search.

Your goal is to analyze the user's research question and determine if it needs clarification to conduct more effective research.

Instructions:
- Analyze the research question for ambiguity, scope, and specificity
- If the question is clear and well-scoped, mark as not needing clarification
- If the question could benefit from clarification, generate 2-4 focused questions that would help narrow the scope or clarify intent
- Consider asking about:
  * Specific time periods or recent developments
  * Particular methodologies or approaches of interest
  * Specific applications or domains
  * Depth of technical detail desired
  * Comparative aspects (vs. other methods)

Current date: {{current_date}}

Output Format:
- Format your response as a JSON object with these exact keys:
   - "needs_clarification": true or false
   - "clarifying_questions": List of 2-4 specific questions (empty list if no clarification needed)
   - "refined_query": If no clarification needed, provide a refined version of the original query
   - "original_query": The exact original query provided

Example 1 (needs clarification):
```json
{
    "needs_clarification": true,
    "clarifying_questions": [
        "Are you interested in recent developments (last 2-3 years) or a comprehensive historical overview?",
        "Do you want to focus on specific application domains (e.g., healthcare, autonomous systems, robotics)?",
        "Are you looking for technical implementation details or high-level conceptual understanding?"
    ],
    "refined_query": "",
    "original_query": "What are AI agents?"
}
```

Example 2 (clear query):
```json
{
    "needs_clarification": false,
    "clarifying_questions": [],
    "refined_query": "Recent advances in multi-agent reinforcement learning for autonomous vehicle coordination, including performance benchmarks and real-world applications",
    "original_query": "Recent advances in multi-agent reinforcement learning for autonomous vehicle coordination"
}
```

Research Question: {{research_question}}"""
    pass

@prompt
def query_writer_instructions(current_date: str, research_topic: str, number_queries: int):
    """Your goal is to generate sophisticated and diverse research queries for academic literature search. These queries will be used to search both local paper databases and external academic sources like ArXiv.

Instructions:
- Generate focused, academic search queries that use precise technical terminology
- Each query should be 3-8 words and target specific concepts, methods, or aspects
- Break down broad topics into specific, searchable components
- Use domain-specific keywords that researchers would use in paper titles and abstracts
- For broad topics, generate {{number_queries}} diverse queries covering different angles
- Prioritize recent research when relevant (current date: {{current_date}})
- Focus on technical terms, methodologies, and specific applications

Query Design Guidelines:
- Use academic terminology (e.g., "neural networks" not "AI", "optimization" not "improvement")
- Target specific methods, algorithms, or frameworks
- Include application domains when relevant
- Avoid conversational language or full sentences
- Make queries specific enough to find relevant research papers

Format: 
- Format your response as a JSON object with these exact keys:
   - "rationale": Brief explanation of the search strategy
   - "query": A list of focused search queries (max {{number_queries}})

Example:

Research Topic: Machine learning approaches for protein folding prediction
```json
{
    "rationale": "Breaking down protein folding prediction into specific ML approaches: deep learning methods, traditional algorithms, and performance evaluation to ensure comprehensive coverage of the research landscape.",
    "query": ["deep learning protein folding prediction", "AlphaFold transformer neural networks", "protein structure prediction algorithms"]
}
```

Research Topic: {{research_topic}}"""
    pass

@prompt
def reflection_instructions(current_date: str, research_topic: str, summaries: str):
    """You are an expert research assistant analyzing research summaries about "{{research_topic}}".

Instructions:
    - First, consider the nature of the user's original research topic: "{{research_topic}}".
    - If the topic implies the user wants YOU to create a survey, a comprehensive review, a comparative analysis, or a synthesized report, then your primary goal is to gather the necessary information to CONSTRUCT this output.
    - Identify knowledge gaps or areas that need deeper exploration.
    - If the user's goal (implied by "{{research_topic}}") is for you to create a synthesized output (like a survey or comparison):
        - A 'knowledge_gap' means you lack sufficient diverse primary information, specific details, different viewpoints, or supporting evidence from various sources TO CONSTRUCT the requested output yourself.
        - In this case, DO NOT identify the mere absence of a pre-existing survey or comparative document as your primary knowledge gap if you have enough raw material to create one. Your task is to build that synthesis.
    - If the user's goal seems to be finding a specific piece of information or a particular existing document, then a 'knowledge_gap' can be the absence of that specific item.
    - If there is a knowledge gap, generate follow-up queries that would help expand understanding or gather more material.
    - If your goal is to CONSTRUCT a survey/comparison based on "{{research_topic}}":
        - Your follow-up queries should aim to gather more raw materials, specific facts, different viewpoints, supporting details for various sections of your intended output, or methodologies to include.
        - For example, instead of asking for "a survey of X", your queries should be more targeted, like "case studies of X in Y context", "common methodologies for X", or "performance metrics for X".
    - If provided summaries are sufficient to answer the user's research question, don't generate follow-up queries.
    - Focus on technical details, methodological specifics, recent developments, or comparative analyses that weren't fully covered.
    - Ensure follow-up queries are academic and research-focused.

Requirements:
- Ensure the follow-up queries are self-contained and include necessary context for academic search.

Output Format:
- Format your response as a JSON object with these exact keys:
   - "is_sufficient": true or false
   - "knowledge_gap": Describe what information is missing or needs clarification
   - "follow_up_queries": Write specific research questions to address this gap

Example:
```json
{
    "is_sufficient": false,
    "knowledge_gap": "The summary lacks information about performance benchmarks and comparative evaluation metrics for different approaches",
    "follow_up_queries": ["performance evaluation metrics protein folding prediction methods", "benchmark datasets protein structure prediction comparison"]
}
```

Reflect carefully on the Research Summaries in light of the original research topic: '{{research_topic}}'. Identify true knowledge gaps (as defined above) that prevent you from fulfilling the user's request, and generate targeted follow-up queries to obtain the necessary information for YOU to complete the task. Then, produce your output following this JSON format:

Research Summaries:
{{summaries}}"""
    pass

@prompt
def answer_instructions(current_date: str, research_topic: str, summaries: str):
    """Generate a comprehensive research summary based on the provided literature summaries and sources.

Instructions:
- The current date is {{current_date}}.
- You are synthesizing research findings from multiple academic sources.
- Generate a well-structured research summary that addresses the user's research question.
- **Include all relevant citations and sources from the summaries using the exact short URL format provided (e.g., [source_1], [source_2])**
- **Important**: Use the short URL placeholders exactly as they appear in the summaries - do NOT convert them to full URLs or modify them
- Organize findings thematically and highlight key insights, methodologies, and conclusions.
- Maintain academic tone and precision.
- Identify any limitations or gaps in the current research landscape.
- End your response with a dedicated "## References" section that lists all sources used in your analysis
- In the References section, include the short URL placeholders which will be converted to clickable links

Research Context:
- {{research_topic}}

Literature Summaries:
{{summaries}}"""
    pass

@prompt
def relevance_rubric(research_topic: str, paper_context: str):
    """You are an expert research curator.  Judge how well a paper aligns with the following research query:
{{research_topic}}.

RUBRIC (apply to the paper)
1. **Topic Match**  
    • High - central focus is the research topic/s  
    • Partial - adjacent or supporting area  
    • Low - unrelated subject matter  

2. **Key Concepts & Terminology**  
    • High - uses core terms/concepts of the topic accurately  
    • Partial - occasional or tangential use  
    • Low - concepts absent or misused  

3. **Methodological Relevance**  
    • High - employs methods typical for research on the research topic/s  
    • Partial - uses partially relevant methods  
    • Low - methods irrelevant to the topic  

4. **Contribution / Novel Insight**  
    • High - offers new findings directly advancing the topic  
    • Partial - incremental or peripheral contribution  
    • Low - no meaningful contribution to the topic  

5. **Application / Use-Case Alignment**  
    • High - results clearly applicable within the topic's domain  
    • Partial - plausible but indirect application  
    • Low - no practical link to the topic  

SCORING RULES

• For each criterion assign: High = 2, Partial = 1, Low = 0.  
• Sum the scores (0 - 10).  
• **relevant** is *true* if total ≥ 6, else *false*.

Format your response as a JSON object with the following schema:
{
    "relevant": boolean,
    "score": 0-10,
    "rationale": string ≤ 80 words explaining key factors
}

Paper Context:
{{paper_context}}
"""
    pass

@prompt
def outline_instructions(
    research_topic: str,
    paper_context: str,
    historical_context: str,
    existing_outline: str | None = None,   # pass "" or None on the first call
):
    """
ROLE
----
You are an expert research assistant preparing a literature-review outline.

INPUTS
------
• Research Topic: {{research_topic}}
• Historical Context (landmark papers, paradigm shifts, etc.): {{historical_context}}
• Paper Context (abstract + any notes for the current paper): {{paper_context}}
• Existing Outline (markdown) - prior iterations, if any:
    {{existing_outline if existing_outline else "[none]"}}

TASK
----
1. **Integrate** the current paper into the outline, maintaining logical hierarchy.
2. **Expand** or **refine** sections where this paper adds new insight, methodology, or debate.
3. **Preserve numbering**:  
    * Top-level Roman numerals (I., II., …)  
    * Second level A., B., C.  
    * Third level 1., 2., 3.  
    * Fourth level a), b), c)
4. Keep headings ≤ 10 words; sub-bullets ≤ 15 words.
5. Do **not** delete existing content unless it is redundant; instead mark obsolete lines with ~~strikethrough~~.

OUTPUT
------
Return **only** the full, updated outline in GitHub-flavored Markdown.  
No extra commentary, metadata, or code fences.
    """
    pass
