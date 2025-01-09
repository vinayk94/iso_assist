# src/api/main.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import RAGResponse, QueryRequest, QueryMetadata, Citation, Source, SourceMetadata

import logging
from typing import Optional

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from src.assistant.rag_assistant import ERCOTRAGAssistant

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
    "https://iso-assist.onrender.com/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG Assistant as a global variable
rag_assistant = None

@app.on_event("startup")
async def startup_event():
    """Initialize RAG Assistant on startup"""
    global rag_assistant
    try:
        rag_assistant = ERCOTRAGAssistant()
        logger.info("RAG Assistant initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG Assistant: {e}")
        raise

@app.get("/")
async def root():
    """Root endpoint to confirm the API is running."""
    return {"message": "Welcome to the RAG API!"}



@app.get("/api/health")
async def health_check():
    """Check API and database health"""
    if not rag_assistant:
        raise HTTPException(
            status_code=503,
            detail="RAG Assistant not initialized"
        )
        
    try:
        # Check database connection
        await rag_assistant.check_health()
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
    
@app.post("/api/query", response_model=RAGResponse)
async def process_query(request: QueryRequest):
    """Process a query and return formatted response with sources"""
    if not rag_assistant:
        raise HTTPException(
            status_code=503,
            detail="RAG Assistant not initialized"
        )

    try:
        logger.info(f"Processing query: {request.query}")
        
        # Get RAG response
        result = await rag_assistant.process_query(request.query)
        
        if 'error' in result:
            raise HTTPException(
                status_code=422,
                detail=result['error']
            )
        
        # Limit sources if specified
        if request.max_sources:
            result['sources'] = result['sources'][:request.max_sources]
        
        # Format response according to our models
        response = RAGResponse(
            answer=result['answer'],
            citations=result['citations'],
            sources=result['sources'],
            metadata=result['metadata']
        )
        
        return response

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    

if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))