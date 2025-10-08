# PRD: Fine-Grained Database Export/Import System

## Document Status
- **Version**: 1.0
- **Created**: 2025-10-07
- **Status**: Draft for Review

## Executive Summary

This PRD outlines enhancements to the Theseus Insight database export/import system to support **fine-grained, profile-aware data migration**. The primary use case is enabling users to export specific research profiles with their associated papers and data, facilitating seamless transfer between machines while maintaining full backward compatibility.

### Current State Analysis

**✅ What Works Well:**
- Full database export/import functionality exists
- Support for 21+ table types including profiles, papers, research runs, etc.
- Backward compatibility with older export formats (v1.0, v2.0, v3.0)
- Comprehensive duplicate detection across all tables
- **Streaming export** for large datasets (handles 10k+ papers efficiently)
- **Parallel processing** for concurrent table exports
- **Incremental export** capability (export only changes since timestamp)
- Profile system with 3 core tables: `research_profiles`, `profile_research_interests`, `paper_profile_scores`

**❌ Current Limitations:**
1. **No fine-grained export**: All-or-nothing export only - cannot export specific profiles
2. **Profile relationship gaps**: Papers exported without their profile-specific scores and relationships
3. **No selective table export**: Cannot export just papers + their dependencies
4. **Profile migration issues**: When importing, profile IDs may change, breaking paper-profile relationships
5. **No profile mapping**: No mechanism to map source profile IDs to target profile IDs during import

### Problem Statement

Users need to:
1. Export a **specific research profile** with all its papers and metadata
2. Transfer their **complete paper library** with profile-specific annotations between machines
3. **Merge** exported data into existing databases without duplicating papers
4. Maintain **referential integrity** when profile IDs differ between source and target databases

## Goals and Non-Goals

### Goals
1. ✅ Enable export of specific profiles with all related data (papers, scores, interests)
2. ✅ Support export of specific table groups (e.g., just papers + metadata)
3. ✅ Implement intelligent profile ID mapping during import
4. ✅ Maintain full backward compatibility with existing exports
5. ✅ Support both full and partial database transfers
6. ✅ Handle profile merging (import into existing profile vs. create new)
7. ✅ **Preserve streaming export for profile-scoped exports** (critical for large libraries)
8. ✅ **Support incremental profile exports** (export only new papers for a profile since timestamp)

### Non-Goals
1. ❌ Real-time synchronization between databases
2. ❌ Partial paper export (papers are atomic units)
3. ❌ Selective column export within tables
4. ❌ Cross-version schema migration (handled separately)

## User Stories

### Story 1: Export Single Profile Library
**As a** researcher with multiple profiles,
**I want to** export my "Machine Learning" profile with all associated papers,
**So that** I can transfer it to my laptop for offline work.

**Acceptance Criteria:**
- Export includes: profile metadata, research interests, all papers scored by this profile, paper-profile scores
- Related data included: paper fulltext, topics, keywords where applicable
- Export is self-contained and can be imported standalone
- File size is optimized (only relevant data included)

### Story 2: Import Library into Existing Database
**As a** user importing a profile export,
**I want to** merge it with my existing data without duplicates,
**So that** I maintain a clean database while adding new content.

**Acceptance Criteria:**
- Duplicate papers detected by URL and skipped
- Profile can be mapped to existing profile OR created as new profile
- Paper-profile scores correctly linked after import
- Import provides clear summary of what was added vs. skipped

### Story 3: Bulk Paper Library Transfer
**As a** user with thousands of papers,
**I want to** export my entire paper library with all metadata,
**So that** I can migrate to a new machine without losing data.

**Acceptance Criteria:**
- All papers with embeddings, fulltext, keywords exported
- All profile scores for all profiles included
- Progress tracking for large exports (10k+ papers)
- Streaming export to handle memory constraints

## Technical Architecture

### 1. Export System Enhancements

#### 1.1 Profile-Scoped Export
```python
class ProfileScopedExporter:
    def export_profile(
        self,
        profile_id: int,
        include_papers: bool = True,
        include_fulltext: bool = True,
        include_topics: bool = False
    ) -> Dict[str, Any]:
        """
        Export a single profile with all related data.

        Returns:
        {
            "export_type": "profile_scoped",
            "profile": {...},
            "profile_research_interests": [...],
            "papers": [...],  # Papers scored by this profile
            "paper_profile_scores": [...],
            "paper_fulltext": [...],  # Optional
            "metadata": {...}
        }
        """
```

**Key Features:**
- Export only papers that have been scored by the specified profile
- Include profile-specific research interests and scores
- Optional inclusion of fulltext, topics, and other related data
- Metadata includes profile mapping information for import

#### 1.2 Table Group Export
```python
class TableGroupExporter:
    EXPORT_GROUPS = {
        "papers_only": ["papers", "paper_fulltext", "paper_topics"],
        "profiles_only": ["research_profiles", "profile_research_interests", "paper_profile_scores"],
        "research_data": ["research_runs", "research_agent_state", "mindmap_reports"],
        "content": ["newsletters", "podcasts", "literature_reviews"]
    }

    def export_table_group(
        self,
        group_name: str,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Export a predefined group of related tables."""
```

#### 1.3 Enhanced Metadata Format
```json
{
  "export_version": "6.0",
  "export_type": "profile_scoped",
  "export_timestamp": "2025-10-07T10:30:00Z",
  "source_database": {
    "schema_version": "5.2",
    "profile_count": 1,
    "paper_count": 1250
  },
  "profile_mapping": {
    "source_profile_id": 5,
    "source_profile_name": "Machine Learning",
    "export_includes_all_papers": false,
    "papers_exported": 1250
  },
  "tables_included": [
    "research_profiles",
    "profile_research_interests",
    "papers",
    "paper_profile_scores",
    "paper_fulltext"
  ],
  "table_relationships": {
    "papers": {
      "foreign_keys": ["profile_research_interests"],
      "related_scores": "paper_profile_scores"
    }
  },
  "backward_compatible": true
}
```

### 2. Import System Enhancements

#### 2.1 Profile Mapping Strategy
```python
class ProfileMapper:
    def map_profile(
        self,
        source_profile: Dict,
        target_db_connection: str,
        strategy: str = "auto"
    ) -> int:
        """
        Map source profile to target profile ID.

        Strategies:
        - "auto": Match by name, create if not exists
        - "create_new": Always create new profile
        - "merge_to": Merge into specified target profile
        - "match_by_name": Must match existing profile by name

        Returns: target_profile_id
        """
```

**Import Flow:**
1. Read export metadata to identify export type
2. If profile-scoped export:
   - Determine profile mapping strategy
   - Map source profile ID to target profile ID
   - Update all paper_profile_scores with new profile ID
3. Import tables in dependency order:
   - research_profiles (with mapping)
   - profile_research_interests (with profile_id mapping)
   - papers (deduplicate by URL)
   - paper_profile_scores (with profile_id mapping)
   - Related tables (fulltext, topics, etc.)

#### 2.2 Foreign Key Remapping
```python
class ForeignKeyRemapper:
    def __init__(self):
        self.id_mappings = {
            "research_profiles": {},  # {source_id: target_id}
            "papers": {},
            "topics": {}
        }

    def remap_foreign_keys(
        self,
        table_data: List[Dict],
        table_name: str
    ) -> List[Dict]:
        """
        Remap foreign key references based on import mappings.

        Example: paper_profile_scores.profile_id = id_mappings["research_profiles"][original_id]
        """
```

#### 2.3 Import Modes
```python
class ImportMode(Enum):
    MERGE = "merge"           # Merge with existing data (skip duplicates)
    OVERWRITE = "overwrite"   # Replace existing data
    PROFILE_CREATE = "create" # Always create new profile
    PROFILE_MERGE = "merge"   # Merge into existing profile by name
```

### 3. Data Relationships & Dependencies

#### 3.1 Table Dependency Graph
```
research_profiles (root)
├── profile_research_interests (depends on: research_profiles)
├── paper_profile_scores (depends on: research_profiles, papers)
└── scheduled_tasks (depends on: research_profiles)

papers (root)
├── paper_fulltext (depends on: papers)
├── paper_topics (depends on: papers, topics)
├── paper_research_interests (depends on: papers, research_interests)
└── paper_profile_scores (depends on: papers, research_profiles)

topics (root)
├── topic_metrics (depends on: topics)
└── paper_topics (depends on: topics, papers)
```

#### 3.2 Import Order (ensures referential integrity)
1. **Independent tables**: research_profiles, papers, topics, model_catalog
2. **First-level dependencies**: profile_research_interests, paper_fulltext, topic_metrics
3. **Second-level dependencies**: paper_profile_scores, paper_topics, paper_research_interests
4. **Scheduled data**: scheduled_tasks, scheduled_task_runs

### 4. Export Format Versions

#### Version 6.0 (New - Fine-Grained)
- **Features**: Profile-scoped export, table group export, profile mapping metadata
- **Compatibility**: Can import v1.0, v2.0, v3.0, v5.0, v6.0 exports
- **New tables**: None (uses existing schema)
- **New metadata**: `export_type`, `profile_mapping`, `table_relationships`

#### Version 5.0 (Current - Full Export)
- **Features**: All 21+ tables, streaming, parallel processing
- **Compatibility**: Can import v1.0, v2.0, v3.0, v5.0
- **Missing**: Profile-scoped export, selective table export

## Implementation Plan

### Phase 1: Core Profile-Scoped Export (Week 1-2)
**Files to modify:**
- `db_export.py`: Add `export_profile_scoped()`, `export_papers_for_profile()`
- `db_migrate.py`: Add CLI flags: `--profile-id`, `--profile-name`

**Deliverables:**
- Export single profile with all related papers
- Generate v6.0 metadata format
- Unit tests for profile filtering

### Phase 2: Import with Profile Mapping (Week 2-3)
**Files to modify:**
- `db_import.py`: Add `ProfileMapper`, `ForeignKeyRemapper`
- `db_import.py`: Update `import_from_directory()` to handle profile mapping

**Deliverables:**
- Profile ID mapping during import
- Foreign key remapping for paper_profile_scores
- Import mode selection (merge vs. create new)
- Unit tests for mapping logic

### Phase 3: Table Group Export (Week 3-4)
**Files to modify:**
- `db_export.py`: Add `TableGroupExporter`, predefined groups
- `db_migrate.py`: Add `--export-group` flag

**Deliverables:**
- Predefined export groups (papers_only, profiles_only, etc.)
- Custom table selection via CLI
- Dependency resolution for selected tables

### Phase 4: UI Integration (Week 4-5)
**Files to modify:**
- `database.py` (API router): Add endpoints for profile-scoped export
- `Settings.tsx`: Add UI for selecting export scope

**Deliverables:**
- API endpoints: `POST /api/settings/database/export-profile`
- UI: Profile selection dropdown in export dialog
- UI: Table group selection checkboxes

### Phase 5: Testing & Documentation (Week 5-6)
**Deliverables:**
- Integration tests for full import/export flow
- Migration guide for users
- Update README and API docs

## API Specifications

### Export Endpoints

#### 1. Profile-Scoped Export
```http
POST /api/settings/database/export-profile
Content-Type: application/json

{
  "profile_id": 5,
  "include_papers": true,
  "include_fulltext": true,
  "include_topics": false,
  "streaming": true
}

Response:
{
  "task_id": "uuid",
  "message": "Profile export started. Use WebSocket for progress."
}
```

#### 2. Table Group Export
```http
POST /api/settings/database/export-group
Content-Type: application/json

{
  "group": "papers_only",
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-12-31"
  }
}
```

### Import Endpoints

#### 1. Profile Import with Mapping
```http
POST /api/settings/database/import-profile
Content-Type: multipart/form-data

{
  "backup_file": <file>,
  "mapping_strategy": "auto",
  "target_profile_id": null,  // Optional: merge into existing
  "create_new_profile": false
}
```

### CLI Specifications

#### Export Commands
```bash
# Export specific profile
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://..." \
    --output ./ml_profile_backup.tar.gz \
    --profile-id 5 \
    --include-fulltext

# Export by profile name
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://..." \
    --output ./ml_backup.tar.gz \
    --profile-name "Machine Learning"

# Export table group
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://..." \
    --output ./papers_only.tar.gz \
    --export-group papers_only

# Export custom tables
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://..." \
    --output ./custom.tar.gz \
    --tables papers paper_fulltext paper_topics
```

#### Import Commands
```bash
# Auto-detect and import (default behavior)
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://..." \
    --input ./ml_profile_backup.tar.gz

# Create new profile (don't merge)
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://..." \
    --input ./ml_profile_backup.tar.gz \
    --create-new-profile \
    --new-profile-name "ML (Imported)"

# Merge into existing profile
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://..." \
    --input ./ml_profile_backup.tar.gz \
    --merge-to-profile "Machine Learning"

# Merge by profile ID
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://..." \
    --input ./ml_profile_backup.tar.gz \
    --merge-to-profile-id 3
```

## Testing Strategy

### Unit Tests
1. Profile filtering logic (export only relevant papers)
2. Foreign key remapping (profile_id mapping)
3. Duplicate detection with profile context
4. Metadata generation for v6.0 format

### Integration Tests
1. Export profile → Import to empty DB → Verify data
2. Export profile → Import to DB with existing profile → Verify merge
3. Export profile → Import with create new → Verify new profile created
4. Large dataset (10k papers) with streaming and progress tracking

### Edge Cases
1. Export profile with no papers
2. Import when target profile name conflicts
3. Import with missing foreign key references (orphaned scores)
4. Backwards compatibility: Import v5.0 export with new v6.0 importer

## Success Metrics

### Functional Metrics
- ✅ Can export specific profile in <30 seconds for 1000 papers
- ✅ Can import profile with 100% referential integrity
- ✅ Zero data loss during profile-scoped export/import
- ✅ Backward compatible with all previous export formats

### Performance Metrics
- Export 10k papers: <2 minutes with streaming
- Import 10k papers: <3 minutes with progress tracking
- Archive size: 30-40% of raw database size (with compression)

### User Experience Metrics
- Export workflow: <3 clicks in UI
- Import workflow: <3 clicks + file selection
- Clear progress indication during long operations
- Informative error messages for all failure scenarios

## Migration & Rollback Plan

### Migration Path
1. **No schema changes required** - uses existing tables
2. Deploy new export/import code alongside existing
3. Update UI to add profile selection (optional)
4. Users can continue using full export or use new profile export

### Rollback Plan
- New export format (v6.0) is backward compatible
- Old import code can still import v6.0 exports (ignores new metadata)
- No database changes required, so rollback is code-only

### Backward Compatibility Matrix

| Import Version | Export v1.0 | Export v2.0 | Export v3.0 | Export v5.0 | Export v6.0 |
|---------------|-------------|-------------|-------------|-------------|-------------|
| Importer v1.0 | ✅ | ✅ | ❌ | ❌ | ❌ |
| Importer v2.0 | ✅ | ✅ | ✅ | ❌ | ❌ |
| Importer v5.0 | ✅ | ✅ | ✅ | ✅ | ⚠️ (ignores profile mapping) |
| Importer v6.0 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Open Questions & Decisions Needed

### 1. Profile Name Collision Handling
**Question**: What if imported profile name already exists?
**Options**:
- A) Auto-rename to "Profile Name (Imported)"
- B) Prompt user for new name
- C) Fail import with error message

**Recommendation**: Option A (auto-rename) with user notification

### 2. Orphaned Data Handling
**Question**: What if papers reference non-existent profiles in import?
**Options**:
- A) Skip importing those papers
- B) Import papers but omit profile scores
- C) Create placeholder profile

**Recommendation**: Option B (import papers, log warning about missing scores)

### 3. Partial Export Scope
**Question**: Should we support exporting only papers with score > 7 for a profile?
**Decision Needed**: Add filtering options or keep it simple (all papers for profile)?

**Recommendation**: Phase 2 enhancement - start simple, add filters later

### 4. UI Complexity
**Question**: How to expose profile mapping options in UI without overwhelming users?
**Options**:
- A) Advanced options panel (collapsed by default)
- B) Simple import with smart defaults
- C) Multi-step wizard

**Recommendation**: Option B for v1, Option A for v2

## Risks & Mitigations

### Risk 1: Foreign Key Integrity Issues
**Impact**: High
**Probability**: Medium
**Mitigation**:
- Comprehensive foreign key remapping
- Import validation before committing
- Rollback capability with savepoints

### Risk 2: Large Export Performance
**Impact**: Medium
**Probability**: Low
**Mitigation**:
- Streaming export for papers
- Parallel processing where applicable
- Progress tracking with estimates

### Risk 3: User Confusion with Mapping Options
**Impact**: Medium
**Probability**: Medium
**Mitigation**:
- Clear UI labels and help text
- Sensible defaults (auto-detect)
- Examples in documentation

### Risk 4: Backward Compatibility Breakage
**Impact**: High
**Probability**: Low
**Mitigation**:
- Extensive testing with old export formats
- Version detection in import code
- Graceful degradation for missing features

## Appendix

### A. Current Export/Import Status

**Profile Tables Currently Exported** ✅:
- `research_profiles` - exported in `export_all()`
- `profile_research_interests` - exported in `export_all()`
- `paper_profile_scores` - exported in `export_all()`

**Profile Tables Currently Imported** ✅:
- All three profile tables are imported correctly
- Import order respects dependencies (profiles → interests → scores)

**Current Issues Found** ❌:
1. No way to export only specific profile
2. Profile ID mapping not implemented - assumes IDs match between source/target
3. Cannot export subset of papers (e.g., papers for one profile)
4. No table group export functionality

### B. Database Schema Summary

**Core Profile Tables**:
```sql
research_profiles (id, name, description, color, tags, email_recipients, arxiv_filters, is_active, is_default)
profile_research_interests (id, profile_id→research_profiles, interest_text, embedding, embedding_model)
paper_profile_scores (id, paper_id→papers, profile_id→research_profiles, score, related, rationale)
```

**Paper-Related Tables**:
```sql
papers (id, title, abstract, url, embedding, ...)
paper_fulltext (id, paper_id→papers, content, embedding, ...)
paper_topics (id, paper_id→papers, topic_id→topics, relevance_score)
paper_research_interests (id, paper_id→papers, research_interest_id→research_interests, similarity_score)
```

**Foreign Key Relationships Critical for Profile Export**:
- `paper_profile_scores.profile_id` → `research_profiles.id`
- `paper_profile_scores.paper_id` → `papers.id`
- `profile_research_interests.profile_id` → `research_profiles.id`

### C. Example Export Metadata (v6.0)

```json
{
  "export_version": "6.0",
  "export_type": "profile_scoped",
  "export_timestamp": "2025-10-07T14:30:00.000Z",
  "source_database": {
    "schema_version": "5.2",
    "profile_count": 1,
    "paper_count": 1250
  },
  "profile_mapping": {
    "source_profile_id": 5,
    "source_profile_name": "Machine Learning",
    "source_profile_color": "#FF6B6B",
    "export_includes_all_papers": false,
    "papers_exported": 1250,
    "paper_selection_criteria": "all papers scored by this profile"
  },
  "tables_included": [
    "research_profiles",
    "profile_research_interests",
    "papers",
    "paper_profile_scores",
    "paper_fulltext",
    "paper_topics"
  ],
  "table_statistics": {
    "research_profiles": 1,
    "profile_research_interests": 15,
    "papers": 1250,
    "paper_profile_scores": 1250,
    "paper_fulltext": 980,
    "paper_topics": 3500
  },
  "table_relationships": {
    "papers": {
      "foreign_keys": [],
      "related_tables": ["paper_profile_scores", "paper_fulltext", "paper_topics"]
    },
    "paper_profile_scores": {
      "foreign_keys": ["papers.id", "research_profiles.id"],
      "related_tables": []
    }
  },
  "import_hints": {
    "profile_mapping_required": true,
    "suggested_mapping_strategy": "auto",
    "duplicate_handling": "skip_by_url"
  },
  "backward_compatible": true,
  "checksums": {
    "papers": "sha256:abc123...",
    "paper_profile_scores": "sha256:def456..."
  }
}
```

### D. References
- Current export implementation: `theseus_insight/utils/db_migration/db_export.py`
- Current import implementation: `theseus_insight/utils/db_migration/db_import.py`
- Profile schema: `scripts/002_migrate_to_profiles.sql`
- Core schema: `scripts/001_init_schema_postgres.sql`
- Migration README: `docs/db_migration_README.md`
