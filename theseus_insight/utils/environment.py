"""Environment detection utilities for worker processes."""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional


class EnvironmentDetector:
    """Detects and provides environment information for worker processes."""

    @staticmethod
    def get_database_url() -> str:
        """Get the database URL from environment."""
        return os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")

    @staticmethod
    def get_working_directory() -> Path:
        """Get the working directory for the application."""
        # Try to find the project root by looking for theseus_insight directory
        current_path = Path.cwd()

        # Look for theseus_insight directory in current or parent directories
        if (current_path / "theseus_insight").exists():
            return current_path
        elif (current_path.parent / "theseus_insight").exists():
            return current_path.parent

        # Fallback to current directory
        return current_path

    @staticmethod
    def get_python_executable() -> str:
        """Get the Python executable path."""
        return sys.executable

    @staticmethod
    def get_project_root() -> Path:
        """Get the project root directory."""
        # Try to find setup.py or pyproject.toml as indicators of project root
        current_path = Path.cwd()

        # Check if we're already in the project root
        if (current_path / "theseus_insight" / "main.py").exists():
            return current_path

        # Check parent directory
        parent_path = current_path.parent
        if (parent_path / "theseus_insight" / "main.py").exists():
            return parent_path

        # Fallback to current directory
        return current_path

    @staticmethod
    def get_environment_hash() -> str:
        """Get a hash representing the current environment for worker identification."""
        import hashlib

        db_url = EnvironmentDetector.get_database_url()
        work_dir = str(EnvironmentDetector.get_working_directory())

        # Create a hash from key environment variables
        env_string = f"{db_url}|{work_dir}"
        return hashlib.md5(env_string.encode()).hexdigest()[:8]

    @staticmethod
    def validate_environment() -> Dict[str, Any]:
        """Validate that the environment is suitable for running workers."""
        issues = []
        warnings = []

        # Check database connectivity
        try:
            from ..db import get_connection_pool
            import asyncio
            # Note: This is a synchronous check, might need adjustment
        except Exception as e:
            issues.append(f"Database connection failed: {e}")

        # Check working directory
        work_dir = EnvironmentDetector.get_working_directory()
        if not (work_dir / "theseus_insight").exists():
            issues.append(f"theseus_insight module not found in {work_dir}")

        # Check Python modules
        required_modules = ['theseus_insight', 'psycopg2', 'fastapi']
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                issues.append(f"Required module '{module}' not available")

        # Check for existing migration
        try:
            from ..db.migrations import check_and_apply_migrations
            # This would be checked at runtime
        except Exception as e:
            warnings.append(f"Migration check failed: {e}")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'database_url': EnvironmentDetector.get_database_url(),
            'working_directory': str(EnvironmentDetector.get_working_directory()),
            'python_executable': EnvironmentDetector.get_python_executable(),
            'environment_hash': EnvironmentDetector.get_environment_hash()
        }

    @staticmethod
    def get_worker_environment() -> Dict[str, str]:
        """Get environment variables needed for worker processes."""
        # Copy essential environment variables
        worker_env = {}

        # Database connection
        worker_env['DATABASE_URL'] = EnvironmentDetector.get_database_url()

        # Python path
        python_path = os.getenv('PYTHONPATH', '')
        project_root = str(EnvironmentDetector.get_project_root())
        if python_path:
            worker_env['PYTHONPATH'] = f"{project_root}:{python_path}"
        else:
            worker_env['PYTHONPATH'] = project_root

        # Working directory
        worker_env['WORKING_DIR'] = str(EnvironmentDetector.get_working_directory())

        # Copy other essential env vars (add more as needed)
        essential_vars = [
            'OLLAMA_URL',  # For single server fallback
            'OPENAI_API_KEY',
            'ANTHROPIC_API_KEY',
            'GROQ_API_KEY',
            'GEMINI_API_KEY'
        ]

        for var in essential_vars:
            value = os.getenv(var)
            if value:
                worker_env[var] = value

        return worker_env

    @staticmethod
    def print_environment_info():
        """Print environment information for debugging."""
        env_info = EnvironmentDetector.validate_environment()

        print("=== Environment Information ===")
        print(f"Database URL: {env_info['database_url']}")
        print(f"Working Directory: {env_info['working_directory']}")
        print(f"Python Executable: {env_info['python_executable']}")
        print(f"Environment Hash: {env_info['environment_hash']}")
        print(f"Environment Valid: {env_info['valid']}")

        if env_info['issues']:
            print("\nIssues:")
            for issue in env_info['issues']:
                print(f"  ❌ {issue}")

        if env_info['warnings']:
            print("\nWarnings:")
            for warning in env_info['warnings']:
                print(f"  ⚠️  {warning}")

        print("=" * 50)
