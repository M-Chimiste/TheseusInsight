from pydantic import BaseModel, Field
from typing import List, Literal


class DialogueItem(BaseModel):
    text: str
    speaker: Literal["speaker-1", "speaker-2", "speaker-3", "speaker-4", "speaker-5", "speaker-6", "speaker-7", "speaker-8", "speaker-9", "speaker-10"]
    segment_label: str | None = None


class Dialogue(BaseModel):
    dialogue: List[DialogueItem]
    section_type: str | None = None

    @staticmethod
    def merge_outputs(outputs: List['Dialogue']) -> 'Dialogue':
        """
        Merges multiple Dialogue models into one, annotating each DialogueItem with its segment label.
        """
        merged_dialogue = []
        for output in outputs:
            segment_label = output.section_type or "unknown"
            for item in output.dialogue:
                # Copy and annotate with segment_label
                merged_dialogue.append(DialogueItem(
                    text=item.text,
                    speaker=item.speaker,
                    segment_label=segment_label
                ))
        return Dialogue(dialogue=merged_dialogue)

class DialogueMessage(BaseModel):
    speaker: Literal["speaker-1", "speaker-2"]
    text: str = Field(..., description="The text content of the dialogue message")

class DialogueOutput(BaseModel):
    dialogue: List[DialogueMessage] = Field(..., description="List of dialogue messages alternating between speakers")

    @staticmethod
    def merge_outputs(outputs: List['DialogueOutput']) -> 'DialogueOutput':
        """
        Merges multiple DialogueOutput models into one, without enforcing alternating speakers.
        """
        merged_dialogue = []

        for output in outputs:
            merged_dialogue.extend(output.dialogue)

        return DialogueOutput(dialogue=merged_dialogue)

class PodcastDescription(BaseModel):
    description: str = Field(..., description="The description of the podcast episode")

class ContentSummary(BaseModel):
    summary: str = Field(..., description="The summary of the text")