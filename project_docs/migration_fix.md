# Theseus Insight - Migration Fix Plan

## Overview

This document outlines a systematic plan to complete the SQLite to PostgreSQL migration. During code review, we identified several critical areas where the migration is incomplete, with legacy SQLite dependencies still present throughout the codebase.

## Current Status Assessment

### ✅ **Completed Components**
- ✅ Repository layer implementation (14 repositories)
- ✅ Most API routers converted (12/12 routers)
- ✅ Core application layer (TaskManager, TheseusInsight classes)
- ✅ Migration utilities (export/import/migrate tools)
- ✅ Infrastructure setup (Docker, PostgreSQL, pgvector)

### ❌ **Critical Issues Identified**
- ❌ Global legacy database instance in `api/dependencies.py`
- ❌ Mindmap module still using legacy database (5 files)
- ❌ Research agent tools using legacy database
- ❌ Communication and podcast modules using legacy database
- ❌ Utility scripts still using SQLite
- ❌ Documentation references SQLite

---

## Fix Plan Structure

### **Phase 1: Critical Dependencies (Priority 1)**
**Estimated Time:** 2-3 hours  
**Risk Level:** HIGH - These are blocking issues affecting entire application

### **Phase 2: Core Module Conversion (Priority 2)**
**Estimated Time:** 4-6 hours  
**Risk Level:** MEDIUM - Feature-specific functionality

### **Phase 3: Utility Scripts & Documentation (Priority 3)**
**Estimated Time:** 2-3 hours  
**Risk Level:** LOW - Standalone scripts and documentation

---

## Phase 1: Critical Dependencies Fix

### 1.1 Fix `api/dependencies.py` 🔴 CRITICAL

**Current Issue:**
```python
from ..data_model.data_handling import PaperDatabase
DB_URL = os.getenv("DATABASE_URL", "data/theseus.db")  # SQLite default!
db = PaperDatabase(DB_URL)  # Global SQLite instance!
```

**Required Changes:**
1. Remove `PaperDatabase` import and global `db` instance
2. Update default DATABASE_URL to PostgreSQL format
3. Create helper functions for credential management
4. Add database connection validation

**New Structure:**
```python
import os

# PostgreSQL default instead of SQLite
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/theseus")

# Credential management (no global db instance)
CREDENTIAL_KEYS = [...]

def get_database_url() -> str:
    """Get validated database URL."""
    return DB_URL

def validate_database_connection() -> bool:
    """Validate PostgreSQL connection."""
    # Implementation using get_cursor()
```

**Files Affected:**
- `api/dependencies.py` (primary)
- `main.py` (imports `db` from dependencies)
- `api/routers/research_agent.py` (imports `db` from dependencies)

### 1.2 Fix `main.py` Legacy Database Usage

**Current Issue:**
```python
from .api.dependencies import db, CREDENTIAL_KEYS
# Uses db.get_secret_setting() for encrypted secrets
```

**Required Changes:**
1. Remove `db` import from dependencies
2. Convert credential loading to use `SettingsRepository`
3. Update secret management to use repository pattern

### 1.3 Fix Remaining Router Dependencies

**Files to Check:**
- `api/routers/research_agent.py` - Still imports `db` from dependencies
- `api/routers/newsletters_and_podcasts.py` - Imports `DB_URL` from dependencies

---

## Phase 2: Core Module Conversion

### 2.1 Mindmap Module Conversion (5 files)

**Files to Convert:**
1. `mindmap/nodes/multi_order_retriever.py`
2. `mindmap/nodes/retriever.py` 
3. `mindmap/nodes/embed_seed.py`
4. `mindmap/nodes/summariser.py`
5. `mindmap/nodes/select_seed.py`

**Legacy Methods to Replace:**
- `self.db.find_similar_papers_mindmap()` → `PaperRepository.find_similar_mindmap()`
- `self.db.get_paper_keywords()` → `PaperRepository.get_keywords()`
- `self.db.update_paper_keywords()` → `PaperRepository.update_keywords()`
- `self.db.get_paper_by_id()` → `PaperRepository.get()`
- `self.db.update_paper_embedding()` → `PaperRepository.update_embedding()`
- `self.db.get_paper_summary()` → `PaperRepository.get_summary()`
- `self.db.update_paper_summary()` → `PaperRepository.update_summary()`

**Required Repository Enhancements:**
Need to add missing methods to `PaperRepository`:
```python
@staticmethod
def find_similar_mindmap(seed_paper_id: int, k: int = 15, similarity_threshold: float = 0.3) -> List[Dict]:
    """Find similar papers for mindmap generation."""

@staticmethod  
def get_summary(paper_id: int) -> str | None:
    """Get paper summary/text."""

@staticmethod
def update_summary(paper_id: int, summary: str) -> None:
    """Update paper summary/text."""

@staticmethod
def update_embedding(paper_id: int, embedding: List[float]) -> None:
    """Update paper embedding."""
```

### 2.2 Research Agent Tools Conversion

**File:** `research_agent/tools/local_search.py`

**Legacy Methods to Replace:**
- `self.db.hybrid_search_papers()` → `PaperRepository.hybrid_search()`
- `self.db.get_paper_by_id()` → `PaperRepository.get()`
- `self.db.update_paper_embedding()` → `PaperRepository.update_embedding()`
- `self.db.update_paper_text()` → `PaperRepository.update_text()`
- `self.db.get_paper_by_url()` → `PaperRepository.get_by_url()`
- `self.db.insert_paper()` → `PaperRepository.insert()`
- `self.db.fetch_all_papers()` → `PaperRepository.get_all()`

**Constructor Changes:**
```python
# Current
def __init__(self, db: PaperDatabase, embedding_model: SentenceTransformerInference, ...):

# New  
def __init__(self, embedding_model: SentenceTransformerInference, ...):
    # Remove db parameter, use repositories directly
```

### 2.3 Communication Module Conversion

**File:** `communication/communication.py`

**Legacy Methods to Replace:**
- `self.db.get_email_recipients()` → `SettingsRepository.get("email_recipients")`

**Required Changes:**
1. Remove `PaperDatabase` import and instance
2. Update constructor to remove `db` parameter
3. Convert email recipient management to settings-based

### 2.4 Podcast Generator Conversion

**File:** `podcast/generator.py`

**Legacy Methods to Replace:**
- `self.db.insert_podcast()` → `PodcastRepository.insert()`

**Required Changes:**
1. Remove `PaperDatabase` import and instance
2. Import `PodcastRepository`
3. Update podcast insertion logic

---

## Phase 3: Utility Scripts & Documentation

### 3.1 Harvest Scripts Conversion

**Files:**
- `utils/harvest_and_judge.py`
- `utils/paperswithcode_harvest_and_judge.py`

**Required Changes:**
1. Replace `PaperDatabase` with repository imports
2. Update database connection to use PostgreSQL URL
3. Convert all database operations to repository methods
4. Update CLI argument defaults from SQLite to PostgreSQL

### 3.2 Backfill Scripts Conversion

**Files:**
- `utils/backfill_embeddings.py`
- `utils/backfill_keywords.py` 
- `utils/update_search_vectors.py`

**Required Changes:**
1. Replace `PaperDatabase` with repository pattern
2. Update default database URLs
3. Convert database operations to repository methods
4. Update CLI help text to reference PostgreSQL

### 3.3 Documentation Updates

**Files:**
- `docs/db_spec.md`

**Required Changes:**
1. Update database engine from SQLite to PostgreSQL
2. Update schema documentation for PostgreSQL types
3. Document pgvector integration
4. Update connection string examples
5. Document migration process

---

## Implementation Strategy

### **Step-by-Step Execution Plan**

#### **Step 1: Dependencies Fix (30 minutes)**
1. Update `api/dependencies.py` - remove global db, fix defaults
2. Update `main.py` - remove db dependency, use repositories
3. Test basic application startup

#### **Step 2: Repository Enhancements (45 minutes)**
1. Add missing methods to `PaperRepository`
2. Add missing methods to other repositories as needed
3. Test repository methods work correctly

#### **Step 3: Mindmap Module (90 minutes)**
1. Convert `embed_seed.py` (uses get_paper_by_id, update_paper_embedding)
2. Convert `select_seed.py` (uses get_paper_by_id, get/update_keywords)
3. Convert `summariser.py` (uses get/update_paper_summary)
4. Convert `retriever.py` (uses find_similar_papers_mindmap, get/update_keywords)
5. Convert `multi_order_retriever.py` (similar to retriever.py)

#### **Step 4: Research Agent Tools (60 minutes)**
1. Update `local_search.py` constructor to remove db parameter
2. Replace all db method calls with repository methods
3. Update any instantiation of LocalSearchTool to remove db parameter

#### **Step 5: Communication & Podcast (30 minutes)**
1. Convert `communication.py` email recipient management
2. Convert `podcast/generator.py` podcast insertion

#### **Step 6: Utility Scripts (60 minutes)**
1. Convert harvest scripts to repositories
2. Convert backfill scripts to repositories
3. Update CLI defaults and help text

#### **Step 7: Documentation (30 minutes)**
1. Update `docs/db_spec.md` for PostgreSQL
2. Update any README references to SQLite

#### **Step 8: Testing & Validation (45 minutes)**
1. Test application startup with PostgreSQL
2. Test key workflows (paper import, mindmap generation, research agent)
3. Verify no remaining SQLite references
4. Run migration utilities to ensure they still work

---

## Risk Mitigation

### **High-Risk Changes**
1. **Dependencies.py modification** - Could break entire application
   - **Mitigation**: Test immediately after change, have rollback plan
   
2. **Mindmap module conversion** - Complex similarity search logic
   - **Mitigation**: Convert one file at a time, test incrementally

3. **Research agent tools** - Critical for research functionality
   - **Mitigation**: Maintain exact same interface, test with sample queries

### **Testing Strategy**
1. **Unit-level**: Test each repository method works correctly
2. **Integration-level**: Test workflows end-to-end
3. **Regression-level**: Ensure existing functionality unchanged

### **Rollback Plan**
1. Keep backup of original files
2. Use git branches for each major change
3. Test each phase before proceeding to next

---

## Success Criteria

### **Phase 1 Complete When:**
- ✅ Application starts without SQLite dependencies
- ✅ No global PaperDatabase instances exist
- ✅ Default DATABASE_URL points to PostgreSQL

### **Phase 2 Complete When:**
- ✅ All mindmap functionality works with repositories
- ✅ Research agent search works with repositories
- ✅ Communication and podcast features work with repositories

### **Phase 3 Complete When:**
- ✅ All utility scripts use PostgreSQL and repositories
- ✅ Documentation reflects PostgreSQL as primary database
- ✅ No references to SQLite remain in codebase

### **Overall Success When:**
- ✅ `grep -r "PaperDatabase" theseus_insight/` returns no results (except in data_model/data_handling.py)
- ✅ `grep -r "sqlite" theseus_insight/` returns no results (except comments/migration utilities)
- ✅ `grep -r "data/theseus.db" .` returns no results
- ✅ All functionality works identically to before migration
- ✅ Application can be deployed using only PostgreSQL

---

## Post-Migration Cleanup

### **Optional Cleanup Tasks**
1. **Remove data_model/data_handling.py** - Legacy SQLite code no longer needed
2. **Remove SQLite dependencies** - Clean up requirements.txt
3. **Archive migration utilities** - Move to separate directory
4. **Performance optimization** - Tune PostgreSQL queries and indexes

### **Future Enhancements**
1. **Connection pooling** - Implement proper connection pool management
2. **Query optimization** - Analyze and optimize slow queries
3. **Monitoring** - Add database performance monitoring
4. **Backup strategy** - Implement PostgreSQL backup procedures

---

## Estimated Timeline

| Phase | Tasks | Time Estimate | Dependencies |
|-------|-------|---------------|--------------|
| **Phase 1** | Critical Dependencies | 2-3 hours | None |
| **Phase 2** | Core Module Conversion | 4-6 hours | Phase 1 complete |
| **Phase 3** | Utilities & Docs | 2-3 hours | Phase 2 complete |
| **Testing** | Validation & Testing | 1-2 hours | All phases complete |
| **Total** | **Complete Migration** | **9-14 hours** | Sequential execution |

**Recommended Execution:** 2-3 focused work sessions over 2-3 days to ensure quality and thorough testing. 