from pydantic import BaseModel, Field
from typing import List, Literal


class DialogueItem(BaseModel):
    text: str
    speaker: Literal["speaker-1", "speaker-2"]


class Dialogue(BaseModel):
    dialogue: List[DialogueItem]

    @staticmethod
    def merge_outputs(outputs: List['Dialogue']) -> 'Dialogue':
        """
        Merges multiple Dialogue models into one, without enforcing alternating speakers.
        """
        merged_dialogue = []
        for output in outputs:
            merged_dialogue.extend(output.dialogue)
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