"""
Bluetooth and Offline Sharing Module for SmartStudy
Enables peer-to-peer sharing of notes, quizzes, and progress between students
"""

import json
import os
import uuid
from datetime import datetime
import tempfile
import shutil

SHARE_DIR = "shared"
QUIZ_SHARE_DIR = "shared/quizzes"
NOTES_SHARE_DIR = "shared/notes"
PROGRESS_SHARE_DIR = "shared/progress"

def init_sharing_dirs():
    """Initialize sharing directories"""
    os.makedirs(QUIZ_SHARE_DIR, exist_ok=True)
    os.makedirs(NOTES_SHARE_DIR, exist_ok=True)
    os.makedirs(PROGRESS_SHARE_DIR, exist_ok=True)

def create_shareable_quiz(quiz_data: dict, creator_username: str) -> str:
    """
    Create a shareable quiz file
    Returns the filename that can be shared via Bluetooth
    """
    init_sharing_dirs()

    share_data = {
        "id": str(uuid.uuid4()),
        "type": "quiz",
        "creator": creator_username,
        "created_at": datetime.now().isoformat(),
        "quiz": quiz_data
    }

    filename = f"quiz_{creator_username}_{share_data['id'][:8]}.json"
    filepath = os.path.join(QUIZ_SHARE_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(share_data, f, indent=2, ensure_ascii=False)

    return filepath

def create_shareable_notes(notes_data: dict, creator_username: str) -> str:
    """
    Create shareable notes file
    """
    init_sharing_dirs()

    share_data = {
        "id": str(uuid.uuid4()),
        "type": "notes",
        "creator": creator_username,
        "created_at": datetime.now().isoformat(),
        "notes": notes_data
    }

    filename = f"notes_{creator_username}_{share_data['id'][:8]}.json"
    filepath = os.path.join(NOTES_SHARE_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(share_data, f, indent=2, ensure_ascii=False)

    return filepath

def create_shareable_progress(progress_data: dict, username: str) -> str:
    """
    Create shareable progress report
    """
    init_sharing_dirs()

    share_data = {
        "id": str(uuid.uuid4()),
        "type": "progress",
        "username": username,
        "created_at": datetime.now().isoformat(),
        "progress": progress_data
    }

    filename = f"progress_{username}_{share_data['id'][:8]}.json"
    filepath = os.path.join(PROGRESS_SHARE_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(share_data, f, indent=2, ensure_ascii=False)

    return filepath

def import_shared_quiz(filepath: str, recipient_profile: dict) -> dict:
    """
    Import a shared quiz into the recipient's profile
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            share_data = json.load(f)

        if share_data.get("type") != "quiz":
            return {"success": False, "message": "Not a valid quiz file"}

        # Add to recipient's quizzes
        quiz = share_data["quiz"]
        quiz["shared_by"] = share_data["creator"]
        quiz["shared_at"] = datetime.now().isoformat()
        quiz["imported"] = True

        recipient_profile.setdefault("shared_quizzes", []).append(quiz)

        return {"success": True, "message": f"Quiz '{quiz.get('title', 'Shared Quiz')}' imported successfully"}

    except Exception as e:
        return {"success": False, "message": f"Failed to import quiz: {str(e)}"}

def import_shared_notes(filepath: str, recipient_profile: dict) -> dict:
    """
    Import shared notes into the recipient's profile
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            share_data = json.load(f)

        if share_data.get("type") != "notes":
            return {"success": False, "message": "Not a valid notes file"}

        # Add to recipient's notes
        notes = share_data["notes"]
        notes["shared_by"] = share_data["creator"]
        notes["shared_at"] = datetime.now().isoformat()
        notes["imported"] = True

        recipient_profile.setdefault("shared_notes", []).append(notes)

        return {"success": True, "message": f"Notes '{notes.get('title', 'Shared Notes')}' imported successfully"}

    except Exception as e:
        return {"success": False, "message": f"Failed to import notes: {str(e)}"}

def import_shared_progress(filepath: str, recipient_profile: dict) -> dict:
    """
    Import shared progress report for comparison
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            share_data = json.load(f)

        if share_data.get("type") != "progress":
            return {"success": False, "message": "Not a valid progress file"}

        # Add to comparison data
        progress = share_data["progress"]
        progress["peer_username"] = share_data["username"]
        progress["shared_at"] = datetime.now().isoformat()

        recipient_profile.setdefault("peer_progress", []).append(progress)

        return {"success": True, "message": f"Progress data from {share_data['username']} imported for comparison"}

    except Exception as e:
        return {"success": False, "message": f"Failed to import progress: {str(e)}"}

def list_available_shares() -> dict:
    """
    List all available shared files for import
    """
    init_sharing_dirs()

    shares = {
        "quizzes": [],
        "notes": [],
        "progress": []
    }

    # List quiz files
    if os.path.exists(QUIZ_SHARE_DIR):
        for filename in os.listdir(QUIZ_SHARE_DIR):
            if filename.endswith('.json'):
                shares["quizzes"].append(filename)

    # List notes files
    if os.path.exists(NOTES_SHARE_DIR):
        for filename in os.listdir(NOTES_SHARE_DIR):
            if filename.endswith('.json'):
                shares["notes"].append(filename)

    # List progress files
    if os.path.exists(PROGRESS_SHARE_DIR):
        for filename in os.listdir(PROGRESS_SHARE_DIR):
            if filename.endswith('.json'):
                shares["progress"].append(filename)

    return shares

def get_share_info(filepath: str) -> dict:
    """
    Get information about a shared file without importing it
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return {
            "type": data.get("type"),
            "creator": data.get("creator") or data.get("username"),
            "created_at": data.get("created_at"),
            "title": data.get("quiz", {}).get("title") or
                    data.get("notes", {}).get("title") or
                    f"Progress report from {data.get('username')}",
            "description": data.get("quiz", {}).get("description") or
                          data.get("notes", {}).get("description") or
                          "Progress comparison data"
        }
    except Exception as e:
        return {"error": str(e)}

def cleanup_old_shares(days_old: int = 30):
    """
    Clean up shared files older than specified days
    """
    from datetime import timedelta

    cutoff_date = datetime.now() - timedelta(days=days_old)

    for directory in [QUIZ_SHARE_DIR, NOTES_SHARE_DIR, PROGRESS_SHARE_DIR]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                try:
                    file_date = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_date < cutoff_date:
                        os.remove(filepath)
                except:
                    pass