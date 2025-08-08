Got it — here’s a **professional `README.md`** tailored to your current setup:

---

```markdown
# 🏗️ MEP engineer AI Tool -  RAG BOT – AI-Powered Building Code Assistant

An intelligent **AI chatbot system** built on **Retrieval-Augmented Generation (RAG)** architecture for **document-based Q&A**.  
Supports PDFs, images, and structured data with semantic understanding powered by **OpenAI embeddings**, **Sentence Transformers**, and **LLMs**.  
Backend services are containerized with **Docker**, running on separate ports for document ingestion and chatbot querying.

---

## ⚙️ Features

✅ **Document-Based Question Answering**  
- Supports PDFs, images, and structured/unstructured data  
- Provides clause/page-referenced answers from building standards  

✅ **RAG Pipeline Implementation**  
- Uses ChromaDB for vector similarity search  
- Embeddings generated via `BAAI/bge-large-en-v1.5`  

✅ **Two Microservices**  
- **PDF Processor** (`test.py` on port 8016) for ingestion & embedding  
- **Chatbot API** (`bot.py` on port 8017) for querying & context-based answers  

✅ **Vector Database Integration**  
- Persistent ChromaDB storage with Docker volumes  

✅ **Data Processing Automation**  
- Extracts text, tables, and figures using **PyMuPDF**, **pdfplumber**, and **Tesseract OCR**  
- Stores results as JSON + real-time vector updates  

✅ **Web Interface**  
- Simple chat UI to select collections and interact with the bot  
- Integrated PDF viewer for relevant standards  

---

## 📦 Architecture

```

+-----------------+       +-----------------+       +-----------------+
\| PDF Processor   | --->  |   ChromaDB       | <---  |   Chatbot API    |
\| (test.py,8016)  |       |  Vector Storage  |       | (bot.py,8017)    |
+-----------------+       +-----------------+       +-----------------+
↑                        ↑                           ↑
\|                        |                           |
PDF Upload               Embeddings                  User Queries
↓                        ↓                           ↓
Extraction → Chunking → Embedding → Storage → Retrieval → LLM Answer

````

---

## 🚀 Getting Started

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/your-repo/rag-bot.git
cd rag-bot
````

### 2️⃣ Create `.env` File

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 3️⃣ Docker Setup

This project uses **Docker Compose** with two services:

* `pdf-processor` → runs `test.py` on **8016**
* `chatbot-api` → runs `bot.py` on **8017**

#### Build & Start

```bash
docker-compose up --build
```

#### Stop

```bash
docker-compose down
```

---

## 📂 Project Structure

```
📦 rag-bot
├── bot.py                # Chatbot API service (FastAPI)
├── test.py               # PDF ingestion & embedding service
├── static/               # Frontend chat UI
├── Standards/            # Uploaded standard documents
├── output/               # Extracted JSON outputs
├── chroma_store/         # ChromaDB vector storage
├── docker-compose.yml    # Multi-service setup
├── Dockerfile.bot        # Chatbot API container
├── Dockerfile.test       # PDF Processor container
└── README.md             # Documentation
```

---

## 📡 API Endpoints

### **PDF Processor** – `http://localhost:8016`

| Method | Endpoint                    | Description                          |
| ------ | --------------------------- | ------------------------------------ |
| GET    | `/collections`              | List all ChromaDB collections        |
| POST   | `/upload_pdf`               | Upload and embed a PDF into ChromaDB |
| POST   | `/embed_pages`              | Embed only selected pages from a PDF |
| DELETE | `/delete_collection/{name}` | Delete a ChromaDB collection         |
| GET    | `/health`                   | Service health check                 |

### **Chatbot API** – `http://localhost:8017`

| Method | Endpoint                | Description                         |
| ------ | ----------------------- | ----------------------------------- |
| POST   | `/chat`                 | Query the bot with a question       |
| GET    | `/api/list-pdfs`        | List available standard PDFs        |
| GET    | `/api/list-collections` | List available ChromaDB collections |
| GET    | `/pdfs/{filename}`      | Serve a PDF file                    |
| GET    | `/health`               | Service health check                |

---

## 💬 Using the Chat UI

1. Open: **[http://localhost:8017/static/index.html](http://localhost:8017/static/index.html)** in your browser
2. Select one or more collections
3. Type your question (or keyword)
4. View the bot's answer with **clause/page references**
5. Open the PDF viewer to read the referenced section

---

## 🛠️ Development Tips

### Rebuilding Only One Service

```bash
docker-compose up --build pdf-processor
```

### Viewing Logs

```bash
docker-compose logs -f chatbot-api
```

### Health Check

```bash
curl http://localhost:8016/health
curl http://localhost:8017/health
```

---

## 📌 TODO / Roadmap

* [ ] Batch embeddings for faster processing
* [ ] PDF search highlight in viewer
* [ ] User authentication for API access
* [ ] Analytics dashboard for query statistics
* [ ] Support for Qdrant as an alternative vector DB

---

## 📜 License

MIT License – You are free to use, modify, and distribute this project.

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss your ideas.

---

```

---

If you want, I can also add **`Dockerfile.bot`** and **`Dockerfile.test`** sections to this README so that anyone cloning your repo can spin it up instantly without extra setup. That would make onboarding for others nearly effortless.
```
