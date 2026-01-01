# Theseus Insight Project Status

## Last Updated: December 31, 2025

---

## Recent Changes

### Version 1.0 Release (2025-12-31)

**What changed:** Bumped repository versions to 1.0.0 to mark the first major release.

**Files modified:**
- `setup.py` (backend version)
- `theseus_insight/__init__.py` (backend package version)
- `theseus-ui/package.json` (frontend version)
- `theseus-ui/package-lock.json` (frontend lockfile version)

### Dashboard Overhaul + Profile Star Map (2025-12-31)

**What changed:** Replaced the landing dashboard from a redundant nav card grid into a real command-center, and introduced a new “Profile Star Map” visualization (dashboard preview + dedicated page) to explore ~10k profile papers as a constellation.

**Frontend (theseus-ui):**
- New widget-based dashboard layout with:
  - **Pinned shortcuts** (user-customizable + reorderable via drag-and-drop; stored in localStorage)
  - **Recent outputs** (Research Agent history, Podcast history, and recent completed tasks)
  - **Insights strip** (compact stacked-area chart from profile interest timeline data)
  - **Star Map preview** (sampled starfield + CTA to full view)
- Added dedicated Star Map page at `'/star-map'` with Canvas rendering, zoom/pan, hover tooltips, and click-through to Papers search.
- Added sidebar entry **Star Map** for easy access.

**Backend (theseus_insight):**
- Added cached star map point storage + recompute pipeline:
  - SQL migration `scripts/015_profile_star_map.sql`
  - Automatic migrations list updated to include `014_interest_short_labels.sql` and `015_profile_star_map.sql`
  - New profile endpoints:
    - `GET /api/profiles/{profile_id}/star-map`
    - `GET /api/profiles/{profile_id}/star-map/status`
    - `POST /api/profiles/{profile_id}/star-map/recompute`
  - New websocket stream:
    - `ws://localhost:8000/ws/star-map/{task_id}`

**Files added/modified (high-signal):**
- Frontend:
  - `theseus-ui/src/pages/Dashboard.tsx`
  - `theseus-ui/src/pages/ProfileStarMap.tsx`
  - `theseus-ui/src/components/dashboard/*`
  - `theseus-ui/src/components/starMap/StarMapCanvas.tsx`
  - `theseus-ui/src/services/api.ts` (added `starMapApi`, extended websocket types)
  - `theseus-ui/src/components/Layout.tsx`, `theseus-ui/src/App.tsx`
- Backend:
  - `theseus_insight/data_access/star_map.py`
  - `theseus_insight/star_map/task.py`
  - `theseus_insight/api/routers/profiles.py`
  - `theseus_insight/api/routers/websockets.py`
  - `theseus_insight/db/migrations.py`
  - `scripts/015_profile_star_map.sql`

### Database Import Profile Merging Fix (2025-11-25)

**Problem:** Database imports involving the Default profile weren't properly migrating research interests. When importing a database backup where the Default profile matched the existing one, the comparison logic only checked `arxiv_filters`, `tags`, and `email_recipients` - ignoring the most important data: research interests.

**Root Cause:**
1. Profile comparison (`_compare_profiles`) did not include research interests
2. When profiles "matched", interests were simply skipped rather than merged
3. No mechanism to detect and merge new interests from source into existing profiles

**Solution Implemented:**

#### 1. Enhanced Profile Comparison (`ProfileMapper._compare_profiles`)
- Now compares research interests in addition to arxiv_filters, tags, and email_recipients
- Returns detailed comparison results including:
  - `new_interests`: Interests in source but not in target
  - `existing_interests`: Interests common to both
  - `missing_interests`: Interests in target but not in source

#### 2. Smart Interest Merging
- Added `merge_interests` parameter (default: True) throughout the import pipeline
- When profiles match on core config (arxiv_filters, tags, email_recipients):
  - Profile ID is mapped to existing profile
  - New interests from source are queued for merging
  - Interests are merged using case-insensitive duplicate detection

#### 3. New `ProfileMapper` Capabilities
- `interests_to_merge`: Queue for interests to be merged after profile mapping
- `apply_queued_interest_merges()`: Method to apply all queued interest merges
- `profile_merge_log`: Tracks what happened during merge for reporting
- Support for `smart_merge` strategy that updates profile config and merges interests

#### 4. Updated API
- `/api/settings/database/import` endpoint now accepts `merge_interests` parameter
- Default behavior merges interests when profiles match

**Files Modified:**
- `theseus_insight/utils/db_migration/db_import.py` - Core import logic with interest merging
- `theseus_insight/api/routers/database.py` - API endpoint with new parameter
- `theseus_insight/api/tasks.py` - Task manager passes merge_interests to importer

---

## What Needs to Be Implemented Next

### Short Term
1. **Star Map quality**: Replace deterministic random projection with a higher-quality dimensionality reduction (e.g. UMAP) with caching + versioning.
2. **Star Map semantics**: Add cluster labeling + selection actions (open Papers with filters, export selection, seed Mind-Map).
3. **Dashboard iteration**: Add “Continue where I left off” cards (active jobs/tasks) and/or user-configurable widget visibility.
4. **UI Update**: Add toggle in Settings/Database import UI to control `merge_interests` behavior
5. **Import Preview**: Show user what interests will be merged before confirming import
6. **Logging**: Add more detailed logging about profile/interest merge decisions

### Medium Term
1. **Interest Similarity Detection**: Use embeddings to detect semantically similar interests (not just exact text match)
2. **Merge Conflict Resolution UI**: When profiles differ significantly, show user options
3. **Profile Version History**: Track changes to profiles over time

---

## Debug Log

### 2025-12-31: Version 1.0 Bump
- Bumped versions in `setup.py`, `theseus_insight/__init__.py`, `theseus-ui/package.json`, and `theseus-ui/package-lock.json` from 0.9.x to 1.0.0.

### 2025-12-31: Landing Dashboard + Star Map Implementation
- Audited existing dashboard; identified it duplicated sidebar navigation and included a broken timeline path.
- Implemented widget-based dashboard with pinned shortcuts, recent outputs, insights strip, and star map preview.
- Added Star Map page (Canvas + d3-zoom + quadtree hit-testing) and wired routing/sidebar.
- Added backend cached point table + recompute task using TaskManager, plus `/api/profiles/{id}/star-map*` endpoints and websocket stream.
- Verified TypeScript lint on edited files and Python syntax via `compileall`.

### 2025-12-31: Star Map numerical stability fix
- Observed runtime warnings during projection (`divide by zero/overflow/invalid in matmul`) caused by non-finite or extreme embedding vectors.
- Hardened star map recompute to:
  - Skip embeddings containing NaN/Inf
  - Skip embeddings with extreme magnitudes
  - Normalize vectors to unit length before projection
  - Drop any points that still become non-finite after projection

### 2025-12-31: Star Map 3D + dashboard preview fit
- Fixed dashboard Star Map preview rendering so it fits/centers on the point cloud (correct DPR rendering + fit-to-bounds mapping).
- Extended star map cache + API to support a Z coordinate for 3D visualization:
  - Added migration `scripts/016_profile_star_map_3d.sql` (adds `z` column)
  - Updated star map recompute to project embeddings to **3D** (x/y/z) and normalize each axis.
- Updated Star Map page to support **3D (rotate/zoom)** and added an Insights panel:
  - Quick stats + top “constellations” (dominant interest labels + counts)
  - 2D/3D toggle

### 2025-11-25: Database Import Investigation
- Traced through `db_import.py` to understand profile mapping flow
- Found `_compare_profiles` only compared 3 fields, not interests
- Identified that `import_profile_research_interests` relied on `profile_id_mapping` but didn't handle merge case
- Implemented comprehensive fix with smart interest merging
- Updated API to expose merge_interests option
- No linting errors after changes

---

## Architecture Notes

### Profile Import Flow
```
1. import_from_archive() extracts tar.gz
2. import_from_directory() orchestrates import
3. Pre-loads interests data for smart merging
4. For each profile:
   a. ProfileMapper.map_profile() compares with existing
   b. If profiles match: map ID + queue new interests for merge
   c. If profiles differ: create new profile
5. apply_queued_interest_merges() adds new interests to matched profiles
6. import_profile_research_interests() handles remaining interests with ID mapping
```

### Profile Matching Logic
```
Profiles "match" if ALL of these are equal:
- arxiv_filters (JSON object)
- tags (JSON array)
- email_recipients (JSON array)

Note: Research interests differences do NOT prevent a match.
Instead, new interests are merged into the existing profile.
```

