# Causal Insight

This is a causal query and graph inference engine that I built to parse customer transcripts, extract semantic concepts, and traverse graph dependencies to isolate root causes in service operations.

I contributed to this problem statement set by **Observe.AI** during the **Inter IIT Tech Meet 14.0**, where our team placed **12th out of 23 IITs**.

## Visual Demo

Here is a live walkthrough of both retrieval strategies (Metadata Filter and Graph Analysis) streaming causal queries in real time:

<video src="https://github.com/user-attachments/assets/5077e641-0e67-4364-94ca-f1aa1e80daa9" width="100%" autoplay loop muted playsinline controls></video>

## Tech Stack

- **Backend**: FastAPI, Uvicorn, Python 3.10
- **Vector Store**: Qdrant (Embedded Local Engine)
- **Graph Network**: NetworkX
- **Vector Embeddings**: Google Gemma 300M (`google/embeddinggemma-300m`)
- **LLM Reasoning**: Google Gemini 3.1 Flash-Lite (`google-genai` SDK)
- **Frontend**: HTML5, Vanilla JS, CSS3 (Outfit typography & ChatGPT dark theme)
- **Infrastructure**: Docker, Docker Compose

## How It Works

The engine provides two separate, selectable retrieval strategies to query and analyze the dataset:

- **Metadata Filter Strategy**: Performs vector similarity search over an embedded Qdrant database (30,000+ points) based on query metadata filters.
- **Graph Analysis Strategy**: Traverses an 8,300+ node NetworkX directed knowledge graph (representing customer interactions, actions, and intents) to trace multi-hop causal relationships.
- **Reasoning**: Integrates Gemini 3.1 Flash-Lite to analyze the retrieved context and synthesize the final answer.

## Data Processing Pipeline

To populate the engine, I built a two-stage metadata enrichment pipeline to process raw transcripts:

1. **Schema Grounding (Gemini 2.5 Pro)**: Extracted candidate topics/outcomes from a representative 40% sample of transcripts to discover a clean, duplicate-folded schema.
2. **Constrained Classification (Gemini 2.5 Flash)**: Classified the remaining transcripts in parallel, mapping them strictly to the discovered labels to eliminate duplicates (e.g., merging "Billing Issue" and "Bills").

## Key Optimizations I Added

The original RAG pipeline suffered from high response latency under concurrent queries. I optimized the hot path using systems-level caching:

- **Caching Dijkstra Graph Traversals**: Wrapped NetworkX shortest-path calculations in an LRU cache. Repeated concept queries bypass graph searches entirely, reducing complexity from $O(V \log V + E)$ to an instantaneous $O(1)$ lookup.
- **Embedding Inference Cache**: Caches local SentenceTransformer vector generations in memory. Subsequent matching queries skip neural network inference passes entirely.

## Performance & Evaluation

I evaluated both retrieval strategies using a test suite measuring Evidence Quality (ID Recall) and trust metrics scored by a Ragas LLM Judge:

| Metric                                 | Graph Strategy | Filter Strategy |
| :------------------------------------- | :------------: | :-------------: |
| **ID Recall** (Evidence Quality)       |     30.8%      |    **36.0%**    |
| **Faithfulness** (Faithful to context) |    **0.74**    |      0.58       |
| **Relevancy** (Query alignment)        |      0.71      |    **0.77**     |

- **Graph Strategy** acts as a strict guardrail—if a path between nodes doesn't exist, it refuses to answer (high faithfulness, zero hallucination).
- **Filter Strategy** is optimal for high-recall semantic discovery.

## Running the App

1. Create a `.env` file with your credentials:
   ```env
   GEMINI_KEY=your_key_here
   ```
2. Spin up the server:
   ```bash
   docker-compose up --build
   ```
3. Open `frontend/index.html` directly in your browser.
