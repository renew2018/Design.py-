import os
import requests
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from difflib import SequenceMatcher

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Constants
CHROMA_DIR = "chroma_store"
EMBED_MODEL = "BAAI/bge-large-en-v1.5"
LLM_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_TOKENS = 700
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Load Models and DB
embedder = SentenceTransformer(EMBED_MODEL)
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))

# Initialize FastAPI
app = FastAPI(title="NBC RAG Assistant")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
async def login(req: LoginRequest):
    valid_username = os.getenv("LOGIN_USERNAME")
    valid_password = os.getenv("LOGIN_PASSWORD")

    if req.username == valid_username and req.password == valid_password:
        return {"success": True}
    else:
        return {"success": False}

# Serve static frontend files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

# === Chat API ===
class ChatRequest(BaseModel):
    collection_id: List[str]
    query: str
    top_k: int = 10

@app.post("/chat")
def chat_with_nbc(req: ChatRequest):
    all_selected = []

    for coll_id in req.collection_id:
        try:
            collection = chroma_client.get_collection(name=coll_id)
        except Exception:
            continue  # Skip if collection not found

        query_embedding = embedder.encode(req.query).tolist()
        try:
            results = collection.query(query_embeddings=[query_embedding], n_results=req.top_k)
        except Exception:
            continue  # Skip if query fails

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        def is_partial_match(query, text):
            return any(q in text.lower() for q in query.lower().split())

        def fuzzy_match(query, text, threshold=0.6):
            return SequenceMatcher(None, query.lower(), text.lower()).ratio() > threshold

        matched = []
        for doc, meta in zip(documents, metadatas):
            if is_partial_match(req.query, doc) or fuzzy_match(req.query, doc):
                matched.append((doc, meta))

        selected = matched if matched else list(zip(documents, metadatas))
        all_selected.extend(selected)

    if not all_selected:
        return {"answer": "No relevant context found in any selected collections."}

    # Build context string
    context_str = ""
    for i, (chunk, meta) in enumerate(all_selected):
        clause = meta.get("clause", "N/A")
        page = meta.get("page", "Unknown")
        context_str += f"[{i+1}] Page {page} | Clause {clause}:\n{chunk.strip()}\n\n"

    # Prompt for LLM
    prompt = f"""You are a senior building code consultant specializing in Indian and international building standards.

Your job is to answer user questions using only the provided context. You must ensure clarity, accuracy, and reference every answer to relevant clauses, pages, tables, and notes.
When the user input is a statement or unclear, use basic common sense to rephrase it into a proper, grammatically correct question.

Handle the user input by applying these Strict Rules for Every Response:

1. If the user query is incomplete, fragmented, or written like a keyword phrase (e.g., “30 mtrs height mercantile building pressurization of staircase is required”), reframe it into a full, grammatically correct question before answering.
2. Always display the reframed question at the top under "Reframed Question:".
3. Use ONLY the provided context. Do not assume or fabricate details outside context.
4. If context lacks a direct answer, but Table/Clause references can be inferred, guide the user to the correct Table/Clause explicitly.
5. Answer clearly and concisely in professional tone. Use bullet points or steps if necessary.
6. Always include:
   - Clause Number
   - Page Number
7. If a figure or table is referenced, mention:
   - Table/Figure number
   - Its title or summary.
8. If a Note is mentioned in context or Table, explain it under “Note Explanation”. If not, skip the Note Explanation section.
9. Do not include irrelevant details, unnecessary repetition, or friendly phrases. Keep answers factual and precise.
10. For partial keyword matches (e.g., “gym”, “hydrant”), expand it into the full matching entry.
11. If the answer is not available in the provided context, respond with:
    "The provided context does not contain information relevant to this question."

== Universal Table & Clause Retrieval Rules ==
12. If the user query mentions phrases like "Table X", "Clause Y", "Size of Mains", "Sprinkler Installation", "Pressurization of Staircase", or similar:
    - Reframe the query to explicitly mention the corresponding Table/Clause.
    - Search context for any chunk that refers to that Table/Clause.
    - If such context is not found, state that "Table X / Clause Y is relevant to this query, but the provided context does not include its details."
16. When the user query involves "Size of Mains" (directly or indirectly), always assume that Table 8 of NBC is relevant.
    - Do NOT differentiate answers based on whether "Automatic Sprinkler Installation" is explicitly mentioned or not.
    - Always include the sizing details from Table 8, referring to the building type (e.g., Educational Buildings) and applicable heights.
    - Mention that Table 8 specifies mains sizes based on building type and height, regardless of sprinkler installation being mentioned.
    - Reference Clause 5.1.1(a) and Page 312 whenever answering Size of Mains related queries.
== Answer Formatting Must Always Follow This Structure ==
Clause: [Clause Number]
Page: [Page Number]
Answer:
[Clear and precise answer based on context]
Note Explanation:
[Explain notes if mentioned; skip this section if none]
Reference:
Clause title - Page Number
Table/Figure - Title (if applicable)

== Important Style Rules ==
- Do NOT use: (), [], asterisks, markdown formatting.
- Use only plain text.
- Do NOT add friendly greetings, small talk, or personal opinions.
- Be factual, precise, and direct.
Context:
{context_str}

Question: {req.query}
"""

    # Call Groq API
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": MAX_TOKENS
        }

        response = requests.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raise HTTPError if status != 200

        response_json = response.json()
        return {"answer": response_json["choices"][0]["message"]["content"].strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM failed: {e}")

# === PDF Library APIs ===
PDF_DIR = "Standards"

@app.get("/api/list-pdfs")
async def list_pdfs():
    pdfs = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    return {"pdfs": pdfs}

@app.get("/api/list-collections")
async def list_collections():
    try:
        collections = chroma_client.list_collections()
        collection_names = [coll.name for coll in collections]
        return {"collections": collection_names}
    except Exception as e:
        return {"error": str(e)}

@app.get("/pdfs/{filename}")
async def serve_pdf(filename: str):
    file_path = os.path.join(PDF_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/pdf")
    return {"error": "File not found"}
