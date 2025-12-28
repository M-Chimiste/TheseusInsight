#!/usr/bin/env python3
"""
Data Validation Framework

This module provides comprehensive data validation capabilities for the
Theseus Insight database migration system.
"""

import json
import hashlib
import logging
import re
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, date
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class ValidationResult:
    """Represents the result of a validation operation."""
    
    def __init__(self, is_valid: bool = True):
        self.is_valid = is_valid
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.statistics: Dict[str, Any] = {}
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.statistics.update(other.statistics)


class FieldValidator:
    """Validates individual fields based on rules."""
    
    @staticmethod
    def validate_required(value: Any, field_name: str) -> ValidationResult:
        """Validate that a field is not empty."""
        result = ValidationResult()
        
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(f"Required field '{field_name}' is missing or empty")
        
        return result
    
    @staticmethod
    def validate_url(value: str, field_name: str) -> ValidationResult:
        """Validate URL format."""
        result = ValidationResult()
        
        if not value:
            return result
        
        try:
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                result.add_error(f"Invalid URL format for '{field_name}': {value}")
        except Exception as e:
            result.add_error(f"URL validation failed for '{field_name}': {e}")
        
        return result
    
    @staticmethod
    def validate_email(value: str, field_name: str) -> ValidationResult:
        """Validate email format."""
        result = ValidationResult()
        
        if not value:
            return result
        
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(value):
            result.add_error(f"Invalid email format for '{field_name}': {value}")
        
        return result
    
    @staticmethod
    def validate_date(value: Any, field_name: str) -> ValidationResult:
        """Validate date format."""
        result = ValidationResult()
        
        if not value:
            return result
        
        # Handle different date formats
        if isinstance(value, (date, datetime)):
            return result
        
        if isinstance(value, str):
            # Try parsing ISO format
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return result
            except ValueError:
                pass
            
            # Try parsing date-only format
            try:
                datetime.strptime(value, '%Y-%m-%d')
                return result
            except ValueError:
                pass
            
            result.add_error(f"Invalid date format for '{field_name}': {value}")
        
        return result
    
    @staticmethod
    def validate_numeric_range(value: Any, field_name: str, min_val: float = None, max_val: float = None) -> ValidationResult:
        """Validate numeric value is within range."""
        result = ValidationResult()
        
        if value is None:
            return result
        
        try:
            num_val = float(value)
            
            if min_val is not None and num_val < min_val:
                result.add_error(f"Value for '{field_name}' ({num_val}) is below minimum ({min_val})")
            
            if max_val is not None and num_val > max_val:
                result.add_error(f"Value for '{field_name}' ({num_val}) is above maximum ({max_val})")
        
        except (ValueError, TypeError):
            result.add_error(f"Non-numeric value for '{field_name}': {value}")
        
        return result
    
    @staticmethod
    def validate_string_length(value: str, field_name: str, min_len: int = None, max_len: int = None) -> ValidationResult:
        """Validate string length."""
        result = ValidationResult()
        
        if not value:
            return result
        
        length = len(str(value))
        
        if min_len is not None and length < min_len:
            result.add_error(f"'{field_name}' is too short ({length} < {min_len})")
        
        if max_len is not None and length > max_len:
            result.add_error(f"'{field_name}' is too long ({length} > {max_len})")
        
        return result
    
    @staticmethod
    def validate_json_structure(value: Any, field_name: str) -> ValidationResult:
        """Validate JSON structure."""
        result = ValidationResult()
        
        if not value:
            return result
        
        if isinstance(value, str):
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                result.add_error(f"Invalid JSON for '{field_name}': {e}")
        elif not isinstance(value, (dict, list)):
            result.add_error(f"'{field_name}' must be JSON-serializable")
        
        return result


class TableValidator:
    """Validates table-specific data."""
    
    def __init__(self):
        self.validators = {
            'papers': self._validate_paper,
            'podcasts': self._validate_podcast,
            'newsletters': self._validate_newsletter,
            'research_profiles': self._validate_research_profile,
            'literature_reviews': self._validate_literature_review,
            'model_catalog': self._validate_model_catalog,
            'topics': self._validate_topic,
            'paper_profile_scores': self._validate_paper_profile_score
        }
    
    def validate_table(self, table_name: str, data: List[Dict], metadata: Dict = None) -> ValidationResult:
        """
        Validate an entire table's data.
        
        Args:
            table_name: Name of the table
            data: List of records
            metadata: Optional metadata for validation context
            
        Returns:
            ValidationResult with overall validation status
        """
        result = ValidationResult()
        
        if not data:
            result.add_warning(f"Table '{table_name}' is empty")
            return result
        
        # Get table-specific validator
        validator = self.validators.get(table_name, self._validate_generic)
        
        # Validate each record
        for i, record in enumerate(data):
            try:
                record_result = validator(record, i)
                result.merge(record_result)
            except Exception as e:
                result.add_error(f"Validation error for {table_name} record {i}: {e}")
        
        # Add statistics
        result.statistics = {
            "total_records": len(data),
            "valid_records": len(data) - len([e for e in result.errors if "record" in e]),
            "error_count": len(result.errors),
            "warning_count": len(result.warnings)
        }
        
        logger.info(f"Validated {table_name}: {result.statistics}")
        return result
    
    def _validate_paper(self, record: Dict, index: int) -> ValidationResult:
        """Validate a paper record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['title', 'abstract']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # String length validations
        if record.get('title'):
            title_result = FieldValidator.validate_string_length(
                record['title'], 'title', min_len=1, max_len=500
            )
            result.merge(title_result)
        
        if record.get('abstract'):
            abstract_result = FieldValidator.validate_string_length(
                record['abstract'], 'abstract', min_len=1, max_len=10000
            )
            result.merge(abstract_result)
        
        # URL validation
        if record.get('url'):
            url_result = FieldValidator.validate_url(record['url'], 'url')
            result.merge(url_result)
        
        # Date validation
        if record.get('date'):
            date_result = FieldValidator.validate_date(record['date'], 'date')
            result.merge(date_result)
        
        # Score validation (scores are 1-10 in the system)
        if record.get('score') is not None:
            score_result = FieldValidator.validate_numeric_range(
                record['score'], 'score', min_val=0.0, max_val=10.0
            )
            result.merge(score_result)
        
        # Embedding validation
        if record.get('embedding'):
            if isinstance(record['embedding'], list):
                if not all(isinstance(x, (int, float)) for x in record['embedding']):
                    result.add_error(f"Paper {index}: embedding contains non-numeric values")
                elif len(record['embedding']) == 0:
                    result.add_error(f"Paper {index}: embedding is empty")
            else:
                result.add_error(f"Paper {index}: embedding must be a list")
        
        return result
    
    def _validate_podcast(self, record: Dict, index: int) -> ValidationResult:
        """Validate a podcast record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['title', 'description']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # URL validation
        if record.get('url'):
            url_result = FieldValidator.validate_url(record['url'], 'url')
            result.merge(url_result)
        
        # Duration validation
        if record.get('duration') is not None:
            duration_result = FieldValidator.validate_numeric_range(
                record['duration'], 'duration', min_val=0
            )
            result.merge(duration_result)
        
        return result
    
    def _validate_newsletter(self, record: Dict, index: int) -> ValidationResult:
        """Validate a newsletter record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['title', 'content']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # URL validation
        if record.get('url'):
            url_result = FieldValidator.validate_url(record['url'], 'url')
            result.merge(url_result)
        
        # Date validation
        if record.get('published_date'):
            date_result = FieldValidator.validate_date(record['published_date'], 'published_date')
            result.merge(date_result)
        
        return result
    
    def _validate_research_profile(self, record: Dict, index: int) -> ValidationResult:
        """Validate a research profile record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['name']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # Email validation
        if record.get('email'):
            email_result = FieldValidator.validate_email(record['email'], 'email')
            result.merge(email_result)
        
        # URL validation
        if record.get('institution_url'):
            url_result = FieldValidator.validate_url(record['institution_url'], 'institution_url')
            result.merge(url_result)
        
        return result
    
    def _validate_literature_review(self, record: Dict, index: int) -> ValidationResult:
        """Validate a literature review record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['query', 'summary']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # Date validation
        if record.get('created_at'):
            date_result = FieldValidator.validate_date(record['created_at'], 'created_at')
            result.merge(date_result)
        
        return result
    
    def _validate_model_catalog(self, record: Dict, index: int) -> ValidationResult:
        """Validate a model catalog record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['model_name', 'provider_name']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # Numeric validations
        for field, min_val in [('max_new_tokens', 1), ('temperature', 0), ('num_ctx', 1)]:
            if record.get(field) is not None:
                num_result = FieldValidator.validate_numeric_range(
                    record[field], field, min_val=min_val
                )
                result.merge(num_result)
        
        return result
    
    def _validate_topic(self, record: Dict, index: int) -> ValidationResult:
        """Validate a topic record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['label']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # Keywords validation
        if record.get('keywords'):
            keywords_result = FieldValidator.validate_json_structure(record['keywords'], 'keywords')
            result.merge(keywords_result)
        
        return result
    
    def _validate_paper_profile_score(self, record: Dict, index: int) -> ValidationResult:
        """Validate a paper profile score record."""
        result = ValidationResult()
        
        # Required fields
        for field in ['paper_id', 'profile_id', 'score']:
            field_result = FieldValidator.validate_required(record.get(field), field)
            result.merge(field_result)
        
        # Score validation (scores are 1-10 in the system)
        if record.get('score') is not None:
            score_result = FieldValidator.validate_numeric_range(
                record['score'], 'score', min_val=0.0, max_val=10.0
            )
            result.merge(score_result)
        
        return result
    
    def _validate_generic(self, record: Dict, index: int) -> ValidationResult:
        """Generic validation for unknown table types."""
        result = ValidationResult()
        
        if not isinstance(record, dict):
            result.add_error(f"Record {index}: Expected dictionary, got {type(record)}")
        
        return result


class DataIntegrityValidator:
    """Validates data integrity across tables."""
    
    def validate_referential_integrity(self, tables: Dict[str, List[Dict]]) -> ValidationResult:
        """
        Validate foreign key relationships between tables.
        
        Args:
            tables: Dictionary mapping table names to their data
            
        Returns:
            ValidationResult with referential integrity status
        """
        result = ValidationResult()
        
        # Build ID indexes for efficient lookups
        id_indexes = {}
        for table_name, data in tables.items():
            if data:
                id_indexes[table_name] = {record.get('id') for record in data if record.get('id')}
        
        # Check paper_profile_scores references
        if 'paper_profile_scores' in tables:
            papers_ids = id_indexes.get('papers', set())
            profiles_ids = id_indexes.get('research_profiles', set())
            
            for i, score in enumerate(tables['paper_profile_scores']):
                paper_id = score.get('paper_id')
                profile_id = score.get('profile_id')
                
                if paper_id not in papers_ids:
                    result.add_error(f"paper_profile_scores[{i}]: paper_id {paper_id} not found in papers table")
                
                if profile_id not in profiles_ids:
                    result.add_error(f"paper_profile_scores[{i}]: profile_id {profile_id} not found in research_profiles table")
        
        # Check paper_topics references
        if 'paper_topics' in tables:
            papers_ids = id_indexes.get('papers', set())
            topics_ids = id_indexes.get('topics', set())
            
            for i, pt in enumerate(tables['paper_topics']):
                paper_id = pt.get('paper_id')
                topic_id = pt.get('topic_id')
                
                if paper_id not in papers_ids:
                    result.add_error(f"paper_topics[{i}]: paper_id {paper_id} not found in papers table")
                
                if topic_id not in topics_ids:
                    result.add_error(f"paper_topics[{i}]: topic_id {topic_id} not found in topics table")
        
        return result
    
    def validate_data_consistency(self, tables: Dict[str, List[Dict]]) -> ValidationResult:
        """
        Validate data consistency within and across tables.
        
        Args:
            tables: Dictionary mapping table names to their data
            
        Returns:
            ValidationResult with consistency status
        """
        result = ValidationResult()
        
        # Check for duplicate IDs within tables
        for table_name, data in tables.items():
            if not data:
                continue
                
            ids = [record.get('id') for record in data if record.get('id') is not None]
            unique_ids = set(ids)
            
            if len(ids) != len(unique_ids):
                duplicates = [id_val for id_val in unique_ids if ids.count(id_val) > 1]
                result.add_error(f"{table_name}: Duplicate IDs found: {duplicates}")
        
        # Check score consistency
        if 'paper_profile_scores' in tables:
            for i, score in enumerate(tables['paper_profile_scores']):
                score_val = score.get('score')
                cosine_sim = score.get('cosine_similarity')
                
                # Scores should be reasonably correlated (this is a business rule example)
                if score_val is not None and cosine_sim is not None:
                    diff = abs(float(score_val) - float(cosine_sim))
                    if diff > 0.5:  # Threshold for suspicious difference
                        result.add_warning(f"paper_profile_scores[{i}]: Large difference between score ({score_val}) and cosine_similarity ({cosine_sim})")
        
        return result


class ComprehensiveValidator:
    """Main validator that orchestrates all validation types."""
    
    def __init__(self):
        self.table_validator = TableValidator()
        self.integrity_validator = DataIntegrityValidator()
    
    def validate_export_data(self, tables: Dict[str, List[Dict]], metadata: Dict = None) -> ValidationResult:
        """
        Perform comprehensive validation of export data.
        
        Args:
            tables: Dictionary mapping table names to their data
            metadata: Optional metadata for validation context
            
        Returns:
            ValidationResult with overall validation status
        """
        overall_result = ValidationResult()
        
        logger.info("Starting comprehensive data validation...")
        
        # Validate each table
        for table_name, data in tables.items():
            logger.info(f"Validating table: {table_name}")
            
            table_result = self.table_validator.validate_table(table_name, data, metadata)
            overall_result.merge(table_result)
            
            if not table_result.is_valid:
                logger.warning(f"Table {table_name} failed validation with {len(table_result.errors)} errors")
        
        # Validate referential integrity
        logger.info("Validating referential integrity...")
        integrity_result = self.integrity_validator.validate_referential_integrity(tables)
        overall_result.merge(integrity_result)
        
        # Validate data consistency
        logger.info("Validating data consistency...")
        consistency_result = self.integrity_validator.validate_data_consistency(tables)
        overall_result.merge(consistency_result)
        
        # Add overall statistics
        overall_result.statistics["validation_summary"] = {
            "total_tables": len(tables),
            "total_records": sum(len(data) for data in tables.values()),
            "tables_with_errors": len([name for name, data in tables.items() 
                                     if not self.table_validator.validate_table(name, data).is_valid]),
            "overall_valid": overall_result.is_valid
        }
        
        logger.info(f"Validation complete. Valid: {overall_result.is_valid}, "
                   f"Errors: {len(overall_result.errors)}, "
                   f"Warnings: {len(overall_result.warnings)}")
        
        return overall_result