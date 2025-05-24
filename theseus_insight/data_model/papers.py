from pydantic import BaseModel, Field, field_validator
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from ..constants import _ARXIV_NS


class ArxivRecord(BaseModel):
    """Structured representation of a single arXiv paper (metadata only).
    
    This class represents the metadata of an arXiv paper, including its ID, title,
    abstract, authors, and other relevant information. It inherits from Pydantic's
    BaseModel for data validation.

    Attributes:
        xml (ET.Element): The raw XML element containing the paper's metadata.
        id (str): ArXiv ID of the paper.
        url (str): URL to the paper's arXiv abstract.
        pdf_url (str): URL to the paper's PDF.
        title (str): Title of the paper.
        abstract (str): Abstract of the paper.
        categories (str): ArXiv categories the paper belongs to.
        created (str): Creation date of the paper.
        updated (str): Last update date of the paper.
        doi (str): Digital Object Identifier of the paper.
        authors (List[str]): List of author names.
        affiliation (List[str]): List of author affiliations.
    """

    model_config = {"arbitrary_types_allowed": True}

    xml: ET.Element
    id: str = Field(description="ArXiv ID of the paper")
    url: str = Field(description="URL to the paper's arXiv abstract")
    pdf_url: str = Field(description="URL to the paper's PDF")
    title: str = Field(description="Title of the paper")
    abstract: str = Field(description="Abstract text of the paper")
    categories: str = Field(alias="cats", description="Categories the paper falls into.")
    created: str = Field(description="ArXiv created date of the paper")
    updated: str = Field(description="ArXiv updated date of the paper")
    doi: str = Field(description="DOI of the paper")
    authors: List[str] = Field(description="Paper authors")
    affiliation: List[str] = Field(description="Author affiliations")

    @staticmethod
    def _get_text(xml: ET.Element, tag: str) -> str:
        """Extract text content from an XML element.

        Args:
            xml (ET.Element): The XML element to search in.
            tag (str): The tag name to find.

        Returns:
            str: The text content of the found element, or empty string if not found.
        """
        try:
            text = xml.find(_ARXIV_NS + tag).text
            if text:
                # Clean up the text by removing newlines and normalizing whitespace
                # This is especially important for titles which can have line breaks
                import re
                # Replace all whitespace (including newlines, tabs) with single spaces
                cleaned_text = re.sub(r'\s+', ' ', text)
                return cleaned_text.strip()
            return ""
        except Exception:  # noqa: BLE001 E722
            return ""

    @staticmethod
    def _get_name(parent: ET.Element, tag: str) -> str:
        """Extract name information from an author XML element.

        Args:
            parent (ET.Element): The parent XML element containing author information.
            tag (str): The tag name to find (e.g., 'forenames' or 'keyname').

        Returns:
            str: The extracted name, or 'n/a' if not found.
        """
        try:
            return parent.find(_ARXIV_NS + tag).text.strip()
        except Exception:  # noqa: BLE001 E722
            return "n/a"

    @staticmethod
    def _get_authors(xml: ET.Element) -> List[str]:
        """Extract all author names from the XML.

        Args:
            xml (ET.Element): The XML element containing author information.

        Returns:
            List[str]: List of author names in "firstname lastname" format.
        """
        people = xml.findall(_ARXIV_NS + "authors/" + _ARXIV_NS + "author")
        firsts = [ArxivRecord._get_name(p, "forenames") for p in people]
        lasts = [ArxivRecord._get_name(p, "keyname") for p in people]
        return [f"{f} {l}".strip() for f, l in zip(firsts, lasts)]

    @staticmethod
    def _get_affiliations(xml: ET.Element) -> List[str]:
        """Extract all author affiliations from the XML.

        Args:
            xml (ET.Element): The XML element containing author information.

        Returns:
            List[str]: List of author affiliations.
        """
        people = xml.findall(_ARXIV_NS + "authors/" + _ARXIV_NS + "author")
        affils = []
        for p in people:
            try:
                affils.append(p.find(_ARXIV_NS + "affiliation").text.strip())
            except Exception:  # noqa: BLE001 E722
                pass
        return affils

    def __init__(self, xml_record: ET.Element):
        """Initialize a Record instance from an XML element.

        Args:
            xml_record (ET.Element): The XML element containing the paper's metadata.
        """
        _id = self._get_text(xml_record, "id")
        super().__init__(
            xml=xml_record,
            id=_id,
            url=f"https://arxiv.org/abs/{_id}",
            pdf_url=f"https://arxiv.org/pdf/{_id}.pdf",
            title=self._get_text(xml_record, "title"),
            abstract=self._get_text(xml_record, "abstract"),
            cats=self._get_text(xml_record, "categories"),
            created=self._get_text(xml_record, "created"),
            updated=self._get_text(xml_record, "updated"),
            doi=self._get_text(xml_record, "doi"),
            authors=self._get_authors(xml_record),
            affiliation=self._get_affiliations(xml_record),
        )

    def model_dump(self) -> Dict[str, Any]:
        """Convert the record to a dictionary, excluding the raw XML.

        Returns:
            Dict[str, Any]: Dictionary representation of the record without the XML element.
        """
        data = super().model_dump()
        data.pop("xml", None)
        return data

class Newsletter(BaseModel):
    content: str
    start_date: str
    end_date: str
    date_sent: str
    

class Paper(BaseModel):
    title: str
    abstract: str
    date: str
    date_run: str
    score: float | int
    rationale: str
    related: bool
    cosine_similarity: float
    url: str
    embedding_model: str
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding of the paper's abstract")

    @field_validator('score')
    @classmethod
    def score_range(cls, v):
        if not 0 <= v <= 10:
            raise ValueError('Score must be between 0 and 10')
        return v

class Logs(BaseModel):
    task_id: str
    status: str
    datetime_run: str | None = None

class Podcast(BaseModel):
    title: str
    date: str
    script: list
    description: str