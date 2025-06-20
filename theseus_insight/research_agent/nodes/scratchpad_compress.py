"""
Scratchpad Compression Node for Research Agent

Compresses evidence and context when token limits are exceeded
to maintain essential information within the token budget.
"""

import logging
from typing import Dict, Any, List

from ..state import OverallState, Message
from ..prompts import scratchpad_compress_prompt
from ..model_router import supports_structured_output
from ..schemas import CompressionResponse, StructuredParsingHelper


class ScratchpadCompressNode:
    """
    LangGraph node that compresses evidence to fit within token budgets.
    
    This node is triggered when the evidence exceeds the maximum context
    tokens and compresses the information while preserving the most
    important details for answer generation.
    """
    
    def __init__(
        self, 
        config: Dict[str, Any],
        max_tokens: int = 15000,
        compression_ratio: float = 0.2,
        preserve_citations: bool = True
    ):
        """
        Initialize the scratchpad compression node.
        
        Args:
            config: Configuration dictionary containing model settings
            max_tokens: Maximum tokens allowed in compressed output
            compression_ratio: Target compression ratio (0.2 = 20% of original)
            preserve_citations: Whether to preserve citation information
        """
        self.config = config
        from ..model_router import get_model_for_node
        self.model_client = get_model_for_node("scratchpad_compress", config)
        self.max_tokens = max_tokens
        self.compression_ratio = compression_ratio
        self.preserve_citations = preserve_citations
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, state: OverallState) -> Dict[str, Any]:
        """
        Execute evidence compression.
        
        Args:
            state: Current research agent state
            
        Returns:
            Updated state with compressed notes
        """
        self.logger.info("Starting evidence compression")
        
        try:
            # Get evidence from state
            evidence = state.get("evidence", [])
            if not evidence:
                self.logger.warning("No evidence available for compression")
                return {
                    "compressed_notes": "",
                    "messages": [Message(role="assistant", content="⚠️ No evidence available for compression.")]
                }
            
            # Check if compression is actually needed
            total_tokens = self._estimate_tokens(evidence)
            if total_tokens <= self.max_tokens:
                self.logger.info(f"Evidence ({total_tokens} tokens) within limit, no compression needed")
                return {
                    "compressed_notes": "\n\n".join(evidence),
                    "messages": [Message(role="assistant", content=f"📝 Evidence review: {total_tokens} tokens within budget, no compression needed.")]
                }
            
            # Extract main research question for context
            main_question = self._extract_main_question(state.get("messages", []))
            
            # Perform compression
            compressed_notes = self._compress_evidence(main_question, evidence, total_tokens)
            
            # Create compression summary
            compression_summary = self._create_compression_summary(
                total_tokens, len(compressed_notes), evidence, compressed_notes
            )
            
            self.logger.info(
                f"Compression complete: {total_tokens} -> {self._estimate_tokens([compressed_notes])} tokens "
                f"({len(evidence)} -> 1 piece)"
            )
            
            return {
                "compressed_notes": compressed_notes,
                "messages": [Message(role="assistant", content=compression_summary)]
            }
            
        except Exception as e:
            self.logger.error(f"Error in evidence compression: {e}")
            # Fallback: use truncated evidence
            fallback_notes = self._fallback_compression(state.get("evidence", []))
            return {
                "compressed_notes": fallback_notes,
                "messages": [Message(role="assistant", content=f"🚨 Compression error: {str(e)}. Using truncated evidence as fallback.")]
            }
    
    def _estimate_tokens(self, text_pieces: List[str]) -> int:
        """
        Estimate token count for text pieces.
        
        Args:
            text_pieces: List of text pieces to count
            
        Returns:
            Estimated token count
        """
        # Simple estimation: ~4 characters per token
        total_chars = sum(len(piece) for piece in text_pieces)
        return total_chars // 4
    
    def _extract_main_question(self, messages: List) -> str:
        """Extract the main research question from messages."""
        for message in reversed(messages):
            if hasattr(message, 'role') and message.role == 'user' and hasattr(message, 'content'):
                return message.content.strip()
        
        return "Research question not found"
    
    def _compress_evidence(
        self, 
        main_question: str, 
        evidence_pieces: List[str], 
        original_tokens: int
    ) -> str:
        """
        Compress evidence using LLM while preserving key information.
        
        Args:
            main_question: The main research question
            evidence_pieces: List of evidence pieces to compress
            original_tokens: Original token count
            
        Returns:
            Compressed evidence text
        """
        try:
            # Calculate target token count
            target_tokens = int(original_tokens * self.compression_ratio)
            target_tokens = min(target_tokens, self.max_tokens)
            
            # Create compression prompt
            prompt = scratchpad_compress_prompt(
                research_question=main_question,
                evidence_pieces=evidence_pieces,
                target_tokens=target_tokens,
                preserve_citations=self.preserve_citations
            )
            
            # Get compressed response using unified interface with structured output if supported
            messages = [{"role": "user", "content": prompt}]
            system_prompt = "You are a research assistant that compresses evidence while preserving key information and citations."
            
            # Try structured output first if supported
            structured_response = None
            if supports_structured_output(self.model_client.provider):
                try:
                    response = self.model_client.invoke(
                        messages, 
                        system_prompt, 
                        schema=CompressionResponse
                    )
                    # Parse structured response if it's JSON
                    if isinstance(response, str):
                        structured_response = StructuredParsingHelper.parse_with_fallback(
                            response, CompressionResponse, self.logger
                        )
                    else:
                        # Response is already structured
                        structured_response = response
                except Exception as e:
                    self.logger.warning(f"Structured output failed, falling back to text parsing: {e}")
            
            # Fallback to regular response if structured failed
            if structured_response is None:
                response = self.model_client.invoke(messages, system_prompt)
                structured_response = StructuredParsingHelper.parse_with_fallback(
                    response, CompressionResponse, self.logger
                )
            
            # Extract compressed content from structured response or fallback to direct response
            if structured_response and isinstance(structured_response, CompressionResponse):
                compressed_text = structured_response.compressed_content
                self.logger.info(f"Structured compression successful: {structured_response.compression_notes}")
            else:
                # Fallback to direct response
                self.logger.warning("Using fallback compression parsing")
                response = self.model_client.invoke(messages, system_prompt) if 'response' not in locals() else response
                compressed_text = response
            
            # Validate compression
            compressed_tokens = self._estimate_tokens([compressed_text])
            if compressed_tokens > self.max_tokens:
                self.logger.warning(f"Compression exceeded target ({compressed_tokens} > {self.max_tokens}), truncating")
                compressed_text = self._truncate_to_token_limit(compressed_text, self.max_tokens)
            
            return compressed_text
            
        except Exception as e:
            self.logger.error(f"Error in LLM compression: {e}")
            return self._fallback_compression(evidence_pieces)
    
    def _fallback_compression(self, evidence_pieces: List[str]) -> str:
        """
        Fallback compression using simple truncation and summarization.
        
        Args:
            evidence_pieces: Evidence pieces to compress
            
        Returns:
            Compressed evidence text
        """
        # Extract key information from each piece
        compressed_parts = []
        
        for i, evidence in enumerate(evidence_pieces, 1):
            # Extract title and key points
            lines = evidence.split('\n')
            title_line = next((line for line in lines if line.startswith('**Source**:')), f"Source {i}")
            
            # Find abstract or main content
            abstract_start = -1
            for j, line in enumerate(lines):
                if '**Abstract**:' in line or 'Abstract:' in line:
                    abstract_start = j + 1
                    break
            
            if abstract_start > 0 and abstract_start < len(lines):
                # Take first 200 characters of abstract
                abstract_text = ' '.join(lines[abstract_start:])[:200] + "..."
                compressed_parts.append(f"{title_line}\n{abstract_text}")
            else:
                # Take first 150 characters of the evidence
                compressed_parts.append(evidence[:150] + "...")
        
        # Combine and ensure within token limit
        combined = "\n\n".join(compressed_parts)
        return self._truncate_to_token_limit(combined, self.max_tokens)
    
    def _truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated text
        """
        # Estimate max characters
        max_chars = max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # Truncate at sentence boundary if possible
        truncated = text[:max_chars]
        last_sentence = truncated.rfind('.')
        
        if last_sentence > max_chars * 0.8:  # If we can find a sentence end reasonably close
            return truncated[:last_sentence + 1] + "\n\n[Content truncated due to token limit]"
        else:
            return truncated + "\n\n[Content truncated due to token limit]"
    
    def _create_compression_summary(
        self,
        original_tokens: int,
        compressed_tokens: int,
        original_evidence: List[str],
        compressed_notes: str
    ) -> str:
        """
        Create a summary of the compression process.
        
        Args:
            original_tokens: Original token count
            compressed_tokens: Compressed token count
            original_evidence: Original evidence pieces
            compressed_notes: Compressed notes
            
        Returns:
            Formatted compression summary
        """
        compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 0
        
        summary_lines = [
            "🗜️ EVIDENCE COMPRESSION COMPLETE",
            "",
            "📊 COMPRESSION STATISTICS:",
            f"  • Original Evidence Pieces: {len(original_evidence)}",
            f"  • Original Token Count: {original_tokens:,}",
            f"  • Compressed Token Count: {compressed_tokens:,}",
            f"  • Compression Ratio: {compression_ratio:.1%}",
            f"  • Token Reduction: {original_tokens - compressed_tokens:,} tokens saved",
            "",
            "🎯 COMPRESSION STRATEGY:",
            f"  • Target Token Limit: {self.max_tokens:,}",
            f"  • Preserve Citations: {'Yes' if self.preserve_citations else 'No'}",
            f"  • Method: {'LLM-based compression' if 'LLM' in str(type(self.model_client)) else 'Fallback truncation'}",
            "",
            "📝 COMPRESSED CONTENT PREVIEW:",
            f"  • Length: {len(compressed_notes)} characters",
            f"  • Preview: {compressed_notes[:200]}{'...' if len(compressed_notes) > 200 else ''}",
            "",
            "🚀 NEXT STEPS:",
            "Compressed evidence is ready for answer generation within token budget.",
            ""
        ]
        
        return "\n".join(summary_lines)
    
    def update_compression_settings(
        self, 
        max_tokens: int = None, 
        compression_ratio: float = None,
        preserve_citations: bool = None
    ) -> None:
        """
        Update compression settings.
        
        Args:
            max_tokens: New maximum token limit
            compression_ratio: New compression ratio
            preserve_citations: New citation preservation setting
        """
        if max_tokens is not None:
            self.max_tokens = max_tokens
        if compression_ratio is not None:
            self.compression_ratio = compression_ratio
        if preserve_citations is not None:
            self.preserve_citations = preserve_citations
        
        self.logger.info(f"Updated compression settings: max_tokens={self.max_tokens}, "
                        f"ratio={self.compression_ratio}, preserve_citations={self.preserve_citations}")
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get information about this node for monitoring and debugging."""
        return {
            "node_type": "scratchpad_compress",
            "max_tokens": self.max_tokens,
            "compression_ratio": self.compression_ratio,
            "preserve_citations": self.preserve_citations,
            "model_client": str(type(self.model_client).__name__),
            "description": "Compresses evidence to fit within token budgets while preserving key information"
        } 