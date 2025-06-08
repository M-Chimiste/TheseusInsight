from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
import re
import time
import json
import logging
from pathlib import Path
from datetime import datetime


logger = logging.getLogger(__name__)


def get_research_topic(messages: List[BaseMessage]) -> str:
    """
    Extract the research topic from conversation messages.
    
    Args:
        messages: List of conversation messages
        
    Returns:
        The research topic/question as a string
    """
    if not messages:
        return ""
    
    # Get the last human message as the current research topic
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            return message.content
        elif not hasattr(message, 'type') and isinstance(message, dict):
            if message.get('role') == 'user':
                return message.get('content', '')
    
    # Fallback to the last message content
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, 'content'):
            return last_msg.content
        elif isinstance(last_msg, dict):
            return last_msg.get('content', '')
    
    return ""


def format_paper_results(
    papers: List[Dict[str, Any]], 
    query: str, 
    source_type: str = "local",
    max_results: int = 10
) -> str:
    """
    Format paper search results into a structured summary.
    
    Args:
        papers: List of paper dictionaries with metadata
        query: The search query that produced these results
        source_type: Type of search ("local" or "external")
        max_results: Maximum number of results to include
        
    Returns:
        Formatted string summary of the search results
    """
    if not papers:
        return f"No papers found for query: '{query}' in {source_type} search."
    
    # Limit results
    papers = papers[:max_results]
    
    result_parts = [
        f"## {source_type.title()} Search Results for: '{query}'",
        f"Found {len(papers)} relevant papers:\n"
    ]
    
    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'Unknown Title')
        authors = paper.get('authors', [])
        year = paper.get('year', 'Unknown Year')
        abstract = paper.get('abstract', '')
        url = paper.get('url', paper.get('arxiv_url', ''))
        
        # Format authors
        if isinstance(authors, list):
            if len(authors) > 3:
                author_str = f"{', '.join(authors[:3])}, et al."
            else:
                author_str = ', '.join(authors)
        else:
            author_str = str(authors) if authors else 'Unknown Authors'
        
        # Truncate abstract if too long
        if abstract and len(abstract) > 300:
            abstract = abstract[:297] + "..."
        
        result_parts.extend([
            f"### {i}. {title}",
            f"**Authors:** {author_str}",
            f"**Year:** {year}",
        ])
        
        if url:
            result_parts.append(f"**URL:** {url}")
        
        if abstract:
            result_parts.extend([
                f"**Abstract:** {abstract}",
            ])
        
        # Add extra metadata for enhanced results
        if paper.get('citations'):
            result_parts.append(f"**Citations:** {paper['citations']}")
        
        if paper.get('venue'):
            result_parts.append(f"**Venue:** {paper['venue']}")
        
        if paper.get('pdf_available'):
            result_parts.append(f"**PDF Available:** Yes")
        
        result_parts.append("")  # Empty line between papers
    
    return "\n".join(result_parts)


def extract_citations_from_summary(summary: str) -> List[Dict[str, str]]:
    """
    Extract citation information from a research summary.
    
    Args:
        summary: The research summary text
        
    Returns:
        List of dictionaries containing citation metadata
    """
    citations = []
    
    # Pattern to match URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, summary)
    
    # Pattern to match titles (between ### and following lines)
    title_pattern = r'###\s*\d+\.\s*([^\n]+)'
    titles = re.findall(title_pattern, summary)
    
    # Pattern to match authors
    author_pattern = r'\*\*Authors:\*\*\s*([^\n]+)'
    authors = re.findall(author_pattern, summary)
    
    # Pattern to match years
    year_pattern = r'\*\*Year:\*\*\s*([^\n]+)'
    years = re.findall(year_pattern, summary)
    
    # Combine the extracted information
    for i in range(min(len(titles), len(urls))):
        citation = {
            'title': titles[i].strip(),
            'url': urls[i] if i < len(urls) else '',
        }
        
        if i < len(authors):
            citation['authors'] = authors[i].strip()
        
        if i < len(years):
            citation['year'] = years[i].strip()
        
        citations.append(citation)
    
    # Also extract any additional URLs not matched with titles
    for url in urls[len(titles):]:
        citations.append({
            'title': 'Untitled Reference',
            'url': url,
            'authors': '',
            'year': ''
        })
    
    return citations


def generate_research_insights(summaries: List[str]) -> str:
    """
    Generate insights and patterns from research summaries.
    
    Args:
        summaries: List of research summary strings
        
    Returns:
        String containing research insights and patterns
    """
    if not summaries:
        return ""
    
    insights = []
    
    # Count total papers found
    total_papers = 0
    local_papers = 0
    external_papers = 0
    
    # Extract themes and keywords
    themes = set()
    years = set()
    authors = set()
    
    for summary in summaries:
        if not summary:
            continue
            
        # Count papers
        paper_count_match = re.search(r'Found (\d+) relevant papers', summary)
        if paper_count_match:
            count = int(paper_count_match.group(1))
            total_papers += count
            
            if 'Local Search Results' in summary:
                local_papers += count
            elif 'External Search Results' in summary:
                external_papers += count
        
        # Extract years
        year_matches = re.findall(r'\*\*Year:\*\*\s*(\d{4})', summary)
        years.update(year_matches)
        
        # Extract author names (first author from each paper)
        author_matches = re.findall(r'\*\*Authors:\*\*\s*([^,\n]+)', summary)
        authors.update([author.strip() for author in author_matches])
        
        # Extract potential themes from titles
        title_matches = re.findall(r'###\s*\d+\.\s*([^\n]+)', summary)
        for title in title_matches:
            # Simple keyword extraction from titles
            words = re.findall(r'\b[A-Za-z]{4,}\b', title.lower())
            themes.update(words[:3])  # Take first 3 significant words
    
    # Generate insights
    if total_papers > 0:
        insights.append(f"**Total Papers Found:** {total_papers}")
        
        if local_papers > 0:
            insights.append(f"- Local database: {local_papers} papers")
        if external_papers > 0:
            insights.append(f"- External sources: {external_papers} papers")
    
    if years:
        year_list = sorted([int(y) for y in years if y.isdigit()])
        if year_list:
            insights.append(f"**Publication Years:** {min(year_list)}-{max(year_list)}")
            recent_papers = len([y for y in year_list if y >= 2020])
            if recent_papers > 0:
                insights.append(f"- Recent papers (2020+): {recent_papers}")
    
    if len(authors) > 1:
        insights.append(f"**Key Authors:** {len(authors)} different first authors identified")
    
    if themes:
        # Filter out common words
        common_words = {'learning', 'analysis', 'study', 'research', 'based', 'using', 'neural', 'model'}
        significant_themes = [t for t in themes if t not in common_words and len(t) > 4]
        if significant_themes:
            insights.append(f"**Research Themes:** {', '.join(list(significant_themes)[:5])}")
    
    return "\n".join(insights) if insights else ""


def combine_search_results(
    results: List[str], 
    queries: List[str],
    max_length: int = 5000
) -> str:
    """
    Combine multiple search results into a unified summary.
    
    Args:
        results: List of search result strings
        queries: List of search queries that produced the results
        max_length: Maximum length of the combined summary
        
    Returns:
        Combined and structured summary string
    """
    if not results:
        return "No search results available."
    
    combined_parts = []
    
    # Add header with overview
    combined_parts.append("# Combined Research Results")
    combined_parts.append(f"Based on {len(queries)} search queries:")
    for i, query in enumerate(queries, 1):
        combined_parts.append(f"{i}. {query}")
    combined_parts.append("")
    
    # Add each result with clear separation
    for i, result in enumerate(results):
        if not result or result.strip() == "":
            continue
            
        # Add section header
        query_context = queries[i] if i < len(queries) else f"Query {i+1}"
        combined_parts.append(f"## Results for: {query_context}")
        combined_parts.append(result)
        combined_parts.append("\n---\n")
    
    # Combine all parts
    combined_text = "\n".join(combined_parts)
    
    # Truncate if too long, preserving structure
    if len(combined_text) > max_length:
        # Try to find a good breaking point
        truncated = combined_text[:max_length]
        last_paper_break = truncated.rfind("### ")
        if last_paper_break > max_length * 0.7:  # If we can save most content
            combined_text = truncated[:last_paper_break] + "\n\n[Results truncated for length]"
        else:
            combined_text = truncated + "\n\n[Results truncated for length]"
    
    return combined_text


def extract_research_gaps(summaries: List[str]) -> List[str]:
    """
    Identify potential research gaps from summaries.
    
    Args:
        summaries: List of research summary strings
        
    Returns:
        List of identified research gaps or areas for further investigation
    """
    gaps = []
    
    # Common indicators of research gaps
    gap_indicators = [
        "limited research",
        "few studies",
        "further investigation",
        "future work",
        "understudied",
        "gap in knowledge",
        "needs more research"
    ]
    
    for summary in summaries:
        if not summary:
            continue
            
        # Look for explicit gap mentions
        for indicator in gap_indicators:
            if indicator in summary.lower():
                # Extract the sentence containing the gap
                sentences = re.split(r'[.!?]', summary)
                for sentence in sentences:
                    if indicator in sentence.lower():
                        gaps.append(sentence.strip())
                        break
        
        # Look for areas with few papers
        paper_count_match = re.search(r'Found (\d+) relevant papers', summary)
        if paper_count_match and int(paper_count_match.group(1)) < 3:
            query_match = re.search(r"Results for: '([^']+)'", summary)
            if query_match:
                gaps.append(f"Limited literature on: {query_match.group(1)}")
    
    # Remove duplicates and return unique gaps
    return list(set(gaps))


def format_conversation_context(messages: List[BaseMessage], max_context: int = 1000) -> str:
    """
    Format conversation history for context in research queries.
    
    Args:
        messages: List of conversation messages
        max_context: Maximum character length for context
        
    Returns:
        Formatted conversation context string
    """
    if not messages or len(messages) <= 1:
        return ""
    
    context_parts = []
    char_count = 0
    
    # Process messages in reverse order (most recent first)
    for message in reversed(messages[:-1]):  # Exclude the current message
        role = "User" if (hasattr(message, 'type') and message.type == 'human') else "Assistant"
        content = message.content if hasattr(message, 'content') else str(message)
        
        # Truncate individual messages if too long
        if len(content) > 200:
            content = content[:197] + "..."
        
        message_text = f"{role}: {content}"
        
        # Check if adding this message would exceed the limit
        if char_count + len(message_text) > max_context:
            break
            
        context_parts.append(message_text)
        char_count += len(message_text)
    
    # Reverse to get chronological order
    context_parts.reverse()
    
    if context_parts:
        return "Previous conversation:\n" + "\n".join(context_parts) + "\n\n"
    return ""


def validate_search_result(result: str) -> bool:
    """
    Validate if a search result contains meaningful content.
    
    Args:
        result: Search result string to validate
        
    Returns:
        True if the result contains meaningful content, False otherwise
    """
    if not result or len(result.strip()) < 50:
        return False
    
    # Check for common error indicators
    error_indicators = [
        "error occurred",
        "failed to",
        "no results",
        "connection timeout",
        "service unavailable"
    ]
    
    result_lower = result.lower()
    for indicator in error_indicators:
        if indicator in result_lower:
            return False
    
    # Check for meaningful content indicators
    content_indicators = [
        "abstract:",
        "authors:",
        "year:",
        "papers found",
        "title:"
    ]
    
    for indicator in content_indicators:
        if indicator in result_lower:
            return True
    
    return True


def clean_search_query(query: str) -> str:
    """
    Clean and normalize a search query.
    
    Args:
        query: Raw search query string
        
    Returns:
        Cleaned and normalized query string
    """
    if not query:
        return ""
    
    # Remove extra whitespace
    query = re.sub(r'\s+', ' ', query.strip())
    
    # Remove common stop words that don't add value to search
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    words = query.lower().split()
    
    # Keep the query if it's short or if removing stop words would make it too short
    if len(words) <= 3:
        return query
    
    filtered_words = [word for word in words if word not in stop_words]
    
    if len(filtered_words) >= 2:
        return ' '.join(filtered_words)
    else:
        return query  # Return original if filtering removes too much


def extract_key_metrics(summaries: List[str]) -> Dict[str, Any]:
    """
    Extract key research metrics from summaries for analysis.
    
    Args:
        summaries: List of research summary strings
        
    Returns:
        Dictionary containing extracted metrics
    """
    metrics = {
        'total_papers': 0,
        'local_papers': 0,
        'external_papers': 0,
        'year_range': None,
        'recent_papers_count': 0,
        'unique_authors': 0,
        'avg_citations': None,
        'top_venues': [],
        'research_themes': []
    }
    
    all_years = []
    all_authors = set()
    all_citations = []
    all_venues = []
    all_themes = set()
    
    for summary in summaries:
        if not summary:
            continue
        
        # Extract paper counts
        paper_count_match = re.search(r'Found (\d+) relevant papers', summary)
        if paper_count_match:
            count = int(paper_count_match.group(1))
            metrics['total_papers'] += count
            
            if 'Local Search Results' in summary:
                metrics['local_papers'] += count
            elif 'External Search Results' in summary:
                metrics['external_papers'] += count
        
        # Extract years
        year_matches = re.findall(r'\*\*Year:\*\*\s*(\d{4})', summary)
        all_years.extend([int(y) for y in year_matches if y.isdigit()])
        
        # Extract authors
        author_matches = re.findall(r'\*\*Authors:\*\*\s*([^\n]+)', summary)
        for author_line in author_matches:
            # Split by common separators and take first author
            first_author = re.split(r'[,;&]', author_line)[0].strip()
            all_authors.add(first_author)
        
        # Extract citations
        citation_matches = re.findall(r'\*\*Citations:\*\*\s*(\d+)', summary)
        all_citations.extend([int(c) for c in citation_matches])
        
        # Extract venues
        venue_matches = re.findall(r'\*\*Venue:\*\*\s*([^\n]+)', summary)
        all_venues.extend([v.strip() for v in venue_matches])
        
        # Extract themes from titles
        title_matches = re.findall(r'###\s*\d+\.\s*([^\n]+)', summary)
        for title in title_matches:
            words = re.findall(r'\b[A-Za-z]{5,}\b', title.lower())
            all_themes.update(words[:2])
    
    # Process collected data
    if all_years:
        metrics['year_range'] = (min(all_years), max(all_years))
        metrics['recent_papers_count'] = len([y for y in all_years if y >= 2020])
    
    metrics['unique_authors'] = len(all_authors)
    
    if all_citations:
        metrics['avg_citations'] = sum(all_citations) / len(all_citations)
    
    # Get top venues
    if all_venues:
        from collections import Counter
        venue_counts = Counter(all_venues)
        metrics['top_venues'] = venue_counts.most_common(5)
    
    # Filter research themes
    common_words = {'learning', 'analysis', 'study', 'research', 'based', 'using', 'neural', 'model'}
    significant_themes = [t for t in all_themes if t not in common_words]
    metrics['research_themes'] = list(significant_themes)[:10]
    
    return metrics 