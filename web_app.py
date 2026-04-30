# Fix SSL/TLS issue on Windows - must be at the top
import ssl
import os

FFMPEG_DIR = r"C:\Users\HOMEPC\ffmpeg-2026-04-22-git-162ad61486-essentials_build\bin"

from pydub import AudioSegment

AudioSegment.converter = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(FFMPEG_DIR, "ffprobe.exe")

os.environ["PATH"] += os.pathsep + FFMPEG_DIR

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["USER_AGENT"] = "SmartStudyBot/1.0"
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from app.loader import load_all_documents
from app.rag import split_docs, create_vector_db, load_vector_db, build_retrieval_qa, format_sources
import pickle

CHROMA_DB_PATH = "db/chroma_db"
CHUNKS_CACHE_PATH = "db/chunks.pkl"
from app.profile_manager import load_profile, save_profile, update_subject, get_weak_subjects
import sys
from app.router import detect_intent
from app.modes import handle_quiz, handle_summary, handle_revision
from app.memory import get_memory, add_memory
from app.tts import text_to_speech
import whisper
import traceback
import warnings
warnings.filterwarnings("ignore")


# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder='templates')
UPLOAD_FOLDER = "data"
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Global variables for RAG system
qa_chain = None
retriever = Nonewhisper_model = whisper.load_model("base")


def is_cache_valid():
    return (
        os.path.exists(CHROMA_DB_PATH) and
        os.path.isdir(CHROMA_DB_PATH) and
        os.path.exists(CHUNKS_CACHE_PATH)
    )

def initialize_system():
    """Initialize the RAG system"""
    global qa_chain, retriever
    
    if qa_chain is None or retriever is None:
        try:
            print("Loading documents...")
            all_docs = load_all_documents("data")
            print(f"Loaded docs count: {len(all_docs)}")
            
            if not all_docs:
                return False, "No PDF files found in the data folder!"
            
            print("Splitting documents...")
            chunks = split_docs(all_docs)
            print(f"Chunks created: {len(chunks)}")
            
            print("Creating vector database...")
            db = create_vector_db(chunks)
            print("Vector database created successfully")
            
            print("Building retrieval QA system...")
            qa_chain, retriever = build_retrieval_qa(db)


            print(f"QA chain created: {qa_chain is not None}")
            print(f"Retriever created: {retriever is not None}")

            return True, f"System initialized with {len(all_docs)} documents"
        except Exception as e:
            import traceback
            print("INITIALIZATION ERROR:")
            print(traceback.format_exc())
            return False, f"Error: {str(e)}"
           
    
    return True, "System already initialized"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Load Whisper model once when app starts
print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper model loaded.")

@app.route('/')
def index():
    """Serve the main chat interface"""
    return render_template('index.html')

@app.route('/api/initialize', methods=['POST'])
def api_initialize():
    """Initialize the system"""
    success, message = initialize_system()
    return jsonify({'success': success, 'message': message})

@app.route('/api/ask', methods=['POST'])
def api_ask():
    """Process a question"""
    global qa_chain, retriever
    
    data = request.json
    question = data.get('question', '').strip()
    profile = load_profile()
    
    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400
    
    if qa_chain is None:
        return jsonify({'error': 'System not initialized. Please refresh the page.'}), 500
    
    intent = detect_intent(question)
    
    try:
        answer = None
        if intent == "quiz":
           answer = handle_quiz(question, qa_chain)
        
        elif intent == "summary":
            answer = handle_summary(question, qa_chain)

        
        elif intent == "revision":
            answer = handle_revision(question, qa_chain)
          

        else:
            memory = get_memory()
            context = "\n".join(
                [f"Q: {m['question']}\nA: {m['answer']}" for m in memory]
            )

        
            result = qa_chain.invoke({
             "query": question + "\n\nPrevious context:\n" + context
            })
            answer = result["result"]

        if not answer:
            raise ValueError("No answer generated.")
        add_memory(question, answer)

        audio_file = text_to_speech(answer, lang="en")

        # Update learner profile
        subject = "General"   # temporary placeholder

        update_subject(profile, subject, success=True)

        save_profile(profile)

        weak_subjects = get_weak_subjects(profile)

        recommendation = ""
        if weak_subjects:
            recommendation = f"Recommended focus: {', '.join(weak_subjects)}"

        # Get sources using the retriever
        try:
            sources = retriever.invoke(question)
            formatted_sources = format_sources(sources) if sources else []
        except Exception as source_err:
            print(f"Source retrieval error: {source_err}")
            formatted_sources = []
        
        return jsonify({
            'success': True,
            'answer': answer,
            'audio': "/" + audio_file,
            'sources': formatted_sources,
            'recommendation': recommendation
})
    except Exception as e:
        import traceback
        print(f"API ask error: {traceback.format_exc()}")
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/api/files', methods=['GET'])
def api_files():
    """Get list of loaded PDF files"""
    data_dir = "data"
    files = []
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.lower().endswith('.pdf'):
                files.append(file)
    
    return jsonify({'files': files})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Upload study materials"""

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

        file.save(filepath)

        # Reset system so uploaded file is included
        global qa_chain, retriever
        qa_chain = None
        retriever = None

        success, message = initialize_system()

        return jsonify({
            'success': True,
            'message': f'{filename} uploaded successfully',
            'system_status': message
        })

    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/voice', methods=['POST'])
def api_voice():
    print("VOICE ROUTE HIT")

    try:
        if 'file' not in request.files:
            print("NO FILE FOUND")
            return jsonify({'error': 'No audio file uploaded'}), 400

        uploaded = request.files['file']
        print("FILE RECEIVED:", uploaded.filename)

        os.makedirs("uploads", exist_ok=True)

        input_path = os.path.join("uploads", secure_filename(uploaded.filename))
        uploaded.save(input_path)
        print("FILE SAVED:", input_path)

        wav_path = input_path + ".wav"

        # Convert uploaded audio to wav
        audio = AudioSegment.from_file(input_path)
        audio.export(wav_path, format="wav")
        print("CONVERTED TO WAV:", wav_path)

        # Speech-to-text
        result = whisper_model.transcribe(wav_path, fp16=False)
        text = result["text"].strip()
        print("TRANSCRIBED TEXT:", text)

        if not text:
            return jsonify({'error': 'No speech detected'}), 500

        if qa_chain is None:
            return jsonify({'error': 'System not initialized'}), 500

        # Query RAG
        qa_result = qa_chain.invoke({"query": text})
        answer = qa_result["result"]
        print("ANSWER:", answer)

        # Text-to-speech
        audio_file = text_to_speech(answer, lang="en")
        print("AUDIO GENERATED:", audio_file)

        return jsonify({
            "success": True,
            "text": text,
            "answer": answer,
            "audio": "/" + audio_file
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("SmartStudy Web Interface")
    print("=" * 60)
    print("\nOpen your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server.\n")
    
    app.run(debug=False, host='127.0.0.1', port=5000)
