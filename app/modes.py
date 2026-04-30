def handle_quiz(question, qa_chain):
    prompt = f"""
    Based on the study material, create 5 quiz questions for the student.

    Topic request: {question}

    Format:
    1. Question
    2. Question
    3. Question
    4. Question
    5. Question
    """

    result = qa_chain.invoke({"query": prompt})
    return result["result"]


def handle_summary(question, qa_chain):
    prompt = f"""
    Summarize the requested topic clearly and concisely for revision purposes.

    Topic request: {question}

    Keep it short, structured, and easy to understand.
    """

    result = qa_chain.invoke({"query": prompt})
    return result["result"]


def handle_revision(question, qa_chain):
    prompt = f"""
    Act as a study coach.

    Help the student revise this topic by explaining key concepts,
    important points to remember, and likely exam focus areas.

    Topic request: {question}
    """

    result = qa_chain.invoke({"query": prompt})
    return result["result"]