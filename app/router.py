def detect_intent(question: str) -> str:
    """
    Simple rule-based intent classifier.
    Returns the intent label.
    """

    q = question.lower()

    if any(word in q for word in ["quiz", "test me", "questions", "mcq"]):
        return "quiz"

    elif any(word in q for word in ["summarize", "summary", "brief"]):
        return "summary"

    elif any(word in q for word in ["revise", "revision", "study plan"]):
        return "revision"

    else:
        return "retrieval"