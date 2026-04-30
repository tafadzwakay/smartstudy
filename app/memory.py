chat_memory = []

def add_memory(question, answer):
    chat_memory.append({
        "question": question,
        "answer": answer
    })

def get_memory(limit=5):
    return chat_memory[-limit:]