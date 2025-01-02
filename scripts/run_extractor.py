import sys
import os

# Add the src directory to sys.path dynamically
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # Project root
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)  # Ensure src is first in path

# Debug sys.path
print("Current sys.path:")
for path in sys.path:
    print(path)

# Debug module import
import importlib.util
print("src module spec:", importlib.util.find_spec("src"))

# Import ContentExtractor after adding src to sys.path
from processor.extractor import ContentExtractor
import asyncio
import logging
from dotenv import load_dotenv

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def main():
    load_dotenv()
    extractor = ContentExtractor()
    await extractor.process_all()

if __name__ == "__main__":
    asyncio.run(main())
