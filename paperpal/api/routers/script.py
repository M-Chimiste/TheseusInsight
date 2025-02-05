from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import os
import time
from paperpal.data_processing.data_handling import PaperDatabase, Podcast

router = APIRouter()

# Configure paths
DB_PATH = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "data/papers.db"
SCRIPT_DIR = Path("scripts")

# Initialize directories and database
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = PaperDatabase(str(DB_PATH))

class DialogueItem(BaseModel):
    speaker: str
    text: str

class Script(BaseModel):
    dialogue: List[DialogueItem]
    metadata: Optional[Dict[str, Any]] = None

class ScriptListItem(BaseModel):
    filename: str
    last_modified: float

@router.get("/list")
async def list_scripts() -> List[ScriptListItem]:
    """
    List all available scripts from both the filesystem and database.
    """
    try:
        scripts = []
        
        # Get scripts from filesystem
        for file in SCRIPT_DIR.glob("*.json"):
            scripts.append(ScriptListItem(
                filename=file.name,
                last_modified=file.stat().st_mtime
            ))
        
        # Get scripts from database
        podcasts = db.fetch_all_podcasts()
        for podcast in podcasts:
            filename = f"podcast_{podcast['title'].lower().replace(' ', '-')}.json"
            # Only add if not already in filesystem
            if not any(s.filename == filename for s in scripts):
                # Create the JSON file if it doesn't exist
                file_path = SCRIPT_DIR / filename
                if not file_path.exists():
                    script_data = {
                        "dialogue": podcast["script"],
                        "metadata": {
                            "title": podcast["title"],
                            "date": podcast["date"],
                            "description": podcast["description"]
                        }
                    }
                    with open(file_path, "w") as f:
                        json.dump(script_data, f, indent=2)
                
                scripts.append(ScriptListItem(
                    filename=filename,
                    last_modified=os.path.getmtime(file_path)
                ))
        
        return sorted(scripts, key=lambda x: x.last_modified, reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/load/{filename}")
async def load_script(filename: str) -> Script:
    """
    Load a script from the filesystem.
    """
    try:
        file_path = SCRIPT_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Script not found")
        
        with open(file_path, "r") as f:
            data = json.load(f)
            return Script(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/save")
async def save_script(script: Script, filename: str) -> Dict[str, str]:
    """
    Save a script to both filesystem and database.
    """
    try:
        if not filename.endswith('.json'):
            filename += '.json'
        
        # Save to filesystem
        file_path = SCRIPT_DIR / filename
        with open(file_path, "w") as f:
            json.dump(script.dict(), f, indent=2)
        
        # Save to database if it's a podcast script
        if filename.startswith("podcast_"):
            title = filename[8:-5].replace("-", " ").title()  # Remove 'podcast_' prefix and '.json' suffix
            podcast = Podcast(
                title=title,
                date=time.strftime('%Y-%m-%d'),
                script=script.dialogue,
                description=script.metadata.get("description", "") if script.metadata else ""
            )
            db.insert_podcast(podcast)
        
        return {"message": f"Script saved as {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{filename}")
async def delete_script(filename: str) -> Dict[str, str]:
    """
    Delete a script from both filesystem and database.
    """
    try:
        file_path = SCRIPT_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Script not found")
        
        # Delete from filesystem
        os.remove(file_path)
        
        # Delete from database if it's a podcast script
        if filename.startswith("podcast_"):
            title = filename[8:-5].replace("-", " ").title()
            db.delete_podcast(title)
        
        return {"message": f"Script {filename} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
