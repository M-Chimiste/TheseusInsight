#!/usr/bin/env python3
"""
Database debugging script for Theseus Insight Electron app.
This script helps diagnose database initialization and connectivity issues.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

def debug_environment():
    """Print environment information for debugging."""
    print("=== ENVIRONMENT DEBUG ===")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Script location: {os.path.abspath(__file__)}")
    
    # Check environment variables
    print("\n=== ENVIRONMENT VARIABLES ===")
    db_url = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {db_url}")
    print(f"ELECTRON_IS_PACKAGED: {os.getenv('ELECTRON_IS_PACKAGED')}")
    print(f"ELECTRON_RESOURCES_PATH: {os.getenv('ELECTRON_RESOURCES_PATH')}")
    print(f"APP_SECRET_KEY set: {bool(os.getenv('APP_SECRET_KEY'))}")
    
    # Check Python path
    print(f"\n=== PYTHON PATH ===")
    for i, path in enumerate(sys.path):
        print(f"{i}: {path}")

def check_sqlite_vec():
    """Check if sqlite-vec extension can be loaded."""
    print("\n=== SQLITE-VEC CHECK ===")
    try:
        conn = sqlite3.connect(':memory:')
        conn.enable_load_extension(True)
        
        # Try different ways to load sqlite-vec
        load_methods = [
            ("sqlite_vec", "Standard name"),
            ("./sqlite_vec", "Relative path"),
            (os.path.join(os.getcwd(), "sqlite_vec"), "Absolute path"),
        ]
        
        # Also check if it's in site-packages
        for path_item in sys.path:
            if 'site-packages' in path_item:
                potential_path = os.path.join(path_item, 'sqlite_vec')
                if os.path.exists(potential_path):
                    for item in os.listdir(potential_path):
                        if item.endswith('.so') or item.endswith('.dylib') or item.endswith('.dll'):
                            load_methods.append((os.path.join(potential_path, item), f"Found in site-packages: {item}"))
        
        for method, description in load_methods:
            try:
                conn.load_extension(method)
                print(f"✅ Successfully loaded sqlite-vec using: {method} ({description})")
                return True
            except Exception as e:
                print(f"❌ Failed to load {method} ({description}): {e}")
        
        conn.close()
        print("❌ Could not load sqlite-vec extension")
        return False
    except Exception as e:
        print(f"❌ Error testing sqlite-vec: {e}")
        return False

def test_database_connection(db_path):
    """Test basic database connectivity."""
    print(f"\n=== DATABASE CONNECTION TEST ===")
    print(f"Database path: {db_path}")
    
    if not db_path:
        print("❌ No database path provided")
        return False
    
    try:
        # Check if database file exists
        if os.path.exists(db_path):
            print(f"✅ Database file exists: {db_path}")
            file_stats = os.stat(db_path)
            print(f"   Size: {file_stats.st_size} bytes")
            print(f"   Readable: {os.access(db_path, os.R_OK)}")
            print(f"   Writable: {os.access(db_path, os.W_OK)}")
        else:
            print(f"⚠️  Database file does not exist: {db_path}")
            # Check if directory exists and is writable
            db_dir = os.path.dirname(db_path)
            if os.path.exists(db_dir):
                print(f"✅ Database directory exists: {db_dir}")
                print(f"   Writable: {os.access(db_dir, os.W_OK)}")
            else:
                print(f"❌ Database directory does not exist: {db_dir}")
                return False
        
        # Try to connect
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test basic SQL operations
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        print(f"✅ SQLite version: {version}")
        
        # Test if we can create/query tables
        cursor.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("INSERT OR REPLACE INTO test_table (id, name) VALUES (1, 'test')")
        cursor.execute("SELECT name FROM test_table WHERE id = 1")
        result = cursor.fetchone()
        
        if result and result[0] == 'test':
            print("✅ Basic database operations working")
        else:
            print("❌ Basic database operations failed")
            return False
        
        # Clean up test table
        cursor.execute("DROP TABLE IF EXISTS test_table")
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_theseus_database():
    """Test Theseus database initialization."""
    print(f"\n=== THESEUS DATABASE TEST ===")
    
    try:
        # Try to import and initialize the database
        sys.path.insert(0, os.getcwd())  # Add current directory to path
        
        print("Attempting to import PaperDatabase...")
        from theseus_insight.data_model.data_handling import PaperDatabase
        print("✅ Successfully imported PaperDatabase")
        
        db_path = os.getenv('DATABASE_URL', 'data/theseus.db')
        print(f"Initializing database at: {db_path}")
        
        db = PaperDatabase(db_path)
        print("✅ Successfully initialized PaperDatabase")
        
        # Test database operations
        print("Testing database operations...")
        
        # Test settings
        db.set_setting('test_key', 'test_value')
        value = db.get_setting('test_key')
        if value == 'test_value':
            print("✅ Settings operations working")
        else:
            print("❌ Settings operations failed")
        
        # Clean up
        db.delete_setting('test_key')
        
        print("✅ Theseus database is working correctly")
        return True
        
    except ImportError as e:
        print(f"❌ Could not import PaperDatabase: {e}")
        return False
    except Exception as e:
        print(f"❌ Theseus database error: {e}")
        return False

def main():
    """Main debugging function."""
    print("🔍 Theseus Insight Database Debug Tool")
    print("=====================================")
    
    debug_environment()
    sqlite_vec_ok = check_sqlite_vec()
    
    db_path = os.getenv('DATABASE_URL', 'data/theseus.db')
    db_connection_ok = test_database_connection(db_path)
    
    if db_connection_ok:
        theseus_db_ok = test_theseus_database()
    else:
        theseus_db_ok = False
    
    print(f"\n=== SUMMARY ===")
    print(f"SQLite-vec extension: {'✅' if sqlite_vec_ok else '❌'}")
    print(f"Database connection: {'✅' if db_connection_ok else '❌'}")
    print(f"Theseus database: {'✅' if theseus_db_ok else '❌'}")
    
    if sqlite_vec_ok and db_connection_ok and theseus_db_ok:
        print("\n🎉 All database components are working correctly!")
        return 0
    else:
        print("\n❌ Some database components have issues. Check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 