# database.py
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Try to import DB libraries
try:
    import boto3
    from pymongo import MongoClient
    DB_LIBS_AVAILABLE = True
except ImportError:
    DB_LIBS_AVAILABLE = False

load_dotenv()

# Logger configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "forensight_db")

# --- INITIALIZATION ---
s3_client = None
cases_collection = None

if DB_LIBS_AVAILABLE:
    # 1. Setup S3
    if AWS_ACCESS_KEY and S3_BUCKET_NAME:
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION
            )
            logger.info("✅ S3 Client Initialized")
        except Exception as e:
            logger.warning(f"Failed to init S3: {e}")

    # 2. Setup MongoDB (Synchronous)
    if MONGO_URI:
        try:
            mongo_client = MongoClient(MONGO_URI)
            db = mongo_client[MONGO_DB_NAME]
            cases_collection = db["cases"]
            logger.info("✅ MongoDB Connected")
        except Exception as e:
            logger.warning(f"Failed to init MongoDB: {e}")
else:
    logger.warning("⚠️ Database dependencies missing (pip install pymongo boto3).")


# --- FUNCTIONS ---

def upload_to_s3(file_path, filename, folder="evidence"):
    if s3_client is None or not S3_BUCKET_NAME:
        return None
    try:
        object_name = f"{folder}/{filename}"
        s3_client.upload_file(file_path, S3_BUCKET_NAME, object_name)
        url = s3_client.generate_presigned_url(
            'get_object', Params={'Bucket': S3_BUCKET_NAME, 'Key': object_name}, ExpiresIn=604800
        )
        return url
    except Exception as e:
        logger.error(f"S3 Upload Error: {e}")
        return None

def get_next_case_id():
    """Generates a sequential Case ID (CASE_0, CASE_1...)"""
    if cases_collection is None:
        import uuid
        return f"CASE_OFFLINE_{str(uuid.uuid4())[:4]}"

    try:
        count = cases_collection.count_documents({})
        return f"CASE_{count}"
    except Exception as e:
        logger.error(f"ID Generation Error: {e}")
        return "CASE_ERROR"

def create_case_record(case_id, file_metadata, analysis_report):
    """Saves the full report to MongoDB."""
    if cases_collection is None:
        return 
    try:
        record = {
            "case_id": case_id,
            "timestamp": datetime.now(timezone.utc),
            "status": "completed",
            "files": file_metadata,   
            "output": analysis_report
        }
        cases_collection.insert_one(record)
        logger.info(f"✅ Case {case_id} saved to DB.")
    except Exception as e:
        logger.error(f"DB Write Error: {e}")

def get_case(case_id):
    """Fetches a specific case from MongoDB (Used by Chat Agent)."""
    if cases_collection is None:
        return None
    try:
        return cases_collection.find_one({"case_id": case_id}, {"_id": 0})
    except Exception as e:
        logger.error(f"DB Read Error: {e}")
        return None