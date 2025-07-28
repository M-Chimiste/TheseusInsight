# Research Agent System Documentation

## Overview

The Research Agent System is Theseus Insight's advanced AI-powered research orchestration platform that provides comprehensive, multi-perspective analysis of research questions. The system supports two distinct operational modes: **Single-Agent Sequential Workflows** and **Multi-Agent Parallel Orchestration**, each optimized for different research scenarios and computational resources.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Operational Modes](#operational-modes)
- [Configuration Management](#configuration-management)
- [Model Integration](#model-integration)
- [API Reference](#api-reference)
- [Usage Examples](#usage-examples)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The Research Agent System is built on a modular architecture that supports flexible model routing, intelligent workload management, and comprehensive progress tracking.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Research Agent System                    │
├─────────────────────────────────────────────────────────────┤
│  API Router                                                 │
│  ├── Task Management                                        │
│  ├── Mode Configuration                                     │
│  └── Progress Tracking                                      │
├─────────────────────────────────────────────────────────────┤
│  Orchestration Layer                                        │
│  ├── Single-Agent Workflow                                 │
│  ├── Multi-Agent Orchestrator                              │
│  └── Question Generator                                     │
├─────────────────────────────────────────────────────────────┤
│  Agent Management                                           │
│  ├── Agent Types & Specializations                         │
│  ├── Agent Manager (Parallel Execution)                    │
│  └── Synthesis Agent                                        │
├─────────────────────────────────────────────────────────────┤
│  Model Infrastructure                                       │
│  ├── Model Router                                          │
│  ├── Structured Output Support                             │
│  └── Local Model Queuing                                   │
├─────────────────────────────────────────────────────────────┤
│  Search & Tools                                            │
│  ├── Unified Search Tool                                   │
│  ├── Local Search (PostgreSQL + pgvector)                 │
│  ├── External Search (ArXiv, Semantic Scholar)            │
│  ├── Deduplication Engine                                  │
│  └── Cross-Encoder Reranking                              │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **Mode Flexibility**: Seamless switching between single-agent and multi-agent modes
2. **Model Agnostic**: Support for OpenAI, Anthropic, Google, Ollama, LlamaCPP, and custom providers
3. **Resource Optimization**: Intelligent queuing for local models and rate limiting
4. **Structured Output**: Direct JSON parsing for compatible providers with graceful fallback
5. **Progress Transparency**: Real-time WebSocket updates with detailed execution metrics
6. **Error Resilience**: Comprehensive error handling with fallback strategies

---

## Operational Modes

### Single-Agent Mode

**Sequential workflow with iterative research loops designed for deep, focused analysis.**

#### Workflow Architecture

```
User Question
      ↓
[Query Planner] → Specialized sub-queries
      ↓
[Evidence Selector] → Search & evaluate sources
      ↓
[Research Loop] → Iterative evidence gathering
      ↓
[Compression*] → Context management (if needed)
      ↓
[Answer Generator] → Final synthesis
      ↓
Final Answer
```

*Compression occurs automatically when token limits are exceeded

#### Key Features

- **Boss Model**: Primary orchestrating model that can handle all workflow nodes
- **Node-Specific Models**: Optional specialized models for specific workflow steps
- **Iterative Research**: Multiple research loops with evidence accumulation
- **Adaptive Compression**: Automatic context compression when token budgets are exceeded
- **Context Management**: Intelligent handling of large evidence sets

#### Configuration Parameters

```json
{
  "max_research_loops": 3,
  "max_research_context_tokens": 15000,
  "compress_to_ratio": 0.2,
  "search_config": {
    "local_limit": 20,
    "external_limit": 15
  }
}
```

### Multi-Agent Mode

**Parallel orchestration with specialized agents for comprehensive, multi-perspective research.**

#### Workflow Architecture

```
User Question
      ↓
[Question Generator] → Specialized sub-questions
      ↓
┌──────────────────────────────────────────────────────────┐
│              Parallel Agent Execution                   │
├──────────────┬──────────────┬──────────────┬────────────┤
│ Research     │ Analysis     │ Verification │ Alternative│
│ Agent        │ Agent        │ Agent        │ Perspective│
│              │              │              │ Agent      │
│ • Broad      │ • Pattern    │ • Fact       │ • Contrarian│
│   research   │   analysis   │   checking   │   views    │
│ • Foundation │ • Trends     │ • Source     │ • Edge     │
│   building   │ • Insights   │   validation │   cases    │
└──────────────┴──────────────┴──────────────┴────────────┘
      ↓              ↓              ↓              ↓
                     Collect Results
                           ↓
              [Synthesis Agent] → Conflict detection & resolution
                           ↓
                    Final Synthesis
```

#### Agent Specializations

1. **Research Agent**: Comprehensive information gathering and foundational research
   - Focus: Breadth of coverage, primary source identification
   - Strategy: Broad comprehensive search with emphasis on authoritative sources

2. **Analysis Agent**: Deep analytical insights and pattern recognition
   - Focus: Trends, contradictions, methodological analysis
   - Strategy: Targeted analytical search with emphasis on comparative studies

3. **Verification Agent**: Fact-checking and source validation
   - Focus: Accuracy, credibility, cross-validation
   - Strategy: Verification-focused search with emphasis on authoritative sources

4. **Alternative Perspective Agent**: Contrarian views and edge cases
   - Focus: Alternative viewpoints, limitations, criticisms
   - Strategy: Alternative-seeking search with emphasis on diverse perspectives

#### Configuration Parameters

```json
{
  "parallel_agents": 4,
  "task_timeout": 300,
  "search_config": {
    "local_limit": 25,
    "external_limit": 20
  },
  "synthesis_config": {
    "conflict_resolution": "weighted_consensus",
    "citation_strategy": "comprehensive"
  }
}
```

---

## Configuration Management

### Model Configuration Structure

The Research Agent system uses a hierarchical model configuration approach:

#### Single-Agent Configuration

```json
{
  "model_config": {
    "boss_model": {
      "model_name": "hf.co/bartowski/microsoft_Phi-4-reasoning-plus-GGUF:Q6_K_L",
      "model_type": "ollama",
      "temperature": 0.1,
      "max_new_tokens": 4096,
      "num_ctx": 131072
    },
    "query_planner_model": {
      // Optional: defaults to boss_model
    },
    "evidence_selector_model": {
      // Optional: defaults to boss_model
    },
    "compression_model": {
      // Optional: defaults to boss_model
    },
    "answer_generator_model": {
      // Optional: defaults to boss_model
    }
  }
}
```

#### Multi-Agent Configuration

```json
{
  "boss_model": {
    "model_name": "hf.co/bartowski/microsoft_Phi-4-reasoning-plus-GGUF:Q6_K_L",
    "model_type": "ollama",
    "temperature": 0.1,
    "max_new_tokens": 4096,
    "num_ctx": 131072
  },
  "specialized_models": {
    "question_generator": {
      // Defaults to boss_model if not specified
    },
    "research_agent": {
      // Defaults to boss_model if not specified
    },
    "analysis_agent": {
      // Defaults to boss_model if not specified
    },
    "verification_agent": {
      // Defaults to boss_model if not specified
    },
    "synthesis_agent": {
      // Defaults to boss_model if not specified
    }
  }
}
```

### Provider-Specific Parameters

Different model providers support different configuration parameters:

#### Ollama / LlamaCPP
```json
{
  "model_type": "ollama",
  "model_name": "llama3.1:8b-instruct-q6_K",
  "temperature": 0.1,
  "max_new_tokens": 4096,
  "num_ctx": 131072
}
```

#### OpenAI
```json
{
  "model_type": "openai",
  "model_name": "gpt-4o",
  "temperature": 0.1,
  "max_new_tokens": 4096
}
```

#### Anthropic
```json
{
  "model_type": "anthropic",
  "model_name": "claude-3-5-sonnet-20241022",
  "temperature": 0.1,
  "max_new_tokens": 4096
}
```

#### Google
```json
{
  "model_type": "google",
  "model_name": "gemini-1.5-pro",
  "temperature": 0.1,
  "max_new_tokens": 4096
}
```

---

## Model Integration

### Structured Output Support

The Research Agent system provides enhanced structured output capabilities for compatible providers:

#### Supported Providers for Structured Output
- **Ollama** - Full JSON schema support
- **LlamaCPP** - Full JSON schema support  
- **Custom-OAI** - Full JSON schema support

#### Automatic Fallback
For providers that don't support structured output (OpenAI, Anthropic, Google), the system automatically falls back to:
1. Free-form text generation
2. JSON parsing with error handling
3. Heuristic text parsing as final fallback

#### Implementation Example

```python
# Question Generator with structured output
class _QResponse(BaseModel):
    reasoning: str
    questions: List[_QItem]

# Automatic provider detection
schema_to_use = _QResponse if supports_structured_output(self.model.provider) else None

response = self.model.invoke(
    messages=messages,
    system_prompt=system_prompt,
    schema=schema_to_use
)

# Handle both structured and unstructured responses
if isinstance(response, BaseModel):
    # Direct structured output
    questions = parse_structured_response(response.model_dump())
else:
    # Fallback parsing
    questions = parse_text_response(str(response))
```

### Local Model Queuing

To prevent resource conflicts on local hardware, the system implements sequential queuing for local models:

#### Thread-Safe Execution
```python
# Global lock for local model serialization
LOCAL_MODEL_RATE_LIMITER = {
    'lock': threading.Lock(),
    'min_interval': 1.0  # Minimum 1 second between calls
}

def invoke(self, messages, system_prompt="", schema=None):
    if self.is_local_model:
        with LOCAL_MODEL_RATE_LIMITER['lock']:
            # Enforce rate limiting and sequential execution
            self._apply_rate_limiting()
            return self._safe_invoke(messages, system_prompt, schema)
    else:
        # Cloud providers run concurrently
        return self._safe_invoke(messages, system_prompt, schema)
```

#### Benefits
- **Resource Protection**: Prevents GPU/CPU overload on local hardware
- **Stability**: Eliminates race conditions and memory conflicts
- **Performance**: Maintains optimal performance for cloud APIs
- **Reliability**: Reduces crashes and timeouts

---

## API Reference

### Core Endpoints

#### Start Research Task
```http
POST /api/research-agent/research
Content-Type: application/json

{
  "research_question": "What are the latest developments in quantum computing for machine learning?",
  "mode": "multi",
  "config": {
    "search_config": {
      "local_limit": 20,
      "external_limit": 15
    }
  },
  "save_to_library": true
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z",
  "research_question": "What are the latest developments in quantum computing for machine learning?",
  "mode": "multi"
}
```

#### Get Task Status
```http
GET /api/research-agent/tasks/{task_id}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "mode": "multi",
  "progress": {
    "phase": "agent_execution",
    "overall_progress": 45.0,
    "status": "Agents conducting research",
    "agents_progress": {
      "0": {
        "status": "completed",
        "current_task": "Research completed",
        "progress_percentage": 100.0,
        "sources_found": 15
      },
      "1": {
        "status": "processing",
        "current_task": "Analyzing research patterns",
        "progress_percentage": 60.0,
        "sources_found": 12
      }
    }
  },
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z"
}
```

#### Get Research Results
```http
GET /api/research-agent/tasks/{task_id}/result
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "research_question": "What are the latest developments in quantum computing for machine learning?",
  "mode": "multi",
  "final_answer": "Recent developments in quantum computing for machine learning show significant progress in three key areas...",
  "generation_summary": "Synthesized responses from 4 specialized agents using weighted_consensus strategy.",
  "statistics": {
    "research_loops": 1,
    "total_sources_found": 47,
    "selected_sources": 4,
    "evidence_pieces": 4,
    "evidence_sufficient": true,
    "agents_used": 4,
    "synthesis_confidence": 0.85
  },
  "sub_queries": [
    "What are the current quantum computing algorithms being developed for machine learning applications?",
    "How do quantum machine learning approaches compare to classical methods in terms of performance?",
    "What are the main limitations and challenges facing quantum ML implementations?",
    "What alternative quantum computing paradigms are being explored for ML applications?"
  ],
  "sources_gathered": [
    {
      "paper_id": "2401.12345",
      "title": "Quantum Advantage in Machine Learning: Recent Theoretical Advances",
      "url": "https://arxiv.org/abs/2401.12345",
      "source": "local",
      "relevance_score": 0.92
    }
  ],
  "evidence": [
    "Research Agent: Comprehensive analysis shows quantum computing for ML is advancing through variational quantum algorithms...",
    "Analysis Agent: Pattern analysis reveals three major trends in quantum ML development...",
    "Verification Agent: Cross-validation of key claims confirms theoretical advantages...",
    "Alternative Agent: Critical examination reveals significant limitations and open challenges..."
  ],
  "workflow_messages": [
    {
      "type": "question_generation",
      "content": "Generated 4 specialized research questions",
      "timestamp": "2024-01-15T10:30:10Z"
    }
  ]
}
```

### Configuration Endpoints

#### Get Current Mode Configuration
```http
GET /api/research-agent/modes
```

**Response:**
```json
{
  "current_mode": "multi",
  "single_agent_config": {
    "model_config": {
      "boss_model": {
        "model_name": "hf.co/bartowski/microsoft_Phi-4-reasoning-plus-GGUF:Q6_K_L",
        "model_type": "ollama",
        "temperature": 0.1,
        "max_new_tokens": 4096
      }
    },
    "max_research_loops": 3,
    "max_research_context_tokens": 15000
  },
  "multi_agent_config": {
    "boss_model": {
      "model_name": "hf.co/bartowski/microsoft_Phi-4-reasoning-plus-GGUF:Q6_K_L",
      "model_type": "ollama",
      "temperature": 0.1,
      "max_new_tokens": 4096
    },
    "parallel_agents": 4,
    "task_timeout": 300
  },
  "validation": {
    "valid": true,
    "issues": []
  }
}
```

#### Switch Research Mode
```http
POST /api/research-agent/modes
Content-Type: application/json

{
  "mode": "single"
}
```

#### Update Mode Configuration
```http
PUT /api/research-agent/config/multi
Content-Type: application/json

{
  "boss_model": {
    "model_name": "gpt-4o",
    "model_type": "openai",
    "temperature": 0.1,
    "max_new_tokens": 4096
  },
  "parallel_agents": 6,
  "task_timeout": 600
}
```

---

## Usage Examples

### Basic Research Query

```python
import requests

# Start a research task
response = requests.post("http://localhost:8000/api/research-agent/research", json={
    "research_question": "What are the latest developments in transformer architectures?",
    "mode": "multi",
    "save_to_library": True
})

task_id = response.json()["task_id"]

# Monitor progress
while True:
    status_response = requests.get(f"http://localhost:8000/api/research-agent/tasks/{task_id}")
    status = status_response.json()["status"]
    
    if status == "completed":
        # Get results
        result_response = requests.get(f"http://localhost:8000/api/research-agent/tasks/{task_id}/result")
        results = result_response.json()
        print(results["final_answer"])
        break
    elif status == "failed":
        print("Research task failed")
        break
    
    time.sleep(5)
```

### Custom Configuration

```python
# Configure for local Ollama setup
config = {
    "boss_model": {
        "model_name": "llama3.1:8b-instruct-q6_K",
        "model_type": "ollama",
        "temperature": 0.1,
        "max_new_tokens": 4096,
        "num_ctx": 131072
    },
    "search_config": {
        "local_limit": 30,
        "external_limit": 20
    },
    "synthesis_config": {
        "conflict_resolution": "evidence_based",
        "citation_strategy": "selective"
    }
}

response = requests.post("http://localhost:8000/api/research-agent/research", json={
    "research_question": "How do large language models handle multilingual understanding?",
    "mode": "multi",
    "config": config,
    "save_to_library": True
})
```

### WebSocket Progress Monitoring

```javascript
// Connect to WebSocket for real-time progress
const ws = new WebSocket(`ws://localhost:8000/ws/research-agent/${taskId}`);

ws.onmessage = (event) => {
    const progress = JSON.parse(event.data);
    
    if (progress.phase === "agent_execution") {
        console.log(`Overall progress: ${progress.overall_progress}%`);
        
        // Monitor individual agent progress
        Object.entries(progress.agents_progress).forEach(([agentId, agentProgress]) => {
            console.log(`Agent ${agentId}: ${agentProgress.current_task} (${agentProgress.progress_percentage}%)`);
        });
    }
};
```

---

## Performance Optimization

### Hardware Configuration

The Research Agent system provides hardware detection and configuration recommendations:

```http
GET /api/performance/system-info
```

**Response includes:**
- CPU core count (logical and physical)
- Memory availability
- GPU detection
- Recommended configuration settings

### Model Selection Guidelines

#### For Local Hardware (Ollama/LlamaCPP)
- **Small Models (7B-8B)**: Fast inference, suitable for simple queries
- **Medium Models (13B-14B)**: Balanced performance and quality
- **Large Models (70B+)**: Highest quality, requires significant resources

#### For Cloud APIs
- **OpenAI GPT-4o**: Excellent general performance, structured output limitations
- **Anthropic Claude-3.5-Sonnet**: Superior reasoning, good for complex analysis
- **Google Gemini-1.5-Pro**: Large context windows, good for document analysis

### Optimization Strategies

1. **Local Model Queuing**: Automatic sequential execution prevents resource conflicts
2. **Structured Output**: Use compatible providers for reduced parsing errors
3. **Context Management**: Automatic compression prevents token limit issues
4. **Search Optimization**: Configurable limits balance comprehensiveness and speed
5. **Parallel Execution**: Multi-agent mode leverages concurrent processing

---

## Troubleshooting

### Common Issues

#### "Failed to parse question response as JSON"
**Cause**: LLM not following JSON format instructions
**Solution**: 
- Use structured output compatible providers (Ollama, LlamaCPP)
- Adjust temperature settings (lower values improve consistency)
- Check model configuration and provider compatibility

#### "Object of type builtin_function_or_method is not JSON serializable"
**Cause**: Non-serializable objects in response data
**Solution**: Fixed in latest version with enhanced serialization handling

#### "'UnifiedSearchTool' object has no attribute 'search'"
**Cause**: Missing search method in UnifiedSearchTool
**Solution**: Updated in latest version with backward-compatible search interface

#### Local Model Resource Conflicts
**Cause**: Multiple concurrent requests to local models
**Solution**: 
- Enable local model queuing (automatic in latest version)
- Adjust `min_interval` in rate limiter if needed
- Monitor system resources and adjust parallel agent count

### Configuration Validation

The system provides automatic configuration validation:

```json
{
  "validation": {
    "valid": false,
    "issues": [
      "Boss model configuration missing",
      "Invalid provider specified for model_type",
      "Temperature outside valid range (0.0-2.0)"
    ]
  }
}
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
DEBUG=true python -m theseus_insight.main
```

This provides:
- Detailed model invocation logs
- Search operation timing
- Agent execution traces
- WebSocket connection status
- Error stack traces

### Performance Monitoring

Monitor research task performance:

```http
GET /api/research-agent/history?limit=10
```

Analyze execution times, success rates, and resource usage patterns to optimize configuration.

---

## Best Practices

### Model Configuration
1. **Start with boss model only**: Configure a single reliable model before adding specialized models
2. **Test locally first**: Validate configuration with Ollama before switching to cloud APIs
3. **Monitor token usage**: Adjust context limits based on model capabilities
4. **Use structured output**: Choose compatible providers when possible

### Search Configuration
1. **Balance sources**: Combine local and external search for comprehensive coverage
2. **Adjust limits**: Higher limits provide more sources but increase processing time
3. **Monitor relevance**: Review search results to optimize limit settings
4. **Use hybrid search**: Leverage both semantic and keyword search capabilities

### Performance Tuning
1. **Hardware matching**: Configure parallel agents based on available CPU cores
2. **Memory management**: Monitor memory usage during large research tasks
3. **Timeout settings**: Adjust based on model performance and question complexity
4. **Progress monitoring**: Use WebSocket connections for real-time feedback

---

This documentation provides comprehensive coverage of the Research Agent System. For additional support or feature requests, consult the main Theseus Insight documentation or submit issues to the project repository. 