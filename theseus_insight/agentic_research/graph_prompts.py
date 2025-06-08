from datetime import datetime


def get_current_date():
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")


query_writer_instructions = """Your goal is to generate sophisticated and diverse research queries for academic literature search. These queries will be used to search both local paper databases and external academic sources.

Instructions:
- Always prefer a single search query, only add another query if the original question requests multiple aspects or elements and one query is not enough.
- Each query should focus on one specific aspect of the original research question.
- Don't produce more than {number_queries} queries.
- Queries should be diverse, if the topic is broad, generate more than 1 query.
- Don't generate multiple similar queries, 1 is enough.
- Query should ensure that the most current research is gathered. The current date is {current_date}.
- Focus on academic and technical terminology relevant to the research domain.

Format: 
- Format your response as a JSON object with ALL three of these exact keys:
   - "rationale": Brief explanation of why these queries are relevant
   - "query": A list of search queries

Example:

Research Topic: Machine learning approaches for protein folding prediction
```json
{{
    "rationale": "To comprehensively analyze machine learning approaches for protein folding prediction, we need to cover both traditional computational methods and recent deep learning advances. These queries target different aspects: foundational algorithms, state-of-the-art neural networks like AlphaFold, and comparative performance studies.",
    "query": ["machine learning protein folding prediction algorithms", "AlphaFold deep learning protein structure", "comparative analysis protein folding prediction methods"]
}}
```

Research Topic: {research_topic}"""


reflection_instructions = """You are an expert research assistant analyzing research summaries about "{research_topic}".

Instructions:
- Identify knowledge gaps or areas that need deeper exploration and generate follow-up queries (1 or multiple).
- If provided summaries are sufficient to answer the user's research question, don't generate follow-up queries.
- If there is a knowledge gap, generate follow-up queries that would help expand understanding.
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
{{
    "is_sufficient": false,
    "knowledge_gap": "The summary lacks information about performance benchmarks and comparative evaluation metrics for different approaches",
    "follow_up_queries": ["performance evaluation metrics protein folding prediction methods", "benchmark datasets protein structure prediction comparison"]
}}
```

Reflect carefully on the Research Summaries to identify knowledge gaps and produce follow-up queries. Then, produce your output following this JSON format:

Research Summaries:
{summaries}"""


answer_instructions = """Generate a comprehensive research summary based on the provided literature summaries and sources.

Instructions:
- The current date is {current_date}.
- You are synthesizing research findings from multiple academic sources.
- Generate a well-structured research summary that addresses the user's research question.
- Include all relevant citations and sources from the summaries.
- Organize findings thematically and highlight key insights, methodologies, and conclusions.
- Maintain academic tone and precision.
- Identify any limitations or gaps in the current research landscape.

Research Context:
- {research_topic}

Literature Summaries:
{summaries}""" 