import json
import os

PROFILE_PATH = "data/student_profile.json"


def load_profile():
    if not os.path.exists(PROFILE_PATH):
        return {
            "name": "default_student",
            "subjects": {},
            "preferred_style": "examples-first",
            "recent_topics": []
        }

    with open(PROFILE_PATH, "r") as f:
        return json.load(f)


def save_profile(profile):
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=4)


def update_subject(profile, subject, success=True):
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


def get_weak_subjects(profile):
    weak = []

    for subject, stats in profile["subjects"].items():
        if stats["confidence"] < 0.6:
            weak.append(subject)

    return weak