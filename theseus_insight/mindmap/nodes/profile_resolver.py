"""
Profile Resolver Node for Mind-Map Explorer

This node resolves profile tags to actual profile IDs and validates profile context
before proceeding with the mind-map generation workflow.
"""

import logging
from typing import Dict, Any, List, Optional

from ..state import MindMapState, Message
from ...data_access import ProfileRepository

logger = logging.getLogger(__name__)


class ProfileResolverNode:
    """
    Node responsible for resolving profile tags to profile IDs and validating profile context.
    
    This node processes profile filtering parameters from the API request and resolves
    them to a concrete list of profile IDs that will be used throughout the workflow.
    """
    
    def __init__(self):
        """Initialize the Profile Resolver Node."""
        pass
        
    def __call__(self, state: MindMapState) -> Dict[str, Any]:
        """
        Execute profile resolution and validation.
        
        Args:
            state: Current mind-map workflow state
            
        Returns:
            Updated state with resolved_profile_ids populated
        """
        try:
            profile_id = state.get("profile_id")
            profile_ids = state.get("profile_ids")
            profile_tag = state.get("profile_tag")
            profile_tags = state.get("profile_tags")
            
            resolved_profile_ids = []
            
            # Handle single profile ID
            if profile_id:
                resolved_profile_ids.append(profile_id)
                logger.info(f"Using single profile ID: {profile_id}")
            
            # Handle multiple profile IDs
            if profile_ids:
                resolved_profile_ids.extend(profile_ids)
                logger.info(f"Using multiple profile IDs: {profile_ids}")
            
            # Handle single profile tag
            if profile_tag:
                tag_profiles = ProfileRepository.get_by_tags([profile_tag])
                tag_profile_ids = [p["id"] for p in tag_profiles]
                resolved_profile_ids.extend(tag_profile_ids)
                logger.info(f"Resolved tag '{profile_tag}' to profile IDs: {tag_profile_ids}")
            
            # Handle multiple profile tags
            if profile_tags:
                tag_profiles = ProfileRepository.get_by_tags(profile_tags)
                tag_profile_ids = [p["id"] for p in tag_profiles]
                resolved_profile_ids.extend(tag_profile_ids)
                logger.info(f"Resolved tags {profile_tags} to profile IDs: {tag_profile_ids}")
            
            # Remove duplicates while preserving order
            final_profile_ids = list(dict.fromkeys(resolved_profile_ids)) if resolved_profile_ids else None
            
            if final_profile_ids:
                # Validate that all profiles exist
                valid_profiles = []
                for pid in final_profile_ids:
                    profile = ProfileRepository.get(pid)
                    if profile and profile.get("is_active", True):
                        valid_profiles.append(pid)
                    else:
                        logger.warning(f"Profile {pid} not found or inactive, skipping")
                
                if not valid_profiles:
                    logger.warning("No valid profiles found after resolution")
                    return {
                        "resolved_profile_ids": None,
                        "warnings": ["No valid profiles found for the specified filters"],
                        "current_node": "profile_resolver",
                        "messages": [Message(
                            role="assistant", 
                            content="Warning: No valid profiles found for filtering"
                        )]
                    }
                
                logger.info(f"Final resolved profile IDs: {valid_profiles}")
                return {
                    "resolved_profile_ids": valid_profiles,
                    "current_node": "profile_resolver",
                    "messages": [Message(
                        role="assistant", 
                        content=f"Resolved profiles for filtering: {len(valid_profiles)} profile(s)"
                    )]
                }
            else:
                logger.info("No profile filtering requested - using all papers")
                return {
                    "resolved_profile_ids": None,
                    "current_node": "profile_resolver",
                    "messages": [Message(
                        role="assistant", 
                        content="No profile filtering applied - using all papers"
                    )]
                }
            
        except Exception as e:
            logger.error(f"Error in profile resolution: {str(e)}")
            return {
                "errors": [f"Profile resolution failed: {str(e)}"],
                "messages": [Message(role="assistant", content=f"Error resolving profiles: {str(e)}")]
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node."""
        return {
            "node_type": "profile_resolver",
            "description": "Resolves profile tags to profile IDs and validates profile context",
            "inputs": ["profile_id", "profile_ids", "profile_tag", "profile_tags"],
            "outputs": ["resolved_profile_ids"]
        }


def create_profile_resolver_node() -> ProfileResolverNode:
    """
    Factory function to create a ProfileResolverNode.
        
    Returns:
        Configured ProfileResolverNode instance
    """
    return ProfileResolverNode() 