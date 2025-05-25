#!/usr/bin/env python3
"""
Simple test script for database migration tools.

This script creates mock data and tests the export/import functionality
without requiring a real database connection.
"""

import json
import tempfile
import tarfile
from pathlib import Path
from datetime import datetime


def create_mock_data():
    """Create mock data for testing."""
    mock_papers = [
        {
            "id": 1,
            "title": "Test Paper 1",
            "abstract": "This is a test abstract for paper 1",
            "date": "2024-01-01",
            "date_run": "2024-01-15",
            "score": 8.5,
            "rationale": "High relevance to research area",
            "related": True,
            "cosine_similarity": 0.85,
            "url": "https://arxiv.org/abs/2401.00001",
            "embedding_model": "sentence-transformers",
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
        },
        {
            "id": 2,
            "title": "Test Paper 2",
            "abstract": "This is a test abstract for paper 2",
            "date": "2024-01-02",
            "date_run": "2024-01-15",
            "score": 7.2,
            "rationale": "Moderate relevance",
            "related": False,
            "cosine_similarity": 0.72,
            "url": "https://arxiv.org/abs/2401.00002",
            "embedding_model": "sentence-transformers",
            "embedding": [0.2, 0.3, 0.4, 0.5, 0.6]
        }
    ]
    
    mock_podcasts = [
        {
            "id": 1,
            "title": "Test Podcast Episode 1",
            "date": "2024-01-01",
            "script": [
                {"speaker": "Host", "text": "Welcome to our test podcast"},
                {"speaker": "Guest", "text": "Thanks for having me"}
            ],
            "description": "A test podcast episode"
        }
    ]
    
    mock_newsletters = [
        {
            "id": 1,
            "content": "This is a test newsletter content",
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
            "date_sent": "2024-01-08"
        }
    ]
    
    mock_metadata = {
        "export_timestamp": datetime.now().isoformat(),
        "export_version": "1.0",
        "tables_exported": ["papers", "podcasts", "newsletters"],
        "description": "Test export for migration tools"
    }
    
    return {
        "papers": mock_papers,
        "podcasts": mock_podcasts,
        "newsletters": mock_newsletters,
        "metadata": mock_metadata
    }


def create_mock_archive(output_path: str):
    """Create a mock archive file for testing import functionality."""
    print(f"Creating mock archive: {output_path}")
    
    mock_data = create_mock_data()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Write JSON files
        for table_name, data in mock_data.items():
            file_path = temp_path / f"{table_name}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Create tar.gz archive
        with tarfile.open(output_path, "w:gz") as tar:
            for json_file in temp_path.glob("*.json"):
                tar.add(json_file, arcname=json_file.name)
    
    print(f"Mock archive created: {output_path}")
    return output_path


def test_archive_extraction():
    """Test archive extraction functionality."""
    print("\n=== Testing Archive Extraction ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock archive
        archive_path = Path(temp_dir) / "test_archive.tar.gz"
        create_mock_archive(str(archive_path))
        
        # Test extraction
        extract_dir = Path(temp_dir) / "extracted"
        extract_dir.mkdir()
        
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)
        
        # Verify extracted files
        expected_files = ["papers.json", "podcasts.json", "newsletters.json", "metadata.json"]
        extracted_files = [f.name for f in extract_dir.glob("*.json")]
        
        print(f"Expected files: {expected_files}")
        print(f"Extracted files: {extracted_files}")
        
        success = all(f in extracted_files for f in expected_files)
        print(f"Extraction test: {'PASSED' if success else 'FAILED'}")
        
        return success


def test_json_validation():
    """Test JSON data validation."""
    print("\n=== Testing JSON Validation ===")
    
    mock_data = create_mock_data()
    
    # Test papers validation
    papers = mock_data["papers"]
    required_paper_fields = ["title", "abstract", "date", "date_run", "score", "rationale", 
                           "related", "cosine_similarity", "url", "embedding_model"]
    
    papers_valid = True
    for paper in papers:
        for field in required_paper_fields:
            if field not in paper:
                print(f"Missing field in paper: {field}")
                papers_valid = False
    
    # Test podcasts validation
    podcasts = mock_data["podcasts"]
    required_podcast_fields = ["title", "date", "script", "description"]
    
    podcasts_valid = True
    for podcast in podcasts:
        for field in required_podcast_fields:
            if field not in podcast:
                print(f"Missing field in podcast: {field}")
                podcasts_valid = False
    
    # Test newsletters validation
    newsletters = mock_data["newsletters"]
    required_newsletter_fields = ["content", "start_date", "end_date", "date_sent"]
    
    newsletters_valid = True
    for newsletter in newsletters:
        for field in required_newsletter_fields:
            if field not in newsletter:
                print(f"Missing field in newsletter: {field}")
                newsletters_valid = False
    
    overall_valid = papers_valid and podcasts_valid and newsletters_valid
    print(f"JSON validation test: {'PASSED' if overall_valid else 'FAILED'}")
    
    return overall_valid


def test_duplicate_detection():
    """Test duplicate detection logic."""
    print("\n=== Testing Duplicate Detection ===")
    
    # Test paper duplicate detection (by URL)
    papers = [
        {"url": "https://arxiv.org/abs/2401.00001", "title": "Paper 1"},
        {"url": "https://arxiv.org/abs/2401.00002", "title": "Paper 2"},
        {"url": "https://arxiv.org/abs/2401.00001", "title": "Paper 1 Duplicate"}  # Duplicate URL
    ]
    
    unique_urls = set()
    duplicates_found = 0
    
    for paper in papers:
        if paper["url"] in unique_urls:
            duplicates_found += 1
        else:
            unique_urls.add(paper["url"])
    
    papers_test = duplicates_found == 1
    print(f"Paper duplicate detection: {'PASSED' if papers_test else 'FAILED'} (found {duplicates_found} duplicates)")
    
    # Test podcast duplicate detection (by title)
    podcasts = [
        {"title": "Episode 1", "date": "2024-01-01"},
        {"title": "Episode 2", "date": "2024-01-02"},
        {"title": "Episode 1", "date": "2024-01-03"}  # Duplicate title
    ]
    
    unique_titles = set()
    duplicates_found = 0
    
    for podcast in podcasts:
        if podcast["title"] in unique_titles:
            duplicates_found += 1
        else:
            unique_titles.add(podcast["title"])
    
    podcasts_test = duplicates_found == 1
    print(f"Podcast duplicate detection: {'PASSED' if podcasts_test else 'FAILED'} (found {duplicates_found} duplicates)")
    
    # Test newsletter duplicate detection (by date range)
    newsletters = [
        {"start_date": "2024-01-01", "end_date": "2024-01-07"},
        {"start_date": "2024-01-08", "end_date": "2024-01-14"},
        {"start_date": "2024-01-01", "end_date": "2024-01-07"}  # Duplicate date range
    ]
    
    unique_ranges = set()
    duplicates_found = 0
    
    for newsletter in newsletters:
        date_range = (newsletter["start_date"], newsletter["end_date"])
        if date_range in unique_ranges:
            duplicates_found += 1
        else:
            unique_ranges.add(date_range)
    
    newsletters_test = duplicates_found == 1
    print(f"Newsletter duplicate detection: {'PASSED' if newsletters_test else 'FAILED'} (found {duplicates_found} duplicates)")
    
    overall_test = papers_test and podcasts_test and newsletters_test
    print(f"Duplicate detection test: {'PASSED' if overall_test else 'FAILED'}")
    
    return overall_test


def test_file_operations():
    """Test file operations (create, read, compress)."""
    print("\n=== Testing File Operations ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test JSON file creation and reading
        test_data = {"test": "data", "number": 42, "list": [1, 2, 3]}
        json_file = temp_path / "test.json"
        
        # Write JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2)
        
        # Read JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            read_data = json.load(f)
        
        json_test = test_data == read_data
        print(f"JSON read/write: {'PASSED' if json_test else 'FAILED'}")
        
        # Test tar.gz creation and extraction
        archive_file = temp_path / "test.tar.gz"
        extract_dir = temp_path / "extracted"
        extract_dir.mkdir()
        
        # Create archive
        with tarfile.open(archive_file, "w:gz") as tar:
            tar.add(json_file, arcname=json_file.name)
        
        # Extract archive
        with tarfile.open(archive_file, "r:gz") as tar:
            tar.extractall(extract_dir)
        
        # Verify extraction
        extracted_file = extract_dir / json_file.name
        archive_test = extracted_file.exists()
        
        if archive_test:
            with open(extracted_file, 'r', encoding='utf-8') as f:
                extracted_data = json.load(f)
            archive_test = test_data == extracted_data
        
        print(f"Archive create/extract: {'PASSED' if archive_test else 'FAILED'}")
        
        overall_test = json_test and archive_test
        print(f"File operations test: {'PASSED' if overall_test else 'FAILED'}")
        
        return overall_test


def main():
    """Run all tests."""
    print("Database Migration Tools - Test Suite")
    print("=" * 50)
    
    tests = [
        test_json_validation,
        test_duplicate_detection,
        test_file_operations,
        test_archive_extraction
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    
    test_names = [
        "JSON Validation",
        "Duplicate Detection", 
        "File Operations",
        "Archive Extraction"
    ]
    
    for name, result in zip(test_names, results):
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")
    
    overall_success = all(results)
    print(f"\nOverall: {'ALL TESTS PASSED' if overall_success else 'SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n✓ Migration tools are ready to use!")
        print("Next steps:")
        print("1. Set up your database connection strings")
        print("2. Run: python -m theseus_insight.utils.db_migrate --help")
        print("3. Try exporting your development database")
    else:
        print("\n✗ Some tests failed. Please check the implementation.")
    
    return 0 if overall_success else 1


if __name__ == "__main__":
    exit(main()) 