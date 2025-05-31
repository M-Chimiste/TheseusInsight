# Hybrid Search with SQLite FTS5 and sqlite-vec

## Overview

Theseus Insight's hybrid search capabilities now leverage SQLite's FTS5 for full-text search and `sqlite-vec` for vector similarity search. This combination provides strong keyword relevance along with contextual semantic understanding.

## What Was Implemented

### 1. Database Schema Enhancements for SQLite

*   **`papers` Table**:
    *   Stores core paper data, including `title`, `abstract`, and `embedding` (as a `BLOB`).
*   **`papers_fts` Virtual Table**:
    *   An FTS5 table created with content from `papers.title` and `papers.abstract`.
    *   Automatically synchronized with the `papers` table using database triggers (`papers_ai`, `papers_ad`, `papers_au`).
    *   Enables efficient keyword searches using `MATCH` and ranking with functions like `bm25()`.
*   **`papers_vss` Virtual Table**:
    *   A `sqlite-vec` (vss0) table storing vector embeddings from `papers.embedding`.
    *   Enables fast k-nearest neighbor searches using vector similarity (e.g., cosine similarity).
    *   Managed by application logic: when a paper's embedding is generated, it's inserted/updated in this table.

### 2. Hybrid Search Algorithm

The `hybrid_search_papers` method in `data_handling.py` now orchestrates:

1.  **Keyword Search (FTS5)**:
    *   Queries the `papers_fts` table using the user's query text.
    *   Retrieves matching paper IDs and their BM25 relevance scores.
    *   Example FTS5 query snippet: `SELECT rowid, bm25(papers_fts) FROM papers_fts WHERE papers_fts MATCH ? ORDER BY bm25(papers_fts) DESC;`
2.  **Semantic Search (sqlite-vec)**:
    *   Generates a vector embedding for the user's query text.
    *   Queries the `papers_vss` table to find papers with similar embeddings.
    *   Retrieves matching paper IDs and their similarity scores (calculated from vector distance).
    *   Example `sqlite-vec` query snippet (conceptual, via Python): Searching `papers_vss` and joining with `papers`.
3.  **Result Combination and Re-ranking (Python)**:
    *   Fetches results from both FTS and VSS searches.
    *   Normalizes keyword scores (e.g., BM25 scores) to a comparable range with semantic scores (e.g., 0-1). Min-max normalization is used for the current batch of FTS scores.
    *   Calculates a final `hybrid_score` for each paper based on a weighted average of its normalized keyword score and its semantic similarity score.
    *   Default weights (e.g., 60% semantic, 40% keyword) can be adjusted via API parameters.
    *   Sorts the combined results by the `hybrid_score`.
    *   Applies pagination to the final sorted list.

### 3. Key Improvements

*   **SQLite Native FTS**: Utilizes FTS5, a robust and efficient full-text search engine built into SQLite.
*   **Specialized Vector Search**: Leverages `sqlite-vec` for optimized vector similarity calculations.
*   **Flexible Ranking**: Python-side combination allows for flexible normalization and weighting strategies.
*   **Automatic Synchronization**: FTS5 table is kept in sync with main paper data via database triggers.

### 4. Data Population

*   **FTS5 (`papers_fts`)**: Automatically populated/updated when records are inserted, updated, or deleted in the `papers` table due to database triggers.
*   **VSS (`papers_vss`)**: Populated by the application logic in `insert_paper` and `update_paper_embedding` methods in `data_handling.py` whenever a paper's embedding is available or updated.

## Performance Benefits

### 1. Search Quality Improvements
- **Relevant Keyword Matching**: BM25 ranking via FTS5 provides nuanced text search.
- **Contextual Understanding**: Semantic search via `sqlite-vec` finds conceptually similar papers.
- **Combined Power**: Hybrid approach aims to balance keyword precision with semantic recall.

### 2. Database Performance
- **FTS5 Efficiency**: FTS5 virtual tables are highly optimized for text indexing and querying.
- **`sqlite-vec` Efficiency**: `sqlite-vec` uses specialized data structures (like IVF_PQ) for fast approximate nearest neighbor search.
- **Embedded Engine**: SQLite runs in the same process as the application, potentially reducing inter-process communication overhead compared to a separate database server for some workloads, though it has different concurrency characteristics.

## API Compatibility

**Backward Compatibility:** The API endpoint (`/api/papers/hybrid-search`) signature remains the same.
- Request parameters (query_text, weights, filters, pagination) are consistent.

**Enhanced Responses:** The response structure is similar, but scores reflect the new backend:
```json
{
  "semantic_score": 0.732,
  "keyword_score": 0.564,  // Now BM25-based instead of boolean
  "hybrid_score": 0.605
}
```

## Testing Results

**Before Enhancement:**
```json
{
  "keyword_score": 0.564,  // Original BM25 score from FTS5
  "normalized_keyword_score": 0.85, // BM25 score normalized to e.g. 0-1 range
  "hybrid_score": 0.605    // Weighted combination of semantic and normalized keyword score
}
```

**Query Examples:**
The effectiveness of queries like "neural network", "transformer attention", or "machine learning optimization" now depends on the FTS5 tokenizer (e.g., `porter` stemmer by default) and the `sqlite-vec` embedding model's understanding.

## Technical Architecture

### SQLite Full-Text Search (FTS5) & Vector Search (sqlite-vec) Stack
1.  **FTS5 Virtual Table (`papers_fts`)**: Stores tokenized text from `papers.title` and `papers.abstract`. Indexed internally by FTS5 for fast `MATCH` queries. Ranking is typically done using `bm25()`.
2.  **`sqlite-vec` Virtual Table (`papers_vss`)**: Stores vector embeddings. Uses an index (e.g., IVF_PQ) for fast similarity searches (e.g., `vss_search` function).
3.  **Python Application Logic**:
    *   Generates embeddings for query text.
    *   Executes separate queries against `papers_fts` and `papers_vss`.
    *   Combines, normalizes, and re-ranks results.

### Integration Points
- **Database Layer**: `hybrid_search_papers()` method in `data_handling.py` orchestrates the FTS and VSS queries and result combination.
- **API Layer**: `/api/papers/hybrid-search` endpoint remains the interface.
- **Frontend**: No changes required to the frontend API call structure, but the quality and nature of scores will change.

## Future Enhancements

### Potential Improvements
1. **Custom Ranking**: Implement custom BM25 parameters (k1, b values)
2. **Multi-Language Support for FTS5**: Configure FTS5 tokenizers for other languages if needed.
3. **Advanced Query Syntax**: Expose more of FTS5's query syntax or `sqlite-vec`'s search parameters if required.
4. **Database-Side Ranking**: For very large datasets, explore more complex SQL-based ranking strategies to reduce Python-side processing, if feasible with SQLite's capabilities.

### Performance Optimizations
1. **`sqlite-vec` Index Tuning**: Experiment with different index types and parameters for `papers_vss` based on dataset size and performance characteristics.
2. **SQLite Pragmas**: Optimize SQLite performance using PRAGMA settings (e.g., `journal_mode=WAL`, `synchronous=NORMAL`, `cache_size`).
3. **Application-Level Caching**: Cache frequent search results or embeddings.

## Migration Notes

**From PostgreSQL to SQLite:**
1.  **Schema Conversion**: The `PaperDatabase._initialize_db()` method creates the new SQLite schema, including FTS5 and VSS tables (if `sqlite-vec` extension is loaded).
2.  **Data Migration**:
    *   Export data from PostgreSQL (e.g., using `db_export.py`).
    *   Import data into SQLite (e.g., using `db_import.py`).
    *   During import:
        *   Text for `papers.title` and `papers.abstract` will be inserted into the `papers` table, and FTS5 triggers will populate `papers_fts`.
        *   Embeddings (as `BLOB`s) will be inserted into `papers.embedding`, and application logic in `insert_paper` will populate `papers_vss`.
3.  **No `update_search_vectors.py` script needed**: The old script for populating PostgreSQL `tsvector` columns is obsolete.

**For New SQLite Installations:**
- The schema (including FTS5 and VSS tables) is created on first application startup by `PaperDatabase._initialize_db()`.
- Data populates FTS and VSS tables automatically as papers are added.

## Conclusion

The hybrid search functionality has been adapted to use SQLite's FTS5 for keyword search and `sqlite-vec` for semantic vector search. This provides a robust embedded search solution. The combination of results and re-ranking is now primarily handled in the Python application layer, offering flexibility in scoring and normalization.