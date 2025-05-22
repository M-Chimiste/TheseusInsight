from .prompting import prompt

@prompt
def podcast_description(podcast_content):
    """Write a short description of the podcast episode that is using this content as the basis for it's content.
Focus on the main topics and contents that are in the content. Write your response in JSON format.
CONTENT: {{podcast_content}}"""

@prompt
def summary_prompt(text):
    """Please summarize the following text extracted from a PDF document:

{{text}}

Your summary should highlight the main ideas, key points, and any important details that capture \
the essence of the document. Keep the summary concise and ensure that it accurately reflects the \
content of the original text."""