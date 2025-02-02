from .prompting import prompt

@prompt
def podcast_description(podcast_content):
    """Write a short description of the podcast episode that is using this content as the basis for it's content.
Focus on the main topics and contents that are in the content. Write your response in JSON format.
CONTENT: {{podcast_content}}"""