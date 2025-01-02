import os
from dataclasses import dataclass
from typing import List, Dict, Optional
import aiohttp
from bs4 import BeautifulSoup
import asyncio
import logging
import psycopg2
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class Document:
    title: str
    url: str
    file_type: str
    section: str

class ERCOTScraper:
    def __init__(self):
        self.base_url = "https://www.ercot.com"
        self.rq_url = f"{self.base_url}/services/rq"
        self.document_patterns = ['.docx', '.pdf', '.xls', '.xlsx', '.doc']
        self.postgres_uri = os.getenv("POSTGRESQL_URI")
        
        if not self.postgres_uri:
            raise ValueError("Database URI not found in environment variables")

    def update_url_status(self, url: str, status: str, error: str = None) -> None:
        """Update URL status during scraping"""
        conn = psycopg2.connect(self.postgres_uri)
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO urls (url, status, last_attempted, error_message)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (url) DO UPDATE 
                SET status = EXCLUDED.status,
                    last_attempted = NOW(),
                    error_message = EXCLUDED.error_message;
            """, (url, status, error))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Error updating URL status for {url}: {e}")
            raise
        finally:
            cur.close()
            conn.close()


    async def fetch_html(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch and return HTML content."""
        try:
            self.update_url_status(url, 'scraping')
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    self.update_url_status(url, 'scraped')
                    return html
                else:
                    error = f"Failed with status {response.status}"
                    self.update_url_status(url, 'failed', error)
                    logging.error(f"Failed to fetch {url}: {error}")
        except Exception as e:
            self.update_url_status(url, 'failed', str(e))
            logging.error(f"Error fetching {url}: {e}")
        return None

    async def download_document(self, url: str, session: aiohttp.ClientSession, section: str) -> Optional[str]:
        """Download a document and save it locally."""
        try:
            self.update_url_status(url, 'downloading')
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Save document locally
                    save_dir = os.path.join("data/documents", section)
                    os.makedirs(save_dir, exist_ok=True)
                    
                    file_name = url.split('/')[-1]
                    file_path = os.path.join(save_dir, file_name)
                    
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    self.update_url_status(url, 'downloaded')
                    return file_path
                else:
                    error = f"Failed with status {response.status}"
                    self.update_url_status(url, 'failed', error)
                    logging.error(f"Failed to download {url}: {error}")
        except Exception as e:
            self.update_url_status(url, 'failed', str(e))
            logging.error(f"Error downloading {url}: {e}")
        return None

    async def get_sections(self, session: aiohttp.ClientSession) -> List[Dict[str, str]]:
        """Get all sections under the RQ page."""
        html = await self.fetch_html(self.rq_url, session)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        sections = []
        
        for link in soup.find_all('a', href=lambda x: x and '/services/rq/' in x):
            section_name = link.text.strip()
            section_url = f"{self.base_url}{link['href']}" if not link['href'].startswith('http') else link['href']
            sections.append({'name': section_name, 'url': section_url})
            self.update_url_status(section_url, 'discovered')
            logging.info(f"Discovered section: {section_name} ({section_url})")

        # Store sections in documents table
        conn = psycopg2.connect(self.postgres_uri)
        cur = conn.cursor()
        try:
            for section in sections:
                cur.execute("""
                    INSERT INTO documents (url, title, content_type)
                    VALUES (%s, %s, 'web')
                    ON CONFLICT (url) DO NOTHING
                """, (section['url'], section['name']))
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return sections

    async def scrape_documents(self, section: Dict[str, str], session: aiohttp.ClientSession) -> List[Document]:
        """Scrape documents from a specific section."""
        html = await self.fetch_html(section['url'], session)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        documents = []

        for link in soup.find_all('a', href=lambda x: x and any(x.endswith(ext) for ext in self.document_patterns)):
            title = link.text.strip()
            url = f"{self.base_url}{link['href']}" if not link['href'].startswith('http') else link['href']
            file_type = url.split('.')[-1].lower()
            
            # Track URL discovery
            self.update_url_status(url, 'discovered')
            
            document = Document(
                title=title,
                url=url,
                file_type=file_type,
                section=section['name']
            )
            documents.append(document)
            logging.info(f"Found document: {title} ({file_type}) in {section['name']}")

        return documents

    async def start(self):
        """Main scraping process."""
        logging.info("Starting ERCOT document scraping...")
        
        async with aiohttp.ClientSession() as session:
            # Get all sections
            sections = await self.get_sections(session)
            all_documents = []
            
            # Get documents from each section
            for section in sections:
                documents = await self.scrape_documents(section, session)
                for doc in documents:
                    # Download document
                    file_path = await self.download_document(doc.url, session, doc.section)
                    if file_path:
                        # Store in database
                        conn = psycopg2.connect(self.postgres_uri)
                        cur = conn.cursor()
                        try:
                            cur.execute("""
                                INSERT INTO documents (url, title, content_type)
                                VALUES (%s, %s, 'document')
                                ON CONFLICT (url) DO NOTHING
                            """, (doc.url, doc.title))
                            conn.commit()
                        finally:
                            cur.close()
                            conn.close()
                
                all_documents.extend(documents)
            
        logging.info(f"Scraping complete. Found {len(all_documents)} documents across {len(sections)} sections.")