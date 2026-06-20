"""
Gamification Module for SmartStudy
Handles badges, achievements, streaks, and progress visualization
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BADGES_DATA_FILE = "data/badges.json"
ACHIEVEMENTS_DATA_FILE = "data/achievements.json"

def init_gamification():
    """Initialize gamification data files"""
    os.makedirs("data", exist_ok=True)

    # Default badges
    if not os.path.exists(BADGES_DATA_FILE):
        default_badges = {
            "starter": {
                "name": "First Steps",
                "description": "Started your learning journey",
                "icon": "🌟",
                "rarity": "common",
                "unlocked_at": None
            },
            "streak_3": {
                "name": "Consistency Builder",
                "description": "3-day study streak",
                "icon": "🔥",
                "rarity": "common",
                "unlocked_at": None
            },
            "streak_7": {
                "name": "Week Warrior",
                "description": "7-day study streak",
                "icon": "⚡",
                "rarity": "uncommon",
                "unlocked_at": None
            },
            "streak_30": {
                "name": "Monthly Champion",
                "description": "30-day study streak",
                "icon": "👑",
                "rarity": "rare",
                "unlocked_at": None
            },
            "quiz_master": {
                "name": "Quiz Master",
                "description": "Completed 10 quizzes",
                "icon": "🎯",
                "rarity": "uncommon",
                "unlocked_at": None
            },
            "subject_expert": {
                "name": "Subject Expert",
                "description": "Achieved 90% confidence in a subject",
                "icon": "🧠",
                "rarity": "rare",
                "unlocked_at": None
            },
            "helper": {
                "name": "Knowledge Sharer",
                "description": "Shared 5 items with peers",
                "icon": "🤝",
                "rarity": "uncommon",
                "unlocked_at": None
            },
            "voice_learner": {
                "name": "Voice Explorer",
                "description": "Used voice features 10 times",
                "icon": "🎤",
                "rarity": "common",
                "unlocked_at": None
            },
            "perfect_score": {
                "name": "Perfect Score",
                "description": "Got 100% on a quiz",
                "icon": "💯",
                "rarity": "epic",
                "unlocked_at": None
            },
            "early_bird": {
                "name": "Early Bird",
                "description": "Studied before 6 AM",
                "icon": "🐦",
                "rarity": "uncommon",
                "unlocked_at": None
            }
        }
        with open(BADGES_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_badges, f, indent=2)

def check_and_award_badges(profile: dict) -> List[str]:
    """
    Check profile against badge criteria and award new badges
    Returns list of newly awarded badge IDs
    """
    init_gamification()

    current_badges = set(profile.get("badges", []))
    new_badges = []

    # Load badge definitions
    try:
        with open(BADGES_DATA_FILE, 'r', encoding='utf-8') as f:
            badge_defs = json.load(f)
    except:
        return []

    # Check each badge criteria
    streak = profile.get("streak", 0)
    subjects = profile.get("subjects", {})
    quizzes_completed = len(profile.get("quizzes", []))
    shared_items = len(profile.get("shared_quizzes", [])) + len(profile.get("shared_notes", []))
    voice_usage = profile.get("voice_usage", 0)

    # Streak badges
    if streak >= 3 and "streak_3" not in current_badges:
        new_badges.append("streak_3")
    if streak >= 7 and "streak_7" not in current_badges:
        new_badges.append("streak_7")
    if streak >= 30 and "streak_30" not in current_badges:
        new_badges.append("streak_30")

    # Quiz badges
    if quizzes_completed >= 10 and "quiz_master" not in current_badges:
        new_badges.append("quiz_master")

    # Subject expertise
    has_expert_subject = any(stats.get("confidence", 0) >= 0.9 for stats in subjects.values())
    if has_expert_subject and "subject_expert" not in current_badges:
        new_badges.append("subject_expert")

    # Sharing badges
    if shared_items >= 5 and "helper" not in current_badges:
        new_badges.append("helper")

    # Voice usage
    if voice_usage >= 10 and "voice_learner" not in current_badges:
        new_badges.append("voice_learner")

    # Perfect score (check recent quiz results)
    recent_quizzes = profile.get("quizzes", [])[-10:]  # Last 10 quizzes
    has_perfect_score = any(quiz.get("score", 0) == 100 for quiz in recent_quizzes)
    if has_perfect_score and "perfect_score" not in current_badges:
        new_badges.append("perfect_score")

    # Early bird (check study times)
    activity = profile.get("activity", [])
    early_sessions = [a for a in activity if isinstance(a, dict) and
                     a.get("timestamp") and
                     datetime.fromisoformat(a["timestamp"].replace(' ', 'T')).hour < 6]
    if len(early_sessions) >= 3 and "early_bird" not in current_badges:
        new_badges.append("early_bird")

    # Award new badges
    for badge_id in new_badges:
        if badge_id not in current_badges:
            profile.setdefault("badges", []).append(badge_id)
            # Record when badge was unlocked
            if badge_id in badge_defs:
                badge_defs[badge_id]["unlocked_at"] = datetime.now().isoformat()

    # Save updated badge definitions
    try:
        with open(BADGES_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(badge_defs, f, indent=2)
    except:
        pass

    return new_badges

def get_progress_bars(profile: dict) -> Dict:
    """
    Calculate progress bars for various achievements
    """
    progress = {}

    # Streak progress (towards next milestone)
    streak = profile.get("streak", 0)
    if streak < 3:
        progress["streak"] = {"current": streak, "target": 3, "percentage": (streak / 3) * 100}
    elif streak < 7:
        progress["streak"] = {"current": streak, "target": 7, "percentage": (streak / 7) * 100}
    elif streak < 30:
        progress["streak"] = {"current": streak, "target": 30, "percentage": (streak / 30) * 100}
    else:
        progress["streak"] = {"current": streak, "target": streak + 7, "percentage": 100}

    # Quiz completion progress
    quizzes_completed = len(profile.get("quizzes", []))
    progress["quizzes"] = {"current": quizzes_completed, "target": 10, "percentage": min((quizzes_completed / 10) * 100, 100)}

    # Subject mastery progress
    subjects = profile.get("subjects", {})
    total_subjects = len(subjects)
    mastered_subjects = len([s for s in subjects.values() if s.get("confidence", 0) >= 0.8])
    progress["subjects"] = {
        "current": mastered_subjects,
        "target": max(total_subjects, 1),
        "percentage": (mastered_subjects / max(total_subjects, 1)) * 100
    }

    # Sharing progress
    shared_items = len(profile.get("shared_quizzes", [])) + len(profile.get("shared_notes", []))
    progress["sharing"] = {"current": shared_items, "target": 5, "percentage": min((shared_items / 5) * 100, 100)}

    # Voice usage progress
    voice_usage = profile.get("voice_usage", 0)
    progress["voice"] = {"current": voice_usage, "target": 10, "percentage": min((voice_usage / 10) * 100, 100)}

    return progress

def get_motivational_messages(profile: dict) -> List[str]:
    """
    Generate contextual motivational messages
    """
    messages = []
    streak = profile.get("streak", 0)
    badges = profile.get("badges", [])
    progress = get_progress_bars(profile)

    # Streak-based motivation
    if streak == 0:
        messages.append("🌅 Ready to start your learning adventure?")
    elif streak == 1:
        messages.append("🚀 Great first step! Tomorrow builds your streak!")
    elif streak == 2:
        messages.append("🔥 Almost there! One more day for your first badge!")
    elif streak < 7:
        messages.append(f"⚡ {streak} days strong! Keep the fire burning!")
    else:
        messages.append(f"👑 {streak}-day champion! You're unstoppable!")

    # Progress-based motivation
    if progress["subjects"]["percentage"] < 50:
        messages.append("📚 Focus on mastering your subjects - you're making progress!")
    elif progress["subjects"]["percentage"] >= 80:
        messages.append("🎓 Subject mastery in sight! Keep pushing!")

    if progress["quizzes"]["percentage"] < 30:
        messages.append("🎯 Quizzes build confidence! Try one today!")
    elif progress["quizzes"]["percentage"] >= 70:
        messages.append("🏆 Quiz champion! Your knowledge is growing!")

    # Badge celebration
    recent_badges = profile.get("recent_badges", [])
    if recent_badges:
        badge_names = [get_badge_info(bid).get("name", bid) for bid in recent_badges[:2]]
        messages.append(f"🏅 New badge{'s' if len(badge_names) > 1 else ''}: {', '.join(badge_names)}!")

    # Time-based motivation
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        messages.append("🌅 Morning study sessions boost memory retention!")
    elif 18 <= current_hour < 22:
        messages.append("🌙 Evening review helps cement today's learning!")

    return messages[:3]

def get_badge_info(badge_id: str) -> Dict:
    """
    Get detailed information about a badge
    """
    init_gamification()
    try:
        with open(BADGES_DATA_FILE, 'r', encoding='utf-8') as f:
            badges = json.load(f)
        return badges.get(badge_id, {"name": badge_id, "description": "Unknown badge"})
    except:
        return {"name": badge_id, "description": "Unknown badge"}

def get_all_badges() -> Dict:
    """
    Get all available badges
    """
    init_gamification()
    try:
        with open(BADGES_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def record_voice_usage(profile: dict):
    """
    Record voice feature usage for badge tracking
    """
    profile["voice_usage"] = profile.get("voice_usage", 0) + 1

def record_early_study(profile: dict):
    """
    Record early morning study session
    """
    current_hour = datetime.now().hour
    if current_hour < 6:
        profile["early_sessions"] = profile.get("early_sessions", 0) + 1

def get_leaderboard_position(profile: dict, all_profiles: List[dict]) -> Dict:
    """
    Calculate leaderboard position
    """
    user_score = (profile.get("streak", 0) * 10 +
                 len(profile.get("badges", [])) * 5 +
                 len(profile.get("subjects", {})) * 2)

    return {
        "position": 1,
        "total_students": len(all_profiles) + 1,
        "score": user_score,
        "rank": "Top 10%" if user_score > 50 else "Keep climbing!"
    }

def get_daily_challenge(profile: dict) -> Dict:
    """
    Generate a daily challenge based on profile
    """
    streak = profile.get("streak", 0)
    weak_subjects = [subj for subj, stats in profile.get("subjects", {}).items()
                    if stats.get("confidence", 0) < 0.6]

    challenges = [
        {
            "title": "Study Sprint",
            "description": "Complete 30 minutes of focused study",
            "reward": "streak_bonus",
            "difficulty": "easy"
        },
        {
            "title": "Quiz Challenge",
            "description": "Complete one quiz with at least 70% score",
            "reward": "confidence_boost",
            "difficulty": "medium"
        },
        {
            "title": "Knowledge Share",
            "description": "Share one note or quiz with a peer",
            "reward": "sharing_badge",
            "difficulty": "easy"
        }
    ]

    if weak_subjects:
        challenges.append({
            "title": "Weakness Crusher",
            "description": f"Study {weak_subjects[0]} for 20 minutes",
            "reward": "subject_boost",
            "difficulty": "medium"
        })

    if streak >= 7:
        challenges.append({
            "title": "Streak Master",
            "description": "Maintain your study streak for one more day",
            "reward": "streak_badge",
            "difficulty": "hard"
        })

    # Return a challenge based on profile
    challenge_index = streak % len(challenges)
    return challenges[challenge_index]


def check_and_award_badges(profile: dict) -> List[str]:
    """
    Check profile against badge criteria and award new badges
    Returns list of newly awarded badge IDs
    """
    init_gamification()

    current_badges = set(profile.get("badges", []))
    new_badges = []

    # Load badge definitions
    try:
        with open(BADGES_DATA_FILE, 'r', encoding='utf-8') as f:
            badge_defs = json.load(f)
    except:
        return []

    # Check each badge criteria
    streak = profile.get("streak", 0)
    subjects = profile.get("subjects", {})
    quizzes_completed = len(profile.get("quizzes", []))
    shared_items = len(profile.get("shared_quizzes", [])) + len(profile.get("shared_notes", []))
    voice_usage = profile.get("voice_usage", 0)

    # Streak badges
    if streak >= 3 and "streak_3" not in current_badges:
        new_badges.append("streak_3")
    if streak >= 7 and "streak_7" not in current_badges:
        new_badges.append("streak_7")
    if streak >= 30 and "streak_30" not in current_badges:
        new_badges.append("streak_30")

    # Quiz badges
    if quizzes_completed >= 10 and "quiz_master" not in current_badges:
        new_badges.append("quiz_master")

    # Subject expertise
    has_expert_subject = any(stats.get("confidence", 0) >= 0.9 for stats in subjects.values())
    if has_expert_subject and "subject_expert" not in current_badges:
        new_badges.append("subject_expert")

    # Sharing badges
    if shared_items >= 5 and "helper" not in current_badges:
        new_badges.append("helper")

    # Voice usage
    if voice_usage >= 10 and "voice_learner" not in current_badges:
        new_badges.append("voice_learner")

    # Perfect score (check recent quiz results)
    recent_quizzes = profile.get("quizzes", [])[-10:]  # Last 10 quizzes
    has_perfect_score = any(quiz.get("score", 0) == 100 for quiz in recent_quizzes)
    if has_perfect_score and "perfect_score" not in current_badges:
        new_badges.append("perfect_score")

    # Early bird (check study times)
    activity = profile.get("activity", [])
    early_sessions = [a for a in activity if isinstance(a, dict) and
                     a.get("timestamp") and
                     datetime.fromisoformat(a["timestamp"]).hour < 6]
    if len(early_sessions) >= 3 and "early_bird" not in current_badges:
        new_badges.append("early_bird")

    # Award new badges
    for badge_id in new_badges:
        if badge_id not in current_badges:
            profile.setdefault("badges", []).append(badge_id)
            # Record when badge was unlocked
            if badge_id in badge_defs:
                badge_defs[badge_id]["unlocked_at"] = datetime.now().isoformat()

    # Save updated badge definitions
    try:
        with open(BADGES_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(badge_defs, f, indent=2)
    except:
        pass

    return new_badges

def get_progress_bars(profile: dict) -> Dict:
    """
    Calculate progress bars for various achievements
    """
    progress = {}

    # Streak progress (towards next milestone)
    streak = profile.get("streak", 0)
    if streak < 3:
        progress["streak"] = {"current": streak, "target": 3, "percentage": (streak / 3) * 100}
    elif streak < 7:
        progress["streak"] = {"current": streak, "target": 7, "percentage": (streak / 7) * 100}
    elif streak < 30:
        progress["streak"] = {"current": streak, "target": 30, "percentage": (streak / 30) * 100}
    else:
        progress["streak"] = {"current": streak, "target": streak + 7, "percentage": 100}

    # Quiz completion progress
    quizzes_completed = len(profile.get("quizzes", []))
    progress["quizzes"] = {"current": quizzes_completed, "target": 10, "percentage": min((quizzes_completed / 10) * 100, 100)}

    # Subject mastery progress
    subjects = profile.get("subjects", {})
    total_subjects = len(subjects)
    mastered_subjects = len([s for s in subjects.values() if s.get("confidence", 0) >= 0.8])
    progress["subjects"] = {
        "current": mastered_subjects,
        "target": total_subjects,
        "percentage": (mastered_subjects / max(total_subjects, 1)) * 100
    }

    # Sharing progress
    shared_items = len(profile.get("shared_quizzes", [])) + len(profile.get("shared_notes", []))
    progress["sharing"] = {"current": shared_items, "target": 5, "percentage": min((shared_items / 5) * 100, 100)}

    # Voice usage progress
    voice_usage = profile.get("voice_usage", 0)
    progress["voice"] = {"current": voice_usage, "target": 10, "percentage": min((voice_usage / 10) * 100, 100)}

    return progress

def get_motivational_messages(profile: dict) -> List[str]:
    """
    Generate contextual motivational messages
    """
    messages = []
    streak = profile.get("streak", 0)
    badges = profile.get("badges", [])
    progress = get_progress_bars(profile)

    # Streak-based motivation
    if streak == 0:
        messages.append("🌅 Ready to start your learning adventure?")
    elif streak == 1:
        messages.append("🚀 Great first step! Tomorrow builds your streak!")
    elif streak == 2:
        messages.append("🔥 Almost there! One more day for your first badge!")
    elif streak < 7:
        messages.append(f"⚡ {streak} days strong! Keep the fire burning!")
    else:
        messages.append(f"👑 {streak}-day champion! You're unstoppable!")

    # Progress-based motivation
    if progress["subjects"]["percentage"] < 50:
        messages.append("📚 Focus on mastering your subjects - you're making progress!")
    elif progress["subjects"]["percentage"] >= 80:
        messages.append("🎓 Subject mastery in sight! Keep pushing!")

    if progress["quizzes"]["percentage"] < 30:
        messages.append("🎯 Quizzes build confidence! Try one today!")
    elif progress["quizzes"]["percentage"] >= 70:
        messages.append("🏆 Quiz champion! Your knowledge is growing!")

    # Badge celebration
    recent_badges = profile.get("recent_badges", [])
    if recent_badges:
        badge_names = [get_badge_info(bid).get("name", bid) for bid in recent_badges[:2]]
        messages.append(f"🏅 New badge{'s' if len(badge_names) > 1 else ''}: {', '.join(badge_names)}!")

    # Time-based motivation
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        messages.append("🌅 Morning study sessions boost memory retention!")
    elif 18 <= current_hour < 22:
        messages.append("🌙 Evening review helps cement today's learning!")

    return messages[:3]  # Return up to 3 messages

def get_badge_info(badge_id: str) -> Dict:
    """
    Get detailed information about a badge
    """
    init_gamification()
    try:
        with open(BADGES_DATA_FILE, 'r', encoding='utf-8') as f:
            badges = json.load(f)
        return badges.get(badge_id, {"name": badge_id, "description": "Unknown badge"})
    except:
        return {"name": badge_id, "description": "Unknown badge"}

def get_all_badges() -> Dict:
    """
    Get all available badges
    """
    init_gamification()
    try:
        with open(BADGES_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def record_voice_usage(profile: dict):
    """
    Record voice feature usage for badge tracking
    """
    profile["voice_usage"] = profile.get("voice_usage", 0) + 1

def record_early_study(profile: dict):
    """
    Record early morning study session
    """
    current_hour = datetime.now().hour
    if current_hour < 6:
        profile["early_sessions"] = profile.get("early_sessions", 0) + 1

def get_leaderboard_position(profile: dict, all_profiles: List[dict]) -> Dict:
    """
    Calculate leaderboard position (mock implementation)
    """
    # This would compare with other students in a real implementation
    # For now, return mock data
    user_score = (profile.get("streak", 0) * 10 +
                 len(profile.get("badges", [])) * 5 +
                 len(profile.get("subjects", {})) * 2)

    # Mock comparison
    return {
        "position": 1,  # Would be calculated from all_profiles
        "total_students": len(all_profiles) + 1,
        "score": user_score,
        "rank": "Top 10%" if user_score > 50 else "Keep climbing!"
    }

def get_daily_challenge(profile: dict) -> Dict:
    """
    Generate a daily challenge based on profile
    """
    streak = profile.get("streak", 0)
    weak_subjects = [subj for subj, stats in profile.get("subjects", {}).items()
                    if stats.get("confidence", 0) < 0.6]

    challenges = [
        {
            "title": "Study Sprint",
            "description": "Complete 30 minutes of focused study",
            "reward": "streak_bonus",
            "difficulty": "easy"
        },
        {
            "title": "Quiz Challenge",
            "description": "Complete one quiz with at least 70% score",
            "reward": "confidence_boost",
            "difficulty": "medium"
        },
        {
            "title": "Knowledge Share",
            "description": "Share one note or quiz with a peer",
            "reward": "sharing_badge",
            "difficulty": "easy"
        }
    ]

    if weak_subjects:
        challenges.append({
            "title": "Weakness Crusher",
            "description": f"Study {weak_subjects[0]} for 20 minutes",
            "reward": "subject_boost",
            "difficulty": "medium"
        })

    if streak >= 7:
        challenges.append({
            "title": "Streak Master",
            "description": "Maintain your study streak for one more day",
            "reward": "streak_badge",
            "difficulty": "hard"
        })

    # Return a challenge based on profile (simplified)
    challenge_index = streak % len(challenges)
    return challenges[challenge_index]