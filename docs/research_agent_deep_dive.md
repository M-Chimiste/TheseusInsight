# Research Agent Deep Dive

## Overview

The Theseus Insight Research Agent is an advanced LangGraph-based system that performs comprehensive literature reviews by intelligently combining local database search with external source expansion. The agent provides real-time progress streaming, smart paper filtering, iterative research outline generation, and full-text PDF processing.

## Table of Contents
- [Architecture](#architecture)
- [Core Features](#core-features)
- [Research Workflow](#research-workflow)
- [Progress Tracking](#progress-tracking)
- [Effort System](#effort-system)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Usage Examples](#usage-examples)
- [Technical Implementation](#technical-implementation)
- [Troubleshooting](#troubleshooting)

---

## Architecture

The Research Agent is built on **LangGraph**, a state machine framework that orchestrates complex multi-step research workflows. The system consists of several interconnected nodes that handle different aspects of the research process:

```
Query Refinement → Query Generation → Local Research → Judge Papers → 
Compile Outline → Reflection → External Research (if needed) → Finalize Answer
```

### Key Components

- **Query Refinement**: Analyzes research questions for clarity and asks clarifying questions when needed
- **Query Generation**: Creates multiple search queries to comprehensively explore the research topic
- **Local Research**: Searches the local paper database with hybrid semantic/keyword search
- **Judge Papers**: Uses LLM-powered relevance filtering to evaluate papers before PDF processing
- **Compile Outline**: Builds and refines research outlines iteratively as new papers are discovered
- **External Research**: Expands search to external sources (ArXiv) when local sources are insufficient
- **Reflection**: Evaluates research completeness and determines next steps
- **Finalize Answer**: Generates comprehensive markdown reports with proper citations

---

## Core Features

### 🔍 Smart Paper Filtering (Judge Papers Step)

The research agent now includes an intelligent paper filtering system that evaluates paper relevance before expensive PDF processing:

**How It Works:**
- Uses a specialized LLM judge model to evaluate each paper
- Analyzes title, abstract, authors, and year against research topic
- Applies a 5-criterion relevance rubric:
  - Topic Match (0-10)
  - Key Concepts (0-10) 
  - Methodological Relevance (0-10)
  - Contribution (0-10)
  - Use-Case Alignment (0-10)
- Only papers scoring 6+ proceed to PDF download

**Benefits:**
- **Efficiency**: Reduces unnecessary PDF downloads by 40-60%
- **Quality**: Ensures only relevant papers consume processing resources
- **Transparency**: Shows exactly which papers passed/failed filtering
- **Cost Savings**: Reduces API calls and bandwidth usage

### 📋 Iterative Research Outline Generation

The agent builds structured research outlines that evolve as new papers are discovered:

**Features:**
- **Dynamic Updates**: Outline grows and refines with each research iteration
- **Hierarchical Structure**: Organized sections and subsections
- **Context Integration**: Incorporates findings from high-relevance papers
- **Historical Awareness**: Tracks important papers and their contributions

**Example Outline Evolution:**
```markdown
# Research Outline: Transformer Attention Mechanisms

## I. Introduction
- Definition of attention mechanisms
- Historical context

## II. Core Transformer Architecture  
- Self-attention mechanisms
- Multi-head attention
- Position encoding

## III. Recent Advances
- Sparse attention patterns
- Efficient attention algorithms
- Linear attention approaches

## IV. Applications and Performance
- Natural language processing
- Computer vision applications
- Comparative analysis

## V. Future Directions
- Scalability improvements
- Novel attention designs
```

### 📄 Full-Text PDF Processing

Advanced PDF processing pipeline with multiple fallback strategies:

**Processing Pipeline:**
1. **URL Validation**: Checks if source has accessible PDF URL
2. **Download**: Robust download with proper headers and timeout handling
3. **Format Validation**: Verifies downloaded file is valid PDF
4. **Text Extraction**: Uses SpacyLayoutDocProcessor with figure/table handling
5. **Intelligent Chunking**: FlatMarkdownParser creates semantically meaningful chunks
6. **Relevance Filtering**: Selects most relevant chunks based on research query
7. **Database Storage**: Updates local database with full text for future searches

**Supported Sources:**
- Local database papers with PDF URLs
- ArXiv papers (automatic PDF URL conversion)
- External academic papers with direct PDF links
- Local file uploads

### ⚡ Real-Time Progress Tracking

Comprehensive progress visibility with sentence-case status names:

**Status Transformations:**
| Technical Name | User-Friendly Display | Icon |
|---|---|---|
| `query_refinement` | "Query refinement" | 🔍 |
| `generate_query` | "Query generation" | 🔍 |
| `local_research` | "Local search" | 🔬 |
| `judge_papers` | "Judging paper relevance" | 🧠 |
| `compile_outline` | "Compiling research outline" | 📋 |
| `external_research` | "External search" | 🔬 |
| `reflection` | "Reflection" | 💭 |
| `finalize_answer` | "Finalizing answer" | ✅ |

**Enhanced Progress Messages:**
- **Local Search**: "Local search: 10 papers found, 5 PDFs processed, 4 with full text"
- **Paper Judging**: "Judging paper relevance: 8 relevant, 3 rejected (total: 11)"
- **Outline Compilation**: "Compiling research outline from 8 relevant papers"
- **External Search**: "External search: 6 papers found (downloaded 3 PDFs)"

### 🎛️ Additive Effort Control

Intelligent effort system that enhances your base configuration rather than overriding it:

**Effort Levels:**
- **Default** (+0 papers, +0 loops): Uses exact base configuration
- **Moderate** (+2 papers, +2 loops): Light research enhancement
- **Medium** (+5 papers, +5 loops): Standard research boost
- **High** (+10 papers, +10 loops): Maximum thoroughness

**How It Works:**
```python
# Base Configuration (from Settings)
base_local_search_limit = 10
base_external_search_limit = 5  
base_max_research_loops = 10

# User selects "Medium" (+5 papers, +5 loops)
papers_bonus = 5
loops_bonus = 5

# Final Configuration (Additive)
final_local_limit = 10 + (5 * 2/3) = 13  # 67% to local
final_external_limit = 5 + (5 * 1/3) = 6  # 33% to external  
final_max_loops = 10 + 5 = 15
```

---

## Research Workflow

### Phase 1: Query Analysis and Generation
1. **Query Refinement**: Analyzes research question clarity
2. **Clarification Requests**: Asks follow-up questions if needed
3. **Query Generation**: Creates 3-5 focused search queries
4. **Query Optimization**: Balances broad coverage with specificity

### Phase 2: Local Knowledge Discovery
1. **Hybrid Search**: Combines semantic similarity with keyword matching
2. **Paper Collection**: Gathers initial paper set from local database
3. **Relevance Judging**: LLM evaluates each paper against research topic
4. **PDF Processing**: Downloads and processes full text for relevant papers

### Phase 3: Knowledge Organization
1. **Outline Compilation**: Creates structured research framework
2. **Context Integration**: Incorporates findings from processed papers
3. **Gap Identification**: Identifies areas needing additional research

### Phase 4: External Expansion (If Needed)
1. **Reflection Analysis**: Determines if local sources are sufficient
2. **External Search**: Queries ArXiv and other external sources
3. **Sequential Processing**: Respectful API usage with rate limiting
4. **Additional PDF Processing**: Downloads external papers when available

### Phase 5: Synthesis and Reporting
1. **Final Reflection**: Comprehensive analysis of all gathered sources
2. **Report Generation**: Creates structured markdown report
3. **Citation Processing**: Converts short URLs to numbered hyperlinks
4. **Reference Section**: Automatically generates formatted bibliography

---

## Progress Tracking

### Real-Time WebSocket Updates

The research agent streams progress updates via WebSocket connection, providing users with transparent visibility into the research process:

```javascript
// WebSocket connection for task progress
const ws = new WebSocket(`ws://localhost:8000/ws/research-agent/${taskId}`);

ws.onmessage = (event) => {
  const status = JSON.parse(event.data);
  
  // Example status object:
  {
    "overallStatus": "processing",
    "currentStep": "judge_papers", 
    "message": "Judging paper relevance: 8 relevant, 3 rejected (total: 11)",
    "progress": 45
  }
};
```

### Activity Timeline

Each research session generates a detailed activity timeline showing:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "step": "judge_papers",
  "action": "Evaluated 11 papers for relevance - 8 passed, 3 filtered out",
  "data": {
    "papers_evaluated": 11,
    "relevant_papers": 8,
    "rejected_papers": 3
  }
}
```

### Progress Indicators

**Visual Progress Bar**: Shows overall research completion (0-100%)

**Step-by-Step Tracking**: 
- Query Generation (15%)
- Local Research (40%)
- Paper Judging (45%)
- Outline Compilation (48%)
- External Research (70%)
- Reflection (75-85%)
- Final Report (90-100%)

---

## Effort System

### Configuration Philosophy

The effort system is designed to be **additive** rather than **absolute**, respecting your carefully configured base settings while allowing temporary research intensity boosts.

### Base Configuration (Settings)

Configure your preferred research parameters in Settings → Research Agent:

```json
{
  "max_research_loops": 10,
  "local_search_limit": 10,
  "external_search_limit": 5,
  "initial_search_query_count": 3
}
```

### Effort Multipliers

| Effort Level | Papers Bonus | Loops Bonus | Use Case |
|---|---|---|---|
| **Default** | +0 | +0 | Quick research with base settings |
| **Moderate** | +2 | +2 | Slightly more thorough investigation |
| **Medium** | +5 | +5 | Standard enhanced research |
| **High** | +10 | +10 | Comprehensive deep dive |

### Paper Distribution Algorithm

When paper bonuses are applied, they're intelligently distributed:

- **67% to Local Search**: Prioritizes your curated database
- **33% to External Search**: Supplements with fresh external sources

**Example**: Medium effort (+5 papers) with base local_limit=10, external_limit=5
- Local gets: 10 + (5 × 2/3) = 10 + 3 = 13 papers
- External gets: 5 + (5 × 1/3) = 5 + 1 = 6 papers

---

## Configuration

### Model Configuration

The research agent supports fine-grained model configuration for different tasks:

```json
{
  "reasoning_model": {
    "model_name": "gemini-2.0-flash",
    "model_type": "gemini", 
    "max_new_tokens": 4096,
    "temperature": 0.1
  },
  "judge_model": {
    "model_name": "claude-3-haiku",
    "model_type": "anthropic",
    "max_new_tokens": 1024,
    "temperature": 0.0
  },
  "query_generator_model": null,  // Defaults to reasoning_model
  "reflection_model": null,       // Defaults to reasoning_model
  "answer_model": null           // Defaults to reasoning_model
}
```

### Research Parameters

```json
{
  "max_research_loops": 10,
  "initial_search_query_count": 3,
  "local_search_limit": 10,
  "external_search_limit": 5,
  "external_search_delay": 2.0,
  "search_config": {
    "semantic_weight": 0.6,
    "keyword_weight": 0.4,
    "similarity_threshold": 0.3,
    "enable_pdf_download": true
  }
}
```

### PDF Processing Settings

```json
{
  "enable_pdf_download": true,
  "pdf_processing_timeout": 60,
  "max_pdf_size_mb": 50,
  "chunk_size_tokens": 8000,
  "max_chunks_per_paper": 10
}
```

---

## API Reference

### Start Research Session

**POST** `/api/research-agent/run`

```json
{
  "research_question": "What are the latest advances in transformer attention mechanisms?",
  "papers_bonus": 5,
  "loops_bonus": 5,
  "conversation_history": [
    {
      "role": "user",
      "content": "Previous research question..."
    }
  ]
}
```

**Response:**
```json
{
  "task_id": "uuid-task-identifier",
  "message": "Research agent task started..."
}
```

### Get Research Results

**GET** `/api/research-agent/reviews/{review_id}`

**Response:**
```json
{
  "id": 123,
  "research_question": "transformer attention mechanisms",
  "report_text": "# Research Report\n\n## Introduction...",
  "summaries": [...],
  "activity_log": [...],
  "created_ts": "2024-01-15T10:00:00Z",
  "total_papers": 15
}
```

### Search Research Library

**POST** `/api/research-agent/library/search`

```json
{
  "query": "attention mechanisms",
  "page": 1,
  "page_size": 20,
  "from_date": "2024-01-01",
  "to_date": "2024-12-31"
}
```

### Model Configuration

**GET** `/api/research-agent/model-config`

Returns current model configuration.

**PUT** `/api/research-agent/model-config`

Updates model configuration with new settings.

---

## Usage Examples

### Basic Research Query

```python
import requests

# Start research
response = requests.post("http://localhost:8000/api/research-agent/run", json={
    "research_question": "What are the security implications of large language models?",
    "papers_bonus": 3,  # Moderate effort
    "loops_bonus": 3
})

task_id = response.json()["task_id"]

# Monitor progress via WebSocket
import websocket

def on_message(ws, message):
    status = json.loads(message)
    print(f"Status: {status['currentStep']} - {status['message']}")

ws = websocket.WebSocketApp(f"ws://localhost:8000/ws/research-agent/{task_id}")
ws.on_message = on_message
ws.run_forever()
```

### Multi-Turn Research Conversation

```python
# Initial research
response1 = requests.post("http://localhost:8000/api/research-agent/run", json={
    "research_question": "How do vision transformers compare to CNNs?",
    "papers_bonus": 5,
    "loops_bonus": 2
})

# Follow-up research with conversation context
conversation_history = [
    {"role": "user", "content": "How do vision transformers compare to CNNs?"},
    {"role": "assistant", "content": "Based on recent research..."}
]

response2 = requests.post("http://localhost:8000/api/research-agent/run", json={
    "research_question": "What about their computational efficiency?",
    "papers_bonus": 2,
    "loops_bonus": 1,
    "conversation_history": conversation_history
})
```

### Research Library Search

```python
# Search previous research
response = requests.post("http://localhost:8000/api/research-agent/library/search", json={
    "query": "transformer efficiency",
    "page": 1,
    "page_size": 10
})

for item in response.json()["results"]:
    print(f"Research: {item['research_question']}")
    print(f"Sources: {item['sources_count']}")
    print(f"Themes: {', '.join(item['themes'])}")
```

---

## Technical Implementation

### LangGraph State Management

The research agent uses TypedDict state classes for robust state management:

```python
class OverallState(TypedDict):
    messages: List[BaseMessage]
    sources_gathered: List[Dict[str, Any]]
    judged_sources: List[Dict[str, Any]]
    current_outline: str
    research_loop_count: int
    # ... other state fields

class JudgeState(TypedDict):
    judged_papers: List[Dict[str, Any]]
    rejected_papers: List[Dict[str, Any]]

class OutlineState(TypedDict):
    outline: str
    paper_contexts: List[str]
```

### PDF Processing Pipeline

```python
def _download_and_process_pdf_from_url(self, pdf_url: str, source: Dict, research_query: str) -> str:
    # 1. Download with robust error handling
    response = requests.get(pdf_url, timeout=60, headers=headers)
    
    # 2. Validate PDF format
    if not header.startswith(b'%PDF'):
        raise ValueError("Invalid PDF format")
    
    # 3. Process with SpacyLayoutDocProcessor
    processor = SpacyLayoutDocProcessor(
        language="en",
        export_figures=False,  # Avoid Docling issues
        remove_md_image_tags=True
    )
    result = processor.process_document(temp_pdf_path)
    
    # 4. Intelligent chunking
    parser = FlatMarkdownParser(result['processed_data'], max_tokens=8000)
    chunks = parser.get_parsed_data()
    
    # 5. Find relevant sections
    relevant_chunks = self._find_relevant_chunks(chunks, research_query)
    
    return processed_summary
```

### Relevance Judging Algorithm

```python
def _judge_papers(self, state: OverallState, config: RunnableConfig) -> JudgeState:
    judged_papers = []
    rejected_papers = []
    
    for source in sources_gathered:
        # Create paper context
        paper_context = format_paper_metadata(source)
        
        # Get LLM judgment
        result = llm.invoke([], relevance_rubric(research_topic, paper_context), 
                           schema=RelevanceRubric)
        
        # Apply 6+ relevance threshold
        if result.relevant and result.score >= 6:
            judged_papers.append({**source, **result.dict()})
        else:
            rejected_papers.append({**source, **result.dict()})
    
    return {"judged_papers": judged_papers, "rejected_papers": rejected_papers}
```

### Citation Processing

```python
def _convert_short_urls_to_markdown_links(self, content: str, sources: List[Dict]) -> str:
    # Map short URLs to numbered references
    source_mapping = {}
    for i, source in enumerate(sources):
        source_mapping[source["short_url"]] = {
            "number": i + 1,
            "title": source["title"],
            "url": source["value"]
        }
    
    # Replace [source_N] with [N](url)
    for short_url, info in source_mapping.items():
        numbered_link = f"[{info['number']}]({info['url']})"
        content = content.replace(short_url, numbered_link)
    
    # Generate references section
    content += generate_references_section(source_mapping)
    return content
```

---

## Troubleshooting

### Common Issues

**PDF Download Failures**
- Check internet connectivity
- Verify PDF URLs are accessible
- Ensure sufficient disk space for temporary files
- Check ArXiv rate limiting (2-second delays enforced)

**Relevance Judging Errors**
- Verify judge model is properly configured
- Check that paper metadata (title/abstract) exists
- Ensure model has sufficient context window for papers

**WebSocket Connection Issues**
- Verify WebSocket endpoint is accessible
- Check for firewall blocking WebSocket connections
- Ensure task ID is valid and hasn't expired

**Memory Issues with Large Papers**
- Reduce `max_chunks_per_paper` setting
- Lower `chunk_size_tokens` for smaller memory footprint
- Disable PDF processing for memory-constrained environments

### Debug Endpoints

**Check PDF Processing Capabilities**
```bash
curl http://localhost:8000/api/research-agent/debug/paper-access
```

**Verify Model Configuration**
```bash
curl http://localhost:8000/api/research-agent/model-config
```

### Performance Optimization

**Database Optimization**
- Ensure sqlite-vec extension is properly loaded
- Run `VACUUM` on database periodically
- Consider indexing frequently searched fields

**Model Performance**
- Use faster models for judging (e.g., Claude Haiku)
- Configure appropriate timeout values
- Monitor token usage for cost optimization

**PDF Processing Optimization**
- Enable parallel processing for multiple papers
- Cache processed PDFs to avoid re-processing
- Use SSD storage for temporary file operations

---

## Advanced Features

### Custom Prompts

You can customize the research agent's behavior by modifying prompt templates in `theseus_insight/prompt/research_agent_prompts.py`:

- `relevance_rubric`: Paper relevance evaluation criteria
- `outline_instructions`: Research outline generation guidance  
- `reflection_instructions`: Research completeness evaluation
- `answer_instructions`: Final report generation format

### Model Routing

The agent supports different models for different tasks:

```python
# In model configuration
{
  "reasoning_model": "gemini-2.0-flash",  # General reasoning
  "judge_model": "claude-3-haiku",        # Fast relevance judging
  "query_generator_model": "gpt-4o-mini", # Query generation
  "reflection_model": "claude-3-sonnet"   # Deep reflection
}
```

### External Search Providers

Currently supports ArXiv with planned expansion to:
- Semantic Scholar
- PubMed
- Google Scholar
- Custom academic databases

### Conversation Context

The agent maintains conversation context for multi-turn research sessions:

```json
{
  "conversation_history": [
    {"role": "user", "content": "Tell me about transformers"},
    {"role": "assistant", "content": "Transformers are..."},
    {"role": "user", "content": "What about their efficiency?"}
  ]
}
```

This enables natural follow-up questions and progressive research refinement.

---

For additional support or feature requests, please refer to the main [Theseus Insight repository](https://github.com/M-Chimiste/TheseusInsight) or create an issue with detailed information about your use case. 