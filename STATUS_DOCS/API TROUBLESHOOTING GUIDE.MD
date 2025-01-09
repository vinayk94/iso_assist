# API Key Troubleshooting Guide

## Environment Setup Issues
Sometimes the API key might not be correctly picked up due to environment variable conflicts. Here's how to diagnose and fix such issues:

### Symptoms
- Getting 402 "Payment Required" errors despite having a valid paid subscription
- API key being used is different from what's in your `.env` file
- Multiple API keys appearing in different places

### Diagnosis Steps
1. Check which key is actually being used:
```python
# Save as check_env.py
import os
from dotenv import load_dotenv, find_dotenv

print("Loading .env from:", find_dotenv())
print("\nCurrent .env content:")
with open(find_dotenv(), 'r') as f:
    content = f.read()
    if "JINA_API_KEY" in content:
        start = content.find("JINA_API_KEY") + len("JINA_API_KEY=")
        key = content[start:].strip()
        masked_key = f"{key[:7]}...{key[-6:]}"
        print(f"JINA_API_KEY={masked_key}")
```

2. Test the key directly:
```python
# Save as test_key.py
import os
import requests
from dotenv import load_dotenv

def force_env_key():
    """Force load API key from .env file"""
    if 'JINA_API_KEY' in os.environ:
        del os.environ['JINA_API_KEY']
    load_dotenv(override=True)
    return os.getenv("JINA_API_KEY")

def test_jina_key():
    api_key = force_env_key()
    masked_key = f"{api_key[:7]}...{api_key[-6:]}"
    print(f"\nUsing API key from .env: {masked_key}")
    
    url = 'https://api.jina.ai/v1/embeddings'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": "jina-embeddings-v3",
        "input": ["test message"]
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.text[:100]}...")

if __name__ == "__main__":
    test_jina_key()
```

### Fix Process
1. First, verify your current API key in Jina AI dashboard
2. Update your `.env` file with the new key:
   ```
   JINA_API_KEY=your_new_key_here
   ```
3. Run the test script:
   ```bash
   python test_key.py
   ```
4. If successful, proceed with embedding generation

### Common Issues
1. **Multiple Environment Sources**
   - OS environment variables may override `.env`
   - Python virtual environment might cache old values
   - Multiple `.env` files in different locations

2. **Solution Approaches**
   - Force load from `.env` using `load_dotenv(override=True)`
   - Clear existing environment variables
   - Use absolute paths for `.env` file

### When Changing API Keys
1. Update the key in `.env` file
2. Run test script to verify
3. If test fails:
   - Check environment variables
   - Clear Python session/terminal
   - Verify key in dashboard

## Integration with Main System
The main embedding generation script (`embedding_generator.py`) includes these fixes:

```python
def get_api_key():
    """Get API key with proper environment handling"""
    if 'JINA_API_KEY' in os.environ:
        del os.environ['JINA_API_KEY']
    load_dotenv(override=True)
    return os.getenv("JINA_API_KEY")
```

## Key Management Best Practices
1. Always use `.env` file for API keys
2. Test new keys before bulk processing
3. Keep test script handy for quick verification
4. Document key changes in project logs
5. Regularly verify key status in dashboard

## Troubleshooting Checklist
- [ ] Verify key in Jina AI dashboard
- [ ] Update `.env` file
- [ ] Run test script
- [ ] Clear environment if needed
- [ ] Verify successful test response
- [ ] Proceed with main processing