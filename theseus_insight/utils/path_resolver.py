"""
Path resolution utilities for handling development vs packaged environments.
"""

import os
from pathlib import Path


def get_config_path(filename: str) -> str:
    """
    Get the full path to a config file, handling both development and packaged environments.
    
    Args:
        filename: Name of the config file (e.g., 'orchestration.json')
        
    Returns:
        Full path to the config file
    """
    # Check if we have a custom config directory set (from packaged app)
    config_dir = os.getenv('THESEUS_CONFIG_DIR')
    
    if config_dir and os.path.exists(config_dir):
        config_path = os.path.join(config_dir, filename)
        if os.path.exists(config_path):
            return config_path
    
    # Fallback to standard relative path (development)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up from theseus_insight/utils to project root, then to config
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_path = os.path.join(project_root, 'config', filename)
    
    return config_path


def get_app_root() -> str:
    """
    Get the application root directory.
    
    Returns:
        Full path to the application root
    """
    # Check if we have a custom app root set (from packaged app)
    app_root = os.getenv('THESEUS_APP_ROOT')
    
    if app_root and os.path.exists(app_root):
        return app_root
    
    # Fallback to standard relative path (development)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up from theseus_insight/utils to project root
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    return project_root


def get_data_path(subdir: str = "") -> str:
    """
    Get the path to the data directory.
    
    Args:
        subdir: Optional subdirectory within data
        
    Returns:
        Full path to the data directory or subdirectory
    """
    app_root = get_app_root()
    data_path = os.path.join(app_root, 'data')
    
    if subdir:
        data_path = os.path.join(data_path, subdir)
    
    # Ensure the directory exists
    os.makedirs(data_path, exist_ok=True)
    
    return data_path


def config_file_exists(filename: str) -> bool:
    """
    Check if a config file exists.
    
    Args:
        filename: Name of the config file
        
    Returns:
        True if the file exists, False otherwise
    """
    config_path = get_config_path(filename)
    return os.path.exists(config_path) 