# Theseus Insight Project Status

## Last Updated: November 25, 2025

---

## Recent Changes

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
1. **UI Update**: Add toggle in Settings/Database import UI to control `merge_interests` behavior
2. **Import Preview**: Show user what interests will be merged before confirming import
3. **Logging**: Add more detailed logging about profile/interest merge decisions

### Medium Term
1. **Interest Similarity Detection**: Use embeddings to detect semantically similar interests (not just exact text match)
2. **Merge Conflict Resolution UI**: When profiles differ significantly, show user options
3. **Profile Version History**: Track changes to profiles over time

---

## Debug Log

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

