# Causal Insight

This is a causal query and graph inference engine that I built to parse customer transcripts, extract semantic concepts, and traverse graph dependencies to isolate root causes in service operations. 

I contributed to this project under a case study challenge set by **Observe.AI** during the **Inter IIT Tech Meet 14.0**, where our team placed **12th out of 23 IITs**.

## Tech Stack

* **Backend**: FastAPI, Uvicorn, Python 3.10
* **Vector Store**: Qdrant (Embedded Local Engine)
* **Graph Network**: NetworkX
* **Vector Embeddings**: Google Gemma 300M (`google/embeddinggemma-300m`)
* **LLM Reasoning**: Google Gemini 3.1 Flash (`google-genai` SDK)
* **Frontend**: HTML5, Vanilla JS, CSS3 (Outfit typography & dark glassmorphic design)
* **Infrastructure**: Docker, Docker Compose

## How it works

The backend uses a dual-retrieval pipeline combining vector search with directed graph traversal:
* **Vector Layer**: Uses an embedded Qdrant database (30,000+ points) running locally inside the application process to fetch semantic nodes.
* **Knowledge Graph**: Traverses an 8,300+ node NetworkX directed graph (representing customer interactions, actions, and intents) to trace root-cause paths.
* **Reasoning**: Integrates Gemini 2.0 Flash to plan the query filters and synthesize the final answer.

## Key Optimizations I Added

The original RAG pipeline suffered from high response latency under concurrent queries. I optimized the hot path using systems-level caching and database configurations:

* **Caching Dijkstra Graph Traversals**: Wrapped NetworkX shortest-path calculations in an LRU cache. Repeated concept queries bypass graph searches entirely, reducing complexity from $O(V \log V + E)$ to an instantaneous $O(1)$ lookup.
* **Embedding Inference Cache**: Caches local SentenceTransformer vector generations in memory. Subsequent matching query queries skip neural network inference passes entirely.
* **Semantic Query Planner**: Uses a lightweight LLM pass to normalize conversational phrasings into canonical search strings, ensuring high cache hit ratios for different phrasings of the same question.
* **Direct Database Mounting**: Configured local database directories directly in Docker Compose to bypass virtual storage volume overhead and optimize read/write file I/O.

## Running the App

1. Create a `.env` file with your credentials:
   ```env
   GOOGLE_API_KEY=your_key_here
   HF_TOKEN=your_token_here
   ```
2. Spin up the server:
   ```bash
   docker-compose up --build
   ```
3. Open `frontend/index.html` directly in your browser.
