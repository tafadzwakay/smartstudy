def handle_quiz(question, qa_chain):
    prompt = f"""
You are a ZIMSEC exam tutor. Based on the study materials, create 5 multiple choice quiz questions about this topic: {question}

You MUST use this EXACT format for every question. Do not deviate:

Q1. [Question text here]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [A, B, C, or D]

Q2. [Question text here]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [A, B, C, or D]

Q3. [Question text here]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [A, B, C, or D]

Q4. [Question text here]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [A, B, C, or D]

Q5. [Question text here]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [A, B, C, or D]

Base ALL questions only on the study materials. Do not add explanations outside this format.
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


def generate_study_plan(profile, qa_chain):
    """Generate a personalized study plan based on student's performance"""
    weak_subjects = []
    for subject, stats in profile.get("subjects", {}).items():
        if stats.get("confidence", 0.5) < 0.7:
            weak_subjects.append(subject)
    
    if not weak_subjects:
        weak_subjects = ["General Revision"]
    
    prompt = f"""
    Create a personalized 7-day study plan for a ZIMSEC student.

    Weak areas identified: {', '.join(weak_subjects)}
    Current grade: {profile.get('grade', 'Form 1')}
    
    Structure the plan with:
    - Daily focus topics
    - Recommended activities (reading, practice, quizzes)
    - Time allocations
    - Progress checkpoints
    
    Make it realistic and achievable.
    """
    
    result = qa_chain.invoke({"query": prompt})
    return result["result"]


def generate_adaptive_quiz(profile, qa_chain):
    """Generate shuffled quiz based on student's learning patterns"""
    import random

    subjects = profile.get("subjects", {})
    recent_topics = profile.get("recent_topics", [])[:5]

    # Focus on weak subjects first
    weak = [s for s, stats in subjects.items() if stats.get("confidence", 0.5) < 0.8]
    strong = [s for s, stats in subjects.items() if stats.get("confidence", 0.5) >= 0.8]

    quiz_topics = weak[:3] if weak else recent_topics[:3]
    if not quiz_topics:
        quiz_topics = ["General ZIMSEC Knowledge"]

    # Shuffle for variety
    random.shuffle(quiz_topics)

    grade = profile.get("grade", "Form 3")

    prompt = f"""
You are a ZIMSEC exam tutor. Create a 10-question quiz for a {grade} student.

Base the questions ONLY on information from the study materials provided.
Focus topics: {', '.join(quiz_topics)}

Include a mix of question types:
- 4 Multiple choice questions (with options A, B, C, D)
- 3 Short answer questions
- 3 True/False questions

Format each question like this:
Q1. [Question text]
Type: Multiple Choice
A) option
B) option
C) option
D) option
Answer: [correct answer]

Q2. [Question text]
Type: True/False
Answer: [True or False]

Q3. [Question text]
Type: Short Answer
Answer: [brief answer]

Make questions relevant to ZIMSEC syllabus. Shuffle question order.
"""

    result = qa_chain.invoke({"query": prompt})
    return result["result"]