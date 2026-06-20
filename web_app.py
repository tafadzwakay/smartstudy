# Fix SSL/TLS issue on Windows - must be at the top
import ssl
import os
import re
import datetime

FFMPEG_DIR = r"C:\Users\HOMEPC\ffmpeg-2026-04-22-git-162ad61486-essentials_build\bin"

try:
    if os.path.exists(os.path.join(FFMPEG_DIR, "ffmpeg.exe")):
        from pydub import AudioSegment
        AudioSegment.converter = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
        AudioSegment.ffprobe = os.path.join(FFMPEG_DIR, "ffprobe.exe")
        os.environ["PATH"] += os.pathsep + FFMPEG_DIR
    else:
        print("Warning: ffmpeg not found at specified path, using system ffmpeg")
        from pydub import AudioSegment
except ImportError:
    print("Warning: pydub not available, voice features disabled")
    AudioSegment = None

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
from app.profile_manager import (
    _hash_password,
    add_message_to_session,
    authenticate_user,
    create_chat_session,
    delete_chat_session,
    get_chat_sessions,
    get_weak_subjects,
    load_profile,
    load_users,
    pin_chat_session,
    register_user,
    rename_chat_session,
    save_profile,
    save_users,
    update_subject,
    analyze_performance,
    generate_study_plan as generate_study_plan_profile,
    generate_adaptive_quiz as generate_adaptive_quiz_autonomous,
    update_progress_streak,
    get_motivation_message,
    get_progress_stats,
    admin_create_user,
    admin_update_user,
    admin_delete_user,
    admin_reset_password,
    admin_get_all_users,
)
from app.sharing import (
    create_shareable_quiz,
    create_shareable_notes,
    create_shareable_progress,
    import_shared_quiz,
    import_shared_notes,
    import_shared_progress,
    list_available_shares,
    get_share_info,
)
from app.gamification import (
    check_and_award_badges,
    get_progress_bars,
    get_motivational_messages,
    get_badge_info,
    get_all_badges,
    record_voice_usage,
    record_early_study,
    get_leaderboard_position,
    get_daily_challenge,
)
import sys
from app.router import detect_intent
from app.modes import handle_quiz, handle_summary, handle_revision, generate_study_plan as generate_study_plan_rag, generate_adaptive_quiz as generate_adaptive_quiz_rag
from app.memory import get_memory, add_memory
from app.tts import text_to_speech
from app.voice import speech_to_text, detect_language
import whisper
import traceback
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit
UPLOAD_FOLDER = "data"
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx", "doc", "ppt", "pptx", "xls", "xlsx", "csv", "rtf", "odt", "ods", "odp", "jpg", "jpeg", "png", "gif", "bmp", "tiff", "mp3", "wav", "mp4", "avi", "mov", "zip", "rar"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

qa_chain = None
retriever = None
vector_db = None
whisper_model = whisper.load_model("base")


# ─────────────────────────────────────────────────────────────────────────────
# GREETING DETECTION — used by both /api/ask and /api/voice
# Catches greetings BEFORE they hit the RAG pipeline
# ─────────────────────────────────────────────────────────────────────────────
GREETING_PATTERNS = [
    r'^\s*(hi|hey|hello|howdy|hiya|sup|yo|greetings|helo|ello|hie)\b',
    r'^\s*good\s*(morning|afternoon|evening|night|day)\b',
    r'^\s*how\s+(are\s+you|you\s+doing|r\s+u|are\s+u|ya\s+doing)\b',
    r'^\s*what\'?s?\s+up\b',
    r'^\s*howzit\b',
    r'^\s*(maswera\s*(sei)?|mhoro|sawubona)\b',
]

def is_greeting(text: str) -> bool:
    """Return True if the text is a greeting and should NOT go to the RAG pipeline."""
    return any(re.match(p, text.strip(), re.IGNORECASE) for p in GREETING_PATTERNS)

def build_greeting_reply(text: str) -> str:
    """Return a warm, time-aware greeting reply."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        time_greet = "Good morning"
    elif hour < 17:
        time_greet = "Good afternoon"
    elif hour < 21:
        time_greet = "Good evening"
    else:
        time_greet = "Good night"

    if re.search(r'maswera|mhoro', text, re.IGNORECASE):
        return f"Maswera! {time_greet}! I'm doing well, thank you 😊 What subject would you like to study today?"
    if re.search(r'sawubona', text, re.IGNORECASE):
        return f"Sawubona! {time_greet}! I'm doing well, thank you 😊 What subject would you like to study today?"
    return f"{time_greet}! I'm doing great, thanks for asking 😊 What subject would you like to study today?"


def is_cache_valid():
    return (
        os.path.exists(CHROMA_DB_PATH) and
        os.path.isdir(CHROMA_DB_PATH) and
        os.path.exists(CHUNKS_CACHE_PATH)
    )

def initialize_system(force_rebuild=False):
    global qa_chain, retriever, vector_db

    if qa_chain is not None and retriever is not None and vector_db is not None:
        return True, "System already initialized"

    try:
        if is_cache_valid() and not force_rebuild:
            print("Loading from cache...")
            db = load_vector_db()
            vector_db = db

            with open(CHUNKS_CACHE_PATH, "rb") as f:
                chunks = pickle.load(f)

            qa_chain, retriever = build_retrieval_qa(db)
            print("Loaded from cache successfully!")
            return True, "Loaded from cache"

        print("Building vector store for the first time...")
        all_docs = load_all_documents("data")

        if not all_docs:
            return False, "No study materials found in data folder!"

        chunks = split_docs(all_docs)
        db = create_vector_db(chunks)
        vector_db = db

        os.makedirs("db", exist_ok=True)
        with open(CHUNKS_CACHE_PATH, "wb") as f:
            pickle.dump(chunks, f)

        qa_chain, retriever = build_retrieval_qa(db)
        print("Built and saved to disk. Next startup will be fast!")
        return True, f"Built from {len(all_docs)} documents"

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return False, f"Error: {str(e)}"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def infer_subject(question: str) -> str:
    q = question.lower()
    subjects = {
        'algebra': 'Mathematics',
        'geometry': 'Mathematics',
        'calculus': 'Mathematics',
        'math': 'Mathematics',
        'biology': 'Biology',
        'chemistry': 'Chemistry',
        'physics': 'Physics',
        'zimbabwe': 'History',
        'history': 'History',
        'geography': 'Geography',
        'english': 'English',
        'shona': 'Languages',
        'environment': 'Science',
        'cell': 'Biology',
        'ecosystem': 'Biology',
        'economics': 'Economics',
        'accounting': 'Commerce'
    }

    for key, subject in subjects.items():
        if key in q:
            return subject

    return 'General'


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/quiz')
def quiz_page():
    return render_template('quiz.html')

@app.route('/api/initialize', methods=['POST'])
def api_initialize():
    success, message = initialize_system()
    return jsonify({'success': success, 'message': message})


def reformat_as_math_card(question, raw_answer):
    """Detects topic from question, pre-solves if possible, applies correct ZIMSEC formula."""
    import re as _re
    import math as _math

    # Clean markdown and LaTeX symbols
    clean = raw_answer
    for symbol in ['##', '**', '$$', '$', '`', '*']:
        clean = clean.replace(symbol, '')
    clean = clean.strip()

    q = question.lower()

    # ── Helper: extract numbers from question ──
    def get_numbers(text):
        return [float(x) for x in _re.findall(r'\d+\.?\d*', text)]

    nums = get_numbers(question)

    # ── Helper: build final structured string ──
    def build(formula_name, formula_expr, variables, steps, answer):
        result = []
        result.append(f"PROBLEM: {question.strip()}")
        result.append("")
        result.append(f"FORMULA: {formula_name}: {formula_expr}")
        result.append("")
        result.append("VARIABLES:")
        for v in variables:
            result.append(v)
        result.append("")
        result.append("STEPS:")
        for i, step in enumerate(steps, 1):
            if isinstance(step, tuple):
                title, formula, note = step if len(step) == 3 else (step[0], step[1], "")
                result.append(f"Step {i}: {title} | {formula} | {note}")
            else:
                result.append(f"Step {i}: Working | {step} | ")
        result.append("")
        result.append(f"ANSWER: {answer}")
        return "\n".join(result)

    # ══════════════════════════════════════════════════════════════
    #  PRE-SOLVED TYPES — calculated automatically from the question
    # ══════════════════════════════════════════════════════════════

    # ── AREA OF CIRCLE ──
    if 'area' in q and 'circle' in q and nums:
        r = nums[0]
        r_sq = round(r * r, 4)
        area = round(3.142 * r_sq, 3)
        return build(
            "Area of a Circle", "A = π × r²",
            ["A = Area of the circle", "π = 3.142 (approx.)", f"r = radius = {r} cm"],
            [
                ("Write the formula",          "A = π × r²",                    ""),
                ("Substitute the radius",      f"A = 3.142 × ({r})²",           f"Replace r with {r}"),
                ("Square the radius",          f"({r})² = {r_sq}",              f"So: A = 3.142 × {r_sq}"),
                ("Multiply by π",              f"A = 3.142 × {r_sq}",           f"A = {area} cm²"),
            ],
            f"A ≈ {area} cm²"
        )

    # ── CIRCUMFERENCE ──
    elif 'circumference' in q and nums:
        r = nums[0]
        c = round(2 * 3.142 * r, 3)
        return build(
            "Circumference of a Circle", "C = 2 × π × r",
            ["C = Circumference", "π = 3.142", f"r = radius = {r} cm"],
            [
                ("Write the formula",       "C = 2 × π × r",            ""),
                ("Substitute the radius",   f"C = 2 × 3.142 × {r}",     f"Replace r with {r}"),
                ("Multiply",                f"C = {c} cm",               ""),
            ],
            f"C = {c} cm"
        )

    # ── AREA OF TRIANGLE ──
    elif 'area' in q and 'triangle' in q and len(nums) >= 2:
        b, h = nums[0], nums[1]
        area = round(0.5 * b * h, 3)
        return build(
            "Area of a Triangle", "A = ½ × base × height",
            ["A = Area", f"base = {b} cm", f"height = {h} cm"],
            [
                ("Write the formula",    "A = ½ × base × height",    ""),
                ("Substitute values",    f"A = ½ × {b} × {h}",       ""),
                ("Multiply",             f"A = {area} cm²",           ""),
            ],
            f"A = {area} cm²"
        )

    # ── AREA OF RECTANGLE ──
    elif 'area' in q and any(k in q for k in ['rectangle', 'square']) and len(nums) >= 2:
        l, w = nums[0], nums[1]
        area = round(l * w, 3)
        return build(
            "Area of Rectangle", "A = length × width",
            [f"length = {l} cm", f"width = {w} cm"],
            [
                ("Write the formula",    "A = length × width",        ""),
                ("Substitute values",    f"A = {l} × {w}",            ""),
                ("Multiply",             f"A = {area} cm²",           ""),
            ],
            f"A = {area} cm²"
        )

    # ── PYTHAGORAS ──
    elif any(k in q for k in ['pythagoras', 'hypotenuse']) and len(nums) >= 2:
        a, b = nums[0], nums[1]
        a_sq = round(a * a, 4)
        b_sq = round(b * b, 4)
        c_sq = round(a_sq + b_sq, 4)
        c = round(_math.sqrt(c_sq), 3)
        return build(
            "Pythagoras Theorem", "c² = a² + b²",
            ["c = hypotenuse (longest side)", f"a = {a} cm", f"b = {b} cm"],
            [
                ("Write the formula",        "c² = a² + b²",              ""),
                ("Substitute values",        f"c² = {a}² + {b}²",         ""),
                ("Calculate squares",        f"c² = {a_sq} + {b_sq}",     ""),
                ("Add the squares",          f"c² = {c_sq}",               ""),
                ("Square root both sides",   f"c = √{c_sq} = {c} cm",      ""),
            ],
            f"c = {c} cm"
        )

    # ── SIMPLE INTEREST ──
    elif any(k in q for k in ['simple interest']) and len(nums) >= 3:
        P, R, T = nums[0], nums[1], nums[2]
        numerator = round(P * R * T, 2)
        I = round(numerator / 100, 2)
        return build(
            "Simple Interest", "I = (P × R × T) / 100",
            ["I = Interest earned", f"P = principal = {P}",
             f"R = rate = {R}%", f"T = time = {T} years"],
            [
                ("Write the formula",     "I = (P × R × T) / 100",           ""),
                ("Substitute values",     f"I = ({P} × {R} × {T}) / 100",    ""),
                ("Multiply numerator",    f"I = {numerator} / 100",           ""),
                ("Divide by 100",         f"I = {I}",                         ""),
            ],
            f"I = {I}"
        )

    # ── PERCENTAGE ──
    elif any(k in q for k in ['percentage', 'percent', '%']) and len(nums) >= 2:
        part, whole = nums[0], nums[1]
        divided = round(part / whole, 6)
        pct = round(divided * 100, 2)
        return build(
            "Percentage", "Percentage = (Part / Whole) × 100",
            ["Part = the portion being considered",
             f"Part = {part}", f"Whole = {whole}"],
            [
                ("Write the formula",    "Percentage = (Part / Whole) × 100",       ""),
                ("Substitute values",    f"Percentage = ({part} / {whole}) × 100",  ""),
                ("Divide",               f"= {divided} × 100",                       ""),
                ("Multiply by 100",      f"= {pct}%",                                ""),
            ],
            f"{pct}%"
        )

    # ── VOLUME OF CYLINDER ──
    elif 'volume' in q and 'cylinder' in q and len(nums) >= 2:
        r, h = nums[0], nums[1]
        r_sq = round(r * r, 4)
        v = round(3.142 * r_sq * h, 3)
        return build(
            "Volume of a Cylinder", "V = π × r² × h",
            ["V = Volume", "π = 3.142", f"r = radius = {r} cm", f"h = height = {h} cm"],
            [
                ("Write the formula",    "V = π × r² × h",                  ""),
                ("Substitute values",    f"V = 3.142 × ({r})² × {h}",       ""),
                ("Square the radius",    f"V = 3.142 × {r_sq} × {h}",       ""),
                ("Multiply",             f"V = {v} cm³",                     ""),
            ],
            f"V = {v} cm³"
        )

    # ── VOLUME OF CONE ──
    elif 'volume' in q and 'cone' in q and len(nums) >= 2:
        r, h = nums[0], nums[1]
        r_sq = round(r * r, 4)
        v = round((1/3) * 3.142 * r_sq * h, 3)
        return build(
            "Volume of a Cone", "V = (1/3) × π × r² × h",
            ["V = Volume", "π = 3.142", f"r = radius = {r} cm", f"h = height = {h} cm"],
            [
                ("Write the formula",    "V = (1/3) × π × r² × h",              ""),
                ("Substitute values",    f"V = (1/3) × 3.142 × ({r})² × {h}",   ""),
                ("Square the radius",    f"V = (1/3) × 3.142 × {r_sq} × {h}",   ""),
                ("Multiply",             f"V = {v} cm³",                          ""),
            ],
            f"V = {v} cm³"
        )

    # ── VOLUME OF SPHERE ──
    elif 'volume' in q and 'sphere' in q and nums:
        r = nums[0]
        r_cb = round(r ** 3, 4)
        v = round((4/3) * 3.142 * r_cb, 3)
        return build(
            "Volume of a Sphere", "V = (4/3) × π × r³",
            ["V = Volume", "π = 3.142", f"r = radius = {r} cm"],
            [
                ("Write the formula",    "V = (4/3) × π × r³",              ""),
                ("Substitute values",    f"V = (4/3) × 3.142 × ({r})³",     ""),
                ("Cube the radius",      f"V = (4/3) × 3.142 × {r_cb}",     ""),
                ("Multiply",             f"V = {v} cm³",                     ""),
            ],
            f"V = {v} cm³"
        )

    # ── VOLUME OF CUBOID ──
    elif 'volume' in q and any(k in q for k in ['cuboid', 'box', 'rectangular']) and len(nums) >= 3:
        l, w, h = nums[0], nums[1], nums[2]
        v = round(l * w * h, 3)
        return build(
            "Volume of a Cuboid", "V = length × width × height",
            [f"length = {l} cm", f"width = {w} cm", f"height = {h} cm"],
            [
                ("Write the formula",    "V = length × width × height",  ""),
                ("Substitute values",    f"V = {l} × {w} × {h}",         ""),
                ("Multiply",             f"V = {v} cm³",                  ""),
            ],
            f"V = {v} cm³"
        )

    # ── SURFACE AREA OF CYLINDER ──
    elif 'surface area' in q and 'cylinder' in q and len(nums) >= 2:
        r, h = nums[0], nums[1]
        sa = round(2 * 3.142 * r * (r + h), 3)
        return build(
            "Surface Area of a Cylinder", "SA = 2 × π × r × (r + h)",
            ["SA = total surface area", "π = 3.142", f"r = {r} cm", f"h = {h} cm"],
            [
                ("Write the formula",    "SA = 2 × π × r × (r + h)",          ""),
                ("Substitute values",    f"SA = 2 × 3.142 × {r} × ({r} + {h})", ""),
                ("Add bracket",          f"SA = 2 × 3.142 × {r} × {r + h}",   ""),
                ("Multiply",             f"SA = {sa} cm²",                      ""),
            ],
            f"SA = {sa} cm²"
        )

    # ── SURFACE AREA OF SPHERE ──
    elif 'surface area' in q and 'sphere' in q and nums:
        r = nums[0]
        sa = round(4 * 3.142 * r * r, 3)
        return build(
            "Surface Area of a Sphere", "SA = 4 × π × r²",
            ["SA = surface area", "π = 3.142", f"r = {r} cm"],
            [
                ("Write the formula",    "SA = 4 × π × r²",              ""),
                ("Substitute values",    f"SA = 4 × 3.142 × ({r})²",     ""),
                ("Square the radius",    f"SA = 4 × 3.142 × {r*r}",      ""),
                ("Multiply",             f"SA = {sa} cm²",                ""),
            ],
            f"SA = {sa} cm²"
        )

    # ── GRADIENT ──
    elif 'gradient' in q and len(nums) >= 4:
        x1, y1, x2, y2 = nums[0], nums[1], nums[2], nums[3]
        rise = round(y2 - y1, 4)
        run  = round(x2 - x1, 4)
        m = round(rise / run, 3) if run != 0 else "undefined"
        return build(
            "Gradient of a Line", "m = (y₂ - y₁) / (x₂ - x₁)",
            ["m = gradient", f"(x₁, y₁) = ({x1}, {y1})", f"(x₂, y₂) = ({x2}, {y2})"],
            [
                ("Write the formula",    "m = (y₂ - y₁) / (x₂ - x₁)",             ""),
                ("Substitute values",    f"m = ({y2} - {y1}) / ({x2} - {x1})",     ""),
                ("Subtract",             f"m = {rise} / {run}",                      ""),
                ("Divide",               f"m = {m}",                                 ""),
            ],
            f"Gradient m = {m}"
        )

    # ── MEAN ──
    elif any(k in q for k in ['mean', 'average']) and nums:
        total = round(sum(nums), 3)
        count = len(nums)
        mean  = round(total / count, 3)
        return build(
            "Mean", "Mean = Sum of all values / Number of values",
            ["Sum = total of all data values", f"n = number of values = {count}"],
            [
                ("List the values",      f"Values: {nums}",               ""),
                ("Add all values",       f"Sum = {total}",                ""),
                ("Count the values",     f"n = {count}",                  ""),
                ("Divide sum by n",      f"Mean = {total} / {count}",     ""),
            ],
            f"Mean = {mean}"
        )

    # ── PROBABILITY ──
    elif any(k in q for k in ['probability', 'chance', 'p(']) and len(nums) >= 2:
        fav, total = nums[0], nums[1]
        p = round(fav / total, 4)
        return build(
            "Probability", "P(E) = Favorable outcomes / Total outcomes",
            ["P(E) = probability of event E",
             f"Favorable outcomes = {fav}",
             f"Total outcomes = {total}",
             "0 ≤ P(E) ≤ 1"],
            [
                ("Write the formula",    "P(E) = Favorable / Total",     ""),
                ("Substitute values",    f"P(E) = {fav} / {total}",      ""),
                ("Divide",               f"P(E) = {p}",                   ""),
            ],
            f"P(E) = {p}"
        )

    # ══════════════════════════════════════════════════════════════
    #  FORMULA-ONLY TYPES — show formula + use model steps
    # ══════════════════════════════════════════════════════════════

    # ── NUMBER SYSTEMS & OPERATIONS ──
    elif any(k in q for k in ['standard form', 'scientific notation']):
        formula_name = "Standard Form"
        formula_expr = "a × 10ⁿ  where 1 ≤ a < 10"
        variables = ["a = number between 1 and 10", "n = power of 10 (positive or negative)"]

    elif any(k in q for k in ['order of operations', 'bodmas', 'bidmas', 'laws of operations']):
        formula_name = "BODMAS / Order of Operations"
        formula_expr = "Brackets → Orders → Division → Multiplication → Addition → Subtraction"
        variables = ["Always work left to right within each operation level"]

    elif any(k in q for k in ['number system', 'binary', 'hexadecimal', 'octal', 'base']):
        formula_name = "Number Base Conversion"
        formula_expr = "Divide by target base repeatedly, read remainders upward"
        variables = ["Base 2 = binary", "Base 8 = octal", "Base 10 = decimal", "Base 16 = hexadecimal"]

    # ── FRACTIONS, RATIOS ──
    elif any(k in q for k in ['ratio', 'proportion', 'share', 'divide in ratio']):
        formula_name = "Ratio and Proportion"
        formula_expr = "Share = (Part / Total parts) × Whole amount"
        variables = ["Part = one share of the ratio", "Total parts = sum of all ratio values", "Whole = total amount being shared"]

    elif any(k in q for k in ['fraction', 'numerator', 'denominator', 'mixed number']):
        formula_name = "Fractions"
        formula_expr = "a/b + c/d = (ad + bc) / bd    |    a/b × c/d = ac/bd"
        variables = ["Numerator = top number", "Denominator = bottom number", "LCD = lowest common denominator for addition/subtraction"]

    # ── FINANCE ──
    elif any(k in q for k in ['profit', 'loss', 'cost price', 'selling price']):
        formula_name = "Profit and Loss"
        formula_expr = "Profit = Selling Price - Cost Price    |    Profit% = (Profit / CP) × 100"
        variables = ["Selling Price = price sold for", "Cost Price = price bought for", "Loss occurs when Cost Price > Selling Price"]

    # ── ALGEBRA ──
    elif any(k in q for k in ['expand', 'expression', 'algebraic', 'simplify', 'collect like terms']):
        formula_name = "Algebraic Expressions"
        formula_expr = "a(b + c) = ab + ac    |    (a+b)² = a²+2ab+b²    |    (a-b)(a+b) = a²-b²"
        variables = ["Expand by multiplying each term in the bracket", "Factorise by finding the HCF", "Collect like terms: same variable and power"]

    elif any(k in q for k in ['simultaneous', 'two equations', 'elimination', 'substitution method']):
        formula_name = "Simultaneous Equations"
        formula_expr = "Elimination: match one variable coefficient, then add or subtract equations"
        variables = ["Method 1 - Elimination: make coefficients equal then eliminate", "Method 2 - Substitution: express one variable in terms of the other", "Check by substituting both values back"]

    elif any(k in q for k in ['discriminant', 'b^2-4ac', 'b2-4ac']):
        formula_name = "Discriminant"
        formula_expr = "D = b² - 4ac"
        variables = ["D > 0 : two real roots", "D = 0 : one repeated root", "D < 0 : no real roots", "a, b, c from ax² + bx + c = 0"]

    elif any(k in q for k in ['quadratic formula', '(-b', 'plus or minus']):
        formula_name = "Quadratic Formula"
        formula_expr = "x = (-b ± √(b² - 4ac)) / 2a"
        variables = ["a = coefficient of x²", "b = coefficient of x", "c = constant term", "From: ax² + bx + c = 0"]

    elif any(k in q for k in ['factorise', 'factorize']) and any(k in q for k in ['x^2', 'x2', 'quadratic']):
        formula_name = "Factorisation of Quadratic"
        formula_expr = "ax² + bx + c = (px + q)(rx + s)"
        variables = ["Find two numbers that multiply to ac and add to b", "pr = a  and  qs = c", "Check by expanding back out"]

    elif any(k in q for k in ['quadratic', 'x^2', 'x2', 'parabola', '= 0']):
        formula_name = "Quadratic Equation"
        formula_expr = "ax² + bx + c = 0"
        variables = ["a = coefficient of x²", "b = coefficient of x", "c = constant term", "Solve by: factorisation or quadratic formula"]

    elif any(k in q for k in ['linear', 'solve for x', 'solve for y', '3x', '2x', '4x', '5x']):
        formula_name = "Linear Equation"
        formula_expr = "ax + b = c    ⟹    x = (c - b) / a"
        variables = ["a = coefficient of x", "b = constant on left", "c = constant on right", "Isolate x by doing same to both sides"]

    # ── TRIGONOMETRY ──
    elif any(k in q for k in ['sine rule', 'sin rule']):
        formula_name = "Sine Rule"
        formula_expr = "a / sin(A) = b / sin(B) = c / sin(C)"
        variables = ["a, b, c = side lengths", "A, B, C = opposite angles", "Use: 2 angles + 1 side, or 2 sides + non-included angle"]

    elif any(k in q for k in ['cosine rule', 'cos rule']):
        formula_name = "Cosine Rule"
        formula_expr = "a² = b² + c² - 2bc × cos(A)"
        variables = ["a = side opposite angle A", "b, c = other two sides", "A = included angle"]

    elif any(k in q for k in ['sin', 'cos', 'tan', 'trigonometry', 'trig', 'soh', 'cah', 'toa']):
        formula_name = "Trigonometric Ratios"
        formula_expr = "sin θ = opp/hyp    |    cos θ = adj/hyp    |    tan θ = opp/adj"
        variables = ["opp = side opposite the angle", "adj = side adjacent to the angle", "hyp = hypotenuse (longest side)", "SOH CAH TOA"]

    # ── GEOMETRY — ANGLES ──
    elif any(k in q for k in ['parallel', 'alternate angle', 'corresponding angle', 'co-interior', 'transversal']):
        formula_name = "Parallel Lines — Angle Facts"
        formula_expr = "Alternate = equal  |  Corresponding = equal  |  Co-interior = 180°"
        variables = ["Alternate angles: Z-shape, equal", "Corresponding angles: F-shape, equal", "Co-interior angles: C-shape, sum = 180°"]

    elif any(k in q for k in ['angle', 'polygon', 'interior angle', 'exterior angle', 'bearing']):
        formula_name = "Angle Facts"
        formula_expr = "Triangle = 180°  |  Straight line = 180°  |  Full turn = 360°"
        variables = ["Interior angles of polygon = (n - 2) × 180°", "n = number of sides", "Exterior angle = 360° / n"]

    # ── PERIMETER ──
    elif 'perimeter' in q:
        formula_name = "Perimeter"
        formula_expr = "Perimeter = sum of all sides"
        variables = ["Rectangle: P = 2(l + w)", "Triangle: P = a + b + c", "Circle: C = 2πr"]

    # ── GRAPHS ──
    elif any(k in q for k in ['equation of line', 'straight line', 'y = mx', 'y=mx']):
        formula_name = "Equation of a Straight Line"
        formula_expr = "y = mx + c"
        variables = ["m = gradient", "c = y-intercept", "x, y = any point on the line"]

    elif any(k in q for k in ['midpoint', 'mid point']):
        formula_name = "Midpoint of Two Points"
        formula_expr = "M = ((x₁ + x₂)/2 , (y₁ + y₂)/2)"
        variables = ["(x₁, y₁) = first point", "(x₂, y₂) = second point"]

    elif any(k in q for k in ['distance between', 'length of line', 'distance formula']):
        formula_name = "Distance Between Two Points"
        formula_expr = "d = √((x₂-x₁)² + (y₂-y₁)²)"
        variables = ["d = distance", "(x₁, y₁) = first point", "(x₂, y₂) = second point"]

    # ── STATISTICS ──
    elif any(k in q for k in ['mean', 'average']) and 'frequency' in q:
        formula_name = "Mean from Frequency Table"
        formula_expr = "Mean = Σ(f × x) / Σf"
        variables = ["f = frequency", "x = data value", "Σf = total frequency", "Σ(fx) = sum of (frequency × value)"]

    elif 'median' in q:
        formula_name = "Median"
        formula_expr = "Middle value when data is arranged in order"
        variables = ["Odd n: middle value", "Even n: mean of two middle values", "Position = (n + 1) / 2"]

    elif 'mode' in q:
        formula_name = "Mode"
        formula_expr = "Mode = value that appears most often"
        variables = ["Can have more than one mode", "No mode if all values appear once"]

    elif 'range' in q and any(k in q for k in ['data', 'values', 'statistics', 'numbers']):
        formula_name = "Range"
        formula_expr = "Range = Highest value - Lowest value"
        variables = ["Highest = largest in data set", "Lowest = smallest in data set"]

    elif any(k in q for k in ['frequency table', 'frequency distribution', 'tally']):
        formula_name = "Frequency Table"
        formula_expr = "Relative Frequency = frequency / total frequency"
        variables = ["Frequency = count of each value", "Cumulative frequency = running total"]

    # ── PROBABILITY (no numbers given) ──
    elif any(k in q for k in ['probability', 'chance', 'likelihood']):
        formula_name = "Probability"
        formula_expr = "P(E) = favorable outcomes / total outcomes"
        variables = ["0 ≤ P(E) ≤ 1", "P(not E) = 1 - P(E)", "P(A and B) = P(A) × P(B) for independent events", "P(A or B) = P(A) + P(B) for mutually exclusive events"]

    # ── TRANSFORMATIONS ──
    elif 'translation' in q:
        formula_name = "Translation"
        formula_expr = "New point = Original point + Translation vector (a, b)"
        variables = ["a = horizontal shift (+ right, - left)", "b = vertical shift (+ up, - down)", "Shape and size unchanged"]

    elif 'reflection' in q:
        formula_name = "Reflection"
        formula_expr = "Reflect each point across the mirror line"
        variables = ["x-axis: (x, y) → (x, -y)", "y-axis: (x, y) → (-x, y)", "y = x: (x, y) → (y, x)"]

    elif 'rotation' in q:
        formula_name = "Rotation"
        formula_expr = "Rotate each point by angle about the centre"
        variables = ["90° clockwise: (x, y) → (y, -x)", "90° anticlockwise: (x, y) → (-y, x)", "180°: (x, y) → (-x, -y)"]

    elif any(k in q for k in ['enlargement', 'scale factor']):
        formula_name = "Enlargement"
        formula_expr = "New length = Scale Factor × Original length"
        variables = ["SF > 1 : enlargement", "0 < SF < 1 : reduction", "SF = New length / Original length"]

    # ── SPEED / DISTANCE / TIME ──
    elif any(k in q for k in ['speed', 'velocity']):
        formula_name = "Speed"
        formula_expr = "Speed = Distance / Time"
        variables = ["Distance = Speed × Time", "Time = Distance / Speed", "Units: km/h or m/s"]

    elif 'distance' in q and any(k in q for k in ['time', 'speed', 'km', 'metres']):
        formula_name = "Distance"
        formula_expr = "Distance = Speed × Time"
        variables = ["Speed = km/h or m/s", "Time = hours or seconds"]

   # ── FALLBACK ──
    # Only apply if there are numbers in the question (genuine calculation)
    elif _re.search(r'\d', question):
        formula_name = "Working"
        formula_expr = "See steps below"
        variables = ["Always write the formula first", "Show all substitution steps", "Include correct units in final answer"]
    else:
        # Not a math question — return the raw model answer unchanged
        return clean

    # ══════════════════════════════════════════════════════════════
    #  For formula-only types: split model response into steps
    # ══════════════════════════════════════════════════════════════
    parts = []
    for sep in ['\n', '. ', ', then ', ', so ', ' therefore ']:
        if sep in clean:
            parts = [p.strip() for p in clean.split(sep) if p.strip() and len(p.strip()) > 4]
            if len(parts) >= 2:
                break
    if not parts:
        parts = [clean]

    step_texts = []
    for i, part in enumerate(parts[:6], 1):
        step_texts.append(f"Step {i}: Working | {part.strip()} | ")

    answer = ""
    for part in reversed(parts):
        if any(kw in part.lower() for kw in ['therefore', 'solution', 'answer', 'x =', 'x=', '= ']):
            answer = part.strip()
            break
    if not answer:
        answer = parts[-1].strip() if parts else clean

    return build(formula_name, formula_expr, variables,
                 [(f"Working", p, "") for p in parts[:6]],
                 answer)

@app.route('/api/ask/stream', methods=['POST'])
def api_ask_stream():
    """Streaming version of /api/ask — sends tokens as they generate"""
    from flask import Response, stream_with_context
    global qa_chain, retriever

    data = request.json
    question = data.get('question', '').strip()
    username = str(data.get('username') or '').strip().lower() or None
    voice_lang = data.get('language', 'en')
    system_prompt = data.get('system_prompt', '')
    

    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400

    # Greetings never need streaming — return instantly
    if is_greeting(question):
        reply = build_greeting_reply(question)
        def instant():
            import json
            yield f"data: {json.dumps({'token': reply, 'done': False})}\n\n"
            yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
        return Response(stream_with_context(instant()),
                        mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    if qa_chain is None:
        return jsonify({'error': 'System not initialized'}), 500

    def generate():
        import json
        try:
            # Retrieve context from vector DB
            docs = retriever.invoke(question)
            context = "\n\n".join([d.page_content for d in docs]) if docs else ""

            # Build the prompt manually so we can stream Ollama directly
            from app.model import load_model
            llm = load_model()

            prompt_text = f"""You are SMARTSTUDY, a ZIMSEC tutor.

RULES:
1. No markdown. No ** or ##.
2. For non-maths questions: answer in plain sentences, 2 to 4 sentences only.
3. Use ONLY the context below. If not found say: Not found in notes.

Context:
{context}

Question: {question}
Answer:"""

            # Collect full response first
            full_response = ""
            for chunk in llm.stream(prompt_text):
                if chunk:
                    full_response += chunk

            import re as _re

            # ── STEP 1: Block definition/concept questions from math card ──
            is_definition = bool(_re.match(
                r'^\s*(what\s+is|what\s+are|define|explain|describe|'
                r'tell\s+me\s+about|what\s+do\s+you\s+mean|who\s+is|'
                r'why\s+is|why\s+are|how\s+does|what\s+does)\b',
                question.strip(), _re.IGNORECASE
            ))

            # ── STEP 2: Detect genuine solving/calculation intent ──
            has_solve_verb = bool(_re.search(
                r'\b(solve|calculate|find|compute|work\s+out|evaluate|'
                r'determine|simplify|factorise|factorize|expand)\b',
                question, _re.IGNORECASE
            ))
            has_math_noun = bool(_re.search(
                r'\b(area|volume|perimeter|circumference|surface\s+area|'
                r'gradient|speed|velocity|acceleration|percentage|interest|'
                r'probability|mean|median|mode|radius|diameter|hypotenuse|'
                r'profit|loss|ratio|midpoint|roots|solutions)\b',
                question, _re.IGNORECASE
            ))
            has_number      = bool(_re.search(r'\d', question))
            has_equation    = bool(_re.search(
                r'\d+\s*[x-z]\s*[\+\-\=]|\bx\^2\b|x²|\=\s*0',
                question, _re.IGNORECASE
            ))
            has_units       = bool(_re.search(
                r'\d+\s*(cm|mm|m|km|kg|g|mg|l|ml|%|°)\b',
                question, _re.IGNORECASE
            ))
            has_named_theorem = bool(_re.search(
                r'\b(pythagoras|sine\s+rule|cosine\s+rule|soh\s+cah\s+toa|'
                r'simple\s+interest|compound\s+interest|quadratic\s+formula)\b',
                question, _re.IGNORECASE
            ))

            is_maths_question = (
                not is_definition
                and (
                    has_equation
                    or has_units
                    or has_named_theorem
                    or (has_solve_verb and has_math_noun)
                    or (has_solve_verb and has_number)
                )
            )

            # ── STEP 3: Apply math card or return clean prose ──
            already_formatted = full_response.strip().upper().startswith('PROBLEM:')

            if is_maths_question and not already_formatted:
                full_response = reformat_as_math_card(question, full_response)
            else:
                # Non-math: strip markdown and any accidental math labels
                full_response = full_response.replace('**', '').replace('##', '').replace('`', '')
                if already_formatted:
                    full_response = _re.sub(
                        r'(PROBLEM|FORMULA|VARIABLES|STEPS|ANSWER):\s*', '', full_response
                    )
                    full_response = _re.sub(r'Step \d+:', '', full_response)
                    full_response = ' '.join(full_response.split()).strip()

            # ── STEP 4: Stream the final response ──
            for token in full_response.split(' '):
                if token:
                    yield f"data: {json.dumps({'token': token + ' ', 'done': False})}\n\n"

            yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'token': f'Error: {str(e)}', 'done': True})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

@app.route('/api/ask', methods=['POST'])
def api_ask():
    global qa_chain, retriever
    
    data = request.json
    question = data.get('question', '').strip()
    username = str(data.get('username') or '').strip().lower() or None
    voice_lang = data.get('language', 'en')
    session_id = data.get('session_id')
    profile = load_profile(username)
    
    if not question:
        return jsonify({'error': 'Question cannot be empty'}), 400

    # ── GREETING SHORT-CIRCUIT ────────────────────────────────────────────────
    # Catch greetings before they ever reach the RAG pipeline
    if is_greeting(question):
        return jsonify({
            'success': True,
            'answer': build_greeting_reply(question),
            'session_id': session_id,
            'sources': [],
            'recommendation': '',
            'profile': profile
        })
    # ─────────────────────────────────────────────────────────────────────────

    if qa_chain is None:
        return jsonify({'error': 'System not initialized. Please refresh the page.'}), 500

    if not session_id and username:
        session_id = create_chat_session(profile, question[:50] + "..." if len(question) > 50 else question)
        save_profile(profile, username)
        profile = load_profile(username)

    intent = detect_intent(question)
    
    try:
        answer = None
        sources = []
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

            try:
                result = qa_chain.invoke({
                    "query": question + "\n\nPrevious context:\n" + context
                })
                answer = result.get("result") or result.get("output")
                sources = result.get("source_documents", []) or []
            except Exception as llm_err:
                print(f"LLM generation error: {llm_err}")
                answer = "I encountered an error while generating the answer. Please try again."

        if not answer:
            raise ValueError("No answer generated.")

        add_memory(question, answer)

        if session_id and username:
            add_message_to_session(profile, session_id, "user", question)
            add_message_to_session(profile, session_id, "assistant", answer)

        subject = infer_subject(question)
        update_subject(profile, subject, success=True)
        profile.setdefault('recent_topics', []).insert(0, question)
        profile['recent_topics'] = profile['recent_topics'][:10]
        profile.setdefault('activity', []).insert(0, {
            'question': question,
            'subject': subject,
            'timestamp': datetime.datetime.now().isoformat(sep=' ', timespec='minutes')
        })
        profile['activity'] = profile['activity'][:20]

        save_profile(profile, username)

        weak_subjects = get_weak_subjects(profile)
        recommendation = ""
        if weak_subjects:
            recommendation = f"Recommended focus: {', '.join(weak_subjects)}"

        try:
            if not sources:
                sources = retriever.invoke(question)
            formatted_sources = format_sources(sources) if sources else []
        except Exception as source_err:
            print(f"Source retrieval error: {source_err}")
            formatted_sources = []
        
        audio_file = text_to_speech(answer, lang=voice_lang)

        return jsonify({
            'success': True,
            'answer': answer,
            'session_id': session_id,
            'audio': "/" + audio_file,
            'sources': formatted_sources,
            'recommendation': recommendation,
            'profile': profile
        })
    except Exception as e:
        import traceback
        print(f"API ask error: {traceback.format_exc()}")
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/api/files', methods=['GET'])
def api_files():
    data_dir = "data"
    files = []
    
    if os.path.exists(data_dir):
        supported_exts = ['.pdf', '.txt', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.csv', '.rtf', '.odt', '.ods', '.odp', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.mp3', '.wav', '.mp4', '.avi', '.mov']
        for file in os.listdir(data_dir):
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_exts:
                files.append(file)
    
    return jsonify({'files': files})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Enter both username and password.'}), 400

    if authenticate_user(username, password):
        profile = load_profile(username)
        return jsonify({'success': True, 'message': 'Logged in', 'profile': profile})

    return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401


@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    grade = data.get('grade', 'Form 1').strip()
    role = data.get('role', 'student').strip().lower()

    if not username or not password or not name:
        return jsonify({'success': False, 'message': 'Username, password, and name are required.'}), 400

    result = register_user(username, password, name, grade, role)
    
    if result.get('success'):
        profile = load_profile(username)
        return jsonify({'success': True, 'message': result['message'], 'profile': profile}), 201
    else:
        return jsonify({'success': False, 'message': result['message']}), 400


@app.route('/api/chat-sessions', methods=['GET'])
def api_get_chat_sessions():
    username = str(request.args.get('username') or '').strip().lower() or None
    profile = load_profile(username)
    sessions = get_chat_sessions(profile)
    return jsonify({'success': True, 'sessions': sessions})

@app.route('/api/chat-sessions', methods=['POST'])
def api_create_chat_session():
    data = request.json or {}
    username = str(data.get('username') or '').strip().lower() or None
    title = data.get('title', 'New Chat').strip()
    
    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400
    
    profile = load_profile(username)
    session_id = create_chat_session(profile, title)
    save_profile(profile, username)
    return jsonify({'success': True, 'session_id': session_id})

@app.route('/api/chat-sessions/<session_id>', methods=['DELETE'])
def api_delete_chat_session(session_id):
    username = str(request.args.get('username') or '').strip().lower() or None
    
    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400
    
    profile = load_profile(username)
    success = delete_chat_session(profile, session_id)
    if success:
        save_profile(profile, username)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Session not found'}), 404

@app.route('/api/chat-sessions/<session_id>/rename', methods=['POST'])
def api_rename_chat_session(session_id):
    data = request.json or {}
    username = str(data.get('username') or '').strip().lower() or None
    new_title = data.get('title', '').strip()
    
    if not username or not new_title:
        return jsonify({'success': False, 'message': 'Username and title required'}), 400
    
    profile = load_profile(username)
    success = rename_chat_session(profile, session_id, new_title)
    if success:
        save_profile(profile, username)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Session not found'}), 404

@app.route('/api/chat-sessions/<session_id>/pin', methods=['POST'])
def api_pin_chat_session(session_id):
    data = request.json or {}
    username = str(data.get('username') or '').strip().lower() or None
    pinned = data.get('pinned', True)
    
    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400
    
    profile = load_profile(username)
    success = pin_chat_session(profile, session_id, pinned)
    if success:
        save_profile(profile, username)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Session not found'}), 404



@app.route('/api/profile', methods=['GET'])
def api_profile():
    username = str(request.args.get('username') or '').strip().lower() or None
    profile = load_profile(username)
    return jsonify({'success': True, 'profile': profile})


@app.route('/api/admin/dashboard', methods=['GET'])
def api_admin_dashboard():
    username = str(request.args.get('username') or '').strip().lower() or None
    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    users = load_users()
    if username not in users or users[username].get('role') not in ['teacher', 'admin']:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    all_users = []
    for uname, udata in users.items():
        profile = load_profile(uname)
        all_users.append({
            'username': uname,
            'name': udata.get('name'),
            'grade': udata.get('grade'),
            'role': udata.get('role'),
            'last_active': profile.get('last_active'),
            'subjects': profile.get('subjects', {}),
            'badges': profile.get('badges', []),
            'activity_count': len(profile.get('activity', []))
        })

    data_dir = "data"
    files = []
    supported_exts = ['.pdf', '.txt', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.csv']
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_exts:
                files.append(file)

    return jsonify({
        'success': True,
        'users': all_users,
        'files': files,
        'total_users': len(all_users),
        'total_files': len(files)
    })


@app.route('/api/admin/delete-file', methods=['POST'])
def api_admin_delete_file():
    username = str(request.args.get('username') or '').strip().lower() or None
    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    users = load_users()
    if username not in users or users[username].get('role') not in ['teacher', 'admin']:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'success': False, 'message': 'Filename required'}), 400

    filepath = os.path.join('data', filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        global qa_chain, retriever
        qa_chain = None
        retriever = None
        return jsonify({'success': True, 'message': f'{filename} deleted'})
    return jsonify({'success': False, 'message': 'File not found'}), 404


@app.route('/api/sync', methods=['POST'])
def api_sync():
    data = request.json or {}
    username = str(data.get('username') or '').strip().lower() or None
    online = data.get('online', False)

    profile = load_profile(username)

    if online:
        now = datetime.datetime.now().isoformat(sep=' ', timespec='minutes')
        profile['last_sync'] = now
        profile.setdefault('sync_history', []).append(now)
        profile['pending_sync'] = 0
        save_profile(profile, username)
        return jsonify({'success': True, 'message': 'Teacher sync completed.', 'last_sync': now})

    profile['pending_sync'] = profile.get('pending_sync', 0) + 1
    save_profile(profile, username)
    return jsonify({'success': False, 'message': 'Offline: sync stored locally until signal returns.', 'pending_sync': profile['pending_sync']})


@app.route('/api/share', methods=['GET'])
def api_share():
    username = str(request.args.get('username') or '').strip().lower() or None
    profile = load_profile(username)
    shared_data = {
        'username': profile.get('username', 'guest'),
        'name': profile.get('name', 'Guest'),
        'grade': profile.get('grade', 'Form 1'),
        'badges': profile.get('badges', []),
        'streak': profile.get('streak', 0),
        'subjects': profile.get('subjects', {}),
        'recent_topics': profile.get('recent_topics', []),
        'notes': profile.get('notes', []),
        'quizzes': profile.get('quizzes', []),
        'generated_at': datetime.datetime.now().isoformat()
    }
    return jsonify({'success': True, 'share_data': shared_data})


@app.route('/api/import-share', methods=['POST'])
def api_import_share():
    data = request.json or {}
    username = str(data.get('username') or '').strip().lower() or None
    share_data = data.get('share_data')

    if not share_data:
        return jsonify({'success': False, 'message': 'No share data provided.'}), 400

    profile = load_profile(username)
    profile.setdefault('notes', []).extend(share_data.get('notes', []))
    profile.setdefault('quizzes', []).extend(share_data.get('quizzes', []))
    profile.setdefault('recent_topics', []).extend(share_data.get('recent_topics', []))
    profile['pending_sync'] = profile.get('pending_sync', 0) + 1
    save_profile(profile, username)
    return jsonify({'success': True, 'message': 'Shared study pack imported locally.'})


@app.route('/api/upload', methods=['POST'])
def api_upload():
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
        global qa_chain, retriever, vector_db
        qa_chain = None
        retriever = None
        vector_db = None

        # Wipe old cache — close ChromaDB first before deleting
        import shutil
        import gc
        import time

        # Force garbage collection to release ChromaDB file handles
        gc.collect()
        time.sleep(0.5)

        try:
            if os.path.exists(CHROMA_DB_PATH):
                shutil.rmtree(CHROMA_DB_PATH)
        except PermissionError:
            # If still locked, just delete the chunks cache and rebuild on top
            pass

        if os.path.exists(CHUNKS_CACHE_PATH):
            os.remove(CHUNKS_CACHE_PATH)

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
        voice_lang = request.form.get('language', 'en')
        username = request.form.get('username', '').strip().lower() or None

        print("FILE RECEIVED:", uploaded.filename)

        os.makedirs("uploads", exist_ok=True)

        input_path = os.path.join("uploads", secure_filename(uploaded.filename))
        uploaded.save(input_path)
        print("FILE SAVED:", input_path)

        wav_path = input_path + ".wav"

        audio = AudioSegment.from_file(input_path)
        audio.export(wav_path, format="wav")
        print("CONVERTED TO WAV:", wav_path)

        whisper_params = {"fp16": False}
        if voice_lang and voice_lang != 'auto':
            whisper_params['language'] = voice_lang
        result = whisper_model.transcribe(wav_path, **whisper_params)
        text = result["text"].strip()
        print("TRANSCRIBED TEXT:", text)

        if not text:
            return jsonify({'error': 'No speech detected'}), 500

        if qa_chain is None:
            return jsonify({'error': 'System not initialized'}), 500

        # ── GREETING SHORT-CIRCUIT ────────────────────────────────────────────
        # Catch greetings BEFORE hitting the RAG pipeline
        if is_greeting(text):
            answer = build_greeting_reply(text)
            print("GREETING DETECTED — skipping RAG, answer:", answer)
        else:
            # Query RAG only for real subject questions
            qa_result = qa_chain.invoke({"query": text})
            answer = qa_result["result"]
        # ─────────────────────────────────────────────────────────────────────

        print("ANSWER:", answer)

        profile = load_profile(username)
        subject = infer_subject(text)
        update_subject(profile, subject, success=True)
        profile.setdefault('recent_topics', []).insert(0, text)
        profile['recent_topics'] = profile['recent_topics'][:10]
        profile.setdefault('activity', []).insert(0, {
            'question': text,
            'subject': subject,
            'timestamp': datetime.datetime.now().isoformat(sep=' ', timespec='minutes')
        })
        profile['activity'] = profile['activity'][:20]
        save_profile(profile, username)

        audio_file = text_to_speech(answer, lang=voice_lang)
        print("AUDIO GENERATED:", audio_file)

        return jsonify({
            "success": True,
            "text": text,
            "answer": answer,
            "audio": "/" + audio_file,
            "profile": profile
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/study-plan', methods=['GET'])
def api_study_plan():
    username = str(request.args.get('username') or '').strip().lower() or None
    profile = load_profile(username)
    
    if not qa_chain:
        return jsonify({'error': 'System not initialized'}), 500
    
    try:
        plan = generate_study_plan_rag(profile, qa_chain)
        return jsonify({'success': True, 'plan': plan})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gamification/progress', methods=['GET'])
def api_get_progress():
    username = request.args.get('username', '').strip().lower() or None
    profile = load_profile(username)

    progress_bars = get_progress_bars(profile)
    motivation_messages = get_motivational_messages(profile)
    daily_challenge = get_daily_challenge(profile)

    return jsonify({
        'success': True,
        'progress': progress_bars,
        'motivation': motivation_messages,
        'daily_challenge': daily_challenge,
        'streak': profile.get('streak', 0),
        'badges': profile.get('badges', [])
    })

@app.route('/api/gamification/badges', methods=['GET'])
def api_get_badges():
    username = request.args.get('username', '').strip().lower() or None
    profile = load_profile(username)

    all_badges = get_all_badges()
    user_badges = profile.get('badges', [])

    for badge_id in all_badges:
        all_badges[badge_id]['earned'] = badge_id in user_badges

    return jsonify({
        'success': True,
        'badges': all_badges,
        'user_badges': user_badges
    })

@app.route('/api/autonomous/analyze', methods=['GET'])
def api_analyze_performance():
    username = request.args.get('username', '').strip().lower() or None
    profile = load_profile(username)

    analysis = analyze_performance(profile)
    study_plan = generate_study_plan_profile(profile)
    motivation = get_motivation_message(profile)

    return jsonify({
        'success': True,
        'analysis': analysis,
        'study_plan': study_plan,
        'motivation': motivation
    })

@app.route('/api/autonomous/quiz', methods=['GET'])
def api_generate_adaptive_quiz():
    username = request.args.get('username', '').strip().lower() or None
    subject = request.args.get('subject', None)

    profile = load_profile(username)
    quiz_structure = generate_adaptive_quiz_autonomous(profile, subject)

    return jsonify({
        'success': True,
        'quiz': quiz_structure
    })

@app.route('/api/sharing/create', methods=['POST'])
def api_create_share():
    data = request.json or {}
    username = str(data.get('username') or '').strip().lower()
    share_type = data.get('type', '')
    content = data.get('content', {})

    if not username or not share_type or not content:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    profile = load_profile(username)

    try:
        if share_type == 'quiz':
            filepath = create_shareable_quiz(content, username)
            message = 'Quiz shared successfully'
        elif share_type == 'notes':
            filepath = create_shareable_notes(content, username)
            message = 'Notes shared successfully'
        elif share_type == 'progress':
            progress_stats = get_progress_stats(profile)
            filepath = create_shareable_progress(progress_stats, username)
            message = 'Progress shared successfully'
        else:
            return jsonify({'success': False, 'message': 'Invalid share type'}), 400

        return jsonify({
            'success': True,
            'message': message,
            'filepath': filepath
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to create share: {str(e)}'}), 500

@app.route('/api/sharing/list', methods=['GET'])
def api_list_shares():
    shares = list_available_shares()

    detailed_shares = {
        'quizzes': [],
        'notes': [],
        'progress': []
    }

    for category, filenames in shares.items():
        for filename in filenames:
            filepath = f"shared/{category}/{filename}"
            if os.path.exists(filepath):
                info = get_share_info(filepath)
                if 'error' not in info:
                    detailed_shares[category].append({
                        'filename': filename,
                        'filepath': filepath,
                        'info': info
                    })

    return jsonify({
        'success': True,
        'shares': detailed_shares
    })

@app.route('/api/sharing/import', methods=['POST'])
def api_sharing_import():
    data = request.json
    username = data.get('username', '').strip().lower()
    filepath = data.get('filepath', '')

    if not username or not filepath:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': 'Shared file not found'}), 404

    profile = load_profile(username)

    try:
        if 'quizzes' in filepath:
            result = import_shared_quiz(filepath, profile)
        elif 'notes' in filepath:
            result = import_shared_notes(filepath, profile)
        elif 'progress' in filepath:
            result = import_shared_progress(filepath, profile)
        else:
            return jsonify({'success': False, 'message': 'Unknown share type'}), 400

        if result['success']:
            save_profile(profile, username)
            new_badges = check_and_award_badges(profile)
            if new_badges:
                result['new_badges'] = new_badges

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'message': f'Import failed: {str(e)}'}), 500

@app.route('/api/voice/process', methods=['POST'])
def api_process_voice():
    if 'audio' not in request.files:
        return jsonify({'success': False, 'message': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    username = request.form.get('username', '').strip().lower() or None

    if not audio_file.filename:
        return jsonify({'success': False, 'message': 'No audio file selected'}), 400

    temp_path = f"temp_audio_{username or 'guest'}.wav"
    audio_file.save(temp_path)

    try:
        text = speech_to_text(temp_path)
        detected_lang = detect_language(text) if text else 'en'

        if username:
            profile = load_profile(username)
            record_voice_usage(profile)
            new_badges = check_and_award_badges(profile)
            save_profile(profile, username)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({
            'success': True,
            'text': text,
            'detected_language': detected_lang,
            'new_badges': new_badges if username and 'new_badges' in locals() else []
        })

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'success': False, 'message': f'Voice processing failed: {str(e)}'}), 500

@app.route('/api/activity/record', methods=['POST'])
def api_record_activity():
    data = request.json
    username = data.get('username', '').strip().lower()
    activity_type = data.get('type', '')

    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    profile = load_profile(username)

    update_progress_streak(profile)

    if activity_type == 'study':
        record_early_study(profile)

    new_badges = check_and_award_badges(profile)

    save_profile(profile, username)

    return jsonify({
        'success': True,
        'streak': profile.get('streak', 0),
        'new_badges': new_badges,
        'motivation': get_motivational_messages(profile)[:1]
    })

@app.route('/api/leaderboard', methods=['GET'])
def api_get_leaderboard():
    username = request.args.get('username', '').strip().lower() or None

    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    profile = load_profile(username)
    position = get_leaderboard_position(profile, [])

    return jsonify({
        'success': True,
        'position': position
    })

@app.route('/api/adaptive-quiz', methods=['GET'])
def api_adaptive_quiz():
    username = str(request.args.get('username') or '').strip().lower() or None
    profile = load_profile(username)

    if not qa_chain:
        return jsonify({'error': 'System not initialized'}), 500

    try:
        from app.modes import generate_adaptive_quiz
        quiz = generate_adaptive_quiz(profile, qa_chain)
        return jsonify({'success': True, 'quiz': quiz})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/view-file/<path:filename>')
def view_file(filename):
    from flask import send_from_directory
    return send_from_directory('data', filename)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN USER MANAGEMENT ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/admin/users', methods=['GET'])
def api_admin_get_users():
    username = str(request.args.get('username') or '').strip().lower()
    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400
    result = admin_get_all_users(username)
    return jsonify(result)


@app.route('/api/admin/users/create', methods=['POST'])
def api_admin_create_user():
    data = request.json or {}
    admin  = str(data.get('admin_username') or '').strip().lower()
    result = admin_create_user(
        admin_username = admin,
        username       = data.get('username', '').strip().lower(),
        password       = data.get('password', '').strip(),
        name           = data.get('name', '').strip(),
        grade          = data.get('grade', 'Form 1').strip(),
        role           = data.get('role', 'student').strip().lower()
    )
    return jsonify(result), (201 if result['success'] else 400)


@app.route('/api/admin/users/update', methods=['POST'])
def api_admin_update_user():
    data  = request.json or {}
    admin = str(data.get('admin_username') or '').strip().lower()
    target = str(data.get('target_username') or '').strip().lower()
    updates = {k: v for k, v in {
        'name':     data.get('name'),
        'grade':    data.get('grade'),
        'role':     data.get('role'),
        'password': data.get('password'),
    }.items() if v}
    result = admin_update_user(admin, target, updates)
    return jsonify(result), (200 if result['success'] else 400)


@app.route('/api/admin/users/delete', methods=['POST'])
def api_admin_delete_user():
    data   = request.json or {}
    admin  = str(data.get('admin_username') or '').strip().lower()
    target = str(data.get('target_username') or '').strip().lower()
    result = admin_delete_user(admin, target)
    return jsonify(result), (200 if result['success'] else 400)


@app.route('/api/admin/users/reset-password', methods=['POST'])
def api_admin_reset_password():
    data   = request.json or {}
    admin  = str(data.get('admin_username') or '').strip().lower()
    target = str(data.get('target_username') or '').strip().lower()
    new_pw = str(data.get('new_password') or '').strip()
    result = admin_reset_password(admin, target, new_pw)
    return jsonify(result), (200 if result['success'] else 400)
if __name__ == '__main__':
    print("=" * 60)
    print("SmartStudy - Complete Offline Learning System")
    print("=" * 60)
    print("Starting server...")
    print("Open: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=False, host='127.0.0.1', port=5000)