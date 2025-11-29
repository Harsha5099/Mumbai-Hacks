
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

RD_API_KEY = os.getenv("RD_API_KEY")
PRESIGNED_ENDPOINT = "https://api.prd.realitydefender.xyz/api/files/aws-presigned"

def debug_rd_request():
    print(f"RD_API_KEY present: {bool(RD_API_KEY)}")
    if not RD_API_KEY:
        print("Error: RD_API_KEY is missing")
        return

    file_name = "flame.jpg"
    headers = {"X-API-KEY": RD_API_KEY, "Content-Type": "application/json"}
    payload = {"fileName": file_name}

    print(f"Sending request to {PRESIGNED_ENDPOINT}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload}")

    try:
        resp = requests.post(PRESIGNED_ENDPOINT, headers=headers, json=payload, timeout=30)
        print(f"Status Code: {resp.status_code}")
        print(f"Response Text: {resp.text}")
        resp.raise_for_status()
        print("Success!")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_rd_request()
