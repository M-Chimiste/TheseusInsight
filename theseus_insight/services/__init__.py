"""Services layer for TheseusInsight.

This module contains high-level business logic services that orchestrate
multiple repositories and components to provide complete features.
"""

from .embedding_service import StreamingEmbeddingService, EmbeddingServiceConfig

__all__ = ['StreamingEmbeddingService', 'EmbeddingServiceConfig']


