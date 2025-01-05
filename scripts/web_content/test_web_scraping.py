import os
import psycopg2
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_scraping_test.log"),
        logging.StreamHandler()
    ]
)

class WebScrapingTester:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))

    def create_test_tables(self):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents_test (LIKE documents INCLUDING ALL);
                CREATE TABLE IF NOT EXISTS chunks_test (LIKE chunks INCLUDING ALL);
                CREATE TABLE IF NOT EXISTS embeddings_test (LIKE embeddings INCLUDING ALL);
            """)
            self.conn.commit()
            logging.info("Test tables created successfully")
        finally:
            cur.close()

    def enhanced_web_content(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove non-content elements
                for elem in soup.select('nav, header, footer, script, style, .nav, .header, .footer'):
                    elem.decompose()
                
                # Try different content selectors
                main_content = None
                
                # Try ERCOT specific content areas first
                for selector in ['.content-area', '#mainContent', 'main', 'article']:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                if main_content:
                    content = main_content.get_text(separator='\n', strip=True)
                else:
                    # Fallback to whole page but with better cleaning
                    content = []
                    for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
                        text = p.get_text().strip()
                        if len(text) > 20:  # Skip very short snippets
                            content.append(text)
                    content = '\n\n'.join(content)
                
                # Clean up the content
                lines = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and len(line) > 20:  # Skip short lines
                        lines.append(line)
                
                return '\n\n'.join(lines)
                
            return f"Error: Status code {response.status_code}"
            
        except Exception as e:
            logging.error(f"Error processing {url}: {e}")
            return f"Error: {str(e)}"

    def check_current_content(self):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT 
                    d.id as document_id,
                    c.id as chunk_id,
                    d.url,
                    c.content
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.content_type = 'web'
                LIMIT 5;
            """)
            
            print("\nCURRENT CONTENT IN DATABASE:")
            print("-" * 50)
            for row in cur.fetchall():
                print(f"""
Document ID: {row[0]}
Chunk ID: {row[1]}
URL: {row[2]}
Content Sample: {row[3][:200]}
-------------------""")
        finally:
            cur.close()

    def test_enhanced_scraping(self):
        cur = self.conn.cursor()
        try:
            # Get all web documents
            cur.execute("""
                SELECT id, url 
                FROM documents 
                WHERE content_type = 'web' 
                LIMIT 3
            """)
            documents = cur.fetchall()
            
            print("\nTESTING ENHANCED SCRAPING:")
            print("-" * 50)
            
            for doc_id, url in documents:
                # Get current content
                cur.execute("""
                    SELECT content 
                    FROM chunks 
                    WHERE document_id = %s
                """, (doc_id,))
                old_content = cur.fetchone()[0]
                
                # Get new content
                print(f"\nTesting URL: {url}")
                new_content = self.enhanced_web_content(url)
                
                print(f"\nOLD CONTENT LENGTH: {len(old_content)}")
                print(f"OLD CONTENT SAMPLE:\n{old_content[:200]}")
                
                print(f"\nNEW CONTENT LENGTH: {len(new_content)}")
                print(f"NEW CONTENT SAMPLE:\n{new_content[:200]}")
                print("\n" + "-" * 50)
                
        finally:
            cur.close()

def main():
    tester = WebScrapingTester()
    
    # 1. Show current content
    print("\nStep 1: Checking current content in database...")
    tester.check_current_content()
    
    # 2. Create test tables
    print("\nStep 2: Creating test tables...")
    tester.create_test_tables()
    
    # 3. Test enhanced scraping
    print("\nStep 3: Testing enhanced scraping...")
    tester.test_enhanced_scraping()

if __name__ == "__main__":
    main()