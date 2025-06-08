#!/usr/bin/env python3
"""
Utility functions for generating concise summaries from research questions.
"""

import re
from typing import List


def generate_short_summary(research_question: str, max_words: int = 6) -> str:
    """
    Generate a few-word summary from a research question.
    
    Args:
        research_question (str): The full research question
        max_words (int): Maximum number of words in the summary
        
    Returns:
        str: A concise summary of the research question
    """
    if not research_question.strip():
        return "Research Query"
    
    # Clean the question
    cleaned = research_question.strip()
    
    # Remove common question starters
    question_starters = [
        "what are", "what is", "how does", "how do", "how can", "how to",
        "why does", "why do", "why is", "why are", "when does", "when do",
        "where does", "where do", "where is", "where are", "who is", "who are",
        "which is", "which are", "can you", "could you", "would you", "will you",
        "please", "help me", "i want to", "i need to", "tell me about", "explain"
    ]
    
    # Remove question marks and normalize case
    cleaned = cleaned.rstrip('?').lower()
    
    # Remove question starters
    for starter in question_starters:
        if cleaned.startswith(starter):
            cleaned = cleaned[len(starter):].strip()
            break
    
    # Split into words and filter
    words = re.findall(r'\b\w+\b', cleaned)
    
    # Remove common stop words but keep important research terms
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'among', 'within',
        'without', 'under', 'over', 'this', 'that', 'these', 'those', 'am',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'shall'
    }
    
    # Keep important words and filter stop words
    important_words = []
    for word in words:
        if word not in stop_words and len(word) > 2:
            important_words.append(word)
    
    # If we have too few words, include some stop words back
    if len(important_words) < 2 and len(words) >= 2:
        important_words = words[:max_words]
    
    # Take the first max_words important words
    summary_words = important_words[:max_words]
    
    # Capitalize first letter of each word for readability
    summary_words = [word.capitalize() for word in summary_words]
    
    # Join and return
    if summary_words:
        return ' '.join(summary_words)
    else:
        return "Research Query"


def extract_key_themes(research_question: str) -> List[str]:
    """
    Extract key themes/topics from a research question for better categorization.
    
    Args:
        research_question (str): The full research question
        
    Returns:
        List[str]: List of key themes/topics identified
    """
    # Common research domains and their keywords
    domain_keywords = {
        'AI/ML': ['artificial intelligence', 'machine learning', 'neural networks', 'deep learning', 
                  'llm', 'language model', 'transformer', 'gpt', 'bert', 'nlp', 'computer vision'],
        'Healthcare': ['medicine', 'medical', 'health', 'disease', 'therapy', 'treatment', 
                      'clinical', 'patient', 'healthcare', 'pharmaceutical'],
        'Technology': ['software', 'algorithm', 'programming', 'computer', 'technology', 
                      'system', 'application', 'digital', 'cyber'],
        'Science': ['research', 'study', 'analysis', 'experiment', 'scientific', 'methodology',
                   'data', 'statistics', 'theory', 'hypothesis'],
        'Business': ['market', 'business', 'economic', 'finance', 'management', 'strategy',
                    'customer', 'revenue', 'profit', 'industry'],
        'Social': ['social', 'society', 'human', 'behavior', 'psychology', 'culture',
                  'community', 'interaction', 'communication']
    }
    
    question_lower = research_question.lower()
    identified_themes = []
    
    for domain, keywords in domain_keywords.items():
        for keyword in keywords:
            if keyword in question_lower:
                if domain not in identified_themes:
                    identified_themes.append(domain)
                break
    
    return identified_themes


def enhance_summary_with_context(research_question: str, themes: List[str]) -> str:
    """
    Enhance the basic summary with contextual themes.
    
    Args:
        research_question (str): The full research question
        themes (List[str]): List of identified themes
        
    Returns:
        str: Enhanced summary with context
    """
    basic_summary = generate_short_summary(research_question)
    
    if themes:
        # Add the most relevant theme as context
        primary_theme = themes[0]
        return f"{basic_summary} ({primary_theme})"
    
    return basic_summary


# Example usage and testing
if __name__ == "__main__":
    test_questions = [
        "What are the current trends in large language model research?",
        "How does machine learning impact healthcare outcomes?",
        "Can you explain the latest advancements in neural networks?",
        "What is the effectiveness of deep learning in computer vision applications?",
        "Research on artificial intelligence ethics and bias mitigation strategies"
    ]
    
    print("Testing summary generation:")
    for question in test_questions:
        summary = generate_short_summary(question)
        themes = extract_key_themes(question)
        enhanced = enhance_summary_with_context(question, themes)
        
        print(f"\nQuestion: {question}")
        print(f"Basic Summary: {summary}")
        print(f"Themes: {themes}")
        print(f"Enhanced Summary: {enhanced}") 