import os
from dotenv import load_dotenv, find_dotenv
import sys

def check_environment():
    print("=== Environment Check ===\n")
    
    # 1. Check .env file
    env_path = find_dotenv()
    print(f"1. Primary .env file:")
    print(f"   Location: {env_path}")
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            content = f.read()
            if "JINA_API_KEY" in content:
                start = content.find("JINA_API_KEY") + len("JINA_API_KEY=")
                key = content[start:].strip()
                masked_key = f"{key[:7]}...{key[-6:]}"
                print(f"   Contains key: {masked_key}")
    
    # 2. Check environment variables
    print("\n2. Environment Variables:")
    env_key = os.getenv("JINA_API_KEY")
    if env_key:
        masked_env_key = f"{env_key[:7]}...{env_key[-6:]}"
        print(f"   OS environment has key: {masked_env_key}")
    else:
        print("   No JINA_API_KEY in OS environment")
    
    # 3. Test load_dotenv behavior
    print("\n3. Testing load_dotenv:")
    load_dotenv(override=True)
    new_key = os.getenv("JINA_API_KEY")
    if new_key:
        masked_new_key = f"{new_key[:7]}...{new_key[-6:]}"
        print(f"   After load_dotenv: {masked_new_key}")
    
    # 4. Check Python path
    print("\n4. Python Path:")
    for path in sys.path:
        if '.env' in os.listdir(path) if os.path.exists(path) else []:
            env_path = os.path.join(path, '.env')
            print(f"   Found .env in: {env_path}")
            with open(env_path, 'r') as f:
                content = f.read()
                if "JINA_API_KEY" in content:
                    start = content.find("JINA_API_KEY") + len("JINA_API_KEY=")
                    key = content[start:].strip()
                    masked_key = f"{key[:7]}...{key[-6:]}"
                    print(f"   Contains key: {masked_key}")

import os
import requests
from dotenv import load_dotenv
import time

def force_env_key():
    """Force load API key from .env file"""
    # Clear any existing env variable
    if 'JINA_API_KEY' in os.environ:
        del os.environ['JINA_API_KEY']
    
    # Load from .env file
    load_dotenv(override=True)
    return os.getenv("JINA_API_KEY")

def test_jina_key():
    api_key = force_env_key()
    
    if not api_key:
        print("Error: No API key found in .env file")
        return
        
    # Print masked key for verification
    masked_key = f"{api_key[:7]}...{api_key[-6:]}"
    print(f"\nUsing API key from .env: {masked_key}")
    
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
        print(f"Response Body: {response.text}")
        print("\nRequest Details:")
        print(f"Authorization Header Used: Bearer {masked_key}")
        
    except Exception as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    test_jina_key()
