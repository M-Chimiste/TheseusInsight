from setuptools import setup, find_packages

setup(
    name="paperpal",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "python-multipart",
        "pydantic",
        "spacy",
        "spacy-layout",
        "docling",
        "python-dotenv",
        "pandas",
        "moviepy",
        "pygame",
        "pydub",
        "numpy",
    ],
    python_requires=">=3.8",
)