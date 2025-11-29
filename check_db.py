import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load your .env file
load_dotenv()

async def check_data():
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "forensight_db")
    
    if not uri:
        print("❌ Error: MONGO_URI not found in .env")
        return

    print(f"Connecting to {db_name}...")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]
    collection = db["cases"]

    # Count records
    count = await collection.count_documents({})
    print(f"✅ Total Case Records: {count}")

    if count > 0:
        # Get the most recent record
        latest = await collection.find_one(sort=[('_id', -1)])
        print("\n--- 📂 LATEST CASE ---")
        print(f"ID: {latest.get('case_id')}")
        print(f"Time: {latest.get('timestamp')}")
        print(f"Status: {latest.get('status')}")
        
        # Show a snippet of the result
        report = latest.get('analysis_json', {})
        verdict = report.get('verdict', 'N/A')
        print(f"Verdict: {verdict}")
        print("----------------------")
    else:
        print("No cases found yet. Go analyze a file!")

if __name__ == "__main__":
    asyncio.run(check_data())