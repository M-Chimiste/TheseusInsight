INSTRUCTION_TEMPLATES = {
  "podcast_into": """Your task is to create a brief yet captivating cold open and agenda for an episode of the podcast 'AI by AI.' \
The input will be a combined or summarized overview of all the topics planned for the episode. Kick things off with an attention-grabbing hook, \
then provide a clear roadmap of what’s coming up without venturing into a full conclusion or outro. Maintain a relaxed, conversational tone \
inspired by the All In Podcast, but do not mention or invent any speaker names. Define any specialized terms in simple language so that anyone \
listening can easily follow along. Focus on being welcoming, energetic, and concise, setting the stage for a deeper exploration in the upcoming sections.""",
  
"podcast_section": """Your task is to generate a deep-dive discussion based on the input text, which will typically be content extracted from parsed PDFs \
or other research. This is part of the 'AI by AI' podcast, so no formal intro or outro should appear here—just jump straight into the detailed conversation. \
Present key findings, discuss interesting points, and clarify concepts, always speaking in a lively, engaging style that keeps listeners intrigued. Keep \
the language straightforward and define terms in an accessible manner. Avoid any unnecessary asides or filler; stay on topic and let the content shine \
through. Do not mention or fabricate any speaker names. Your goal is to immerse listeners in the substance of the research while maintaining a casual, \
conversational tone that feels both informative and approachable.""",
  
  "podcast_outro": """Your task is to craft a concluding segment for the 'AI by AI' podcast after the entire conversation—including all deep-dive \
sections—has been completed. You will receive the full transcript of the episode as input. Summarize the main themes and insights from the show \
without making it feel like a bullet-point recap. Instead, weave in key highlights naturally as part of a friendly and organic closing discussion. \
Keep the tone casual, reflective, and forward-looking, offering a sense of closure while hinting at future possibilities or topics. Avoid introducing \
new topics or repeating any speaker names. The goal is to leave listeners satisfied, informed, and excited about what might come next."""
}