import os
import asyncio
import hashlib
import json
import logging
import uuid
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from typing import Dict, Any

# --- IMPORT DATABASE HELPERS ---
try:
    from database import upload_to_s3, create_case_record, get_next_case_id, get_case
except ImportError:
    upload_to_s3, create_case_record, get_next_case_id, get_case = None, None, None, None

# --- 1. LOAD ENV & LOGGING ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- 2. PATH CONFIG ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND_FOLDER = os.path.join(PROJECT_ROOT, 'Frontend')
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# API Keys
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Allowed Extensions
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'm4a',
    'mp4', 'mov', 'avi', 'mkv', 'txt', 'pdf', 'docx', 'json'
}

# --- 3. FLASK SETUP ---
app = Flask(__name__, 
            template_folder=FRONTEND_FOLDER, 
            static_folder=FRONTEND_FOLDER, 
            static_url_path='')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# --- 4. AGENT IMPORTS ---
AGENTS_LOADED = True
try:
    # Analysis Agents
    from agents.image_deepfake_agent import analyze_image_with_rd_and_gemini
    from agents.audio_agent import analyze_audio_file 
    from agents.doc_misinfo_agent import read_files_from_paths, run_gemini_analysis
    from agents.video_agent import run_video_forensics
    from agents.meta_agent import meta_process
    from agents.blockchain_agent import log_verification_hash
    from agents.fact_check_agent import fact_check_agent
    
    # Chat Agent (Replaces RAG)
    try:
        from agents.gemini_agent import run_gemini_chat
    except ImportError:
        logger.warning("⚠️ run_gemini_chat not found. Chat will be disabled.")
        run_gemini_chat = None

    # Partner Tech
    try:
        from agents.neysa_agent import analyze_document_privately
        from agents.horizon_agent import log_evidence_gasless
    except ImportError:
        analyze_document_privately, log_evidence_gasless = None, None

except ImportError as e:
    logger.critical(f"Failed to import agents: {e}")
    AGENTS_LOADED = False

# --- HELPERS ---
class AnalysisResponse:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
    def model_dump(self): return self.__dict__

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_report_hash(data: dict) -> str:
    data_str = json.dumps(data, sort_keys=True, indent=None)
    return hashlib.sha256(data_str.encode()).hexdigest()

# --- PIPELINE FUNCTIONS ---

async def run_forensight_pipeline_image(file_path: str, case_id: str = "temp"):
    logger.info(f"Running Image Pipeline: {file_path}")
    
    # 1. Run Analysis
    if asyncio.iscoroutinefunction(analyze_image_with_rd_and_gemini):
        results = await analyze_image_with_rd_and_gemini(file_path)
    else:
        results = await asyncio.to_thread(analyze_image_with_rd_and_gemini, file_path)
    
    final_report = {
        "verdict": results.get("verdict", "Unknown"),
        "authenticity_score": results.get("authenticity_score", 0.0),
        "details": {"file_type": "Image", "full_analysis": results}
    }
    return await _finalize_report(final_report)

async def run_forensight_pipeline_audio(file_path: str, case_id: str = "temp"):
    logger.info(f"Running Audio Pipeline: {file_path}")
    if not ASSEMBLYAI_API_KEY: raise ValueError("ASSEMBLYAI_API_KEY missing")
    
    # 1. Transcribe
    audio_results = await asyncio.to_thread(analyze_audio_file, file_path, api_key=ASSEMBLYAI_API_KEY)
    transcript = audio_results.get("transcript", {}).get("text", "")

    final_report = {
        "verdict": "Audio Processed", 
        "authenticity_score": 0.0, 
        "details": {
            "file_type": "Audio",
            "transcript_id": audio_results.get("transcript_id"),
            "full_transcript": transcript
        }
    }
    return await _finalize_report(final_report)

async def run_forensight_pipeline_video(file_path: str, case_id: str = "temp"):
    logger.info(f"Running Video Pipeline: {file_path}")
    
    # 1. Analyze
    video_results = await asyncio.to_thread(run_video_forensics, file_path)
    
    final_report = {
        "verdict": video_results.get("verdict", "Unknown"),
        "authenticity_score": video_results.get("authenticity_score", 0.0),
        "details": {"file_type": "Video", "analysis": video_results.get("visual_analysis", {})}
    }
    return await _finalize_report(final_report)

async def run_forensight_pipeline_document(file_path: str, case_id: str = "temp"):
    logger.info(f"Running Document Pipeline: {file_path} (Case: {case_id})")
    
    text_content = read_files_from_paths([file_path])
    
    # 1. Neysa Private Audit
    neysa_result = None
    if analyze_document_privately:
        neysa_result = await asyncio.to_thread(analyze_document_privately, text_content[:3000])

    # 2. Gemini Analysis
    gemini_data = await asyncio.to_thread(run_gemini_analysis, text_content)
    danger = gemini_data.get("misinformationAnalysis", {}).get("dangerScore", 0)
    
    # 3. OpenAI Fact Check
    fact_check_result = "Skipped"
    if text_content.strip():
        claim_to_check = text_content[:500] 
        if gemini_data.get("finalReport", {}).get("findings"):
             claim_to_check = gemini_data["finalReport"]["findings"][:1000]
        fact_check_result = await asyncio.to_thread(fact_check_agent, claim_to_check)
    
    agent_summaries = {
        "fact_check_agent": {"provider": "OpenAI + DuckDuckGo", "result": fact_check_result},
        "private_audit_agent": {"provider": "Neysa/Pipeshift", "result": neysa_result if neysa_result else "Not configured"},
        "gemini_analyst": {"provider": "Google Gemini 2.5", "danger_score": danger, "flags": gemini_data.get("misinformationAnalysis", {}).get("flags", [])}
    }
    
    gemini_data["summary"] = f"🤖 **VERIFICATION**:\n{fact_check_result}\n\n" + gemini_data.get("summary", "")
    if neysa_result and "error" not in neysa_result:
        gemini_data["summary"] = f"🔒 **PRIVATE AUDIT**:\n{neysa_result}\n\n" + gemini_data["summary"]

    gemini_data["agent_breakdown"] = agent_summaries
    
    final_report = {
        "verdict": f"Danger Score: {danger}/100",
        "authenticity_score": (100 - danger) / 100.0,
        "details": {"file_type": "Document", "analysis": gemini_data}
    }
    return await _finalize_report(final_report)

async def _finalize_report(report_data):
    report_hash = f"0x{create_report_hash(report_data)}"
    
    tx_data = None
    if log_evidence_gasless:
        tx_data = log_evidence_gasless(report_hash)
    
    if not tx_data or not tx_data.get("success"):
        if log_verification_hash:
            try: tx_data = log_verification_hash(report_hash)
            except Exception: pass
            
    report_data["blockchain_tx"] = tx_data
    return AnalysisResponse(**report_data).model_dump()

# --- ROUTES ---

@app.route('/', methods=['GET'])
def index():
    return render_template('dashboard.html')

@app.route('/verify', methods=['POST'])
async def verify_file():
    if not AGENTS_LOADED: return jsonify({"error": "Agents failed to load"}), 500
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    if not allowed_file(file.filename): return jsonify({"error": "Invalid file"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    case_id = "CASE_TEMP"
    if get_next_case_id:
        case_id = get_next_case_id() 
    
    try:
        ext = filename.rsplit('.', 1)[1].lower()
        if ext in {'png', 'jpg', 'jpeg', 'gif'}: 
            report = await run_forensight_pipeline_image(file_path, case_id)
        elif ext in {'mp3', 'wav', 'm4a'}: 
            report = await run_forensight_pipeline_audio(file_path, case_id)
        elif ext in {'mp4', 'mov', 'avi', 'mkv'}: 
            report = await run_forensight_pipeline_video(file_path, case_id)
        elif ext in {'txt', 'pdf', 'docx', 'json'}: 
            report = await run_forensight_pipeline_document(file_path, case_id)
        else: return jsonify({"error": "Unsupported type"}), 400
        
        if upload_to_s3 and create_case_record:
            s3_url = upload_to_s3(file_path, filename, folder=case_id)
            file_meta = {"filename": filename, "s3_url": s3_url, "local_path": file_path}
            
            create_case_record(case_id, file_meta, report)
            
            report["case_id"] = case_id
            report["s3_url"] = s3_url
        
        report["case_id"] = case_id
        return jsonify({"status": "success", "report": report})

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/verify_with_instructions', methods=['POST'])
async def meta_verify():
    if 'files' not in request.files: return jsonify({"error": "No files"}), 400
    files = request.files.getlist('files')
    
    session_id = "CASE_TEMP"
    if get_next_case_id:
        session_id = get_next_case_id()
    
    session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    saved_paths = []
    file_metadata_list = []

    for f in files:
        filename = secure_filename(f.filename)
        path = os.path.join(session_dir, filename)
        f.save(path)
        saved_paths.append(path)
        s3_link = None
        if upload_to_s3:
            s3_link = upload_to_s3(path, filename, folder=session_id)
        file_metadata_list.append({"filename": filename, "s3_url": s3_link})

    try:
        report = await meta_process(session_id, saved_paths, request.form.get('instructions', ""), {"assemblyai": ASSEMBLYAI_API_KEY})
        
        if create_case_record:
            create_case_record(session_id, file_metadata_list, report)

        return jsonify({"status": "success", "meta_report": report})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chat', methods=['POST'])
async def chat_with_case():
    data = request.json
    query = data.get("query")
    case_id = data.get("case_id")
    
    if not query:
        return jsonify({"error": "Query required"}), 400
    
    # 1. Get Context from DB using the new database function
    context_text = ""
    if get_case and case_id:
        # Use asyncio.to_thread because database.get_case is synchronous (PyMongo)
        case_data = await asyncio.to_thread(get_case, case_id)
        if case_data:
            summary = case_data.get('output', {}).get('final_summary') or case_data.get('output', {}).get('verdict') or "No summary."
            results = case_data.get('output', {})
            context_text = f"CASE SUMMARY: {summary}\n\nDETAILS: {str(results)[:15000]}"

    # 2. Run Gemini Agent
    if run_gemini_chat:
        # Use asyncio.to_thread to keep the server responsive
        response = await asyncio.to_thread(run_gemini_chat, query, context_text)
        return jsonify({"response": response})
    else:
        return jsonify({"error": "Chat Agent not loaded"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000, use_reloader=False)