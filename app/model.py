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

system_prompt = """You are SMARTSTUDY, a ZIMSEC tutor.
RULES:
- Answer ONLY using the provided context
- Keep answers short and clear (2-4 sentences max)
- If not in context, say: "Not found in notes."
- Never write "User:" or "Assistant:"
- Never add notes or disclaimers about missing context"""

_llm_instance = None

def load_model():
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    _llm_instance = Ollama(
        model="gemma:2b",
        temperature=0.1,
        num_predict=300,
        num_ctx=2048,
        top_k=20,
        top_p=0.85,
        repeat_penalty=1.1,
        system=system_prompt,
    )
    return _llm_instance