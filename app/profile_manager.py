import hashlib
import json
import os
from datetime import datetime

USERS_PATH = "db/users.json"
PROFILE_PATH = "db/student_profile.json"


def _ensure_data_folder():
    os.makedirs("data", exist_ok=True)
    os.makedirs("db", exist_ok=True)
    if not os.path.exists(USERS_PATH):
        with open(USERS_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _safe_username(username: str) -> str:
    return username.strip().lower()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _profile_path(username: str | None = None) -> str:
    if username:
        return f"db/profile_{username}.json"
    return PROFILE_PATH


def _default_profile(username: str | None = None, name: str = "Learner", grade: str = "Form 1", role: str = "student") -> dict:
    return {
        "username": username or "guest",
        "name": name,
        "grade": grade,
        "role": role,
        "preferred_style": "examples-first",
        "subjects": {},
        "recent_topics": [],
        "activity": [],
        "notes": [],
        "quizzes": [],
        "chat_sessions": [],
        "badges": ["Starter"] if role == "student" else [],
        "streak": 0,
        "last_active": None,
        "last_sync": None,
        "pending_sync": 0,
        "sync_history": []
    }


def _ensure_profile_defaults(profile: dict) -> dict:
    defaults = _default_profile(profile.get("username"), profile.get("name", "Learner"), profile.get("grade", "Form 1"), profile.get("role", "student"))
    for key, value in defaults.items():
        profile.setdefault(key, value)
    if "subjects" not in profile:
        profile["subjects"] = {}
    if "recent_topics" not in profile:
        profile["recent_topics"] = []
    if "activity" not in profile:
        profile["activity"] = []
    if "notes" not in profile:
        profile["notes"] = []
    if "quizzes" not in profile:
        profile["quizzes"] = []
    if "badges" not in profile:
        profile["badges"] = ["Starter"]
    if "streak" not in profile:
        profile["streak"] = 0
    if "pending_sync" not in profile:
        profile["pending_sync"] = 0
    if "chat_sessions" not in profile:
        profile["chat_sessions"] = []
    return profile


def _award_badges(profile: dict) -> None:
    # Only award badges to students
    if profile.get("role") in ["teacher", "admin"]:
        profile["badges"] = []
        return

    badges = set(profile.get("badges", []))
    streak = profile.get("streak", 0)
    subjects = profile.get("subjects", {})

    if streak >= 3:
        badges.add("Streak Champion")
    if any(stats.get("confidence", 0) >= 0.85 for stats in subjects.values()):
        badges.add("Top Performer")
    if len(profile.get("recent_topics", [])) >= 5:
        badges.add("Consistent Learner")
    if any(stats.get("confidence", 0) < 0.5 for stats in subjects.values()):
        badges.add("Growth Seeker")

    profile["badges"] = sorted(badges)


def load_users() -> dict:
    _ensure_data_folder()
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_users(users: dict) -> None:
    _ensure_data_folder()
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)


def authenticate_user(username: str, password: str) -> bool:
    username = _safe_username(username)
    users = load_users()
    hashed = _hash_password(password)
    return users.get(username, {}).get("password") == hashed


def register_user(username: str, password: str, name: str, grade: str, role: str = "student") -> dict:
    username = _safe_username(username)
    _ensure_data_folder()
    users = load_users()

    if not username or not password or not name:
        return {"success": False, "message": "Missing signup information."}
    if username in users:
        return {"success": False, "message": "This username is already taken."}
    if role not in ["student", "teacher", "admin"]:
        return {"success": False, "message": "Invalid role specified."}

    users[username] = {
        "password": _hash_password(password),
        "name": name,
        "grade": grade,
        "role": role,
        "created_at": datetime.now().isoformat(sep=" ", timespec="minutes")
    }
    save_users(users)

    profile = _default_profile(username, name, grade)
    profile["role"] = role
    save_profile(profile, username)
    return {"success": True, "message": "Account created successfully."}


def load_profile(username: str | None = None) -> dict:
    _ensure_data_folder()
    path = _profile_path(username)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except json.JSONDecodeError:
            profile = {}
    else:
        profile = _default_profile(username)

    profile = _ensure_profile_defaults(profile)
    _award_badges(profile)
    return profile


def save_profile(profile: dict, username: str | None = None) -> None:
    _ensure_data_folder()
    path = _profile_path(username)
    _award_badges(profile)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=4)


def update_subject(profile: dict, subject: str, success: bool = True) -> None:
    if subject not in profile["subjects"]:
        profile["subjects"][subject] = {
            "confidence": 0.5,
            "mistakes": 0
        }

    if success:
        profile["subjects"][subject]["confidence"] += 0.05
    else:
        profile["subjects"][subject]["mistakes"] += 1
        profile["subjects"][subject]["confidence"] -= 0.05

    profile["subjects"][subject]["confidence"] = max(
        0, min(1, profile["subjects"][subject]["confidence"])
    )


def get_weak_subjects(profile: dict) -> list:
    return [subject for subject, stats in profile.get("subjects", {}).items() if stats.get("confidence", 0) < 0.6]


def create_chat_session(profile: dict, title: str) -> str:
    """Create a new chat session and return its ID"""
    import uuid
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "title": title,
        "messages": [],
        "created_at": datetime.now().isoformat(),
        "pinned": False
    }
    profile.setdefault("chat_sessions", []).append(session)
    return session_id


def add_message_to_session(profile: dict, session_id: str, role: str, content: str):
    """Add a message to a chat session"""
    sessions = profile.get("chat_sessions", [])
    for session in sessions:
        if session["id"] == session_id:
            session["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            session["last_updated"] = datetime.now().isoformat()
            break


def get_chat_sessions(profile: dict) -> list:
    """Get all chat sessions sorted by last updated"""
    sessions = profile.get("chat_sessions", [])
    return sorted(sessions, key=lambda x: x.get("last_updated", x.get("created_at", "")), reverse=True)


def delete_chat_session(profile: dict, session_id: str) -> bool:
    """Delete a chat session"""
    sessions = profile.get("chat_sessions", [])
    for i, session in enumerate(sessions):
        if session["id"] == session_id:
            sessions.pop(i)
            return True
    return False


def rename_chat_session(profile, session_id, new_title):
    for session in profile.get('chat_sessions', []):
        if session['id'] == session_id:
            session['title'] = new_title.strip()
            return True
    return False


def pin_chat_session(profile, session_id, pinned=True):
    for session in profile.get('chat_sessions', []):
        if session['id'] == session_id:
            session['pinned'] = pinned
            return True
    return False


# AUTONOMOUS STUDY FEATURES

def analyze_performance(profile: dict) -> dict:
    """
    Analyze student performance and return insights
    """
    subjects = profile.get("subjects", {})
    activity = profile.get("recent_topics", [])
    streak = profile.get("streak", 0)

    # Calculate overall performance
    if subjects:
        avg_confidence = sum(stats.get("confidence", 0) for stats in subjects.values()) / len(subjects)
        weak_subjects = [subj for subj, stats in subjects.items() if stats.get("confidence", 0) < 0.6]
    else:
        avg_confidence = 0.5
        weak_subjects = []

    # Activity analysis
    recent_activity = len([a for a in activity if isinstance(a, dict) and
                          (datetime.now() - datetime.fromisoformat(a.get("timestamp", ""))).days <= 7])

    return {
        "overall_confidence": avg_confidence,
        "weak_subjects": weak_subjects,
        "streak": streak,
        "recent_activity": recent_activity,
        "total_subjects": len(subjects),
        "performance_level": "excellent" if avg_confidence >= 0.8 else
                           "good" if avg_confidence >= 0.6 else
                           "needs_improvement" if avg_confidence >= 0.4 else "critical"
    }


def generate_study_plan(profile: dict) -> dict:
    """
    Generate a personalized study plan based on performance analysis
    """
    analysis = analyze_performance(profile)
    weak_subjects = analysis["weak_subjects"]

    # Base study plan
    plan = {
        "daily_goals": [],
        "weekly_focus": [],
        "recommendations": [],
        "estimated_time": "2-3 hours daily",
        "priority_subjects": weak_subjects[:3]  # Focus on top 3 weak areas
    }

    # Daily goals based on performance level
    if analysis["performance_level"] == "excellent":
        plan["daily_goals"] = [
            "Review challenging concepts for 30 minutes",
            "Practice 2-3 quiz questions daily",
            "Explore advanced topics in strong subjects"
        ]
        plan["estimated_time"] = "1-2 hours daily"
    elif analysis["performance_level"] == "good":
        plan["daily_goals"] = [
            "Spend 45 minutes on weak subjects",
            "Complete 1 quiz daily",
            "Review notes from previous sessions"
        ]
    elif analysis["performance_level"] == "needs_improvement":
        plan["daily_goals"] = [
            "Focus 1 hour on each weak subject",
            "Complete 2 quizzes daily",
            "Study with examples and practice problems",
            "Review fundamental concepts"
        ]
        plan["estimated_time"] = "3-4 hours daily"
    else:  # critical
        plan["daily_goals"] = [
            "Dedicate 1.5 hours to each weak subject",
            "Complete 3 quizzes daily",
            "Seek help with fundamental concepts",
            "Practice basic skills extensively"
        ]
        plan["estimated_time"] = "4-5 hours daily"

    # Weekly focus
    if weak_subjects:
        plan["weekly_focus"] = [
            f"Master {subject} fundamentals" for subject in weak_subjects[:2]
        ]
        plan["weekly_focus"].append("Build confidence through consistent practice")

    # Specific recommendations
    if analysis["streak"] < 3:
        plan["recommendations"].append("Build a daily study streak to stay motivated")
    if analysis["recent_activity"] < 5:
        plan["recommendations"].append("Increase study frequency for better retention")
    if len(weak_subjects) > 2:
        plan["recommendations"].append("Focus on quality over quantity - master fewer topics deeply")

    return plan


def generate_adaptive_quiz(profile: dict, subject: str = None) -> dict:
    """
    Generate an adaptive quiz based on student performance
    """
    subjects = profile.get("subjects", {})

    # If no subject specified, choose the weakest
    if not subject:
        weak_subjects = [(subj, stats.get("confidence", 0))
                        for subj, stats in subjects.items()]
        if weak_subjects:
            subject = min(weak_subjects, key=lambda x: x[1])[0]
        else:
            subject = "General Mathematics"

    # Get performance level for this subject
    confidence = subjects.get(subject, {}).get("confidence", 0.5)

    # Adaptive difficulty
    if confidence >= 0.8:
        difficulty = "advanced"
        num_questions = 8
    elif confidence >= 0.6:
        difficulty = "intermediate"
        num_questions = 6
    else:
        difficulty = "basic"
        num_questions = 5

    # Generate quiz structure
    quiz = {
        "subject": subject,
        "difficulty": difficulty,
        "questions": [],
        "estimated_time": f"{num_questions * 3} minutes",
        "focus_areas": []
    }

    # Add focus areas based on weak spots
    if confidence < 0.6:
        quiz["focus_areas"] = ["Fundamentals", "Basic concepts", "Simple applications"]
    elif confidence < 0.8:
        quiz["focus_areas"] = ["Problem solving", "Application of concepts", "Word problems"]
    else:
        quiz["focus_areas"] = ["Complex problems", "Advanced applications", "Critical thinking"]

    # Note: Actual questions would be generated from the RAG system
    # This is just the quiz metadata/structure

    return quiz


def update_progress_streak(profile: dict) -> None:
    """
    Update the daily study streak
    """
    last_active = profile.get("last_active")
    current_streak = profile.get("streak", 0)

    today = datetime.now().date()

    if last_active:
        last_date = datetime.fromisoformat(last_active).date()
        days_diff = (today - last_date).days

        if days_diff == 1:
            # Consecutive day
            profile["streak"] = current_streak + 1
        elif days_diff == 0:
            # Same day, don't change streak
            pass
        else:
            # Streak broken
            profile["streak"] = 1
    else:
        # First activity
        profile["streak"] = 1

    profile["last_active"] = today.isoformat()


def get_motivation_message(profile: dict) -> str:
    """
    Generate a personalized motivation message
    """
    streak = profile.get("streak", 0)
    badges = profile.get("badges", [])
    analysis = analyze_performance(profile)

    messages = []

    # Streak-based messages
    if streak == 0:
        messages.append("Ready to start your learning journey?")
    elif streak == 1:
        messages.append("Great start! Keep the momentum going.")
    elif streak < 7:
        messages.append(f"{streak} days strong! You're building great habits.")
    elif streak < 30:
        messages.append(f"Amazing {streak}-day streak! You're unstoppable!")
    else:
        messages.append(f"Incredible {streak}-day streak! You're a learning champion!")

    # Performance-based messages
    if analysis["performance_level"] == "excellent":
        messages.append("Outstanding performance! Keep up the excellent work.")
    elif analysis["performance_level"] == "good":
        messages.append("You're doing well! Focus on your weak areas to reach excellence.")
    elif analysis["performance_level"] == "needs_improvement":
        messages.append("You're making progress! Consistent practice will boost your confidence.")
    else:
        messages.append("Every expert was once a beginner. You've got this!")

    # Badge-based messages
    if "Top Performer" in badges:
        messages.append("🏆 Top Performer! Your hard work is paying off.")
    if "Streak Champion" in badges:
        messages.append("🔥 Streak Champion! Consistency is your superpower.")

    return " ".join(messages[:2])  # Return 1-2 messages combined


def get_progress_stats(profile: dict) -> dict:
    """
    Get comprehensive progress statistics
    """
    analysis = analyze_performance(profile)

    return {
        "streak": profile.get("streak", 0),
        "badges_earned": len(profile.get("badges", [])),
        "subjects_mastered": len([s for s in profile.get("subjects", {}).values()
                                 if s.get("confidence", 0) >= 0.8]),
        "total_subjects": len(profile.get("subjects", {})),
        "weak_areas": len(analysis["weak_subjects"]),
        "recent_activity": analysis["recent_activity"],
        "performance_level": analysis["performance_level"],
        "overall_confidence": analysis["overall_confidence"]
    }


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN USER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def admin_create_user(admin_username: str, username: str, password: str,
                      name: str, grade: str, role: str) -> dict:
    """Admin creates a new user account."""
    users = load_users()
    if users.get(admin_username, {}).get('role') not in ['admin']:
        return {"success": False, "message": "Admin access required."}
    return register_user(username, password, name, grade, role)


def admin_update_user(admin_username: str, target_username: str,
                      updates: dict) -> dict:
    """Admin updates any field of a user account."""
    users = load_users()
    if users.get(admin_username, {}).get('role') not in ['admin']:
        return {"success": False, "message": "Admin access required."}

    target = _safe_username(target_username)
    if target not in users:
        return {"success": False, "message": "User not found."}

    # Update users.json fields
    allowed_user_fields = ['name', 'grade', 'role']
    for field in allowed_user_fields:
        if field in updates:
            # Validate role
            if field == 'role' and updates[field] not in ['student', 'teacher', 'admin']:
                return {"success": False, "message": "Invalid role."}
            users[target][field] = updates[field]

    # Update password if provided
    if 'password' in updates and updates['password']:
        users[target]['password'] = _hash_password(updates['password'])

    save_users(users)

    # Also update profile file
    profile = load_profile(target)
    for field in allowed_user_fields:
        if field in updates:
            profile[field] = updates[field]
    save_profile(profile, target)

    return {"success": True, "message": f"{target} updated successfully."}


def admin_delete_user(admin_username: str, target_username: str) -> dict:
    """Admin deletes a user account and their profile."""
    users = load_users()
    if users.get(admin_username, {}).get('role') not in ['admin']:
        return {"success": False, "message": "Admin access required."}

    target = _safe_username(target_username)
    if target not in users:
        return {"success": False, "message": "User not found."}

    if target == _safe_username(admin_username):
        return {"success": False, "message": "You cannot delete your own account."}

    # Remove from users.json
    del users[target]
    save_users(users)

    # Remove profile file
    profile_file = _profile_path(target)
    if os.path.exists(profile_file):
        os.remove(profile_file)

    return {"success": True, "message": f"{target} deleted successfully."}


def admin_reset_password(admin_username: str, target_username: str,
                         new_password: str) -> dict:
    """Admin resets any user's password."""
    users = load_users()
    if users.get(admin_username, {}).get('role') not in ['admin']:
        return {"success": False, "message": "Admin access required."}

    target = _safe_username(target_username)
    if target not in users:
        return {"success": False, "message": "User not found."}

    if not new_password or len(new_password) < 4:
        return {"success": False, "message": "Password must be at least 4 characters."}

    users[target]['password'] = _hash_password(new_password)
    save_users(users)
    return {"success": True, "message": f"Password reset for {target}."}


def admin_get_all_users(admin_username: str) -> dict:
    """Get full details of all users for admin view."""
    users = load_users()
    if users.get(admin_username, {}).get('role') not in ['admin']:
        return {"success": False, "message": "Admin access required."}

    all_users = []
    for uname, udata in users.items():
        all_users.append({
            "username": uname,
            "name": udata.get("name", ""),
            "grade": udata.get("grade", ""),
            "role": udata.get("role", "student"),
            "created_at": udata.get("created_at", "")
        })

    return {"success": True, "users": all_users}