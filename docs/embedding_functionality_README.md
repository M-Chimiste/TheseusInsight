# Embedding Functionality for Semantic Search

This document describes the vector embedding functionality added to Theseus Insight, enabling semantic similarity search using sqlite-vec with SQLite.

## Overview

The system now stores vector embeddings of paper abstracts in the database, allowing for sophisticated semantic similarity searches that go beyond simple keyword matching.

## Features

### 1. Automatic Embedding Generation
- When papers are processed through the main pipeline, their abstracts are automatically embedded using the configured embedding model
- Embeddings are stored as vectors in the SQLite database using the sqlite-vec extension

### 2. Similarity Search API
New API endpoints for semantic search:

#### `POST /api/papers/similarity-search`
Performs semantic similarity search on papers using embeddings.

**Request Body:**
```json
{
  "query_text": "machine learning for natural language processing",
  "limit": 10,
  "similarity_threshold": 0.7
}
```

**Response:**
```json
{
  "query_text": "machine learning for natural language processing",
  "results": [
    {
      "id": 1,
      "title": "Paper Title",
      "abstract": "Paper abstract...",
      "similarity_score": 0.85,
      // ... other paper fields
    }
  ],
  "total_results": 5
}
```

#### `GET /api/papers/without-embeddings`
Returns papers that don't have embeddings yet.

#### `POST /api/papers/{paper_id}/update-embedding`
Generates and updates the embedding for a specific paper.

#### `GET /api/papers/{paper_id}/similar`
Finds papers similar to an existing paper using its stored embedding.

**Query Parameters:**
- `limit` (optional): Maximum number of similar papers to return (default: 10, max: 50)
- `similarity_threshold` (optional): Minimum similarity score 0-1 (default: 0.7)

**Response:**
```json
{
  "reference_paper": {
    "id": 123,
    "title": "Reference Paper Title",
    "abstract": "Reference paper abstract...",
    // ... other paper fields
  },
  "similar_papers": [
    {
      "id": 456,
      "title": "Similar Paper Title",
      "abstract": "Similar paper abstract...",
      "similarity_score": 0.85,
      // ... other paper fields
    }
  ],
  "total_similar": 5
}
```

### 3. Database Schema Updates

The `papers` table now includes:
- `embedding VECTOR` - Stores the vector embedding of the paper's abstract
- Updated `fetch_all_papers()` to include embeddings
- New similarity search methods using sqlite-vec cosine distance functions

### 4. Data Model Updates

The `Paper` model now includes:
```python
embedding: Optional[List[float]] = Field(default=None, description="Vector embedding of the paper's abstract")
```

## Usage

### Running Similarity Searches

```python
from theseus_insight.data_model.data_handling import PaperDatabase
from theseus_insight.inference import SentenceTransformerInference

# Initialize database and embedding model
db = PaperDatabase("postgresql://...")
embedding_model = SentenceTransformerInference("Alibaba-NLP/gte-modernbert-base")

# Perform semantic search with text query
similar_papers = db.find_papers_by_semantic_search(
    query_text="deep learning for computer vision",
    embedding_model=embedding_model,
    limit=10,
    similarity_threshold=0.7
)

# Find papers similar to an existing paper
similar_to_existing = db.find_similar_papers_to_existing(
    paper_id=123,
    limit=10,
    similarity_threshold=0.7
)
```

### Backfilling Embeddings

For existing papers without embeddings, use the backfill utility:

```bash
# Dry run to see what would be processed
python -m theseus_insight.utils.backfill_embeddings --dry-run

# Run the actual backfill
python -m theseus_insight.utils.backfill_embeddings

# Use a specific embedding model
python -m theseus_insight.utils.backfill_embeddings --embedding-model "sentence-transformers/all-MiniLM-L6-v2"

# Process in smaller batches
python -m theseus_insight.utils.backfill_embeddings --batch-size 5
```

## Technical Details

### Vector Storage
- Uses the sqlite-vec extension for efficient vector storage and similarity search
- Embeddings are stored as BLOB columns compatible with sqlite-vec
- Cosine similarity is calculated using sqlite-vec functions

### Similarity Calculation
- Uses cosine distance: `embedding <=> query_embedding`
- Similarity score is calculated as: `1 - cosine_distance`
- Results are ordered by similarity (highest first)
- Reference paper is excluded from similarity search results

### Model Configuration
- Embedding model is configured in the orchestration settings
- Supports any SentenceTransformer-compatible model
- Default model: `Alibaba-NLP/gte-modernbert-base`

## Migration Notes

### For Existing Installations

1. **Database Migration**: The database schema is automatically updated to include the `embedding` column when the application starts.

2. **Existing Papers**: Papers created before this update won't have embeddings. Use the backfill utility to generate them:
   ```bash
   python -m theseus_insight.utils.backfill_embeddings
   ```

3. **No Breaking Changes**: The system continues to work normally for papers without embeddings.

### Performance Considerations

- Embedding generation adds processing time to the paper analysis pipeline
- Consider the embedding model size vs. performance trade-off
- Use appropriate batch sizes for backfilling large numbers of papers
- sqlite-vec provides efficient indexing for similarity searches

## Future Enhancements

Potential improvements include:
- Vector indexing optimization for large datasets
- Multiple embedding models for different use cases
- Similarity search in the web UI
- Clustering and visualization of papers based on embeddings
- Recommendation systems based on user preferences
- "More like this" buttons in the paper UI