# Bulk Operations Performance Improvement Plan

## Overview
This plan outlines the implementation of performance improvements for bulk paper operations in TheseusInsight, with a focus on reducing the 8-hour processing time for 1M papers to under 1 hour. Given the constraint that Ollama API calls cannot be parallelized due to local compute limitations, we'll focus on optimizing other bottlenecks.

## Phase 0: Critical Bug Fixes (Days 1-2)
**Goal**: Fix duplicate evaluation and unnecessary downloads

### 0.1 Fix Duplicate Paper Evaluation
- **Task**: Coordinate pipeline stages to avoid re-processing papers
- **Implementation**:
  - Pass processed paper IDs from stage 1 to stage 2
  - Modify `BulkJudgeRunner._get_papers_to_score()` to accept a paper ID filter
  - Only score papers that were newly added or updated
- **Expected Impact**: 50% reduction in processing time for bulk operations
- **Effort**: 4 hours

### 0.2 Fix Profile Aware Ingestion Downloads
- **Task**: Check existing papers before downloading
- **Implementation**:
  - Query existing papers in date range first using `get_papers_in_date_range()`
  - Build set of existing URLs
  - Filter download requests to exclude existing papers
  - Implement batch existence checking
- **Expected Impact**: 70-90% reduction in download volume for updates
- **Effort**: 6 hours

### 0.3 Optimize Kaggle Dataset Processing
- **Task**: Implement smart Kaggle data filtering
- **Implementation**:
  - Add date filtering during Kaggle CSV parsing (not after)
  - Cache parsed Kaggle metadata with date index
  - Only parse relevant date ranges from CSV
  - Skip Kaggle entirely if all papers exist in date range
- **Expected Impact**: 10-100x faster for small date range updates
- **Effort**: 4 hours

## Phase 1: Quick Wins (Week 1)
**Goal**: Achieve 3-5x performance improvement with minimal changes

### 1.1 Implement Connection Pooling
- **Task**: Add psycopg3 connection pooling to `db/__init__.py`
- **Implementation**:
  - Create a global connection pool (min=5, max=20 connections)
  - Modify `get_cursor()` to use pooled connections
  - Add pool statistics logging
- **Expected Impact**: 20-30% faster database operations
- **Effort**: 4 hours

### 1.2 Optimize Duplicate Checking
- **Task**: Replace in-memory duplicate detection with database queries
- **Implementation**:
  - Create composite index: `CREATE INDEX idx_papers_url_title ON papers(url, title)`
  - Implement batch EXISTS queries using `WHERE url = ANY(%s)`
  - Process in chunks of 10,000 papers
- **Expected Impact**: 50-100x faster duplicate checking
- **Effort**: 6 hours

### 1.3 Batch Database Updates for Embeddings
- **Task**: Replace individual UPDATE statements with batch operations
- **Implementation**:
  - Use PostgreSQL arrays for bulk updates
  - Implement `UPDATE papers SET embedding = data.embedding FROM (VALUES ...) AS data`
  - Batch size: 1000 papers per update
- **Expected Impact**: 5-10x faster embedding storage
- **Effort**: 4 hours

## Phase 2: Database Optimization (Week 2)
**Goal**: Implement PostgreSQL COPY for 10-50x improvement

### 2.1 Staging Table Architecture
- **Task**: Design and implement staging tables for bulk imports
- **Implementation**:
  ```sql
  CREATE TABLE papers_staging (LIKE papers INCLUDING ALL);
  CREATE TABLE embeddings_staging (paper_id INTEGER, embedding vector(768));
  ```
- **Workflow**:
  1. COPY data to staging tables
  2. Deduplicate using SQL
  3. Merge into main tables
  4. Truncate staging tables
- **Expected Impact**: 10-20x faster imports
- **Effort**: 8 hours

### 2.2 Implement PostgreSQL COPY
- **Task**: Replace INSERT operations with COPY
- **Implementation**:
  - Use `psycopg3.Copy` for streaming data
  - Implement CSV generation for COPY format
  - Handle special characters and escaping
- **Expected Impact**: 10-50x faster than INSERT
- **Effort**: 8 hours

### 2.3 Optimize Indexes
- **Task**: Analyze and optimize database indexes
- **Implementation**:
  - Add partial indexes for common queries
  - Remove unused indexes
  - Implement index-only scans where possible
- **Expected Impact**: 2-3x faster queries
- **Effort**: 4 hours

## Phase 3: Processing Pipeline Optimization (Week 3)
**Goal**: Optimize embedding and scoring pipelines

### 3.1 Parallel Embedding Generation
- **Task**: Implement multi-threaded embedding generation
- **Implementation**:
  - Use ThreadPoolExecutor for database I/O
  - Increase SentenceTransformer batch size to 512-1024
  - Implement producer-consumer pattern:
    - Producer: Read papers from database
    - Consumer: Generate embeddings and queue for storage
  - Stream embeddings to staging table
- **Expected Impact**: 3-5x faster embedding generation
- **Effort**: 8 hours

### 3.2 Optimize Ollama Scoring Pipeline
- **Task**: Improve efficiency of sequential LLM calls
- **Implementation**:
  - Implement smart caching for similar papers
  - Pre-filter papers using embeddings similarity
  - Batch context preparation
  - Optimize prompt templates for faster inference
  - Add progress checkpointing every 100 papers
- **Expected Impact**: 20-30% faster scoring
- **Effort**: 6 hours

### 3.3 Memory-Efficient Batch Processing
- **Task**: Reduce memory footprint for large datasets
- **Implementation**:
  - Use generators throughout the pipeline
  - Implement streaming from database
  - Process in optimal chunk sizes (10k-50k papers)
  - Add memory monitoring and alerts
- **Expected Impact**: Handle 10x larger datasets
- **Effort**: 6 hours

## Phase 4: Architecture Improvements (Week 4)
**Goal**: Build foundation for future scaling

### 4.1 Implement Checkpoint System
- **Task**: Add resumable processing capability
- **Implementation**:
  - Track processing state in database
  - Implement checkpoint every 1000 papers
  - Add resume functionality
  - Handle partial failures gracefully
- **Expected Impact**: Fault tolerance, no re-processing
- **Effort**: 8 hours

### 4.2 Add Monitoring and Metrics
- **Task**: Implement performance monitoring
- **Implementation**:
  - Add timing metrics for each pipeline stage
  - Implement progress estimation
  - Create performance dashboard
  - Add alerting for bottlenecks
- **Expected Impact**: Identify optimization opportunities
- **Effort**: 6 hours

### 4.3 Create Bulk Operations API
- **Task**: Expose optimized bulk operations via API
- **Implementation**:
  - New endpoints for bulk paper import
  - Streaming upload support
  - Async job management
  - Progress tracking via WebSocket
- **Expected Impact**: Better user experience
- **Effort**: 8 hours

## Implementation Schedule

### Days 1-2: Critical Fixes
- Day 1: Fix duplicate evaluation and ingestion downloads
- Day 2: Optimize Kaggle processing and testing

### Week 1: Foundation
- Monday-Tuesday: Connection pooling and duplicate checking
- Wednesday-Thursday: Batch database updates
- Friday: Testing and benchmarking

### Week 2: Database Layer
- Monday-Tuesday: Staging table architecture
- Wednesday-Thursday: PostgreSQL COPY implementation
- Friday: Index optimization and testing

### Week 3: Processing Pipeline
- Monday-Tuesday: Parallel embedding generation
- Wednesday: Ollama pipeline optimization
- Thursday-Friday: Memory optimization and testing

### Week 4: Architecture & Polish
- Monday-Tuesday: Checkpoint system
- Wednesday-Thursday: Monitoring and metrics
- Friday: API development and final testing

## Success Metrics

### Performance Targets
| Metric | Current | Target | Measurement |
|--------|---------|---------|-------------|
| 1M Paper Import | 8 hours | < 1 hour | End-to-end time |
| Duplicate Check | O(n²) | O(n log n) | Papers/second |
| Embedding Storage | 100/sec | 10,000/sec | Updates/second |
| Memory Usage | Unbounded | < 8GB | Peak RAM usage |
| Duplicate Evaluation | 2x per paper | 1x per paper | Processing count |
| Update Downloads | 100% re-download | < 10% re-download | Data volume |
| Kaggle Processing | Full 4GB scan | Only new dates | Processing time |

### Quality Metrics
- Zero data loss during migration
- Maintain exact embedding values
- Preserve all metadata
- No regression in API response times

## Risk Mitigation

### Technical Risks
1. **Connection Pool Exhaustion**
   - Mitigation: Implement connection timeout and monitoring
   - Fallback: Increase pool size dynamically

2. **Staging Table Conflicts**
   - Mitigation: Use unique staging table names per import
   - Fallback: Implement table locking

3. **Memory Pressure**
   - Mitigation: Implement backpressure in pipelines
   - Fallback: Reduce batch sizes dynamically

### Operational Risks
1. **Import Failures**
   - Mitigation: Checkpoint system for resume
   - Fallback: Keep transaction logs

2. **Performance Regression**
   - Mitigation: A/B testing with old pipeline
   - Fallback: Feature flags for rollback

## Testing Strategy

### Unit Tests
- Connection pool behavior
- Batch operation correctness
- COPY format generation
- Checkpoint/resume logic

### Integration Tests
- End-to-end import pipeline
- Concurrent operation handling
- Memory usage under load
- Error recovery scenarios

### Performance Tests
- Benchmark each optimization
- Load testing with 1M+ papers
- Memory profiling
- Database query analysis

## Rollout Plan

1. **Development Environment**
   - Implement all phases
   - Run full test suite
   - Benchmark improvements

2. **Staging Environment**
   - Test with production-like data
   - Verify no regressions
   - Performance validation

3. **Production Rollout**
   - Feature flag for new pipeline
   - Gradual rollout (10%, 50%, 100%)
   - Monitor metrics closely
   - Keep old pipeline for rollback

## Expected Outcomes

After implementing all phases:
- **1M papers import**: 45-60 minutes (vs 8 hours)
- **Memory usage**: Constant 4-8GB (vs unbounded)
- **Database load**: 80% reduction in connections
- **Error recovery**: Full checkpoint/resume capability
- **Monitoring**: Real-time performance visibility
- **Duplicate processing**: Eliminated (saves 50% on bulk operations)
- **Update efficiency**: 90% reduction in redundant downloads
- **Kaggle optimization**: 10-100x faster for date-limited operations

The plan prioritizes changes that don't require parallelizing Ollama calls while maximizing performance gains through database optimization, efficient batching, and smart pipeline design. The critical fixes in Phase 0 alone should provide immediate relief for the duplicate evaluation and unnecessary download issues.