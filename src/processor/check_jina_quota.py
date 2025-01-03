import os
import requests
import logging
from dotenv import load_dotenv
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_jina_quota(api_key):
    """Check Jina AI API quota and status"""
    # First, try to get quota information
    quota_url = 'https://api.jina.ai/v1/quota'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }

    try:
        # Try a quota check first
        quota_response = requests.get(quota_url, headers=headers)
        print("\nQuota Check Response:")
        print(f"Status Code: {quota_response.status_code}")
        print("Response Headers:", json.dumps(dict(quota_response.headers), indent=2))
        print("Response Body:", json.dumps(quota_response.json() if quota_response.content else {}, indent=2))

        # Try a small embedding request
        embed_url = 'https://api.jina.ai/v1/embeddings'
        test_data = {
            "model": "jina-embeddings-v3",
            "task": "text-matching",
            "dimensions": 1024,
            "embedding_type": "float",
            "input": ["test"]
        }
        
        embed_response = requests.post(embed_url, headers=headers, json=test_data)
        print("\nTest Embedding Response:")
        print(f"Status Code: {embed_response.status_code}")
        print("Response Headers:", json.dumps(dict(embed_response.headers), indent=2))
        print("Response Body:", json.dumps(embed_response.json() if embed_response.content else {}, indent=2))

        # Check for specific error messages
        if embed_response.status_code == 402:
            if 'x-ratelimit-remaining' in embed_response.headers:
                print(f"\nRate Limit Remaining: {embed_response.headers['x-ratelimit-remaining']}")
            if 'x-ratelimit-reset' in embed_response.headers:
                print(f"Rate Limit Reset: {embed_response.headers['x-ratelimit-reset']}")
            if 'x-credits-remaining' in embed_response.headers:
                print(f"Credits Remaining: {embed_response.headers['x-credits-remaining']}")

    except Exception as e:
        print(f"\nError checking quota: {e}")

import os
import requests
from dotenv import load_dotenv

def mask_api_key(key):
    """Show first 7 and last 6 characters of the key"""
    if len(key) <= 13:  # If key is too short, show less
        return "..." + key[-6:]
    return f"{key[:7]}...{key[-6:]}"

def test_jina_key():
    load_dotenv()
    api_key = os.getenv("JINA_API_KEY")
    
    if not api_key:
        print("Error: No API key found in .env file")
        return
        
    # Print masked key for verification
    print(f"\nUsing API key: {mask_api_key(api_key)}")
    
    url = 'https://api.jina.ai/v1/embeddings'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "model": "jina-embeddings-v3",
        "task": "text-matching",
        "dimensions": 1024,
        "embedding_type": "float",
        "input": ["test message"]
    }
    
    try:
        print("\nSending request to Jina AI API...")
        response = requests.post(url, headers=headers, json=data)
        
        print(f"\nAPI Response Details:")
        print(f"Status Code: {response.status_code}")
        print("Headers:", response.headers)
        print(f"Response Body: {response.text}")
        
        # Print Authorization header (masked)
        auth_header = headers['Authorization']
        print(f"\nAuthorization Header Used: Bearer {mask_api_key(auth_header.replace('Bearer ', ''))}")
        
    except Exception as e:
        print(f"Error making request: {e}")

def main():
    """
    load_dotenv()
    jina_api_key = os.getenv("JINA_API_KEY")
    
    if not jina_api_key:
        print("Error: JINA_API_KEY not found in environment variables")
        return
    
    print("\nChecking Jina AI API status...")
    #check_jina_quota(jina_api_key)
    test_jina_key()
    """
    import os
    from dotenv import load_dotenv, find_dotenv

    # Find the .env file location
    env_path = find_dotenv()
    print(f"Loading .env from: {env_path}")

    # Print current content (masking the key)
    with open(env_path, 'r') as f:
        content = f.read()
        if "JINA_API_KEY" in content:
            start = content.find("JINA_API_KEY") + len("JINA_API_KEY=")
            key = content[start:].strip()
            masked_key = f"{key[:7]}...{key[-6:]}"
            print(f"\nCurrent .env content:")
            print(f"JINA_API_KEY={masked_key}")

if __name__ == "__main__":
    #main()
    import os
    from pathlib import Path
    import sys

    print("Current working directory:", os.getcwd())
    print("Python path:", sys.path)
    print("\nChecking for .env files in and above current directory:")

    current = Path.cwd()
    while current.parent != current:
        env_file = current / '.env'
        if env_file.exists():
            print(f"Found .env at: {env_file}")
            with open(env_file, 'r') as f:
                content = f.read()
                if "JINA_API_KEY" in content:
                    start = content.find("JINA_API_KEY") + len("JINA_API_KEY=")
                    key = content[start:].strip()
                    masked_key = f"{key[:7]}...{key[-6:]}"
                    print(f"Contains key: {masked_key}")
        current = current.parent