import datetime
import numpy as np
import requests
import re

TODAY = datetime.date.today()

def get_n_days_ago(n_days):
    """
    Get the date n days ago from today.

    Args:
        n_days (int): Number of days to look back.

    Returns:
        datetime.date: The date n days ago.
    """
    return TODAY - datetime.timedelta(days=n_days)


def cosine_similarity(a, b):
    """
    Calculate the cosine similarity between two vectors.

    Args:
        a (numpy.ndarray): First vector.
        b (numpy.ndarray): Second vector.

    Returns:
        float: The cosine similarity between the two vectors.
    """
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def purge_ollama_cache(ollama_url, model_name):
    """
    Purge the cache for a specific Ollama model.

    This function sends a request to the Ollama API to clear the cache for the specified model,
    which can help free up system resources. It sends a generate request with keep_alive=0 to
    ensure the model is unloaded.

    Args:
        ollama_url (str): The base URL of the Ollama API server (e.g. "http://localhost:11434")
        model_name (str): The name of the model to purge from cache

    Returns:
        None
    """
    requests.post(f"{ollama_url}/api/generate", json={"model": model_name, "keep_alive": 0})


def clean_string(input_string):
    """
    Cleans the input string by performing the following operations:

    1. Replaces multiple consecutive newline characters with a single newline character.
    2. Removes any leading and trailing whitespace from the string.

    Args:
        input_string (str): The string to be cleaned.
        
    Returns:
        str: The cleaned string with single newlines and no leading or trailing whitespace.
"""
    cleaned_string = re.sub(r'\n+', '\n', input_string)
    cleaned_string = cleaned_string.strip()
    return cleaned_string


def remove_markdown_tables(text: str) -> str:
    """
    Remove Markdown tables from the given text.
    This function identifies and removes lines that are part of Markdown tables.
    Specifically, it removes lines that start and end with '|' (table rows) and
    lines that are used as table headers or separators (e.g., "| --- | :---: | --- |").
    Args:
        text (str): The input text containing potential Markdown tables.
    Returns:
        str: The text with Markdown tables removed.
    """
   
    # A line that starts with '|' and ends with '|', ignoring leading/trailing spaces:
    table_row_pattern = re.compile(r'^\s*\|.*\|\s*$')
    
    # A line often used for table headers/separators, 
    # e.g. "| --- | :---: | --- |"
    # This pattern can vary, so feel free to make it more general or strict:
    table_separator_pattern = re.compile(r'^\s*\|(?:\s*:?-+:?\s*\|)+\s*$')

    filtered_lines = []
    for line in text.split('\n'):
        if table_row_pattern.match(line) or table_separator_pattern.match(line):
            # It's a Markdown table row or separator -> skip it
            continue
        else:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)
