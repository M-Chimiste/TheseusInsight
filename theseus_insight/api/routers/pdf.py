from fastapi import APIRouter, UploadFile, HTTPException
from typing import List
import tempfile
import os
from pathlib import Path

router = APIRouter()

# Configure upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_pdf(file: UploadFile):
    """
    Upload a PDF file.
    Returns the file path that can be used by the podcast generator.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Create a unique filename to avoid collisions
        file_path = UPLOAD_DIR / f"{file.filename}"
        
        # Save the file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "filename": file.filename,
            "file_path": str(file_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-upload")
async def upload_multiple_pdfs(files: List[UploadFile]):
    """
    Upload multiple PDF files.
    Returns a list of file paths that can be used by the podcast generator.
    """
    results = []
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            continue
        
        try:
            # Create a unique filename to avoid collisions
            file_path = UPLOAD_DIR / f"{file.filename}"
            
            # Save the file
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            results.append({
                "filename": file.filename,
                "file_path": str(file_path)
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    if not results:
        raise HTTPException(status_code=400, detail="No valid PDF files provided")
    
    return results
