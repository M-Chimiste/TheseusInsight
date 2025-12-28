#!/usr/bin/env python3
"""
Database Import Utility

This script imports data from JSON files or tar.gz archives into the Theseus Insight database.
It handles duplicate detection and provides options for handling conflicts.

Usage:
    python -m theseus_insight.utils.db_import --db-path "postgresql://..." --input-path ./export.tar.gz
    python -m theseus_insight.utils.db_import --db-path "postgresql://..." --input-dir ./export
"""

import os
import json
import tarfile
import argparse
import tempfile
import csv
import hashlib
import logging
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple
from contextlib import contextmanager

from ...data_access import (
    PaperRepository, NewsletterRepository, PodcastRepository, 
    LitReviewRepository, ResearchRunRepository, ResearchAgentStateRepository,
    PaperFulltextRepository, MindmapReportRepository, ModelCatalogRepository
)
from ...data_model.papers import Paper, Podcast, Newsletter
from ...db import get_cursor

logger = logging.getLogger(__name__)

# Import parallel processor if available
try:
    from .parallel_processor import ParallelImporter
    PARALLEL_AVAILABLE = True
except ImportError:
    PARALLEL_AVAILABLE = False
    logger.debug("Parallel processing not available")


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class ProfileMapper:
    """Handles mapping of profile IDs during import."""

    def __init__(self, db_path: str, merge_interests: bool = True):
        """
        Initialize the profile mapper.
        
        Args:
            db_path: Database connection string
            merge_interests: Whether to merge research interests when profiles match
        """
        self.db_path = db_path
        self.id_mappings = {}  # {source_id: target_id}
        self.merge_interests = merge_interests
        self.interests_to_merge = {}  # {target_profile_id: [interest_texts_from_source]}
        self.profile_merge_log = []  # Track what happened during merge for reporting

    def _safe_deserialize_json(self, value, default=None):
        """
        Safely deserialize a value that might be a JSON string or already a Python object.
        
        Args:
            value: Value to deserialize (can be str, dict, list, or None)
            default: Default value if deserialization fails or value is None
            
        Returns:
            Deserialized Python object or default
        """
        if value is None:
            return default
        # If already a dict or list, return as-is
        if isinstance(value, (dict, list)):
            return value
        # If a string, try to parse as JSON
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Failed to parse JSON value: {value[:100] if len(value) > 100 else value}")
                return default
        # Unknown type, return default
        return default
    
    def _safe_serialize_json(self, value):
        """
        Safely serialize a value to JSON string.
        
        Args:
            value: Value to serialize (can be str, dict, list, or None)
            
        Returns:
            JSON string
        """
        if value is None:
            return None
        # If already a string, assume it's JSON and return as-is
        if isinstance(value, str):
            # Validate it's valid JSON
            try:
                json.loads(value)
                return value
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, treat as regular string and encode
                return json.dumps(value)
        # Convert dict/list to JSON string
        return json.dumps(value)

    def _get_profile_research_interests(self, profile_id: int) -> List[str]:
        """
        Get all research interests for a profile.
        
        Args:
            profile_id: Profile ID to get interests for
            
        Returns:
            List of interest text strings
        """
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT interest_text FROM profile_research_interests 
                WHERE profile_id = %s ORDER BY id
            """, (profile_id,))
            return [row['interest_text'] for row in cursor.fetchall()]

    def _normalize_interest(self, text: str) -> str:
        """Normalize interest text for comparison."""
        return text.lower().strip()

    def _compare_profiles(
        self, 
        profile1: Dict, 
        profile2: Dict, 
        source_interests: List[str] = None,
        target_profile_id: int = None,
        include_interests: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Compare two profiles to determine if they are substantially the same.
        
        Compares: arxiv_filters, tags, email_recipients, and optionally research interests.
        
        Args:
            profile1: First (source) profile data dictionary
            profile2: Second (target) profile data dictionary (from database)
            source_interests: List of interest texts from source profile
            target_profile_id: ID of target profile for fetching interests
            include_interests: Whether to include research interests in comparison
            
        Returns:
            Tuple of (profiles_match: bool, comparison_details: dict)
        """
        comparison = {
            "arxiv_filters_match": True,
            "tags_match": True,
            "email_recipients_match": True,
            "interests_match": True,
            "new_interests": [],
            "existing_interests": [],
            "missing_interests": []
        }
        
        # Compare arxiv_filters
        filters1 = self._safe_deserialize_json(profile1.get("arxiv_filters"), {})
        filters2 = self._safe_deserialize_json(profile2.get("arxiv_filters"), {})
        if filters1 != filters2:
            logger.info(f"Profiles differ in arxiv_filters: {filters1} vs {filters2}")
            comparison["arxiv_filters_match"] = False
        
        # Compare tags
        tags1 = set(self._safe_deserialize_json(profile1.get("tags"), []) or [])
        tags2 = set(self._safe_deserialize_json(profile2.get("tags"), []) or [])
        if tags1 != tags2:
            logger.info(f"Profiles differ in tags: {tags1} vs {tags2}")
            comparison["tags_match"] = False
        
        # Compare email_recipients
        recipients1 = set(self._safe_deserialize_json(profile1.get("email_recipients"), []) or [])
        recipients2 = set(self._safe_deserialize_json(profile2.get("email_recipients"), []) or [])
        if recipients1 != recipients2:
            logger.info(f"Profiles differ in email_recipients")
            comparison["email_recipients_match"] = False
        
        # Compare research interests if enabled
        if include_interests and target_profile_id is not None:
            target_interests = self._get_profile_research_interests(target_profile_id)
            target_interests_normalized = {self._normalize_interest(i) for i in target_interests}
            
            if source_interests:
                source_interests_normalized = {self._normalize_interest(i) for i in source_interests}
                
                # Find interests that exist in both (by normalized text)
                common = source_interests_normalized & target_interests_normalized
                comparison["existing_interests"] = list(common)
                
                # Find interests only in source (new interests to potentially add)
                new_in_source = source_interests_normalized - target_interests_normalized
                comparison["new_interests"] = [
                    i for i in source_interests 
                    if self._normalize_interest(i) in new_in_source
                ]
                
                # Find interests only in target (would be lost if we replaced)
                missing_from_source = target_interests_normalized - source_interests_normalized
                comparison["missing_interests"] = [
                    i for i in target_interests 
                    if self._normalize_interest(i) in missing_from_source
                ]
                
                # Interests match if there's significant overlap or source has no interests
                if len(source_interests) > 0:
                    overlap_ratio = len(common) / max(len(source_interests), len(target_interests)) if target_interests else 0
                    # Consider a match if at least 50% overlap, or if differences are only additions
                    comparison["interests_match"] = (
                        overlap_ratio >= 0.5 or 
                        (len(comparison["missing_interests"]) == 0 and len(target_interests) > 0)
                    )
                    logger.info(f"Interest comparison: {len(common)} common, {len(comparison['new_interests'])} new, "
                               f"{len(comparison['missing_interests'])} missing, overlap ratio: {overlap_ratio:.2%}")
        
        # Overall match: all core fields must match
        # For Default profiles, we're more lenient - we consider them matching if core config matches,
        # even if interests differ (interests can be merged)
        profiles_match = (
            comparison["arxiv_filters_match"] and 
            comparison["tags_match"] and 
            comparison["email_recipients_match"]
        )
        
        return profiles_match, comparison

    def map_profile(
        self,
        source_profile: Dict,
        strategy: str = "auto",
        target_profile_id: int = None,
        create_new_profile_name: str = None,
        source_interests: List[str] = None
    ) -> int:
        """
        Map source profile to target profile ID.

        Strategies:
        - "auto": Match by name, create if not exists. For Default profiles, compares content.
                  If merge_interests is enabled, new interests from source are queued for merge.
        - "smart_merge": Like auto, but always merges interests and updates profile config
        - "create_new": Always create new profile
        - "merge_to": Merge into specified target profile
        - "match_by_name": Must match existing profile by name

        Args:
            source_profile: Source profile data
            strategy: Mapping strategy
            target_profile_id: For merge_to strategy
            create_new_profile_name: Override profile name for create_new strategy
            source_interests: List of interest texts from source profile

        Returns:
            target_profile_id
        """
        source_id = source_profile['id']

        # Check if already mapped
        if source_id in self.id_mappings:
            return self.id_mappings[source_id]

        with get_cursor() as cursor:
            if strategy == "merge_to":
                if not target_profile_id:
                    raise ValueError("target_profile_id required for merge_to strategy")

                # Verify target profile exists
                cursor.execute("SELECT id FROM research_profiles WHERE id = %s", (target_profile_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Target profile {target_profile_id} not found")

                self.id_mappings[source_id] = target_profile_id
                
                # Queue interests for merging if enabled
                if self.merge_interests and source_interests:
                    self._queue_interests_for_merge(target_profile_id, source_interests)
                
                return target_profile_id

            elif strategy == "create_new":
                # Always create a new profile
                profile_name = create_new_profile_name or f"{source_profile['name']} (Imported)"

                cursor.execute("""
                    INSERT INTO research_profiles (
                        name, description, color, tags, email_recipients,
                        arxiv_filters, is_active, is_default
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    profile_name,
                    source_profile.get('description'),
                    source_profile.get('color'),
                    self._safe_serialize_json(source_profile.get('tags', [])),
                    self._safe_serialize_json(source_profile.get('email_recipients', [])),
                    self._safe_serialize_json(source_profile.get('arxiv_filters', {})),
                    source_profile.get('is_active', True),
                    False  # Never set imported profile as default
                ))

                new_id = cursor.fetchone()['id']
                self.id_mappings[source_id] = new_id
                return new_id

            elif strategy == "match_by_name":
                # Must match existing profile by name
                cursor.execute(
                    "SELECT id FROM research_profiles WHERE name = %s",
                    (source_profile['name'],)
                )
                result = cursor.fetchone()

                if not result:
                    raise ValueError(f"No profile found with name: {source_profile['name']}")

                self.id_mappings[source_id] = result['id']
                
                # Queue interests for merging if enabled
                if self.merge_interests and source_interests:
                    self._queue_interests_for_merge(result['id'], source_interests)
                
                return result['id']

            elif strategy == "smart_merge":
                # Smart merge: always try to merge with existing profile, updating config and interests
                return self._smart_merge_profile(source_profile, source_interests)

            else:  # "auto" strategy
                # Special handling for Default profile
                if source_profile.get("is_default", False) or source_profile.get("name") == "Default":
                    cursor.execute("""
                        SELECT id, name, description, color, tags, email_recipients, 
                               arxiv_filters, is_active, is_default 
                        FROM research_profiles 
                        WHERE is_default = true
                    """)
                    result = cursor.fetchone()
                    
                    if result:
                        target_id = result['id']
                        existing_profile = {
                            "arxiv_filters": result["arxiv_filters"],
                            "tags": result["tags"],
                            "email_recipients": result["email_recipients"]
                        }
                        
                        # Enhanced comparison including interests
                        profiles_match, comparison = self._compare_profiles(
                            source_profile, 
                            existing_profile,
                            source_interests=source_interests,
                            target_profile_id=target_id,
                            include_interests=True
                        )
                        
                        if profiles_match:
                            # Profiles match (core config is same), use existing default
                            logger.info(f"Default profiles match - mapping source profile {source_id} to existing Default profile {target_id}")
                            self.id_mappings[source_id] = target_id
                            
                            # Queue new interests for merging if enabled
                            if self.merge_interests and comparison.get("new_interests"):
                                self._queue_interests_for_merge(target_id, comparison["new_interests"])
                                self.profile_merge_log.append({
                                    "source_profile_id": source_id,
                                    "source_profile_name": source_profile.get("name"),
                                    "target_profile_id": target_id,
                                    "action": "merged_interests",
                                    "new_interests_count": len(comparison["new_interests"]),
                                    "existing_interests_count": len(comparison["existing_interests"])
                                })
                            
                            return target_id
                        else:
                            # Core config differs - create a new profile
                            logger.info(f"Default profiles differ - creating new profile 'Default (Imported)'")
                            profile_name = "Default (Imported)"
                            
                            cursor.execute("""
                                INSERT INTO research_profiles (
                                    name, description, color, tags, email_recipients,
                                    arxiv_filters, is_active, is_default
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (
                                profile_name,
                                source_profile.get('description'),
                                source_profile.get('color'),
                                self._safe_serialize_json(source_profile.get('tags', [])),
                                self._safe_serialize_json(source_profile.get('email_recipients', [])),
                                self._safe_serialize_json(source_profile.get('arxiv_filters', {})),
                                source_profile.get('is_active', True),
                                False  # Never set imported profile as default
                            ))

                            new_id = cursor.fetchone()['id']
                            self.id_mappings[source_id] = new_id
                            
                            self.profile_merge_log.append({
                                "source_profile_id": source_id,
                                "source_profile_name": source_profile.get("name"),
                                "target_profile_id": new_id,
                                "action": "created_new",
                                "reason": "profiles_differ"
                            })
                            
                            return new_id
                
                # Try to match by name for non-default profiles
                cursor.execute(
                    "SELECT id, tags, email_recipients, arxiv_filters FROM research_profiles WHERE name = %s",
                    (source_profile['name'],)
                )
                result = cursor.fetchone()

                if result:
                    # Profile exists, use it
                    target_id = result['id']
                    self.id_mappings[source_id] = target_id
                    
                    # Queue interests for merging if enabled
                    if self.merge_interests and source_interests:
                        existing_profile = {
                            "arxiv_filters": result["arxiv_filters"],
                            "tags": result["tags"],
                            "email_recipients": result["email_recipients"]
                        }
                        _, comparison = self._compare_profiles(
                            source_profile, 
                            existing_profile,
                            source_interests=source_interests,
                            target_profile_id=target_id,
                            include_interests=True
                        )
                        if comparison.get("new_interests"):
                            self._queue_interests_for_merge(target_id, comparison["new_interests"])
                    
                    return target_id
                else:
                    # Create new profile
                    cursor.execute("""
                        INSERT INTO research_profiles (
                            name, description, color, tags, email_recipients,
                            arxiv_filters, is_active, is_default
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        source_profile['name'],
                        source_profile.get('description'),
                        source_profile.get('color'),
                        self._safe_serialize_json(source_profile.get('tags', [])),
                        self._safe_serialize_json(source_profile.get('email_recipients', [])),
                        self._safe_serialize_json(source_profile.get('arxiv_filters', {})),
                        source_profile.get('is_active', True),
                        False  # Never set imported profile as default
                    ))

                    new_id = cursor.fetchone()['id']
                    self.id_mappings[source_id] = new_id
                    return new_id

    def _queue_interests_for_merge(self, target_profile_id: int, interests: List[str]):
        """Queue interests to be merged into a target profile."""
        if target_profile_id not in self.interests_to_merge:
            self.interests_to_merge[target_profile_id] = []
        
        # Get existing interests for this profile to avoid duplicates
        existing_interests = self._get_profile_research_interests(target_profile_id)
        existing_normalized = {self._normalize_interest(i) for i in existing_interests}
        
        for interest in interests:
            if self._normalize_interest(interest) not in existing_normalized:
                self.interests_to_merge[target_profile_id].append(interest)
                existing_normalized.add(self._normalize_interest(interest))
        
        if self.interests_to_merge[target_profile_id]:
            logger.info(f"Queued {len(self.interests_to_merge[target_profile_id])} new interests for profile {target_profile_id}")

    def _smart_merge_profile(self, source_profile: Dict, source_interests: List[str] = None) -> int:
        """
        Smart merge: merge source profile into existing profile with same name,
        updating configuration and merging interests.
        """
        with get_cursor() as cursor:
            source_id = source_profile['id']
            profile_name = source_profile.get('name', 'Unknown')
            
            # For Default profile, look for existing default
            if source_profile.get("is_default", False) or profile_name == "Default":
                cursor.execute("""
                    SELECT id, name, description, color, tags, email_recipients, 
                           arxiv_filters, is_active, is_default 
                    FROM research_profiles 
                    WHERE is_default = true
                """)
            else:
                cursor.execute("""
                    SELECT id, name, description, color, tags, email_recipients, 
                           arxiv_filters, is_active, is_default 
                    FROM research_profiles 
                    WHERE name = %s
                """, (profile_name,))
            
            result = cursor.fetchone()
            
            if result:
                target_id = result['id']
                
                # Update the profile configuration (smart merge updates config)
                # Merge tags and email_recipients rather than replacing
                existing_tags = set(self._safe_deserialize_json(result['tags'], []) or [])
                new_tags = set(self._safe_deserialize_json(source_profile.get('tags'), []) or [])
                merged_tags = list(existing_tags | new_tags)
                
                existing_recipients = set(self._safe_deserialize_json(result['email_recipients'], []) or [])
                new_recipients = set(self._safe_deserialize_json(source_profile.get('email_recipients'), []) or [])
                merged_recipients = list(existing_recipients | new_recipients)
                
                # For arxiv_filters, prefer the source if it has any, otherwise keep existing
                source_filters = self._safe_deserialize_json(source_profile.get('arxiv_filters'), {})
                existing_filters = self._safe_deserialize_json(result['arxiv_filters'], {})
                merged_filters = source_filters if source_filters else existing_filters
                
                # Update the profile
                cursor.execute("""
                    UPDATE research_profiles 
                    SET tags = %s, email_recipients = %s, arxiv_filters = %s, updated_at = NOW()
                    WHERE id = %s
                """, (
                    self._safe_serialize_json(merged_tags),
                    self._safe_serialize_json(merged_recipients),
                    self._safe_serialize_json(merged_filters),
                    target_id
                ))
                
                self.id_mappings[source_id] = target_id
                
                # Queue interests for merging
                if source_interests:
                    self._queue_interests_for_merge(target_id, source_interests)
                
                self.profile_merge_log.append({
                    "source_profile_id": source_id,
                    "source_profile_name": profile_name,
                    "target_profile_id": target_id,
                    "action": "smart_merged",
                    "tags_merged": len(merged_tags),
                    "recipients_merged": len(merged_recipients)
                })
                
                return target_id
            else:
                # No existing profile, create new one
                cursor.execute("""
                    INSERT INTO research_profiles (
                        name, description, color, tags, email_recipients,
                        arxiv_filters, is_active, is_default
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    profile_name,
                    source_profile.get('description'),
                    source_profile.get('color'),
                    self._safe_serialize_json(source_profile.get('tags', [])),
                    self._safe_serialize_json(source_profile.get('email_recipients', [])),
                    self._safe_serialize_json(source_profile.get('arxiv_filters', {})),
                    source_profile.get('is_active', True),
                    False  # Never set imported profile as default
                ))

                new_id = cursor.fetchone()['id']
                self.id_mappings[source_id] = new_id
                return new_id

    def apply_queued_interest_merges(self) -> Dict[str, int]:
        """
        Apply all queued interest merges to the database.
        
        Returns:
            Dictionary with merge statistics
        """
        stats = {"profiles_updated": 0, "interests_added": 0, "errors": 0}
        
        for profile_id, interests in self.interests_to_merge.items():
            if not interests:
                continue
                
            try:
                with get_cursor() as cursor:
                    for interest_text in interests:
                        try:
                            cursor.execute("""
                                INSERT INTO profile_research_interests (profile_id, interest_text, created_at, updated_at)
                                VALUES (%s, %s, NOW(), NOW())
                                ON CONFLICT (profile_id, interest_text) DO NOTHING
                            """, (profile_id, interest_text))
                            
                            if cursor.rowcount > 0:
                                stats["interests_added"] += 1
                        except Exception as e:
                            logger.warning(f"Could not add interest to profile {profile_id}: {e}")
                            stats["errors"] += 1
                
                stats["profiles_updated"] += 1
                logger.info(f"Merged {len(interests)} interests into profile {profile_id}")
                
            except Exception as e:
                logger.error(f"Error merging interests for profile {profile_id}: {e}")
                stats["errors"] += 1
        
        return stats

    def get_mapping(self, source_id: int) -> Optional[int]:
        """Get the target ID for a source ID."""
        return self.id_mappings.get(source_id)
    
    def get_merge_log(self) -> List[Dict[str, Any]]:
        """Get the log of profile merge operations."""
        return self.profile_merge_log


class ForeignKeyRemapper:
    """Handles remapping of foreign key references during import."""

    def __init__(self):
        """Initialize the foreign key remapper."""
        self.id_mappings = {
            "research_profiles": {},  # {source_id: target_id}
            "papers": {},
            "topics": {}
        }

    def add_mapping(self, table_name: str, source_id: int, target_id: int):
        """Add a mapping for a table."""
        if table_name not in self.id_mappings:
            self.id_mappings[table_name] = {}
        self.id_mappings[table_name][source_id] = target_id

    def remap_foreign_keys(
        self,
        table_data: List[Dict],
        table_name: str
    ) -> List[Dict]:
        """
        Remap foreign key references based on import mappings.

        Args:
            table_data: Table data to remap
            table_name: Name of the table

        Returns:
            Remapped table data
        """
        if not table_data:
            return table_data

        remapped_data = []

        for row in table_data:
            remapped_row = row.copy()

            # Remap paper_profile_scores
            if table_name == "paper_profile_scores":
                if 'profile_id' in row and row['profile_id'] in self.id_mappings.get("research_profiles", {}):
                    remapped_row['profile_id'] = self.id_mappings["research_profiles"][row['profile_id']]

                if 'paper_id' in row and row['paper_id'] in self.id_mappings.get("papers", {}):
                    remapped_row['paper_id'] = self.id_mappings["papers"][row['paper_id']]

            # Remap profile_research_interests
            elif table_name == "profile_research_interests":
                if 'profile_id' in row and row['profile_id'] in self.id_mappings.get("research_profiles", {}):
                    remapped_row['profile_id'] = self.id_mappings["research_profiles"][row['profile_id']]

            # Remap paper_topics
            elif table_name == "paper_topics":
                if 'paper_id' in row and row['paper_id'] in self.id_mappings.get("papers", {}):
                    remapped_row['paper_id'] = self.id_mappings["papers"][row['paper_id']]

                if 'topic_id' in row and row['topic_id'] in self.id_mappings.get("topics", {}):
                    remapped_row['topic_id'] = self.id_mappings["topics"][row['topic_id']]

            # Remap paper_fulltext
            elif table_name == "paper_fulltext":
                if 'paper_id' in row and row['paper_id'] in self.id_mappings.get("papers", {}):
                    remapped_row['paper_id'] = self.id_mappings["papers"][row['paper_id']]

            # Remap scheduled_tasks
            elif table_name == "scheduled_tasks":
                if 'profile_id' in row and row['profile_id'] in self.id_mappings.get("research_profiles", {}):
                    remapped_row['profile_id'] = self.id_mappings["research_profiles"][row['profile_id']]

            remapped_data.append(remapped_row)

        return remapped_data


class DatabaseImporter:
    """Handles importing database contents from JSON files."""
    
    def __init__(self, db_path: str, dry_run: bool = False, auto_migrate: bool = False, merge_strategy: str = 'upsert'):
        """
        Initialize the importer.
        
        Args:
            db_path: Database connection string (PostgreSQL URL)
            dry_run: If True, validate without making changes
            auto_migrate: If True, automatically apply schema migrations when needed
            merge_strategy: Strategy for incremental imports ('upsert', 'insert_only', 'update_only')
        """
        # Store the db_path for reference (repositories handle their own connections)
        self.db_path = db_path
        self.dry_run = dry_run
        self.auto_migrate = auto_migrate
        self.merge_strategy = merge_strategy
        self.import_version = "5.2"  # Updated version with incremental support
        self.validation_results = {
            "tables": {},
            "errors": [],
            "warnings": []
        }
    
    @contextmanager
    def _transaction_context(self, table_name: str):
        """
        Context manager for transactional operations with savepoints.
        
        Args:
            table_name: Name of the table for the savepoint
            
        Yields:
            Database cursor
        """
        if self.dry_run:
            # In dry-run mode, use a transaction that will be rolled back
            with get_cursor() as cursor:
                cursor.execute("BEGIN")
                try:
                    yield cursor
                finally:
                    cursor.execute("ROLLBACK")
        else:
            # Normal mode with savepoints
            with get_cursor() as cursor:
                savepoint = f"sp_{table_name.replace('-', '_')}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                
                try:
                    yield cursor
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
                except Exception as e:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    logger.error(f"Transaction failed for {table_name}: {e}")
                    raise
    
    def _validate_table_data(self, table_name: str, data: List[Dict], checksum: Optional[str] = None) -> bool:
        """
        Validate table data integrity using comprehensive validation framework.
        
        Args:
            table_name: Name of the table
            data: Table data as list of dictionaries
            checksum: Expected checksum from metadata
            
        Returns:
            True if valid
        """
        validation_errors = []
        
        # Calculate data checksum if provided
        if checksum:
            hasher = hashlib.sha256()
            for row in data:
                row_json = json.dumps(row, sort_keys=True, default=str)
                hasher.update(row_json.encode())
            
            calculated_checksum = hasher.hexdigest()
            if calculated_checksum != checksum:
                validation_errors.append(f"Checksum mismatch for {table_name}")
        
        # Use comprehensive validation framework
        try:
            from .data_validation import ComprehensiveValidator
            validator = ComprehensiveValidator()
            
            # Validate single table
            result = validator.table_validator.validate_table(table_name, data)
            
            # Add errors from validation result
            validation_errors.extend(result.errors)
            
            # Store detailed validation results
            self.validation_results["tables"][table_name] = {
                "record_count": len(data),
                "errors": result.errors,
                "warnings": result.warnings,
                "statistics": result.statistics,
                "valid": result.is_valid and len(validation_errors) == 0  # Include checksum result
            }
            
            # Log warnings
            for warning in result.warnings:
                logger.warning(f"{table_name}: {warning}")
            
        except ImportError:
            logger.warning("Comprehensive validation not available, using basic validation")
            
            # Fallback to basic validation
            if table_name == "papers":
                required_fields = ["title", "abstract"]
                for i, row in enumerate(data):
                    for field in required_fields:
                        if not row.get(field):
                            validation_errors.append(f"Row {i}: Missing required field '{field}'")
            
            # Store basic validation results
            self.validation_results["tables"][table_name] = {
                "record_count": len(data),
                "errors": validation_errors,
                "valid": len(validation_errors) == 0
            }
        
        # Log errors
        if validation_errors:
            for error in validation_errors:
                logger.warning(f"{table_name}: {error}")
        
        return len(validation_errors) == 0
    
    def _import_with_copy(
        self, 
        table_name: str, 
        data: List[Dict], 
        columns: List[str],
        skip_duplicates: bool = True,
        unique_columns: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, int]:
        """
        Import data using PostgreSQL COPY for performance.
        
        Args:
            table_name: Target table name
            data: Data to import
            columns: Column names
            skip_duplicates: Whether to skip duplicate records
            unique_columns: Columns that define uniqueness
            
        Returns:
            Import statistics
        """
        stats = {"imported": 0, "skipped": 0, "errors": 0}
        
        if not data:
            return stats
        
        total_records = len(data)
        logger.info(f"Starting COPY import for {table_name} with {total_records} records")
        
        if progress_callback:
            progress_callback(0, total_records, f"Preparing {table_name} for COPY import")
        
        with self._transaction_context(table_name) as cursor:
            try:
                # Prepare CSV data
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                    writer = csv.DictWriter(tmp, fieldnames=columns, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(data)
                    tmp_path = tmp.name
                
                # If skip_duplicates is False (overwrite mode), copy directly to target table
                if not skip_duplicates:
                    with open(tmp_path, 'r', encoding='utf-8') as f:
                        with cursor.connection.cursor() as copy_cursor:
                            with copy_cursor.copy(f"COPY {table_name} ({','.join(columns)}) FROM STDIN WITH CSV HEADER") as copy:
                                bytes_processed = 0
                                file_size = os.path.getsize(tmp_path)
                                last_progress_pct = -1  # Track last reported progress to prevent flooding
                                
                                while chunk := f.read(65536):  # Read in larger chunks for better performance
                                    copy.write(chunk)
                                    bytes_processed += len(chunk)
                                    
                                    # Throttle progress reporting - only report when percentage changes significantly
                                    if progress_callback and file_size > 0:
                                        progress_pct = int((bytes_processed / file_size) * 100)
                                        # Only report progress if it changed by at least 5% or at the end
                                        if progress_pct >= last_progress_pct + 5 or bytes_processed >= file_size:
                                            progress_callback(
                                                bytes_processed, 
                                                file_size, 
                                                f"COPY progress for {table_name}: {progress_pct}%"
                                            )
                                            last_progress_pct = progress_pct
                    
                    stats["imported"] = total_records
                    if progress_callback:
                        progress_callback(total_records, total_records, f"Imported {total_records} records into {table_name}")
                    
                    return stats
                
                # Original logic for skip_duplicates = True (merge mode)
                # Create temporary table for staging
                temp_table = f"temp_{table_name}_{id(self)}"
                
                # Create temp table with same structure
                cursor.execute(f"""
                    CREATE TEMP TABLE {temp_table} 
                    (LIKE {table_name} INCLUDING ALL)
                """)
                
                # COPY data into temp table using psycopg3 syntax
                with open(tmp_path, 'r', encoding='utf-8') as f:
                    with cursor.connection.cursor() as copy_cursor:
                        with copy_cursor.copy(f"COPY {temp_table} ({','.join(columns)}) FROM STDIN WITH CSV HEADER") as copy:
                            bytes_processed = 0
                            file_size = os.path.getsize(tmp_path)
                            last_progress_pct = -1  # Track last reported progress to prevent flooding
                            
                            while chunk := f.read(65536):  # Read in larger chunks for better performance
                                copy.write(chunk)
                                bytes_processed += len(chunk)
                                
                                # Throttle progress reporting - only report when percentage changes significantly
                                if progress_callback and file_size > 0:
                                    progress_pct = int((bytes_processed / file_size) * 100)
                                    # Only report progress if it changed by at least 5% or at the end
                                    if progress_pct >= last_progress_pct + 5 or bytes_processed >= file_size:
                                        progress_callback(
                                            bytes_processed, 
                                            file_size, 
                                            f"COPY progress for {table_name}: {progress_pct}%"
                                        )
                                        last_progress_pct = progress_pct
                
                if progress_callback:
                    progress_callback(total_records, total_records, f"COPY complete, inserting into {table_name}")
                
                # Handle duplicates and insert
                if skip_duplicates and unique_columns:
                    # Insert only non-duplicates
                    unique_clause = " AND ".join([
                        f"t.{col} = s.{col}" for col in unique_columns
                    ])
                    
                    cursor.execute(f"""
                        INSERT INTO {table_name} ({','.join(columns)})
                        SELECT {','.join(columns)} FROM {temp_table} s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM {table_name} t
                            WHERE {unique_clause}
                        )
                    """)
                    
                    stats["imported"] = cursor.rowcount
                    
                    # Count skipped
                    cursor.execute(f"SELECT COUNT(*) FROM {temp_table}")
                    total_count = cursor.fetchone()[0]
                    stats["skipped"] = total_count - stats["imported"]
                else:
                    # Insert all records
                    cursor.execute(f"""
                        INSERT INTO {table_name} ({','.join(columns)})
                        SELECT {','.join(columns)} FROM {temp_table}
                    """)
                    stats["imported"] = cursor.rowcount
                
                # Drop temp table (only exists in merge mode)
                if skip_duplicates:
                    cursor.execute(f"DROP TABLE {temp_table}")
                
            except Exception as e:
                logger.error(f"COPY import failed for {table_name}: {e}")
                stats["errors"] = len(data)
                raise
            finally:
                # Clean up temp file
                if 'tmp_path' in locals():
                    os.unlink(tmp_path)
        
        return stats

    def extract_archive(self, archive_path: str, extract_dir: str) -> str:
        """
        Extract tar.gz archive to a directory.
        
        Args:
            archive_path: Path to the tar.gz archive
            extract_dir: Directory to extract files to
            
        Returns:
            Path to the extraction directory
        """
        print(f"Extracting archive: {archive_path}")
        
        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_path)
        
        print(f"Archive extracted to: {extract_path}")
        return str(extract_path)
    
    def validate_import(self, input_path: str) -> Dict[str, Any]:
        """
        Perform dry-run validation of import data.
        
        Args:
            input_path: Path to import directory or archive
            
        Returns:
            Validation results
        """
        self.dry_run = True
        input_path_obj = Path(input_path)
        
        if input_path_obj.is_dir():
            return self._validate_directory(input_path)
        elif input_path_obj.suffix == ".gz":
            return self._validate_archive(input_path)
        else:
            raise ValueError(f"Invalid input path: {input_path}")
    
    def _validate_directory(self, input_dir: str) -> Dict[str, Any]:
        """Validate all files in a directory."""
        input_path = Path(input_dir)
        
        # Check metadata
        metadata_file = input_path / "metadata.json"
        if metadata_file.exists():
            self.validate_metadata(str(metadata_file))
        else:
            self.validation_results["warnings"].append("No metadata.json found")
        
        # Validate each table file
        table_files = {
            "papers": "papers.json",
            "podcasts": "podcasts.json",
            "newsletters": "newsletters.json",
            "literature_reviews": "literature_reviews.json"
        }
        
        for table_name, filename in table_files.items():
            file_path = input_path / filename
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    checksum = self.validation_results.get("checksums", {}).get(table_name)
                    self._validate_table_data(table_name, data, checksum)
        
        return self.validation_results
    
    def _validate_archive(self, archive_path: str) -> Dict[str, Any]:
        """Validate files in an archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract archive
            extract_dir = self.extract_archive(archive_path, temp_dir)
            return self._validate_directory(extract_dir)
    
    def validate_comprehensive(self, input_path: str) -> Dict[str, Any]:
        """
        Perform comprehensive validation including referential integrity and data consistency.
        
        Args:
            input_path: Path to import directory or archive
            
        Returns:
            Comprehensive validation results
        """
        # First perform basic validation
        basic_results = self.validate_import(input_path)
        
        try:
            from .data_validation import ComprehensiveValidator
            
            # Load all table data
            input_path_obj = Path(input_path)
            if input_path_obj.suffix == ".gz":
                # Extract to temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    extract_dir = self.extract_archive(input_path, temp_dir)
                    tables_data = self._load_all_tables(extract_dir)
            else:
                tables_data = self._load_all_tables(input_path)
            
            # Perform comprehensive validation
            validator = ComprehensiveValidator()
            comprehensive_result = validator.validate_export_data(tables_data)
            
            # Merge results
            basic_results["comprehensive_validation"] = {
                "is_valid": comprehensive_result.is_valid,
                "errors": comprehensive_result.errors,
                "warnings": comprehensive_result.warnings,
                "statistics": comprehensive_result.statistics
            }
            
            # Add overall status
            basic_results["overall_valid"] = (
                basic_results.get("overall_valid", True) and 
                comprehensive_result.is_valid
            )
            
        except ImportError:
            logger.warning("Comprehensive validation framework not available")
            basic_results["comprehensive_validation"] = {
                "status": "unavailable",
                "message": "Comprehensive validation framework not available"
            }
        except Exception as e:
            logger.error(f"Comprehensive validation failed: {e}")
            basic_results["comprehensive_validation"] = {
                "status": "error",
                "message": str(e)
            }
        
        return basic_results
    
    def _load_all_tables(self, input_dir: str) -> Dict[str, List[Dict]]:
        """Load all table data from directory."""
        input_path = Path(input_dir)
        tables_data = {}
        
        # Define all possible table files
        table_files = {
            "papers": "papers.json",
            "podcasts": "podcasts.json",
            "newsletters": "newsletters.json",
            "literature_reviews": "literature_reviews.json",
            "research_profiles": "research_profiles.json",
            "profile_research_interests": "profile_research_interests.json",
            "paper_profile_scores": "paper_profile_scores.json",
            "research_runs": "research_runs.json",
            "research_agent_state": "research_agent_state.json",
            "paper_fulltext": "paper_fulltext.json",
            "mindmap_reports": "mindmap_reports.json",
            "model_catalog": "model_catalog.json",
            "topics": "topics.json",
            "topic_metrics": "topic_metrics.json",
            "paper_topics": "paper_topics.json",
            "research_interests": "research_interests.json",
            "research_interest_metrics": "research_interest_metrics.json",
            "paper_research_interests": "paper_research_interests.json",
            "label_summaries": "label_summaries.json"
        }
        
        for table_name, filename in table_files.items():
            file_path = input_path / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        tables_data[table_name] = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load {filename}: {e}")
                    tables_data[table_name] = []
            else:
                logger.debug(f"Table file {filename} not found")
        
        return tables_data
    
    def apply_migrations(self, migration_info: Dict[str, Any]) -> bool:
        """
        Apply database schema migrations.
        
        Args:
            migration_info: Migration information from validation results
            
        Returns:
            True if migrations were applied successfully
        """
        if not migration_info:
            return True
        
        try:
            from .schema_versioning import SchemaMigrator
            migrator = SchemaMigrator(self.db_path)
            
            migration_path = migration_info.get("migration_path", [])
            from_version = migration_info.get("from_version")
            to_version = migration_info.get("to_version")
            
            print(f"Applying migrations from {from_version} to {to_version}")
            
            for path in migration_path:
                print(f"Applying migration: {path}")
                
                if self.dry_run:
                    # Validate migration without applying
                    success = migrator.apply_migration(path, dry_run=True)
                    if success:
                        print(f"Migration {path} validation: SUCCESS")
                    else:
                        print(f"Migration {path} validation: FAILED")
                        return False
                else:
                    # Apply migration
                    success = migrator.apply_migration(path, dry_run=False)
                    if success:
                        print(f"Migration {path}: SUCCESS")
                    else:
                        print(f"Migration {path}: FAILED")
                        return False
            
            print("All migrations applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            print(f"Error applying migrations: {e}")
            return False
    
    def validate_metadata(self, metadata_path: str) -> bool:
        """
        Validate the metadata file to ensure compatibility.
        
        Args:
            metadata_path: Path to the metadata.json file
            
        Returns:
            True if metadata is valid
        """
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            required_fields = ["export_timestamp", "export_version", "tables_exported"]
            for field in required_fields:
                if field not in metadata:
                    print(f"Warning: Missing required metadata field: {field}")
                    return False
            
            # Core required tables (literature_reviews is optional for backward compatibility)
            expected_tables = {"papers", "podcasts", "newsletters"}
            exported_tables = set(metadata["tables_exported"])
            
            if not expected_tables.issubset(exported_tables):
                missing = expected_tables - exported_tables
                print(f"Warning: Missing expected tables in export: {missing}")
                return False
            
            # Check schema version compatibility if available
            if "schema_version" in metadata:
                try:
                    from .schema_versioning import SchemaVersionManager, SchemaMigrator
                    schema_manager = SchemaVersionManager(self.db_path)
                    
                    # Load source schema version
                    import_dir = Path(metadata_path).parent
                    source_schema = schema_manager.load_schema_version(import_dir)
                    
                    # Check compatibility
                    is_compatible, warnings = schema_manager.check_compatibility(source_schema)
                    
                    for warning in warnings:
                        print(f"Schema compatibility: {warning}")
                    
                    if not is_compatible:
                        # Try to find migration path
                        if source_schema:
                            migrator = SchemaMigrator(self.db_path)
                            current_schema = schema_manager.extract_current_schema()
                            
                            migration_path = migrator.get_migration_path(
                                source_schema.version, 
                                current_schema.version
                            )
                            
                            if migration_path:
                                print(f"Migration available: {' -> '.join(migration_path)}")
                                print("Use --auto-migrate flag to apply migrations automatically")
                                
                                # Store migration info for later use
                                self.validation_results["migration_required"] = {
                                    "from_version": source_schema.version,
                                    "to_version": current_schema.version,
                                    "migration_path": migration_path
                                }
                            else:
                                print("Error: No migration path available")
                                return False
                        else:
                            print("Error: Schema versions are not compatible")
                            return False
                        
                except Exception as e:
                    print(f"Warning: Could not check schema compatibility: {e}")
            
            # Check version and available features
            export_version = metadata.get("export_version", "1.0")
            print(f"Export version: {export_version}")
            
            # Store checksums if available
            if "checksums" in metadata:
                self.validation_results["checksums"] = metadata["checksums"]
            
            # List new features if available
            new_features = metadata.get("new_features", [])
            if new_features:
                print(f"New features detected: {new_features}")
            
            # Check if new tables are available
            new_table_names = {
                "research_runs", "research_agent_state", "paper_fulltext",
                "mindmap_reports", "model_catalog"
            }
            available_new_tables = new_table_names.intersection(exported_tables)
            if available_new_tables:
                print(f"New tables available for import: {available_new_tables}")
            
            print(f"Metadata validation passed. Export from: {metadata['export_timestamp']}")
            return True
            
        except Exception as e:
            print(f"Error validating metadata: {e}")
            return False
    
    def import_papers_optimized(self, papers_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import papers using optimized COPY method.
        
        Args:
            papers_file: Path to papers.json
            skip_duplicates: Whether to skip duplicates
            progress_callback: Optional progress callback
            
        Returns:
            Import statistics
        """
        logger.info(f"Importing papers from {papers_file} using optimized method")
        
        with open(papers_file, 'r', encoding='utf-8') as f:
            papers_data = json.load(f)
        
        # Validate data
        checksum = self.validation_results.get("checksums", {}).get("papers")
        if not self._validate_table_data("papers", papers_data, checksum):
            if not self.dry_run:
                self.validation_results["warnings"].append("Papers validation failed but continuing")
        
        if self.dry_run:
            return {"total": len(papers_data), "validated": len(papers_data)}
        
        # Prepare data for COPY
        columns = [
            "title", "abstract", "date", "date_run", "score", "rationale",
            "related", "cosine_similarity", "url", "embedding_model", "embedding"
        ]
        
        # Convert embeddings to PostgreSQL format
        for paper in papers_data:
            if paper.get("embedding"):
                paper["embedding"] = json.dumps(paper["embedding"])
        
        # Import using COPY with progress callback
        def copy_progress(current, total, message):
            if progress_callback:
                progress_callback(current, total, f"COPY import: {message}")
        
        stats = self._import_with_copy(
            "papers",
            papers_data,
            columns,
            skip_duplicates=skip_duplicates,
            unique_columns=["url"],
            progress_callback=copy_progress
        )
        
        if progress_callback:
            progress_callback(len(papers_data), len(papers_data), f"Imported {stats['imported']} papers")
        
        return stats
    
    def import_papers(self, papers_file: str, skip_duplicates: bool = True, progress_callback=None, use_copy: bool = True) -> Dict[str, int]:
        """
        Import papers from JSON file using bulk insert for improved performance.
        
        Args:
            papers_file: Path to papers.json file
            skip_duplicates: Whether to skip papers that already exist (by URL)
            progress_callback: Optional callback function(current, total, message)
            use_copy: Whether to use the optimized COPY method
            
        Returns:
            Dictionary with import statistics
        """
        # Use optimized method if requested
        if use_copy:
            try:
                return self.import_papers_optimized(papers_file, skip_duplicates, progress_callback)
            except Exception as e:
                logger.warning(f"Optimized import failed, falling back to traditional method: {e}")
        
        # Traditional method
        print("Importing papers...")
        
        with open(papers_file, 'r', encoding='utf-8') as f:
            papers_data = json.load(f)
        
        print(f"Loading {len(papers_data)} papers for bulk import...")
        
        # Convert JSON data to Paper objects
        papers = []
        conversion_errors = 0
        
        for i, paper_data in enumerate(papers_data):
            try:
                # Create Paper object (exclude 'id' field if present in backup data)
                paper = Paper(
                    title=paper_data["title"],
                    abstract=paper_data["abstract"],
                    date=paper_data["date"],
                    date_run=paper_data["date_run"],
                    score=paper_data["score"],
                    rationale=paper_data["rationale"],
                    related=paper_data["related"],
                    cosine_similarity=paper_data["cosine_similarity"],
                    url=paper_data["url"],
                    embedding_model=paper_data["embedding_model"],
                    embedding=paper_data.get("embedding")
                )
                
                # Add summary as text field for PostgreSQL compatibility
                if paper_data.get("summary"):
                    paper.text = paper_data["summary"]
                
                papers.append(paper)
                
            except Exception as e:
                print(f"Error converting paper '{paper_data.get('title', 'Unknown')}': {e}")
                conversion_errors += 1
            
            # Report conversion progress
            if progress_callback and (i + 1) % 1000 == 0:
                progress_callback(i + 1, len(papers_data), f"Converting papers to objects: {i + 1}/{len(papers_data)}")
        
        print(f"Converted {len(papers)} papers successfully, {conversion_errors} conversion errors")
        
        # Use bulk insert for much better performance
        def bulk_progress_callback(current, total, message):
            if progress_callback:
                progress_callback(current, total, message)
        
        bulk_stats = PaperRepository.bulk_insert(
            papers, 
            skip_duplicates=skip_duplicates, 
            progress_callback=bulk_progress_callback
        )
        
        # Handle keywords separately for imported papers if available
        if bulk_stats["imported"] > 0:
            print("Processing keywords for imported papers...")
            papers_with_keywords = [p for p in papers_data if p.get("keywords")]
            if papers_with_keywords:
                print(f"Found {len(papers_with_keywords)} papers with keywords to process")
                
                # Get paper IDs by URL for keyword updates
                url_to_id = {}
                with get_cursor() as cursor:
                    cursor.execute("SELECT id, url FROM papers WHERE url = ANY(%s)", 
                                 ([p["url"] for p in papers_with_keywords],))
                    url_to_id = {row["url"]: row["id"] for row in cursor.fetchall()}
                
                # Update keywords in batches
                for i, paper_data in enumerate(papers_with_keywords):
                    if paper_data["url"] in url_to_id:
                        paper_id = url_to_id[paper_data["url"]]
                        try:
                            PaperRepository.update_keywords(paper_id, paper_data["keywords"])
                        except Exception as e:
                            print(f"Error updating keywords for paper {paper_id}: {e}")
                    
                    if progress_callback and (i + 1) % 100 == 0:
                        progress_callback(i + 1, len(papers_with_keywords), f"Processing keywords: {i + 1}/{len(papers_with_keywords)}")
        
        # Add conversion errors to bulk stats
        bulk_stats["errors"] += conversion_errors
        
        print(f"Papers import completed: {bulk_stats['imported']} imported, {bulk_stats['skipped']} skipped, {bulk_stats['errors']} errors")
        
        # Migrate paper scores to default profile for backward compatibility
        if bulk_stats["imported"] > 0:
            self._migrate_papers_to_default_profile(papers_data, progress_callback)
        
        return bulk_stats
    
    def _migrate_papers_to_default_profile(self, papers_data: List[Dict], progress_callback=None):
        """
        Migrate paper scores from old schema to profile-based schema.
        This ensures backward compatibility with old backups.
        """
        print("Migrating paper scores to profile-based system...")
        
        # Ensure default profile exists
        default_profile_id = self.ensure_default_profile()
        
        # Get papers that have scores but no profile scores
        papers_with_scores = [p for p in papers_data if p.get("score") is not None]
        if not papers_with_scores:
            print("No paper scores to migrate")
            return
        
        print(f"Found {len(papers_with_scores)} papers with scores to migrate to default profile")
        
        migrated_count = 0
        skipped_count = 0
        
        # Get paper IDs by URL
        url_to_id = {}
        with get_cursor() as cursor:
            cursor.execute("SELECT id, url FROM papers WHERE url = ANY(%s)", 
                         ([p["url"] for p in papers_with_scores],))
            url_to_id = {row["url"]: row["id"] for row in cursor.fetchall()}
        
        for i, paper_data in enumerate(papers_with_scores):
            try:
                paper_id = url_to_id.get(paper_data["url"])
                if not paper_id:
                    continue
                
                # Check if score already exists for this profile
                with get_cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) FROM paper_profile_scores 
                        WHERE paper_id = %s AND profile_id = %s
                    """, (paper_id, default_profile_id))
                    if cursor.fetchone()[0] > 0:
                        skipped_count += 1
                        continue
                
                # Insert paper score for default profile
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO paper_profile_scores 
                        (paper_id, profile_id, score, related, rationale, date_scored, judge_model)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        paper_id,
                        default_profile_id,
                        paper_data.get("score"),
                        paper_data.get("related"),
                        paper_data.get("rationale"),
                        paper_data.get("date_run"),  # Use date_run as date_scored
                        "legacy_import"  # Mark as imported from legacy system
                    ))
                
                migrated_count += 1
                
            except Exception as e:
                print(f"Error migrating score for paper '{paper_data.get('title', 'Unknown')}': {e}")
            
            # Report progress
            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, len(papers_with_scores), 
                                f"Migrating scores to profile system: {i + 1}/{len(papers_with_scores)}")
        
        print(f"Score migration completed: {migrated_count} migrated, {skipped_count} already existed")
    
    def import_podcasts(self, podcasts_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import podcasts from JSON file.
        
        Args:
            podcasts_file: Path to podcasts.json file
            skip_duplicates: Whether to skip podcasts that already exist (by title)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing podcasts...")
        
        with open(podcasts_file, 'r', encoding='utf-8') as f:
            podcasts_data = json.load(f)
        
        stats = {"total": len(podcasts_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, podcast_data in enumerate(podcasts_data):
            try:
                # Check for duplicates by title if requested
                if skip_duplicates:
                    # Check if podcast with same title already exists
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) as count FROM podcasts WHERE title = %s", (podcast_data["title"],))
                        result = cursor.fetchone()
                        if result and result["count"] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Create Podcast object
                podcast = Podcast(
                    title=podcast_data["title"],
                    date=podcast_data["date"],
                    script=podcast_data["script"],
                    description=podcast_data["description"]
                )
                
                # Insert podcast using repository
                PodcastRepository.insert(podcast)
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing podcast '{podcast_data.get('title', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(podcasts_data), f"Importing podcasts: {i + 1}/{len(podcasts_data)}")
        
        print(f"Podcasts import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_newsletters(self, newsletters_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import newsletters from JSON file.
        
        Args:
            newsletters_file: Path to newsletters.json file
            skip_duplicates: Whether to skip newsletters that already exist (by date range)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing newsletters...")
        
        with open(newsletters_file, 'r', encoding='utf-8') as f:
            newsletters_data = json.load(f)
        
        stats = {"total": len(newsletters_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, newsletter_data in enumerate(newsletters_data):
            try:
                # Check for duplicates by date range if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM newsletters 
                            WHERE start_date = %s AND end_date = %s
                        """, (newsletter_data["start_date"], newsletter_data["end_date"]))
                        result = cursor.fetchone()
                        if result and result["count"] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Create Newsletter object
                newsletter = Newsletter(
                    content=newsletter_data["content"],
                    start_date=newsletter_data["start_date"],
                    end_date=newsletter_data["end_date"],
                    date_sent=newsletter_data["date_sent"]
                )
                
                # Insert newsletter using repository
                NewsletterRepository.insert(newsletter)
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing newsletter {newsletter_data.get('start_date', 'Unknown')}-{newsletter_data.get('end_date', 'Unknown')}: {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(newsletters_data), f"Importing newsletters: {i + 1}/{len(newsletters_data)}")
        
        print(f"Newsletters import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_literature_reviews(self, literature_reviews_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import literature reviews from JSON file.
        
        Args:
            literature_reviews_file: Path to literature_reviews.json file
            skip_duplicates: Whether to skip literature reviews that already exist (by research question and date)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing literature reviews...")
        
        with open(literature_reviews_file, 'r', encoding='utf-8') as f:
            literature_reviews_data = json.load(f)
        
        stats = {"total": len(literature_reviews_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, review_data in enumerate(literature_reviews_data):
            try:
                # Check for duplicates by research question and creation timestamp if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM lit_reviews 
                            WHERE research_question = %s AND created_ts = %s
                        """, (review_data["research_question"], review_data["created_ts"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert literature review using repository
                LitReviewRepository.insert(
                    research_question=review_data["research_question"],
                    summary_json=review_data["summary_json"],
                    trace_json=review_data["trace_json"],
                    report_text=review_data.get("report_text")  # Optional field for backward compatibility
                )
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing literature review '{review_data.get('research_question', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(literature_reviews_data), f"Importing literature reviews: {i + 1}/{len(literature_reviews_data)}")
        
        print(f"Literature reviews import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_research_runs(self, research_runs_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import research runs from JSON file.
        
        Args:
            research_runs_file: Path to research_runs.json file
            skip_duplicates: Whether to skip research runs that already exist (by task_id)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research runs...")
        
        with open(research_runs_file, 'r', encoding='utf-8') as f:
            research_runs_data = json.load(f)
        
        stats = {"total": len(research_runs_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, run_data in enumerate(research_runs_data):
            try:
                # Check for duplicates by task_id if requested
                if skip_duplicates:
                    existing_run = ResearchRunRepository.get(run_data["task_id"])
                    if existing_run:
                        stats["skipped"] += 1
                        continue
                
                # Insert research run - use raw SQL to handle all fields including timestamps
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_runs 
                        (task_id, research_question, status, config_json, created_at, started_at,
                         completed_at, error_message, final_answer, generation_summary, statistics_json,
                         sub_queries_json, sources_gathered_json, judged_sources_json, evidence_json,
                         compressed_notes, workflow_messages_json, research_loop_count, is_sufficient, save_to_library)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        run_data["task_id"],
                        run_data["research_question"],
                        run_data["status"],
                        json.dumps(run_data.get("config")) if run_data.get("config") else None,
                        run_data["created_at"],
                        run_data.get("started_at"),
                        run_data.get("completed_at"),
                        run_data.get("error_message"),
                        run_data.get("final_answer"),
                        run_data.get("generation_summary"),
                        json.dumps(run_data.get("statistics")) if run_data.get("statistics") else None,
                        json.dumps(run_data.get("sub_queries", [])),
                        json.dumps(run_data.get("sources_gathered", [])),
                        json.dumps(run_data.get("judged_sources", [])),
                        json.dumps(run_data.get("evidence", [])),
                        run_data.get("compressed_notes"),
                        json.dumps(run_data.get("workflow_messages", [])),
                        run_data.get("research_loop_count", 0),
                        run_data.get("is_sufficient", False),
                        run_data.get("save_to_library", True)
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing research run '{run_data.get('task_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(research_runs_data), f"Importing research runs: {i + 1}/{len(research_runs_data)}")
        
        print(f"Research runs import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_research_agent_state(self, research_agent_state_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import research agent state snapshots from JSON file.
        
        Args:
            research_agent_state_file: Path to research_agent_state.json file
            skip_duplicates: Whether to skip state snapshots that already exist (by id or timestamp+task_id+node_name)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research agent state...")
        
        with open(research_agent_state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        stats = {"total": len(state_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, state_record in enumerate(state_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM research_agent_state 
                            WHERE task_id = %s AND node_name = %s AND timestamp = %s
                        """, (state_record["task_id"], state_record["node_name"], state_record["timestamp"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert state record
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_agent_state (task_id, node_name, state_json, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        state_record["task_id"],
                        state_record["node_name"],
                        state_record["state_json"],
                        state_record["timestamp"]
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing research agent state for task '{state_record.get('task_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(state_data), f"Importing research agent state: {i + 1}/{len(state_data)}")
        
        print(f"Research agent state import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_paper_fulltext(self, paper_fulltext_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import paper full-text content from JSON file.
        
        Args:
            paper_fulltext_file: Path to paper_fulltext.json file
            skip_duplicates: Whether to skip full-text entries that already exist (by paper_id)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing paper full-text content...")
        
        with open(paper_fulltext_file, 'r', encoding='utf-8') as f:
            fulltext_data = json.load(f)
        
        stats = {"total": len(fulltext_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, fulltext_record in enumerate(fulltext_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    if PaperFulltextRepository.exists(fulltext_record["paper_id"]):
                        stats["skipped"] += 1
                        continue
                
                # Convert embedding from list to pgvector format if present
                embedding_str = None
                if fulltext_record.get("embedding"):
                    try:
                        # Convert list to JSON string for pgvector
                        embedding_str = json.dumps(fulltext_record["embedding"])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for paper_id {fulltext_record['paper_id']}: {e}")
                
                # Handle metadata
                metadata_str = None
                if fulltext_record.get("metadata"):
                    try:
                        metadata_str = json.dumps(fulltext_record["metadata"]) if isinstance(fulltext_record["metadata"], dict) else fulltext_record["metadata"]
                    except:
                        metadata_str = str(fulltext_record["metadata"])
                
                # Insert full-text record using repository
                PaperFulltextRepository.insert(
                    paper_id=fulltext_record["paper_id"],
                    content=fulltext_record["content"],
                    embedding=embedding_str,
                    embedding_model=fulltext_record.get("embedding_model"),
                    extraction_method=fulltext_record.get("extraction_method", "unknown"),
                    metadata=metadata_str
                )
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing paper fulltext for paper_id '{fulltext_record.get('paper_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(fulltext_data), f"Importing paper fulltext: {i + 1}/{len(fulltext_data)}")
        
        print(f"Paper fulltext import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_mindmap_reports(self, mindmap_reports_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import mindmap reports from JSON file.
        
        Args:
            mindmap_reports_file: Path to mindmap_reports.json file
            skip_duplicates: Whether to skip mindmap reports that already exist (by title and created_at)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing mindmap reports...")
        
        with open(mindmap_reports_file, 'r', encoding='utf-8') as f:
            reports_data = json.load(f)
        
        stats = {"total": len(reports_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, report_data in enumerate(reports_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM mindmap_reports 
                            WHERE title = %s AND created_at = %s
                        """, (report_data["title"], report_data["created_at"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert mindmap report directly to preserve all original data including IDs
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO mindmap_reports 
                        (title, description, seed_paper_id, seed_paper_title, mindmap_data_json, 
                         parameters_json, statistics_json, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        report_data["title"],
                        report_data.get("description"),
                        report_data["seed_paper_id"],
                        report_data["seed_paper_title"],
                        json.dumps(report_data.get("mindmap_data", {})),
                        json.dumps(report_data.get("parameters", {})),
                        json.dumps(report_data.get("statistics", {})),
                        report_data["created_at"]
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing mindmap report '{report_data.get('title', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(reports_data), f"Importing mindmap reports: {i + 1}/{len(reports_data)}")
        
        print(f"Mindmap reports import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_model_catalog(self, model_catalog_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import model catalog entries from JSON file.
        
        Args:
            model_catalog_file: Path to model_catalog.json file
            skip_duplicates: Whether to skip model catalog entries that already exist (by alias)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing model catalog...")
        
        with open(model_catalog_file, 'r', encoding='utf-8') as f:
            catalog_data = json.load(f)
        
        stats = {"total": len(catalog_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, model_data in enumerate(catalog_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM model_catalog WHERE alias = %s", (model_data["alias"],))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert model catalog entry
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO model_catalog 
                        (alias, model_string, provider_name, model_type, description, max_new_tokens,
                         temperature, num_ctx, trust_remote_code, tags_json, is_favorite, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        model_data["alias"],
                        model_data["model_string"],
                        model_data["provider_name"],
                        model_data["model_type"],
                        model_data.get("description"),
                        model_data.get("max_new_tokens"),
                        model_data.get("temperature"),
                        model_data.get("num_ctx"),
                        model_data.get("trust_remote_code", False),
                        json.dumps(model_data.get("tags", [])),
                        model_data.get("is_favorite", False),
                        model_data.get("created_at"),
                        model_data.get("updated_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing model catalog entry '{model_data.get('alias', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(catalog_data), f"Importing model catalog: {i + 1}/{len(catalog_data)}")
        
        print(f"Model catalog import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def ensure_default_profile(self) -> int:
        """
        Ensure a default profile exists and return its ID.
        This is used for backward compatibility when importing old backups.
        
        Returns:
            ID of the default profile
        """
        with get_cursor() as cursor:
            # Check if default profile exists
            cursor.execute("SELECT id FROM research_profiles WHERE is_default = TRUE LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                return result['id']
            
            # Create default profile if it doesn't exist
            cursor.execute("""
                INSERT INTO research_profiles (name, description, is_active, is_default, created_at, updated_at)
                VALUES (%s, %s, TRUE, TRUE, NOW(), NOW())
                RETURNING id
            """, ("Default Profile", "Default research profile for backward compatibility"))
            
            default_id = cursor.fetchone()['id']
            print(f"Created default profile with ID: {default_id}")
            return default_id
    
    def _safe_deserialize_json(self, value, default=None):
        """
        Safely deserialize a value that might be a JSON string or already a Python object.
        
        Args:
            value: Value to deserialize (can be str, dict, list, or None)
            default: Default value if deserialization fails or value is None
            
        Returns:
            Deserialized Python object or default
        """
        if value is None:
            return default
        # If already a dict or list, return as-is
        if isinstance(value, (dict, list)):
            return value
        # If a string, try to parse as JSON
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Failed to parse JSON value: {value[:100] if len(value) > 100 else value}")
                return default
        # Unknown type, return default
        return default
    
    def _safe_serialize_json(self, value):
        """
        Safely serialize a value to JSON string.
        
        Args:
            value: Value to serialize (can be str, dict, list, or None)
            
        Returns:
            JSON string
        """
        if value is None:
            return None
        # If already a string, assume it's JSON and return as-is
        if isinstance(value, str):
            # Validate it's valid JSON
            try:
                json.loads(value)
                return value
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, treat as regular string and encode
                return json.dumps(value)
        # Convert dict/list to JSON string
        return json.dumps(value)
    
    def _compare_profiles(self, profile1: Dict, profile2: Dict, check_interests: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """
        Compare two profiles to determine if they are substantially the same.
        
        Compares: arxiv_filters, tags, email_recipients, and optionally research interests.
        
        Args:
            profile1: First (source) profile data dictionary
            profile2: Second (target) profile data dictionary
            check_interests: Whether to check research interests as well
            
        Returns:
            Tuple of (profiles_match: bool, comparison_details: dict)
        """
        comparison = {
            "arxiv_filters_match": True,
            "tags_match": True,
            "email_recipients_match": True,
            "interests_match": True,
            "new_interests": [],
            "existing_interests": [],
        }
        
        # Compare arxiv_filters
        filters1 = self._safe_deserialize_json(profile1.get("arxiv_filters"), {})
        filters2 = self._safe_deserialize_json(profile2.get("arxiv_filters"), {})
        if filters1 != filters2:
            logger.info(f"Profiles differ in arxiv_filters: {filters1} vs {filters2}")
            comparison["arxiv_filters_match"] = False
        
        # Compare tags
        tags1 = set(self._safe_deserialize_json(profile1.get("tags"), []) or [])
        tags2 = set(self._safe_deserialize_json(profile2.get("tags"), []) or [])
        if tags1 != tags2:
            logger.info(f"Profiles differ in tags: {tags1} vs {tags2}")
            comparison["tags_match"] = False
        
        # Compare email_recipients
        recipients1 = set(self._safe_deserialize_json(profile1.get("email_recipients"), []) or [])
        recipients2 = set(self._safe_deserialize_json(profile2.get("email_recipients"), []) or [])
        if recipients1 != recipients2:
            logger.info(f"Profiles differ in email_recipients")
            comparison["email_recipients_match"] = False
        
        # For backwards compatibility, also check interests if we have them
        if check_interests:
            source_interests = profile1.get("_interests", [])
            target_interests = profile2.get("_interests", [])
            
            if source_interests or target_interests:
                source_normalized = {i.lower().strip() for i in source_interests}
                target_normalized = {i.lower().strip() for i in target_interests}
                
                new_in_source = source_normalized - target_normalized
                comparison["new_interests"] = list(new_in_source)
                comparison["existing_interests"] = list(source_normalized & target_normalized)
                
                # Interests don't need to match for profiles to be considered "same"
                # but we track them for potential merging
        
        # Core match: arxiv_filters, tags, email_recipients must all match
        profiles_match = (
            comparison["arxiv_filters_match"] and 
            comparison["tags_match"] and 
            comparison["email_recipients_match"]
        )
        
        return profiles_match, comparison
    
    def import_research_profiles(
        self, 
        profiles_file: str, 
        skip_duplicates: bool = True, 
        progress_callback=None,
        merge_interests: bool = True,
        interests_data: List[Dict] = None
    ) -> Dict[str, int]:
        """
        Import research profiles from JSON file with smart interest merging.
        
        Args:
            profiles_file: Path to research_profiles.json file
            skip_duplicates: Whether to skip profiles that already exist (by name)
            progress_callback: Optional callback function(current, total, message)
            merge_interests: Whether to merge research interests from matched profiles
            interests_data: Pre-loaded interests data (optional, for interest merging)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research profiles...")
        
        with open(profiles_file, 'r', encoding='utf-8') as f:
            profiles_data = json.load(f)
        
        stats = {
            "total": len(profiles_data), 
            "imported": 0, 
            "skipped": 0, 
            "merged": 0,
            "interests_merged": 0,
            "errors": 0
        }
        
        # Store mapping of old profile IDs to new ones for later use
        if not hasattr(self, 'profile_id_mapping'):
            self.profile_id_mapping = {}
        
        # Track interests to be merged
        if not hasattr(self, 'interests_to_merge'):
            self.interests_to_merge = {}
        
        # Build a lookup of interests by profile ID if interests_data is provided
        interests_by_profile = {}
        if interests_data:
            for interest in interests_data:
                pid = interest.get("profile_id")
                if pid not in interests_by_profile:
                    interests_by_profile[pid] = []
                interests_by_profile[pid].append(interest.get("interest_text", ""))
        
        for i, profile_data in enumerate(profiles_data):
            try:
                old_profile_id = profile_data.get("id")
                source_interests = interests_by_profile.get(old_profile_id, [])
                
                # Special handling for Default profile
                if profile_data.get("is_default", False) or profile_data["name"] == "Default":
                    with get_cursor() as cursor:
                        # Get the existing Default profile
                        cursor.execute("""
                            SELECT id, name, description, color, tags, email_recipients, 
                                   arxiv_filters, is_active, is_default 
                            FROM research_profiles 
                            WHERE is_default = true
                        """)
                        result = cursor.fetchone()
                        if result and skip_duplicates:
                            target_id = result["id"]
                            existing_profile = {
                                "arxiv_filters": result["arxiv_filters"],
                                "tags": result["tags"],
                                "email_recipients": result["email_recipients"]
                            }
                            
                            # Get existing interests for comparison
                            cursor.execute("""
                                SELECT interest_text FROM profile_research_interests 
                                WHERE profile_id = %s
                            """, (target_id,))
                            existing_interests = [row['interest_text'] for row in cursor.fetchall()]
                            existing_profile["_interests"] = existing_interests
                            profile_data["_interests"] = source_interests
                            
                            profiles_match, comparison = self._compare_profiles(profile_data, existing_profile)
                            
                            if profiles_match:
                                # Profiles core config matches, map IDs
                                if old_profile_id:
                                    self.profile_id_mapping[old_profile_id] = target_id
                                
                                # Queue new interests for merging if enabled
                                if merge_interests and comparison.get("new_interests"):
                                    if target_id not in self.interests_to_merge:
                                        self.interests_to_merge[target_id] = []
                                    self.interests_to_merge[target_id].extend(comparison["new_interests"])
                                    stats["merged"] += 1
                                    logger.info(f"Default profile matched - will merge {len(comparison['new_interests'])} new interests")
                                else:
                                    stats["skipped"] += 1
                                
                                logger.info(f"Default profiles match - mapping source profile {old_profile_id} to existing Default profile {target_id}")
                                continue
                            else:
                                # Profiles are different, import as a new profile
                                logger.info(f"Default profiles differ - importing source Default profile as a new profile")
                                # Change the name to avoid conflict
                                profile_data["name"] = "Default (Imported)"
                                profile_data["is_default"] = False
                                # Fall through to insert logic below
                        elif result and not skip_duplicates:
                            # In overwrite mode, update the existing Default profile
                            cursor.execute("""
                                UPDATE research_profiles 
                                SET name = %s, description = %s, color = %s, tags = %s, 
                                    email_recipients = %s, arxiv_filters = %s, is_active = %s, 
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                                RETURNING id
                            """, (
                                profile_data["name"],
                                profile_data.get("description"),
                                profile_data.get("color"),
                                self._safe_serialize_json(profile_data.get("tags", [])),
                                self._safe_serialize_json(profile_data.get("email_recipients", [])),
                                self._safe_serialize_json(profile_data.get("arxiv_filters", {})),
                                profile_data.get("is_active", True),
                                result["id"]
                            ))
                            updated_result = cursor.fetchone()
                            if old_profile_id:
                                self.profile_id_mapping[old_profile_id] = updated_result["id"]
                            stats["imported"] += 1
                            logger.info(f"Updated existing Default profile with ID: {updated_result['id']}")
                            continue
                
                # Check for duplicates if requested (for non-Default profiles)
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT id, tags, email_recipients, arxiv_filters 
                            FROM research_profiles WHERE name = %s
                        """, (profile_data["name"],))
                        result = cursor.fetchone()
                        if result:
                            target_id = result["id"]
                            # Map old profile ID to existing profile ID
                            if old_profile_id:
                                self.profile_id_mapping[old_profile_id] = target_id
                            
                            # Queue interests for merging if enabled
                            if merge_interests and source_interests:
                                # Get existing interests
                                cursor.execute("""
                                    SELECT interest_text FROM profile_research_interests 
                                    WHERE profile_id = %s
                                """, (target_id,))
                                existing_interests = {row['interest_text'].lower().strip() for row in cursor.fetchall()}
                                
                                # Find new interests
                                new_interests = [
                                    i for i in source_interests 
                                    if i.lower().strip() not in existing_interests
                                ]
                                
                                if new_interests:
                                    if target_id not in self.interests_to_merge:
                                        self.interests_to_merge[target_id] = []
                                    self.interests_to_merge[target_id].extend(new_interests)
                                    stats["merged"] += 1
                                    logger.info(f"Profile '{profile_data['name']}' matched - will merge {len(new_interests)} new interests")
                                else:
                                    stats["skipped"] += 1
                            else:
                                stats["skipped"] += 1
                            continue
                
                # Insert profile
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_profiles 
                        (name, description, color, tags, email_recipients, arxiv_filters, 
                         is_active, is_default, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        profile_data["name"],
                        profile_data.get("description"),
                        profile_data.get("color"),
                        self._safe_serialize_json(profile_data.get("tags", [])),
                        self._safe_serialize_json(profile_data.get("email_recipients", [])),
                        self._safe_serialize_json(profile_data.get("arxiv_filters", {})),
                        profile_data.get("is_active", True),
                        profile_data.get("is_default", False),
                        profile_data.get("created_at"),
                        profile_data.get("updated_at")
                    ))
                    new_id = cursor.fetchone()["id"]
                    # Map old profile ID to new profile ID
                    if old_profile_id:
                        self.profile_id_mapping[old_profile_id] = new_id
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing profile '{profile_data.get('name', 'Unknown')}': {e}")
                import traceback
                traceback.print_exc()
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(profiles_data), f"Importing profiles: {i + 1}/{len(profiles_data)}")
        
        # Apply queued interest merges
        if self.interests_to_merge:
            print(f"Applying interest merges to {len(self.interests_to_merge)} profiles...")
            merge_stats = self._apply_interest_merges()
            stats["interests_merged"] = merge_stats.get("interests_added", 0)
            print(f"Merged {stats['interests_merged']} interests")
        
        print(f"Profiles import completed: {stats['imported']} imported, {stats['skipped']} skipped, "
              f"{stats['merged']} merged, {stats['interests_merged']} interests merged, {stats['errors']} errors")
        return stats
    
    def _apply_interest_merges(self) -> Dict[str, int]:
        """Apply all queued interest merges."""
        stats = {"profiles_updated": 0, "interests_added": 0, "errors": 0}
        
        for profile_id, interests in self.interests_to_merge.items():
            if not interests:
                continue
                
            try:
                with get_cursor() as cursor:
                    for interest_text in interests:
                        try:
                            # Check if already exists (case-insensitive)
                            cursor.execute("""
                                SELECT 1 FROM profile_research_interests 
                                WHERE profile_id = %s AND LOWER(interest_text) = LOWER(%s)
                            """, (profile_id, interest_text))
                            
                            if not cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO profile_research_interests 
                                    (profile_id, interest_text, created_at, updated_at)
                                    VALUES (%s, %s, NOW(), NOW())
                                """, (profile_id, interest_text))
                                stats["interests_added"] += 1
                        except Exception as e:
                            logger.warning(f"Could not add interest to profile {profile_id}: {e}")
                            stats["errors"] += 1
                
                stats["profiles_updated"] += 1
                logger.info(f"Merged interests into profile {profile_id}")
                
            except Exception as e:
                logger.error(f"Error merging interests for profile {profile_id}: {e}")
                stats["errors"] += 1
        
        # Clear the queue
        self.interests_to_merge = {}
        
        return stats
    
    def import_profile_research_interests(self, interests_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import profile research interests from JSON file.
        
        Args:
            interests_file: Path to profile_research_interests.json file
            skip_duplicates: Whether to skip interests that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing profile research interests...")
        
        with open(interests_file, 'r', encoding='utf-8') as f:
            interests_data = json.load(f)
        
        stats = {"total": len(interests_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, interest_data in enumerate(interests_data):
            try:
                # Map old profile ID to new profile ID if available
                original_profile_id = interest_data["profile_id"]
                mapped_profile_id = original_profile_id
                if hasattr(self, 'profile_id_mapping') and original_profile_id in self.profile_id_mapping:
                    mapped_profile_id = self.profile_id_mapping[original_profile_id]
                    logger.debug(f"Mapped profile ID {original_profile_id} to {mapped_profile_id}")
                
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM profile_research_interests 
                            WHERE profile_id = %s AND interest_text = %s
                        """, (mapped_profile_id, interest_data["interest_text"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Convert embedding from list to pgvector format if present
                embedding_str = None
                if interest_data.get("embedding"):
                    try:
                        embedding_str = json.dumps(interest_data["embedding"])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for interest: {e}")
                
                # Insert interest
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO profile_research_interests
                        (profile_id, interest_text, embedding, embedding_model, short_label, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        mapped_profile_id,
                        interest_data["interest_text"],
                        embedding_str,
                        interest_data.get("embedding_model"),
                        interest_data.get("short_label"),
                        interest_data.get("created_at"),
                        interest_data.get("updated_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing profile interest: {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(interests_data), f"Importing profile interests: {i + 1}/{len(interests_data)}")
        
        print(f"Profile interests import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_paper_profile_scores(self, scores_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import paper profile scores from JSON file using bulk COPY for efficiency.
        
        Args:
            scores_file: Path to paper_profile_scores.json file
            skip_duplicates: Whether to skip scores that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing paper profile scores...")
        
        with open(scores_file, 'r', encoding='utf-8') as f:
            scores_data = json.load(f)
        
        # Apply profile ID mapping if available
        if hasattr(self, 'profile_id_mapping') and self.profile_id_mapping:
            for score_data in scores_data:
                original_profile_id = score_data["profile_id"]
                if original_profile_id in self.profile_id_mapping:
                    score_data["profile_id"] = self.profile_id_mapping[original_profile_id]
                    logger.debug(f"Mapped profile ID {original_profile_id} to {score_data['profile_id']}")
        
        # Use bulk COPY import for efficiency (500k+ records)
        columns = ["paper_id", "profile_id", "score", "related", "rationale", "date_scored", "judge_model"]
        unique_columns = ["paper_id", "profile_id"]
        
        try:
            stats = self._import_with_copy(
                "paper_profile_scores",
                scores_data,
                columns,
                skip_duplicates=skip_duplicates,
                unique_columns=unique_columns,
                progress_callback=progress_callback
            )
            print(f"Paper profile scores import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
            return stats
        except Exception as e:
            print(f"Error during bulk import of paper profile scores: {e}")
            # Fall back to row-by-row import if bulk fails
            print("Falling back to row-by-row import...")
            return self._import_paper_profile_scores_fallback(scores_data, skip_duplicates, progress_callback)
    
    def _import_paper_profile_scores_fallback(self, scores_data: List[Dict], skip_duplicates: bool, progress_callback=None) -> Dict[str, int]:
        """Fallback method for importing paper profile scores row-by-row."""
        stats = {"total": len(scores_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, score_data in enumerate(scores_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM paper_profile_scores 
                            WHERE paper_id = %s AND profile_id = %s
                        """, (score_data["paper_id"], score_data["profile_id"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert score
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO paper_profile_scores 
                        (paper_id, profile_id, score, related, rationale, date_scored, judge_model)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        score_data["paper_id"],
                        score_data["profile_id"],
                        score_data.get("score"),
                        score_data.get("related"),
                        score_data.get("rationale"),
                        score_data.get("date_scored"),
                        score_data.get("judge_model")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing paper profile score: {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(scores_data), f"Importing paper profile scores: {i + 1}/{len(scores_data)}")
        
        print(f"Paper profile scores import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_topics(self, topics_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import topics from JSON file.
        
        Args:
            topics_file: Path to topics.json file
            skip_duplicates: Whether to skip topics that already exist (by label)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing topics...")
        
        with open(topics_file, 'r', encoding='utf-8') as f:
            topics_data = json.load(f)
        
        stats = {"total": len(topics_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, topic_data in enumerate(topics_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM topics WHERE label = %s", (topic_data["label"],))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Convert embedding from list to pgvector format if present
                embedding_str = None
                if topic_data.get("centroid_embedding"):
                    try:
                        embedding_str = json.dumps(topic_data["centroid_embedding"])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for topic {topic_data['label']}: {e}")
                
                # Insert topic
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO topics (label, keywords, centroid_embedding, embedding_model, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        topic_data["label"],
                        topic_data.get("keywords", []),
                        embedding_str,
                        topic_data.get("embedding_model"),
                        topic_data.get("created_at"),
                        topic_data.get("updated_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing topic '{topic_data.get('label', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(topics_data), f"Importing topics: {i + 1}/{len(topics_data)}")
        
        print(f"Topics import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_topic_metrics(self, topic_metrics_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import topic metrics from JSON file.
        
        Args:
            topic_metrics_file: Path to topic_metrics.json file
            skip_duplicates: Whether to skip topic metrics that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing topic metrics...")
        
        with open(topic_metrics_file, 'r', encoding='utf-8') as f:
            metrics_data = json.load(f)
        
        stats = {"total": len(metrics_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, metric_data in enumerate(metrics_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM topic_metrics 
                            WHERE topic_id = %s AND period_start = %s AND period_end = %s AND period_type = %s
                        """, (metric_data["topic_id"], metric_data["period_start"], 
                              metric_data["period_end"], metric_data["period_type"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert topic metric
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO topic_metrics 
                        (topic_id, period_start, period_end, period_type, doc_count, avg_score, 
                         growth_rate, forecast_1m, forecast_3m, forecast_6m, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        metric_data["topic_id"],
                        metric_data["period_start"],
                        metric_data["period_end"],
                        metric_data["period_type"],
                        metric_data["doc_count"],
                        metric_data.get("avg_score"),
                        metric_data.get("growth_rate"),
                        metric_data.get("forecast_1m"),
                        metric_data.get("forecast_3m"),
                        metric_data.get("forecast_6m"),
                        metric_data.get("created_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing topic metric for topic_id '{metric_data.get('topic_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(metrics_data), f"Importing topic metrics: {i + 1}/{len(metrics_data)}")
        
        print(f"Topic metrics import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_paper_topics(self, paper_topics_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import paper-topic relationships from JSON file.
        
        Args:
            paper_topics_file: Path to paper_topics.json file
            skip_duplicates: Whether to skip relationships that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing paper-topic relationships...")
        
        with open(paper_topics_file, 'r', encoding='utf-8') as f:
            relationships_data = json.load(f)
        
        stats = {"total": len(relationships_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, rel_data in enumerate(relationships_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM paper_topics 
                            WHERE paper_id = %s AND topic_id = %s
                        """, (rel_data["paper_id"], rel_data["topic_id"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert paper-topic relationship
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO paper_topics (paper_id, topic_id, relevance_score, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        rel_data["paper_id"],
                        rel_data["topic_id"],
                        rel_data.get("relevance_score", 0.0),
                        rel_data.get("created_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing paper-topic relationship for paper_id '{rel_data.get('paper_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(relationships_data), f"Importing paper-topic relationships: {i + 1}/{len(relationships_data)}")
        
        print(f"Paper-topic relationships import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_research_interests(self, research_interests_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import research interests from JSON file.
        
        Args:
            research_interests_file: Path to research_interests.json file
            skip_duplicates: Whether to skip research interests that already exist (by interest_text)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research interests...")
        
        with open(research_interests_file, 'r', encoding='utf-8') as f:
            interests_data = json.load(f)
        
        stats = {"total": len(interests_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, interest_data in enumerate(interests_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM research_interests WHERE interest_text = %s", 
                                     (interest_data["interest_text"],))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Convert embedding from list to pgvector format if present
                embedding_str = None
                if interest_data.get("embedding"):
                    try:
                        embedding_str = json.dumps(interest_data["embedding"])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for research interest {interest_data['interest_text']}: {e}")
                
                # Insert research interest
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_interests (interest_text, embedding, embedding_model, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        interest_data["interest_text"],
                        embedding_str,
                        interest_data.get("embedding_model"),
                        interest_data.get("created_at"),
                        interest_data.get("updated_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing research interest '{interest_data.get('interest_text', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(interests_data), f"Importing research interests: {i + 1}/{len(interests_data)}")
        
        print(f"Research interests import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_research_interest_metrics(self, research_interest_metrics_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import research interest metrics from JSON file.
        
        Args:
            research_interest_metrics_file: Path to research_interest_metrics.json file
            skip_duplicates: Whether to skip metrics that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research interest metrics...")
        
        with open(research_interest_metrics_file, 'r', encoding='utf-8') as f:
            metrics_data = json.load(f)
        
        stats = {"total": len(metrics_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, metric_data in enumerate(metrics_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM research_interest_metrics 
                            WHERE research_interest_id = %s AND period_start = %s AND period_end = %s AND period_type = %s
                        """, (metric_data["research_interest_id"], metric_data["period_start"], 
                              metric_data["period_end"], metric_data["period_type"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert research interest metric
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_interest_metrics 
                        (research_interest_id, period_start, period_end, period_type, doc_count, 
                         avg_relevance_score, avg_paper_score, growth_rate, forecast_1m, forecast_3m, forecast_6m, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        metric_data["research_interest_id"],
                        metric_data["period_start"],
                        metric_data["period_end"],
                        metric_data["period_type"],
                        metric_data["doc_count"],
                        metric_data.get("avg_relevance_score"),
                        metric_data.get("avg_paper_score"),
                        metric_data.get("growth_rate"),
                        metric_data.get("forecast_1m"),
                        metric_data.get("forecast_3m"),
                        metric_data.get("forecast_6m"),
                        metric_data.get("created_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing research interest metric for research_interest_id '{metric_data.get('research_interest_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(metrics_data), f"Importing research interest metrics: {i + 1}/{len(metrics_data)}")
        
        print(f"Research interest metrics import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_paper_research_interests(self, paper_research_interests_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import paper-research interest relationships from JSON file.
        
        Args:
            paper_research_interests_file: Path to paper_research_interests.json file
            skip_duplicates: Whether to skip relationships that already exist
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing paper-research interest relationships...")
        
        with open(paper_research_interests_file, 'r', encoding='utf-8') as f:
            relationships_data = json.load(f)
        
        stats = {"total": len(relationships_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, rel_data in enumerate(relationships_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM paper_research_interests 
                            WHERE paper_id = %s AND research_interest_id = %s
                        """, (rel_data["paper_id"], rel_data["research_interest_id"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert paper-research interest relationship
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO paper_research_interests (paper_id, research_interest_id, similarity_score, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        rel_data["paper_id"],
                        rel_data["research_interest_id"],
                        rel_data.get("similarity_score", 0.0),
                        rel_data.get("created_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing paper-research interest relationship for paper_id '{rel_data.get('paper_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(relationships_data), f"Importing paper-research interest relationships: {i + 1}/{len(relationships_data)}")
        
        print(f"Paper-research interest relationships import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_profile_paper_interests(self, profile_paper_interests_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import profile paper-interest relationships from JSON file.

        Args:
            profile_paper_interests_file: Path to profile_paper_interests.json file
            skip_duplicates: Whether to skip relationships that already exist
            progress_callback: Optional callback function(current, total, message)

        Returns:
            Dictionary with import statistics
        """
        print("Importing profile paper-interest relationships...")

        with open(profile_paper_interests_file, 'r', encoding='utf-8') as f:
            relationships_data = json.load(f)

        stats = {"total": len(relationships_data), "imported": 0, "skipped": 0, "errors": 0}

        for i, rel_data in enumerate(relationships_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM profile_paper_interests
                            WHERE paper_id = %s AND profile_interest_id = %s
                        """, (rel_data["paper_id"], rel_data["profile_interest_id"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue

                # Insert profile paper-interest relationship
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO profile_paper_interests (paper_id, profile_interest_id, similarity_score, created_at)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        rel_data["paper_id"],
                        rel_data["profile_interest_id"],
                        rel_data.get("similarity_score", 0.0),
                        rel_data.get("created_at")
                    ))

                stats["imported"] += 1

            except Exception as e:
                print(f"Error importing profile paper-interest relationship for paper_id '{rel_data.get('paper_id', 'Unknown')}': {e}")
                stats["errors"] += 1

            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(relationships_data), f"Importing profile paper-interest relationships: {i + 1}/{len(relationships_data)}")

        print(f"Profile paper-interest relationships import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_profile_interest_metrics(self, profile_interest_metrics_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import profile interest metrics from JSON file.

        Args:
            profile_interest_metrics_file: Path to profile_interest_metrics.json file
            skip_duplicates: Whether to skip metrics that already exist
            progress_callback: Optional callback function(current, total, message)

        Returns:
            Dictionary with import statistics
        """
        print("Importing profile interest metrics...")

        with open(profile_interest_metrics_file, 'r', encoding='utf-8') as f:
            metrics_data = json.load(f)

        stats = {"total": len(metrics_data), "imported": 0, "skipped": 0, "errors": 0}

        for i, metric_data in enumerate(metrics_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM profile_interest_metrics
                            WHERE profile_interest_id = %s AND period_start = %s AND period_type = %s
                        """, (metric_data["profile_interest_id"], metric_data["period_start"], metric_data["period_type"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue

                # Insert profile interest metric
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO profile_interest_metrics (
                            profile_interest_id, period_start, period_end, period_type,
                            doc_count, avg_relevance_score, avg_paper_score, growth_rate, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        metric_data["profile_interest_id"],
                        metric_data["period_start"],
                        metric_data["period_end"],
                        metric_data["period_type"],
                        metric_data.get("doc_count", 0),
                        metric_data.get("avg_relevance_score"),
                        metric_data.get("avg_paper_score"),
                        metric_data.get("growth_rate"),
                        metric_data.get("created_at")
                    ))

                stats["imported"] += 1

            except Exception as e:
                print(f"Error importing profile interest metric for interest_id '{metric_data.get('profile_interest_id', 'Unknown')}': {e}")
                stats["errors"] += 1

            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(metrics_data), f"Importing profile interest metrics: {i + 1}/{len(metrics_data)}")

        print(f"Profile interest metrics import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_label_summaries(self, label_summaries_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import label summaries from JSON file.
        
        Args:
            label_summaries_file: Path to label_summaries.json file
            skip_duplicates: Whether to skip label summaries that already exist (by original_label)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing label summaries...")
        
        with open(label_summaries_file, 'r', encoding='utf-8') as f:
            summaries_data = json.load(f)
        
        stats = {"total": len(summaries_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, summary_data in enumerate(summaries_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM label_summaries WHERE original_label = %s", 
                                     (summary_data["original_label"],))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert label summary
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO label_summaries (original_label, summarized_label, model_used, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        summary_data["original_label"],
                        summary_data["summarized_label"],
                        summary_data.get("model_used"),
                        summary_data.get("created_at"),
                        summary_data.get("updated_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing label summary '{summary_data.get('original_label', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(summaries_data), f"Importing label summaries: {i + 1}/{len(summaries_data)}")
        
        print(f"Label summaries import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def import_scheduled_tasks(self, scheduled_tasks_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """Import scheduled tasks configuration."""
        print(f"Importing scheduled tasks from {scheduled_tasks_file}...")
        
        with open(scheduled_tasks_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
        
        imported_count = 0
        skipped_count = 0
        
        with get_cursor() as cursor:
            for i, task in enumerate(tasks):
                if progress_callback:
                    progress_callback(i, len(tasks), f"Importing scheduled task {i+1}/{len(tasks)}")
                
                # Check if task already exists by name
                if skip_duplicates:
                    cursor.execute(
                        "SELECT id FROM scheduled_tasks WHERE name = %s",
                        (task['name'],)
                    )
                    if cursor.fetchone():
                        skipped_count += 1
                        continue
                
                # Insert scheduled task
                cursor.execute("""
                    INSERT INTO scheduled_tasks (
                        name, task_type, profile_id, is_enabled, frequency,
                        day_of_week, day_of_month, hour, minute, timezone,
                        config, last_run_at, next_run_at, last_run_status,
                        last_run_task_id, run_count, error_count,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    task['name'],
                    task['task_type'],
                    task.get('profile_id'),
                    task.get('is_enabled', True),
                    task['frequency'],
                    task.get('day_of_week'),
                    task.get('day_of_month'),
                    task['hour'],
                    task.get('minute', 0),
                    task.get('timezone', 'UTC'),
                    json.dumps(task.get('config', {})),
                    task.get('last_run_at'),
                    task.get('next_run_at'),
                    task.get('last_run_status'),
                    task.get('last_run_task_id'),
                    task.get('run_count', 0),
                    task.get('error_count', 0),
                    task.get('created_at'),
                    task.get('updated_at')
                ))
                imported_count += 1
        
        print(f"Imported {imported_count} scheduled tasks, skipped {skipped_count}")
        
        return {"imported": imported_count, "skipped": skipped_count, "errors": 0}
    
    def import_scheduled_task_runs(self, scheduled_task_runs_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """Import scheduled task run history."""
        print(f"Importing scheduled task runs from {scheduled_task_runs_file}...")
        
        with open(scheduled_task_runs_file, 'r', encoding='utf-8') as f:
            runs = json.load(f)
        
        imported_count = 0
        skipped_count = 0
        
        with get_cursor() as cursor:
            for i, run in enumerate(runs):
                if progress_callback:
                    progress_callback(i, len(runs), f"Importing task run {i+1}/{len(runs)}")
                
                # Check if run already exists by task_id
                if skip_duplicates:
                    cursor.execute(
                        "SELECT id FROM scheduled_task_runs WHERE task_id = %s",
                        (run['task_id'],)
                    )
                    if cursor.fetchone():
                        skipped_count += 1
                        continue
                
                # Insert task run
                cursor.execute("""
                    INSERT INTO scheduled_task_runs (
                        scheduled_task_id, task_id, started_at, completed_at,
                        status, error_message, result
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    run['scheduled_task_id'],
                    run['task_id'],
                    run['started_at'],
                    run.get('completed_at'),
                    run['status'],
                    run.get('error_message'),
                    json.dumps(run.get('result')) if run.get('result') else None
                ))
                imported_count += 1
        
        print(f"Imported {imported_count} scheduled task runs, skipped {skipped_count}")
        
        return {"imported": imported_count, "skipped": skipped_count, "errors": 0}

    def import_from_directory(
        self,
        input_dir: str,
        skip_duplicates: bool = True,
        progress_callback=None,
        mapping_strategy: str = "auto",
        merge_to_profile_id: int = None,
        create_new_profile_name: str = None,
        merge_interests: bool = True
    ) -> Dict[str, Any]:
        """
        Import all data from a directory containing JSON files.

        Args:
            input_dir: Directory containing the JSON files
            skip_duplicates: Whether to skip duplicate entries
            progress_callback: Optional callback function(current, total, message)
            mapping_strategy: Profile mapping strategy for profile-scoped imports
            merge_to_profile_id: Target profile ID for merge_to strategy
            create_new_profile_name: Override profile name for create_new strategy
            merge_interests: Whether to merge research interests when profiles match

        Returns:
            Dictionary with import results
        """
        input_path = Path(input_dir)

        # Validate metadata if present
        metadata_file = input_path / "metadata.json"
        is_profile_scoped = False
        profile_mapper = None
        fk_remapper = ForeignKeyRemapper()

        if metadata_file.exists():
            if not self.validate_metadata(str(metadata_file)):
                print("Warning: Metadata validation failed, continuing anyway...")

            # Check if this is a profile-scoped import
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                export_type = metadata.get("export_type")

                if export_type == "profile_scoped":
                    is_profile_scoped = True
                    print(f"Detected profile-scoped export (version {metadata.get('export_version', 'unknown')})")
                    print(f"Mapping strategy: {mapping_strategy}")

                    # Initialize profile mapper with merge_interests setting
                    profile_mapper = ProfileMapper(self.db_path, merge_interests=merge_interests)

            # Check for required migrations
            migration_info = self.validation_results.get("migration_required")
            if migration_info:
                if self.auto_migrate:
                    print("Auto-migration enabled, applying required migrations...")
                    if not self.apply_migrations(migration_info):
                        raise ValueError("Migration failed, cannot proceed with import")
                elif not self.dry_run:
                    print("Migration required but auto-migrate not enabled.")
                    print("Use --auto-migrate flag or manually apply migrations before importing.")
                    raise ValueError("Schema migration required before import")

        results = {}
        current_step = 0
        
        # Check what files are available
        available_files = []
        file_map = {
            "research_profiles": "research_profiles.json",  # Import profiles first
            "papers": "papers.json",
            "profile_research_interests": "profile_research_interests.json",
            "paper_profile_scores": "paper_profile_scores.json",
            "podcasts": "podcasts.json", 
            "newsletters": "newsletters.json",
            "literature_reviews": "literature_reviews.json",
            "research_runs": "research_runs.json",
            "research_agent_state": "research_agent_state.json",
            "paper_fulltext": "paper_fulltext.json",
            "mindmap_reports": "mindmap_reports.json",
            "model_catalog": "model_catalog.json",
            "topics": "topics.json",
            "topic_metrics": "topic_metrics.json",
            "paper_topics": "paper_topics.json",
            "research_interests": "research_interests.json",
            "research_interest_metrics": "research_interest_metrics.json",
            "paper_research_interests": "paper_research_interests.json",
            "profile_paper_interests": "profile_paper_interests.json",
            "profile_interest_metrics": "profile_interest_metrics.json",
            "label_summaries": "label_summaries.json",
            "scheduled_tasks": "scheduled_tasks.json",
            "scheduled_task_runs": "scheduled_task_runs.json"
        }

        for table_name, filename in file_map.items():
            if (input_path / filename).exists():
                available_files.append(table_name)
        
        total_steps = len(available_files)
        
        # Pre-load interests data for smart profile merging
        interests_data = None
        interests_file = input_path / "profile_research_interests.json"
        if interests_file.exists() and merge_interests:
            try:
                with open(interests_file, 'r') as f:
                    interests_data = json.load(f)
                print(f"Pre-loaded {len(interests_data)} research interests for smart merging")
            except Exception as e:
                print(f"Warning: Could not pre-load interests data: {e}")
        
        # Helper function to create progress callback for each import
        def create_progress_callback(step_index, table_name):
            def table_progress_callback(current, total, message):
                if progress_callback:
                    # Calculate overall progress: each table gets equal weight
                    step_progress = (current / total) * (100 / total_steps)
                    overall_progress = int((step_index / total_steps) * 100 + step_progress)
                    progress_callback(overall_progress, 100, f"{table_name}: {message}")
            return table_progress_callback
        
        # Import each available table
        for i, table_name in enumerate(available_files):
            filename = file_map[table_name]
            file_path = input_path / filename
            
            if progress_callback:
                progress_callback(int((i / total_steps) * 100), 100, f"Starting {table_name} import...")
            
            try:
                if table_name == "research_profiles":
                    # Handle profile mapping for profile-scoped imports
                    if is_profile_scoped and profile_mapper:
                        with open(file_path, 'r') as f:
                            profiles_data = json.load(f)

                        # Build interests lookup by profile ID
                        interests_by_profile = {}
                        if interests_data:
                            for interest in interests_data:
                                pid = interest.get("profile_id")
                                if pid not in interests_by_profile:
                                    interests_by_profile[pid] = []
                                interests_by_profile[pid].append(interest.get("interest_text", ""))

                        # Map each profile with its interests
                        for profile in profiles_data:
                            source_interests = interests_by_profile.get(profile['id'], [])
                            target_id = profile_mapper.map_profile(
                                profile,
                                strategy=mapping_strategy,
                                target_profile_id=merge_to_profile_id,
                                create_new_profile_name=create_new_profile_name,
                                source_interests=source_interests
                            )
                            fk_remapper.add_mapping("research_profiles", profile['id'], target_id)
                            print(f"Mapped profile '{profile['name']}' (ID {profile['id']}) → Target ID {target_id}")

                        # Apply queued interest merges
                        if profile_mapper.interests_to_merge:
                            merge_stats = profile_mapper.apply_queued_interest_merges()
                            results["interests_merged"] = merge_stats

                        results[table_name] = {
                            "imported": len(profiles_data),
                            "skipped": 0,
                            "mapped": True,
                            "merge_log": profile_mapper.get_merge_log()
                        }
                    else:
                        # Non-profile-scoped import with smart interest merging
                        results[table_name] = self.import_research_profiles(
                            str(file_path), 
                            skip_duplicates, 
                            create_progress_callback(i, table_name),
                            merge_interests=merge_interests,
                            interests_data=interests_data
                        )
                elif table_name == "papers":
                    # Track paper ID mappings for foreign key remapping
                    papers_result = self.import_papers(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                    results[table_name] = papers_result

                    # If we have imported papers and need to track mappings, load the mappings
                    # Note: import_papers may update IDs, we'll need to track old→new mappings
                    # For now, we'll handle this in the FK remapping for dependent tables

                elif table_name == "profile_research_interests":
                    # Remap foreign keys if this is a profile-scoped import
                    if is_profile_scoped and fk_remapper:
                        with open(file_path, 'r') as f:
                            interests_data = json.load(f)

                        # Remap profile_ids
                        remapped_data = fk_remapper.remap_foreign_keys(interests_data, "profile_research_interests")

                        # Write remapped data to temp file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                            json.dump(remapped_data, tmp_file, indent=2)
                            tmp_path = tmp_file.name

                        try:
                            results[table_name] = self.import_profile_research_interests(
                                tmp_path, skip_duplicates, create_progress_callback(i, table_name)
                            )
                        finally:
                            os.unlink(tmp_path)
                    else:
                        results[table_name] = self.import_profile_research_interests(
                            str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                        )

                elif table_name == "paper_profile_scores":
                    # Remap foreign keys if this is a profile-scoped import
                    if is_profile_scoped and fk_remapper:
                        with open(file_path, 'r') as f:
                            scores_data = json.load(f)

                        # Remap profile_ids and paper_ids
                        remapped_data = fk_remapper.remap_foreign_keys(scores_data, "paper_profile_scores")

                        # Write remapped data to temp file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                            json.dump(remapped_data, tmp_file, indent=2)
                            tmp_path = tmp_file.name

                        try:
                            results[table_name] = self.import_paper_profile_scores(
                                tmp_path, skip_duplicates, create_progress_callback(i, table_name)
                            )
                        finally:
                            os.unlink(tmp_path)
                    else:
                        results[table_name] = self.import_paper_profile_scores(
                            str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                        )
                elif table_name == "podcasts":
                    results[table_name] = self.import_podcasts(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "newsletters":
                    results[table_name] = self.import_newsletters(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "literature_reviews":
                    results[table_name] = self.import_literature_reviews(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "research_runs":
                    results[table_name] = self.import_research_runs(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "research_agent_state":
                    results[table_name] = self.import_research_agent_state(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "paper_fulltext":
                    results[table_name] = self.import_paper_fulltext(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "mindmap_reports":
                    results[table_name] = self.import_mindmap_reports(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "model_catalog":
                    results[table_name] = self.import_model_catalog(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "topics":
                    results[table_name] = self.import_topics(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "topic_metrics":
                    results[table_name] = self.import_topic_metrics(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "paper_topics":
                    results[table_name] = self.import_paper_topics(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "research_interests":
                    results[table_name] = self.import_research_interests(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "research_interest_metrics":
                    results[table_name] = self.import_research_interest_metrics(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "paper_research_interests":
                    results[table_name] = self.import_paper_research_interests(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "profile_paper_interests":
                    results[table_name] = self.import_profile_paper_interests(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "profile_interest_metrics":
                    results[table_name] = self.import_profile_interest_metrics(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "label_summaries":
                    results[table_name] = self.import_label_summaries(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "scheduled_tasks":
                    results[table_name] = self.import_scheduled_tasks(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "scheduled_task_runs":
                    results[table_name] = self.import_scheduled_task_runs(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
            except Exception as e:
                print(f"Error importing {table_name}: {e}")
                results[table_name] = {"error": str(e)}
        
        # Handle missing files with informative messages
        for table_name, filename in file_map.items():
            if table_name not in results:
                if table_name in ["papers", "podcasts", "newsletters"]:
                    print(f"Warning: {filename} not found")
                    results[table_name] = {"error": "File not found"}
                else:
                    print(f"Note: {filename} not found (this is optional for older exports)")
                    results[table_name] = {"note": "File not found (optional)"}

        # Add profile mapping info if this was a profile-scoped import
        if is_profile_scoped and profile_mapper:
            results["profile_mapping"] = profile_mapper.id_mappings
            print(f"\nProfile mapping summary:")
            for source_id, target_id in profile_mapper.id_mappings.items():
                print(f"  Source profile {source_id} → Target profile {target_id}")

        if progress_callback:
            progress_callback(100, 100, "Import completed!")

        return results

    def import_from_archive(
        self, 
        archive_path: str, 
        skip_duplicates: bool = True, 
        progress_callback=None,
        merge_interests: bool = True
    ) -> Dict[str, Any]:
        """
        Import all data from a tar.gz archive.
        
        Args:
            archive_path: Path to the tar.gz archive
            skip_duplicates: Whether to skip duplicate entries
            progress_callback: Optional callback function(current, total, message)
            merge_interests: Whether to merge research interests when profiles match
            
        Returns:
            Dictionary with import results
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            if progress_callback:
                progress_callback(0, 100, "Extracting archive...")
            extract_dir = self.extract_archive(archive_path, temp_dir)
            if progress_callback:
                progress_callback(10, 100, "Archive extracted, starting import...")
            
            # Adjust progress callback to account for extraction taking 10%
            def adjusted_progress_callback(current, total, message):
                if progress_callback:
                    # Map 0-100% import progress to 10-100% overall progress
                    adjusted_progress = 10 + int((current / total) * 90)
                    progress_callback(adjusted_progress, 100, message)
            
            return self.import_from_directory(
                extract_dir, 
                skip_duplicates, 
                adjusted_progress_callback,
                merge_interests=merge_interests
            )
    
    def import_tables_parallel(
        self,
        input_dir: str,
        skip_duplicates: bool = True,
        max_workers: int = 4,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Import tables in parallel respecting dependencies.
        
        Args:
            input_dir: Directory containing import files
            skip_duplicates: Whether to skip duplicates
            max_workers: Maximum parallel workers
            progress_callback: Optional progress callback
            
        Returns:
            Import results
        """
        if not PARALLEL_AVAILABLE:
            logger.warning("Parallel processing not available, falling back to sequential import")
            return self.import_from_directory(input_dir, skip_duplicates, progress_callback)
        
        input_path = Path(input_dir)
        
        # Build file map
        file_map = {}
        table_files = {
            "research_profiles": "research_profiles.json",
            "papers": "papers.json",
            "profile_research_interests": "profile_research_interests.json",
            "paper_profile_scores": "paper_profile_scores.json",
            "podcasts": "podcasts.json",
            "newsletters": "newsletters.json",
            "literature_reviews": "literature_reviews.json"
        }
        
        for table, filename in table_files.items():
            file_path = input_path / filename
            if file_path.exists():
                file_map[table] = str(file_path)
        
        # Use parallel importer
        parallel_importer = ParallelImporter(self, max_workers)
        return parallel_importer.import_tables_parallel(
            file_map, skip_duplicates, progress_callback
        )
    
    def import_incremental(self, input_path: str) -> Dict[str, Any]:
        """
        Import incremental data using delta processing and UPSERT operations.
        
        Args:
            input_path: Path to incremental export directory or archive
            
        Returns:
            Import results with delta statistics
        """
        try:
            from .incremental_ops import IncrementalImporter
        except ImportError:
            raise RuntimeError("Incremental import functionality not available")
        
        logger.info(f"Starting incremental import from {input_path}")
        
        # Create incremental importer
        incremental_importer = IncrementalImporter(self.db_path)
        
        # Detect if this is an incremental export
        if not incremental_importer.detect_incremental_import(input_path):
            raise ValueError("Input does not appear to be an incremental export")
        
        # Handle archive extraction if needed
        import_dir = input_path
        temp_dir = None
        
        if Path(input_path).suffix == ".gz":
            import tempfile
            temp_dir = tempfile.mkdtemp()
            import_dir = self.extract_archive(input_path, temp_dir)
        
        try:
            # Validate metadata and check for migrations
            metadata_file = Path(import_dir) / "metadata.json"
            if metadata_file.exists():
                if not self.validate_metadata(str(metadata_file)):
                    logger.warning("Metadata validation failed for incremental import")
                
                # Check for required migrations
                migration_info = self.validation_results.get("migration_required")
                if migration_info:
                    if self.auto_migrate:
                        logger.info("Auto-migration enabled for incremental import")
                        if not self.apply_migrations(migration_info):
                            raise ValueError("Migration failed, cannot proceed with incremental import")
                    elif not self.dry_run:
                        raise ValueError("Schema migration required before incremental import")
            
            # Perform incremental import
            results = incremental_importer.import_incremental(import_dir, self.merge_strategy)
            
            # Add validation info to results
            results["validation_results"] = self.validation_results
            
            logger.info(f"Incremental import completed: {results.get('total_stats', {})}")
            return results
            
        finally:
            # Clean up temporary directory
            if temp_dir:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def import_all(
        self,
        input_path: str,
        skip_duplicates: bool = True,
        parallel: bool = False,
        max_workers: int = 4,
        mapping_strategy: str = "auto",
        merge_to_profile_id: int = None,
        create_new_profile_name: str = None,
        merge_interests: bool = True
    ) -> Dict[str, Any]:
        """
        Import data from either a directory or archive.

        Args:
            input_path: Path to directory or tar.gz archive
            skip_duplicates: Whether to skip duplicate entries
            parallel: Whether to use parallel processing
            max_workers: Maximum parallel workers
            mapping_strategy: Profile mapping strategy for profile-scoped imports
            merge_to_profile_id: Target profile ID for merge_to strategy
            create_new_profile_name: Override profile name for create_new strategy
            merge_interests: Whether to merge research interests when profiles match

        Returns:
            Dictionary with import results
        """
        # Auto-detect incremental imports
        try:
            from .incremental_ops import IncrementalImporter
            incremental_importer = IncrementalImporter(self.db_path)

            if incremental_importer.detect_incremental_import(input_path):
                print(f"Detected incremental import: {input_path}")
                return self.import_incremental(input_path)
        except ImportError:
            logger.debug("Incremental import detection not available")

        input_path_obj = Path(input_path)

        if input_path_obj.is_dir():
            print(f"Importing from directory: {input_path}")
            if parallel:
                print(f"Using parallel import with {max_workers} workers")
                return self.import_tables_parallel(input_path, skip_duplicates, max_workers)
            else:
                return self.import_from_directory(
                    input_path,
                    skip_duplicates,
                    mapping_strategy=mapping_strategy,
                    merge_to_profile_id=merge_to_profile_id,
                    create_new_profile_name=create_new_profile_name,
                    merge_interests=merge_interests
                )
        elif input_path_obj.suffix == ".gz" and input_path_obj.name.endswith(".tar.gz"):
            print(f"Importing from archive: {input_path}")
            # Extract first then decide on parallel
            with tempfile.TemporaryDirectory() as temp_dir:
                extract_dir = self.extract_archive(input_path, temp_dir)
                if parallel:
                    print(f"Using parallel import with {max_workers} workers")
                    return self.import_tables_parallel(extract_dir, skip_duplicates, max_workers)
                else:
                    return self.import_from_directory(
                        extract_dir,
                        skip_duplicates,
                        mapping_strategy=mapping_strategy,
                        merge_to_profile_id=merge_to_profile_id,
                        create_new_profile_name=create_new_profile_name,
                        merge_interests=merge_interests
                    )
        else:
            raise ValueError(f"Input path must be a directory or .tar.gz archive: {input_path}")

    def clear_all_data(self, progress_callback=None) -> Dict[str, int]:
        """
        Clear all data from the main tables.
        WARNING: This is destructive and cannot be undone.
        
        Args:
            progress_callback: Optional callback function(current, total, message)
        
        Returns:
            Dictionary with counts of deleted records for each table
        """
        print("WARNING: Clearing all data from database tables...")
        
        # Tables to clear in order (respecting foreign key constraints)
        # Order: Child tables first, then parent tables
        # Foreign key relationships documented inline
        tables_to_clear = [
            # System/logging tables (no FK dependencies)
            'logs', 
            'error_logs',
            'tasks',
            
            # Worker management (depends on processing_jobs)
            'worker_heartbeats',  # FK: processing_jobs.id
            'judge_task_queue',   # FK: processing_jobs.id, papers.id, research_profiles.id
            
            # Processing jobs (depends on nothing in this list)
            'processing_jobs',

            # Inference servers (no FK dependencies) - renamed from ollama_servers
            'inference_servers',

            # Scheduled tasks (depends on research_profiles)
            'scheduled_task_runs',  # FK: scheduled_tasks.id
            'scheduled_tasks',      # FK: research_profiles.id
            
            # Research agent (depends on research_runs)
            'research_agent_state',  # FK: research_runs.task_id
            'research_runs',
            
            # Content tables (mostly depend on papers)
            'lit_reviews',
            'mindmap_reports',       # FK: papers.id
            'model_catalog',
            'paper_fulltext',        # FK: papers.id
            'newsletters',
            'podcasts',
            
            # Topics and relationships (depend on papers, topics, research_profiles)
            'paper_topics',          # FK: papers.id, topics.id
            'topic_metrics',         # FK: topics.id, research_profiles.id
            'topics',                # FK: research_profiles.id
            
            # Research interests (depend on papers, research_interests)
            'paper_research_interests',      # FK: papers.id, research_interests.id
            'research_interest_metrics',     # FK: research_interests.id
            'research_interests',

            # Profile-specific interest tables (depend on profile_research_interests)
            'profile_paper_interests',       # FK: papers.id, profile_research_interests.id
            'profile_interest_metrics',      # FK: profile_research_interests.id

            # Misc tables
            'label_summaries',

            # Profile relationships (depend on papers, research_profiles)
            'paper_profile_scores',          # FK: papers.id, research_profiles.id
            'profile_research_interests',    # FK: research_profiles.id
            
            # Core tables (parent tables - delete last)
            'papers',
            'research_profiles'
        ]
        deletion_counts = {}
        total_tables = len(tables_to_clear)
        
        with get_cursor() as cursor:
            for i, table in enumerate(tables_to_clear):
                if progress_callback:
                    progress_callback(i, total_tables, f"Clearing {table} table...")
                
                try:
                    # Check if table exists first
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        )
                    """, (table,))
                    table_exists = cursor.fetchone()[0]
                    
                    if not table_exists:
                        print(f"Table {table} does not exist, skipping...")
                        deletion_counts[table] = 0
                    else:
                        # Get count before deletion
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count_before = cursor.fetchone()[0]
                        
                        # Delete all records (PostgreSQL doesn't require special syntax)
                        cursor.execute(f"DELETE FROM {table}")
                        deletion_counts[table] = count_before
                        
                        print(f"Cleared {count_before} records from {table} table")
                    
                except Exception as e:
                    print(f"Error clearing table {table}: {e}")
                    deletion_counts[table] = 0
                
                if progress_callback:
                    progress_callback(i + 1, total_tables, f"Cleared {table} table")
        
        total_deleted = sum(deletion_counts.values())
        print(f"Total records cleared: {total_deleted}")
        
        if progress_callback:
            progress_callback(total_tables, total_tables, f"Database clearing complete. {total_deleted} records deleted.")
        
        return deletion_counts


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Import Theseus Insight database from files")
    parser.add_argument("--db-path", required=True, help="Database connection string")
    parser.add_argument("--input-path", required=True, help="Input directory or tar.gz archive")
    parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate entries (don't skip)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without importing")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum parallel workers")
    parser.add_argument("--use-copy", action="store_true", default=True, help="Use COPY for bulk import (default: True)")
    parser.add_argument("--auto-migrate", action="store_true", help="Automatically apply schema migrations")
    parser.add_argument("--merge-strategy", choices=['upsert', 'insert_only', 'update_only'], 
                       default='upsert', help="Strategy for incremental imports (default: upsert)")
    parser.add_argument("--force-incremental", action="store_true", help="Force incremental import mode")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        importer = DatabaseImporter(
            args.db_path, 
            dry_run=args.dry_run,
            auto_migrate=args.auto_migrate,
            merge_strategy=args.merge_strategy
        )
        
        if args.dry_run:
            print("Running in dry-run mode - no changes will be made")
            results = importer.validate_import(args.input_path)
            
            print("\nValidation Results:")
            for table, validation in results["tables"].items():
                status = "VALID" if validation.get("valid", False) else "INVALID"
                print(f"  {table}: {status} ({validation.get('record_count', 0)} records)")
                if validation.get("errors"):
                    for error in validation["errors"][:5]:  # Show first 5 errors
                        print(f"    - {error}")
                    if len(validation["errors"]) > 5:
                        print(f"    ... and {len(validation['errors']) - 5} more errors")
        else:
            # Check if we should force incremental mode
            if args.force_incremental:
                print(f"Forcing incremental import mode with {args.merge_strategy} strategy")
                results = importer.import_incremental(args.input_path)
            else:
                # import_all will auto-detect incremental imports
                results = importer.import_all(
                    args.input_path,
                    skip_duplicates=not args.allow_duplicates,
                    parallel=args.parallel,
                    max_workers=args.max_workers
                )
        
        print("\nImport Summary:")
        for table, stats in results.items():
            if "error" in stats:
                print(f"{table.capitalize()}: {stats['error']}")
            else:
                print(f"{table.capitalize()}: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
        # Calculate totals
        total_imported = sum(stats.get('imported', 0) for stats in results.values())
        total_skipped = sum(stats.get('skipped', 0) for stats in results.values())
        total_errors = sum(stats.get('errors', 0) for stats in results.values())
        
        print(f"\nOverall: {total_imported} imported, {total_skipped} skipped, {total_errors} errors")
        
        if total_errors > 0:
            return 1
            
    except Exception as e:
        print(f"Import failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 