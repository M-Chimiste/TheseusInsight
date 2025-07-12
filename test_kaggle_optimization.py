#!/usr/bin/env python3
"""Test script for Kaggle dataset optimization."""

import sys
import os
import time
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from theseus_insight.data_processing.kaggle_harvester import KaggleArxivHarvester
from theseus_insight.data_processing.kaggle_optimizer import OptimizedKaggleProcessor


def test_optimizer_vs_legacy():
    """Compare performance of optimized vs legacy Kaggle processing."""
    
    # Check if Kaggle dataset exists
    kaggle_path = os.getenv("KAGGLE_ARXIV_PATH", "data/arxiv-metadata-oai-snapshot.json")
    if not os.path.exists(kaggle_path):
        print(f"❌ Kaggle dataset not found at: {kaggle_path}")
        print("   Please download the dataset or set KAGGLE_ARXIV_PATH")
        return
    
    print("="*60)
    print("Testing Kaggle Dataset Optimization")
    print("="*60)
    print(f"Dataset: {kaggle_path}")
    print(f"Size: {os.path.getsize(kaggle_path) / (1024**3):.2f} GB")
    print()
    
    # Test parameters
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    print(f"Test date range: {start_date} to {end_date}")
    print()
    
    # Test 1: Legacy processing
    print("Test 1: Legacy Processing")
    print("-" * 40)
    os.environ['USE_KAGGLE_OPTIMIZER'] = 'false'
    
    legacy_harvester = KaggleArxivHarvester(
        dataset_path=kaggle_path,
        category='cs',
        date_from=start_date,
        date_until=end_date,
        subcategories=['cs.lg', 'cs.ai'],
        max_results=100,
        verbose=True
    )
    
    start_time = time.time()
    try:
        legacy_results = legacy_harvester.harvest()
        legacy_time = time.time() - start_time
        print(f"✅ Legacy: Found {len(legacy_results)} papers in {legacy_time:.2f} seconds")
    except Exception as e:
        print(f"❌ Legacy failed: {e}")
        legacy_time = None
        legacy_results = []
    
    print()
    
    # Test 2: Optimized processing
    print("Test 2: Optimized Processing")
    print("-" * 40)
    os.environ['USE_KAGGLE_OPTIMIZER'] = 'true'
    
    optimized_harvester = KaggleArxivHarvester(
        dataset_path=kaggle_path,
        category='cs',
        date_from=start_date,
        date_until=end_date,
        subcategories=['cs.lg', 'cs.ai'],
        max_results=100,
        verbose=True
    )
    
    start_time = time.time()
    try:
        optimized_results = optimized_harvester.harvest()
        optimized_time = time.time() - start_time
        print(f"✅ Optimized: Found {len(optimized_results)} papers in {optimized_time:.2f} seconds")
    except Exception as e:
        print(f"❌ Optimized failed: {e}")
        optimized_time = None
        optimized_results = []
    
    print()
    
    # Results comparison
    print("="*60)
    print("Performance Comparison")
    print("="*60)
    
    if legacy_time and optimized_time:
        speedup = legacy_time / optimized_time
        print(f"Legacy time:     {legacy_time:.2f} seconds")
        print(f"Optimized time:  {optimized_time:.2f} seconds")
        print(f"Speedup:         {speedup:.1f}x faster")
        print()
        print(f"Legacy results:    {len(legacy_results)} papers")
        print(f"Optimized results: {len(optimized_results)} papers")
        
        if speedup > 10:
            print("\n🎉 HUGE IMPROVEMENT! Over 10x faster!")
        elif speedup > 5:
            print("\n🚀 Great improvement! Over 5x faster!")
        elif speedup > 2:
            print("\n✨ Good improvement! Over 2x faster!")
        else:
            print("\n📊 Modest improvement")
    
    # Test 3: Index info
    print("\n" + "="*60)
    print("Index Information")
    print("="*60)
    
    try:
        optimizer = OptimizedKaggleProcessor(kaggle_path)
        date_start, date_end = optimizer.get_date_range()
        print(f"Dataset date range: {date_start} to {date_end}")
        
        # Test different date ranges
        test_ranges = [
            (7, "Last week"),
            (30, "Last month"),
            (365, "Last year"),
        ]
        
        for days, label in test_ranges:
            test_start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            test_end = datetime.now().strftime('%Y-%m-%d')
            estimated = optimizer.estimate_records_in_range(test_start, test_end)
            print(f"{label}: ~{estimated:,} papers")
            
    except Exception as e:
        print(f"Could not get index info: {e}")
    
    print("\n" + "="*60)
    print("Optimization Features:")
    print("="*60)
    print("✅ Date-based index for O(log n) lookups")
    print("✅ Binary search to find date boundaries")  
    print("✅ Memory-mapped file for random access")
    print("✅ Process only relevant date range")
    print("✅ One-time index build, reused forever")
    print("\nExpected improvement: 10-100x for small date ranges")


if __name__ == "__main__":
    test_optimizer_vs_legacy()