# Topic Evolution & Trend-Forecast Dashboard API Specification

## Overview

The Topic Evolution & Trend-Forecast Dashboard provides automated analysis of emerging machine learning research topics, temporal trend tracking, and predictive forecasting. This comprehensive API enables researchers to identify trending areas, understand topic evolution, and make data-driven research decisions.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Authentication](#authentication)
3. [Core Topic Endpoints](#core-topic-endpoints)
4. [Research Interest Endpoints](#research-interest-endpoints)
5. [Administrative Endpoints](#administrative-endpoints)
6. [Label Summarization](#label-summarization)
7. [Integration Endpoints](#integration-endpoints)
8. [Data Models](#data-models)
9. [Error Handling](#error-handling)
10. [Performance Considerations](#performance-considerations)
11. [Examples](#examples)

---

## Core Concepts

### Topic Discovery
- **Automatic Topic Discovery**: Uses BERTopic with HDBSCAN clustering to identify emerging topics from paper embeddings
- **Research Interest Analysis**: Alternative clustering based on user-configured research interests
- **Temporal Analysis**: Tracks topic evolution across weekly, monthly, and quarterly periods

### Forecasting
- **Prophet Integration**: Time series forecasting with 1, 3, and 6-month predictions
- **Accuracy Validation**: Comprehensive metrics (MAE, MSE, RMSE, MAPE, R²) with automated alerting
- **Performance Tracking**: Historical accuracy monitoring with configurable thresholds

### Data Processing
- **Incremental Processing**: Efficient updates that only process new papers and recent periods
- **Full Recalculation**: Complete recomputation option for accuracy or major changes
- **Nuclear Option**: Complete data clearing and rebuild for troubleshooting

---

## Authentication

All API endpoints use the same authentication mechanism as the main Theseus Insight API. No additional authentication is required for trends endpoints.

---

## Core Topic Endpoints

### GET /api/trends

List trending topics with their latest metrics.

**Parameters:**
- `limit` (int, optional): Maximum number of topics to return (1-100, default: 20)
- `period_type` (str, optional): Display granularity - "week", "month", "quarter" (default: "month")
- `duration_months` (int, optional): Duration to analyze - 1, 3, 6, 12, 24 months (default: 6)
- `min_doc_count` (int, optional): Minimum document count filter (default: 5)
- `sort_by` (str, optional): Sort by "growth_rate", "doc_count", "forecast_3m" (default: "growth_rate")

**Response:**
```json
{
  "topics": [
    {
      "id": 42,
      "label": "Mixture of experts in large language models",
      "keywords": ["mixture", "experts", "moe", "llm", "scaling"],
      "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T15:45:00Z",
      "latest_doc_count": 156,
      "latest_growth_rate": 0.23,
      "total_papers": 1247,
      "forecast_1m": 180,
      "forecast_3m": 210,
      "forecast_6m": 245
    }
  ],
  "total_topics": 87,
  "total_papers_with_topics": 45231,
  "period_type": "month",
  "duration_months": 6
}
```

**Example:**
```bash
curl "http://localhost:8000/api/trends?period_type=month&duration_months=6&sort_by=growth_rate&limit=10"
```

### GET /api/trends/{topic_id}

Get detailed information about a specific topic including timeline and representative papers.

**Parameters:**
- `topic_id` (int): Topic identifier
- `period_type` (str, optional): Period type for timeline - "week", "month", "quarter" (default: "month")
- `timeline_limit` (int, optional): Number of timeline points (1-100, default: 24)
- `papers_limit` (int, optional): Number of representative papers (1-100, default: 20)

**Response:**
```json
{
  "topic": {
    "id": 42,
    "label": "Mixture of experts in large language models",
    "keywords": ["mixture", "experts", "moe", "llm", "scaling"],
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T15:45:00Z",
    "latest_doc_count": 156,
    "latest_growth_rate": 0.23,
    "total_papers": 1247,
    "forecast_1m": 180,
    "forecast_3m": 210,
    "forecast_6m": 245
  },
  "timeline": [
    {
      "id": 1001,
      "topic_id": 42,
      "period_start": "2024-01-01T00:00:00Z",
      "period_end": "2024-01-31T23:59:59Z",
      "period_type": "month",
      "doc_count": 134,
      "avg_score": 0.78,
      "growth_rate": 0.15,
      "forecast_1m": 150,
      "forecast_3m": 180,
      "forecast_6m": 210,
      "created_at": "2024-02-01T02:30:00Z"
    }
  ],
  "representative_papers": [
    {
      "id": 12345,
      "title": "Scaling Mixture-of-Experts with Switch Transformer",
      "abstract": "We present Switch Transformer, a sparsely-activated expert model...",
      "score": 0.89,
      "date": "2024-01-15",
      "url": "https://arxiv.org/abs/2101.03961",
      "similarity_score": 0.92,
      "keywords": ["switch", "transformer", "moe", "sparsity"]
    }
  ],
  "total_papers": 1247
}
```

### GET /api/trends/search

Search topics by label or keywords.

**Parameters:**
- `query` (str): Search query (minimum 1 character)
- `limit` (int, optional): Maximum number of results (1-50, default: 10)

**Response:**
```json
{
  "query": "transformer",
  "topics": [
    {
      "id": 15,
      "label": "Vision Transformers for image classification",
      "keywords": ["vision", "transformer", "vit", "classification"],
      "latest_doc_count": 89,
      "latest_growth_rate": 0.12,
      "total_papers": 567
    }
  ],
  "total_results": 3
}
```

### GET /api/trends/{topic_id}/papers

Get papers associated with a specific topic.

**Parameters:**
- `topic_id` (int): Topic identifier
- `limit` (int, optional): Maximum number of papers (1-200, default: 50)
- `min_relevance` (float, optional): Minimum relevance score (0.0-1.0, default: 0.1)
- `sort_by` (str, optional): Sort by "relevance", "score", "date" (default: "relevance")

**Response:**
```json
{
  "topic_id": 42,
  "topic_label": "Mixture of experts in large language models",
  "papers": [
    {
      "id": 12345,
      "title": "Scaling Mixture-of-Experts with Switch Transformer",
      "abstract": "We present Switch Transformer...",
      "score": 0.89,
      "date": "2024-01-15",
      "url": "https://arxiv.org/abs/2101.03961",
      "similarity_score": 0.92
    }
  ],
  "total_papers": 1247
}
```

---

## Research Interest Endpoints

### GET /api/trends/research-interests

Analyze trends based on configured research interests rather than automatic topic discovery.

**Parameters:** Same as `/api/trends` endpoint

**Response:** Same structure as `/api/trends` but with topics labeled as "Interest: {interest_text}"

### GET /api/trends/research-interests/search

Search research interests by text content.

### GET /api/trends/research-interests/{interest_id}

Get detailed information about a specific research interest.

### POST /api/trends/research-interests/recompute

Trigger recomputation of research interest clustering.

**Request Body:**
```json
{
  "lookback_months": 24,
  "duration_months": 6,
  "min_papers": 100,
  "similarity_threshold": 0.3,
  "clear_all_data": false
}
```

### GET /api/trends/research-interests/{interest_id}/papers

Get papers associated with a specific research interest.

---

## Administrative Endpoints

### POST /api/trends/recompute

Trigger recomputation of trends analysis pipeline.

**Request Body:**
```json
{
  "lookback_months": 24,
  "duration_months": 6,
  "min_papers": 100,
  "force_full_recalc": false,
  "clear_all_data": false
}
```

**Parameters:**
- `lookback_months` (int): How far back to analyze (1-36, default: 24)
- `duration_months` (int): Analysis duration (1-24, default: 6) 
- `min_papers` (int): Minimum papers per topic (1-1000, default: 100)
- `force_full_recalc` (bool): Force complete recalculation (default: false)
- `clear_all_data` (bool): Nuclear option - clear all data first (default: false)

**Response:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6",
  "message": "Trends recomputation started (incremental processing, 6M duration)",
  "estimated_duration_minutes": 5
}
```

**Processing Types:**
- **Incremental Processing** (default): Only analyzes new papers and recent periods
- **Full Recalculation** (`force_full_recalc=true`): Recalculates all metrics but preserves existing topics
- **Nuclear Option** (`clear_all_data=true`): Completely clears and rebuilds all trend data

### POST /api/trends/validate-accuracy

Validate forecast accuracy for a specific period type.

**Request Body:**
```json
{
  "period_type": "month"
}
```

**Response:**
```json
{
  "status": "started",
  "message": "Forecast accuracy validation started for month periods",
  "task_id": "validation-task-id",
  "estimated_time_minutes": 5
}
```

### GET /api/trends/system-info

Get system hardware information and recommended performance configuration.

**Response:**
```json
{
  "cpu_count_physical": 8,
  "cpu_count_logical": 16,
  "memory_total_gb": 32.0,
  "memory_available_gb": 24.5,
  "gpu_available": true,
  "gpu_name": "Apple Silicon MPS (arm64)",
  "recommended_config": {
    "max_cores": 16,
    "max_memory_gb": 25,
    "hdbscan_n_jobs": 16,
    "clustering_batch_size": 320000,
    "embedding_batch_size": 640,
    "vector_processing_workers": 16,
    "enable_memory_mapping": true,
    "cache_embeddings": true,
    "aggressive_garbage_collection": false,
    "development_mode": false,
    "development_max_papers": 32000
  }
}
```

### GET /api/trends/performance-config

Get current performance configuration.

### POST /api/trends/performance-config

Update performance configuration.

**Request Body:**
```json
{
  "max_cores": 16,
  "max_memory_gb": 25,
  "hdbscan_n_jobs": 16,
  "clustering_batch_size": 100000,
  "embedding_batch_size": 512,
  "vector_processing_workers": 8,
  "enable_memory_mapping": true,
  "cache_embeddings": true,
  "aggressive_garbage_collection": false,
  "development_mode": false,
  "development_max_papers": 10000
}
```

---

## Label Summarization

### POST /api/trends/summarize-labels

Generate AI summaries for topic labels using the configured LLM.

**Request Body:**
```json
[
  "Mixture of experts in large language models for efficient scaling",
  "Vision transformers for medical image analysis and diagnosis",
  "Reinforcement learning methods for autonomous vehicle control"
]
```

**Response:**
```json
{
  "Mixture of experts in large language models for efficient scaling": "MoE LLM Scaling",
  "Vision transformers for medical image analysis and diagnosis": "Medical Vision Transformers", 
  "Reinforcement learning methods for autonomous vehicle control": "RL Autonomous Vehicles"
}
```

**Features:**
- **Database Caching**: Summaries are cached to avoid re-generation
- **Configurable LLM**: Uses the configured "judge" model from orchestration settings
- **Robust Parsing**: Handles various LLM response formats and extracts JSON

### GET /api/trends/label-cache/stats

Get statistics about the label summaries cache.

**Response:**
```json
{
  "status": "success",
  "cache_stats": {
    "total_cached_labels": 247,
    "models_used": ["gpt-4", "claude-3-sonnet"],
    "oldest_entry": "2024-01-15T10:30:00Z",
    "newest_entry": "2024-01-20T15:45:00Z",
    "cache_hit_rate": 0.73
  }
}
```

### DELETE /api/trends/label-cache

Clear cached label summaries.

**Parameters:**
- `older_than_days` (int, optional): Clear entries older than N days

**Response:**
```json
{
  "status": "success",
  "message": "Cleared 45 cached summaries older than 30 days",
  "cleared_count": 45
}
```

---

## Integration Endpoints

The trends system enhances existing Theseus Insight APIs with topic-based functionality:

### Enhanced Papers API

**GET /api/papers?topic_id={topic_id}**

Filter papers by topic ID. All existing parameters (search, date range, pagination) work with topic filtering.

### Enhanced Mind-Map API

**POST /api/mindmap/expand**

```json
{
  "topic_id": 42,
  "similarity_threshold": 0.7,
  "max_papers": 20,
  "expansion_orders": [1, 2]
}
```

Generate mind-maps seeded from a topic's most representative papers.

### Enhanced Newsletter API

**POST /api/newsletter/run**

```json
{
  "topic_id": 42,
  "max_papers": 10,
  "newsletter_config": {
    "title": "Mixture of Experts Trends",
    "description": "Latest developments in MoE research"
  }
}
```

Generate newsletters focused on a specific topic, overriding research interests filtering.

---

## Data Models

### TopicApiResponse

```typescript
interface TopicApiResponse {
  id: number;
  label: string;
  keywords: string[];
  embedding_model?: string;
  created_at: string;
  updated_at?: string;
  latest_doc_count?: number;
  latest_growth_rate?: number;
  total_papers: number;
  forecast_1m?: number;
  forecast_3m?: number;
  forecast_6m?: number;
}
```

### TopicMetricResponse

```typescript
interface TopicMetricResponse {
  id: number;
  topic_id: number;
  period_start: string;
  period_end: string;
  period_type: "week" | "month" | "quarter";
  doc_count: number;
  avg_score?: number;
  growth_rate?: number;
  forecast_1m?: number;
  forecast_3m?: number;
  forecast_6m?: number;
  created_at: string;
}
```

### TrendsRecomputeRequest

```typescript
interface TrendsRecomputeRequest {
  lookback_months?: number; // 1-36, default: 24
  duration_months?: number; // 1-24, default: 6
  min_papers?: number; // 1-1000, default: 100
  force_full_recalc?: boolean; // default: false
  clear_all_data?: boolean; // default: false
}
```

---

## Error Handling

### Common Error Responses

**400 Bad Request**
```json
{
  "detail": "Invalid period_type. Must be 'week', 'month', or 'quarter'"
}
```

**404 Not Found**
```json
{
  "detail": "Topic not found"
}
```

**422 Unprocessable Entity**
```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "ensure this value is greater than or equal to 1",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

**500 Internal Server Error**
```json
{
  "detail": "Failed to get trending topics: Database connection error"
}
```

### Task Status Tracking

Background tasks (recomputation, validation) can be tracked via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.task_id === 'your-task-id') {
    console.log(`Progress: ${data.progress}% - ${data.message}`);
  }
};
```

---

## Performance Considerations

### Optimization Strategies

1. **Incremental Processing**: Default mode only processes new papers and recent periods
2. **Performance Configuration**: Automatically detects system capabilities and recommends optimal settings
3. **Database Indexing**: Leverages PostgreSQL indexes for fast topic and paper retrieval
4. **Caching**: Label summaries and embeddings are cached to avoid redundant computation

### Recommended Usage

- **Development**: Use `development_mode=true` with limited paper counts for faster iteration
- **Production**: Enable `cache_embeddings=true` and `enable_memory_mapping=true` for optimal performance
- **Large Datasets**: Use incremental processing and adjust batch sizes based on available memory

### Rate Limiting

- **Recomputation**: Limited to one concurrent trends task per system
- **Label Summarization**: Respects LLM provider rate limits
- **API Queries**: No specific rate limiting, but database connection pooling applies

---

## Examples

### Complete Workflow Example

```bash
# 1. Get system information and optimize configuration
curl "http://localhost:8000/api/trends/system-info"

# 2. Trigger initial trends computation
curl -X POST "http://localhost:8000/api/trends/recompute" \
  -H "Content-Type: application/json" \
  -d '{"lookback_months": 12, "duration_months": 6, "min_papers": 50}'

# 3. List trending topics
curl "http://localhost:8000/api/trends?period_type=month&duration_months=6&sort_by=growth_rate"

# 4. Get detailed topic information
curl "http://localhost:8000/api/trends/42?timeline_limit=12&papers_limit=10"

# 5. Generate mind-map from trending topic
curl -X POST "http://localhost:8000/api/mindmap/expand" \
  -H "Content-Type: application/json" \
  -d '{"topic_id": 42, "similarity_threshold": 0.7, "max_papers": 15}'

# 6. Generate newsletter from trending topic
curl -X POST "http://localhost:8000/api/newsletter/run" \
  -H "Content-Type: application/json" \
  -d '{"topic_id": 42, "max_papers": 8}'

# 7. Validate forecast accuracy
curl -X POST "http://localhost:8000/api/trends/validate-accuracy" \
  -H "Content-Type: application/json" \
  -d '{"period_type": "month"}'
```

### JavaScript/TypeScript Integration

```typescript
// Fetch trending topics
const response = await fetch('/api/trends?period_type=month&duration_months=6');
const trends = await response.json();

// Get topic details for visualization
const topicResponse = await fetch(`/api/trends/${topicId}?timeline_limit=24`);
const topicDetail = await response.json();

// Render timeline chart with D3.js
const timelineData = topicDetail.timeline.map(point => ({
  date: new Date(point.period_start),
  value: point.doc_count,
  forecast: point.forecast_3m
}));

// Generate label summaries for legend
const labels = trends.topics.map(topic => topic.label);
const summaryResponse = await fetch('/api/trends/summarize-labels', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(labels)
});
const summaries = await summaryResponse.json();
```

### Python Integration

```python
import requests
import json

# Initialize trends computation
response = requests.post('http://localhost:8000/api/trends/recompute', 
                        json={'lookback_months': 12, 'min_papers': 100})
task_id = response.json()['task_id']

# Get trending topics
trends = requests.get('http://localhost:8000/api/trends', 
                     params={'period_type': 'month', 'duration_months': 6})

# Analyze specific topic
topic_id = trends.json()['topics'][0]['id']
topic_detail = requests.get(f'http://localhost:8000/api/trends/{topic_id}',
                           params={'timeline_limit': 24})

# Generate content from trending topic
mindmap_response = requests.post('http://localhost:8000/api/mindmap/expand',
                                json={'topic_id': topic_id, 'max_papers': 20})

newsletter_response = requests.post('http://localhost:8000/api/newsletter/run',
                                   json={'topic_id': topic_id, 'max_papers': 10})
```

---

This comprehensive API specification provides all the information needed to integrate with and extend the Topic Evolution & Trend-Forecast Dashboard functionality in Theseus Insight. 