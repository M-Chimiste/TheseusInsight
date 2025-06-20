#!/usr/bin/env python3
"""
Example script showing how to use the Kaggle ArXiv dataset as a fallback
when the OAI-PMH API is down, with automatic download and cleanup.

Usage Options:

1. AUTOMATIC DOWNLOAD (Recommended):
   # Set up Kaggle API credentials:
   export KAGGLE_USERNAME="your_username"
   export KAGGLE_KEY="your_api_key"
   # Or place kaggle.json in ~/.kaggle/
   
   export DEBUG=true
   python example_kaggle_harvest.py
   # Will automatically download and clean up the dataset!

2. MANUAL DATASET:
   # Download manually from: https://www.kaggle.com/datasets/Cornell-University/arxiv
   # Extract arxiv-metadata-oai-snapshot.json to your data/ directory
   export KAGGLE_ARXIV_PATH="data/arxiv-metadata-oai-snapshot.json"
   export DEBUG=true
   python example_kaggle_harvest.py

3. FORCE KAGGLE MODE:
   export FORCE_KAGGLE=true
   export DEBUG=true
   python example_kaggle_harvest.py

Environment Variables:
- KAGGLE_USERNAME: Your Kaggle username
- KAGGLE_KEY: Your Kaggle API key  
- KAGGLE_ARXIV_PATH: Path to existing dataset file
- FORCE_KAGGLE: Skip OAI-PMH, use Kaggle directly
- AUTO_DOWNLOAD: Enable/disable auto download (default: true)
- DEBUG: Enable detailed logging
"""

import os
from theseus_insight.data_processing import UnifiedArxivHarvester

def main():
    print("🔬 ArXiv Unified Harvester Example")
    print("=" * 50)
    
    # Configure harvester (using context manager for automatic cleanup)
    with UnifiedArxivHarvester(
        category="cs",
        date_from="2024-12-01",
        date_until="2024-12-07",
        subcategories=["cs.ai", "cs.cl", "cs.lg"],
        max_results=10,  # Limit for demo
        verbose=True,
    ) as harvester:
        
        # Show status of both methods
        print("\n📊 Harvester Status:")
        status = harvester.get_status()
        
        print(f"OAI-PMH API: {'✅ Available' if status['oai_pmh']['available'] else '❌ Unavailable'}")
        if status['oai_pmh']['error']:
            print(f"  Error: {status['oai_pmh']['error']}")
        
        kaggle_info = status['kaggle']
        if kaggle_info['available']:
            print(f"Kaggle Dataset: ✅ Available")
            print(f"  Path: {kaggle_info['path']}")
            print(f"  Size: {kaggle_info['size_mb']} MB")
            print(f"  Last Modified: {kaggle_info['last_modified']}")
        else:
            print(f"Kaggle Dataset: ❌ Not Available")
            print(f"  Path: {kaggle_info['path']}")
            if 'error' in kaggle_info:
                print(f"  Error: {kaggle_info['error']}")
        
        print(f"Force Kaggle Mode: {'✅ Enabled' if status['force_kaggle'] else '❌ Disabled'}")
        
        # Show harvest info
        print("\n⚙️  Harvest Configuration:")
        info = harvester.get_harvest_info()
        print(f"Category: {info['category']}")
        print(f"Date Range: {info['date_range']}")
        print(f"Subcategories: {info['subcategories']}")
        print(f"Max Results: {info['max_results']}")
        
        # Perform harvest
        print("\n🚀 Starting Harvest...")
        print("-" * 30)
        
        try:
            papers = harvester.harvest()
            
            print(f"\n✅ Harvest Successful!")
            print(f"Found {len(papers)} papers")
            
            # Show first few papers
            if papers:
                print("\n📄 Sample Papers:")
                for i, paper in enumerate(papers[:3]):
                    print(f"\n{i+1}. {paper['title'][:80]}...")
                    print(f"   ID: {paper['id']}")
                    print(f"   Authors: {paper['authors'][:60]}...")
                    print(f"   Categories: {paper['categories']}")
                    print(f"   Date: {paper['created']}")
            
            # Convert to DataFrame if pandas is available
            try:
                df = harvester.to_dataframe()
                print(f"\n📊 DataFrame created with {len(df)} rows and {len(df.columns)} columns")
                print(f"Columns: {list(df.columns)}")
            except Exception as e:
                print(f"\n⚠️  Could not create DataFrame: {e}")
                
        except Exception as e:
            print(f"\n❌ Harvest Failed: {e}")
            print("\n💡 Troubleshooting:")
            print("1. Set up Kaggle API credentials:")
            print("   export KAGGLE_USERNAME='your_username'")
            print("   export KAGGLE_KEY='your_api_key'")
            print("2. Or download manually: https://www.kaggle.com/datasets/Cornell-University/arxiv")
            print("3. Set KAGGLE_ARXIV_PATH environment variable")
            print("4. Try setting FORCE_KAGGLE=true to skip OAI-PMH")

if __name__ == "__main__":
    main() 