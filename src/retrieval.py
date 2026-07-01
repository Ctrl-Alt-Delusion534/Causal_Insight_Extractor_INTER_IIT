import json
import pickle
import os
import networkx as nx
import itertools
from typing import List, AsyncGenerator
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import huggingface_hub

from src.config import GRAPH_PATH, QDRANT_PATH, ENUMS_PATH, MODEL_ID
from functools import lru_cache

load_dotenv()

with open(ENUMS_PATH, "r") as f:
    ENUMS = json.load(f)

client = None
qdrant_client = None
G = None
G_undirected = None
model = None

def init_resources():
    """Call this ONCE from main.py lifespan"""
    global model, qdrant_client, G, G_undirected, client
    
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        huggingface_hub.login(token=hf_token)

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    model = SentenceTransformer(MODEL_ID, trust_remote_code=True)
    qdrant_client = QdrantClient(path=str(QDRANT_PATH))
    
    with open(GRAPH_PATH, "rb") as f:
        G = pickle.load(f)
    G_undirected = G.to_undirected()
    print("initiallized resources")


def reformulate_query(query: str, chat_history: list) -> str:
    """
    If history exists, rewrite the query to be self-contained.
    If no history, return original query.
    """
    if not chat_history:
        return query
    
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    
    prompt = f"""
    You are a Query Resolver.
    
    CHAT HISTORY:
    {history_text}
    
    LATEST USER QUERY: "{query}"
    
    TASK:
    Rewrite the Latest User Query to be a standalone search query.
    - Replace pronouns ("it", "that", "he") with the specific entities from history.
    - Keep the intent (e.g., "Show me an example" -> "Show me an example of [Previous Logic]").
    - Output ONLY the rewritten string.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        rewritten = response.text.strip()
        return rewritten
    except:
        return query


#adding the caching as the customers can repeatedly ask the same queries
@lru_cache(maxsize=1024)
def get_embedding(text: str):
    q_vec = model.encode(text, normalize_embeddings=True).tolist()
    return q_vec

@lru_cache(maxsize=2048)
def get_cached_shortest_path(start: str, end: str):
    try:
        if nx.has_path(G_undirected, start, end):
            return tuple(nx.shortest_path(G_undirected, start, end))
    except:
        pass
    return None
async def run_graph_strategy(user_query: str, chat_history: list) -> AsyncGenerator:
    yield {"event": "status", "data": "Init"}
    
    if client is None:
        raise ValueError("Gemini Client is None! Init failed?")
    if qdrant_client is None:
        raise ValueError("Qdrant Client is None! Init failed?")


    refined_query = reformulate_query(user_query, chat_history)
    
    # [FIX] Infer domain to restrict graph search
    plan = await infer_filters(user_query, chat_history)
    
    # [Revert] Don't strict filter Qdrant initial query because Concepts might lack domain
    q_vec = get_embedding(refined_query)
    hits = qdrant_client.query_points("convo_graph", query=q_vec, limit=50).points

    entry_calls = set()
    entry_concepts = []
    
    target_domain = None
    if plan.filters:
        for f in plan.filters:
            if f.field == 'domain' and f.value:
                raw_domain = f.value[0]
                valid_domains = ['Hotel', 'Telecom', 'Finance']
                target_domain = next((d for d in valid_domains if d.lower() == raw_domain.lower()), raw_domain)
                break
    

    for h in hits:
        if h.score < 0.5: continue
        
        nid = h.payload['node_id']
        ntype = h.payload['type']
        
        # [Filter] Only accept Calls from target domain
        if ntype == 'Call': 
            if target_domain:
                if nid in G and G.nodes[nid].get('domain') == target_domain:
                    entry_calls.add(nid)
            else:
                  entry_calls.add(nid)
                 
        elif ntype == 'Concept': 
            entry_concepts.append(nid)
        
    entry_concepts = list(dict.fromkeys(entry_concepts))
    
    if entry_concepts:
        yield {"event": "concepts", "data": entry_concepts}

    final_evidence_ids = set(entry_calls)
    
    yield {"event": "status", "data": "Traversing Causal Logic..."}

    if entry_concepts and G:
        if len(entry_concepts) == 1:
            concept = entry_concepts[0]
            if concept in G:
                neighbors = list(G_undirected.neighbors(concept))
                # [Filter] Check domain in graph
                calls = []
                for n in neighbors:
                    if G.nodes[n].get('type') == 'Call':
                        if target_domain:
                            if G.nodes[n].get('domain') == target_domain:
                                calls.append(n)
                        else:
                            calls.append(n)
                            
                final_evidence_ids.update(calls[:10])

        else:
            concept_call_map = {}
            for c in entry_concepts:
                if c not in G: continue
                neighbors = list(G_undirected.neighbors(c))
                
                valid = set()
                for n in neighbors:
                    if G.nodes[n].get('type') == 'Call':
                        if target_domain:
                            if G.nodes[n].get('domain') == target_domain:
                                valid.add(n)
                        else:
                            valid.add(n)
                            
                if valid: concept_call_map[c] = valid
            
            # Intersection
            if concept_call_map:
                intersection = set.intersection(*concept_call_map.values())
                if intersection:
                    final_evidence_ids.update(list(intersection))
                else:
                    # Pathfinding
                    path_nodes = set()
                    for start, end in itertools.combinations(entry_concepts, 2):
                        path = get_cached_shortest_path(start, end)
                        if path and len(path) <= 4: 
                            path_nodes.update(path)
                    
                    for node in path_nodes:
                        if G.nodes[node].get('type') == 'Call':
                            final_evidence_ids.add(node)
                        elif G.nodes[node].get('type') == 'Concept':
                            nbs = list(G_undirected.neighbors(node))
                            calls = [n for n in nbs if G.nodes[n].get('type') == 'Call']
                            if calls: final_evidence_ids.add(calls[0])

    sorted_ids = list(final_evidence_ids)
    
    # [FIX] Send full source details including transcript
    sources_payload = []
    evidence_texts = []
    
    for cid in sorted_ids:
        if cid in G:
            data = G.nodes[cid]
            text = data.get('full_text', '')
            summary = data.get('summary', '')
            domain = data.get('domain', 'Unknown')
            
            sources_payload.append({
                "id": cid,
                "summary": summary,
                "full_text": text,
                "domain": domain
            })
            
            if len(text) > 50:
                evidence_texts.append(f"CALL ID: {cid}\nSUMMARY: {summary}\nTRANSCRIPT:\n{text[:1000]}")
    
    yield {"event": "sources", "data": sources_payload}

    if not evidence_texts:
        yield {"event": "token", "data": "Graph logic found connections, but no transcripts were attached."}
        return

    context = "\n\n".join(evidence_texts)
    prompt = f"""
        You are a Senior Data Analyst.
        QUERY: "{user_query}"
        EVIDENCE: {context}
        INSTRUCTIONS:
        1. Answer the query using ONLY the evidence.
        2. Cite Call IDs.
        3. Explain the causal link.
        4. Deny if no evidence is provided.
    """
    
    yield {"event": "status", "data": "Streaming Answer..."}
    
    response = client.models.generate_content_stream(
        model="gemini-2.0-flash",
        contents=prompt
    )
    for chunk in response:
        yield {"event": "token", "data": chunk.text}
    return


class SearchFilter(BaseModel):
    field: str
    value: List[str]

class SearchPlan(BaseModel):
    search_text: str
    filters: List[SearchFilter]

async def infer_filters(user_query: str, chat_history: list) -> SearchPlan:
    """Helper to infer domain/filters using Gemini."""
    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history]) if chat_history else "None"
    prompt = f"""
      You are a Search Query Planner.
      USER QUERY: "{user_query}"
      CHAT HISTORY: {history_str}
      AVAILABLE FILTERS:
      - domain: {ENUMS.get('domains', [])}
      - outcome: {ENUMS.get('outcomes', [])}
      - topics: {ENUMS.get('topics', [])}

      INSTRUCTIONS:
      1. Analyze the User Query.
      2. PREDICT THE DOMAIN. This is critical.
      3. Return NULL for others if unsure.
    """
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", 
            response_schema=SearchPlan, temperature=0.0
        )
    )
    return resp.parsed

async def run_filter_strategy(user_query: str, chat_history: list) -> AsyncGenerator:
    yield {"event": "status", "data": "Init"}
    refined_query = reformulate_query(user_query, chat_history)
    plan = await infer_filters(user_query, chat_history)
    
    yield {"event": "concepts", "data": [f"{f.field}:{f.value[0]}" for f in plan.filters]}

    qdrant_filter = None
    if plan.filters:
        must_conditions = []
        should_conditions = []
        for f in plan.filters:
            key = "topics" if f.field == "topic" else f.field
            
            # Normalize values
            enum_key = key + 's' if not key.endswith('s') else key
            valid_values = ENUMS.get(enum_key, [])
            
            normalized_values = []
            for v in f.value:
                match = next((pv for pv in valid_values if pv.lower() == v.lower()), v)
                normalized_values.append(match)

            if key == 'domain': 
                must_conditions.append(FieldCondition(key=key, match=MatchAny(any=normalized_values)))
            else:
                should_conditions.append(FieldCondition(key=key, match=MatchAny(any=normalized_values)))
        
        qdrant_filter = Filter(
            must=must_conditions if must_conditions else None, 
            should=should_conditions if should_conditions else None
        )

    yield {"event": "status", "data": "Executing Filtered Search..."}
    q_vec = get_embedding(plan.search_text)
    
    hits = qdrant_client.query_points(
        collection_name= "convo_tech_meet",
        query=q_vec,
        query_filter=qdrant_filter,
        limit=40,
        with_payload=True
    ).points

    evidence_text = ""
    sources_payload = []
    
    for i, hit in enumerate(hits):
        if hit.score < 0.4: continue
        
        payload = hit.payload 
        if 'display_text' in payload:
            evidence_text += f"\n--- EVIDENCE (Call ID: {payload.get('call_id')}) ---\n{payload.get('display_text')}\n"
            
            sources_payload.append({
                "id": payload.get('call_id'),
                "summary": payload.get('outcome', 'Call Log'),
                "domain": payload.get('domain'),
                "full_text": payload.get('display_text') 
            })

    yield {"event": "sources", "data": sources_payload[:15]}

    if not evidence_text:
        yield {"event": "token", "data": "No relevant information found"}
        return

    yield {"event": "status", "data": "Synthesizing Answer..."}
    
    gen_prompt = f"""
        You are an expert Call Center Analyst.

        USER QUERY: {refined_query}

        EVIDENCE FROM DATABASE:
        {evidence_text}

        INSTRUCTIONS:
        1. Answer the query using ONLY the provided evidence.
        2. Synthesize the root cause.
        3. Cite specific Call IDs (e.g., INS-AKME-0002) to support every claim.
        4. If the evidence talks about a specific technical error (like 'checksum'), mention it.
    """
    
    response = client.models.generate_content_stream(model="gemini-2.0-flash", contents=gen_prompt)
    for chunk in response:
        yield {"event": "token", "data": chunk.text}