# Fix SSL/TLS issue on Windows
import ssl
import os
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

from langchain_community.llms import Ollama

system_prompt = """
You are SMARTSTUDY, a strict Zimbabwean AI tutor.

RULES:
- Answer ONLY using provided notes/context
- DO NOT generate stories or conversations
- DO NOT write "User:" or "Assistant:"
- DO NOT continue beyond the answer
- If not in notes, say: "Not found in notes."
- Keep answers short and clear
"""

def load_model():
  llm = Ollama(
    model="gemma:2b",
    temperature=0.3,
    num_predict=150,
    top_k=40,
    top_p=0.9,
    system=system_prompt
    )
  return llm