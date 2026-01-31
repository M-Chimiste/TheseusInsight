from setuptools import setup, find_packages
from pathlib import Path

# Load requirements from the requirements.txt file
req_path = Path(__file__).resolve().parent / "requirements.txt"
with req_path.open() as f:
    requirements = [
        line.strip()
        for line in f.read().splitlines()
        if line.strip() and not line.startswith('#')
    ]

setup(
    name="theseus-insight",
    version="1.0.1",
    packages=find_packages(),
    install_requires=requirements,
    python_requires=">=3.10",
)
