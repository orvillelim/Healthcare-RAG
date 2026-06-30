"""
RAG Starter: Interactive query loop over ChromaDB
==================================================
Prerequisites:
  1. Run ingestion first: python ingest.py if there's no data in the database
  2. Then run this: python starter.py
"""

import os
import re

import ollama
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types
from config import CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL, LLM_MODEL, PROVIDERS_NAMES
from console_formatter import (
    print_rewritten_query,
    print_context,
    print_question,
    print_answer,
)


REQUEST_TIMEOUT = 30
REQUEST_DELAY = 2.5  # seconds between requests
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # multiplier for exponential backoff
CHUNK_SIZE = 8192

SIMILARITY_THRESHOLD = 0.30  # absolute floor — drop anything below this
SCORE_DROP_RATIO = 0.70  # drop chunks scoring below 70% of the best result
MAX_CONTEXT_CHUNKS = 5  # never send more than this to the LLM
VECTOR_CANDIDATE_COUNT = 25
KEYWORD_CANDIDATE_COUNT = 5
KEYWORD_BOOST = 0.65

QUERY_STOPWORDS = {
    "about",
    "benefit",
    "benefits",
    "cover",
    "covered",
    "covers",
    "coverage",
    "does",
    "hmo",
    "include",
    "included",
    "includes",
    "insurance",
    "the",
    "what",
    "when",
    "where",
    "which",
    "with",
}

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set. Add it to your .env file.")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "You are an HMO knowledge base assistant. "
    "Answer the user's question based only on the provided context. "
    "If the answer is not in the context, say so."
)


REWRITE_INSTRUCTION = (
    "Rewrite the following user question into a concise, search-optimized query "
    "for retrieving relevant HMO/health insurance documents from a vector database. "
    "Focus on key terms: provider names, plan names, benefits, coverage types, pricing, eligibility. "
    "Return ONLY the rewritten query, nothing else."
)


def embed_text(text):
    """Embed a query text using Ollama."""
    result = ollama.embed(model=EMBEDDING_MODEL, input="search_query: " + text)
    return result["embeddings"][0]


def extract_query_providers(query):
    """Return all provider names mentioned in the query."""
    query_lower = query.lower()
    return [provider for provider in PROVIDERS_NAMES if provider in query_lower]


def extract_query_keywords(query, providers):
    """Return meaningful query terms for exact-match retrieval."""
    provider_terms = set()
    for provider in providers:
        provider_terms.update(re.findall(r"[a-z0-9]+", provider.lower()))

    keywords = []
    seen = set()
    for term in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", query.lower()):
        if term in seen or term in provider_terms or term in QUERY_STOPWORDS:
            continue
        seen.add(term)
        keywords.append(term)
    return keywords


def keyword_variants(term):
    """Try common casing variants because Chroma substring matching is literal."""
    return list(dict.fromkeys([term, term.title(), term.upper()]))


def get_retrieval_candidates(collection, query_embedding, query, where_filter):
    """Combine vector candidates with exact keyword hits, then rerank."""
    candidates = {}

    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=VECTOR_CANDIDATE_COUNT,
        where=where_filter,
    )

    for chunk_id, doc, dist, meta in zip(
        vector_results["ids"][0],
        vector_results["documents"][0],
        vector_results["distances"][0],
        vector_results["metadatas"][0],
    ):
        candidates[chunk_id] = {
            "doc": doc,
            "meta": meta,
            "vector_similarity": 1 - dist,
            "keyword_hits": 0,
        }

    keywords = extract_query_keywords(query, extract_query_providers(query))
    for keyword in keywords:
        matched_ids = set()
        for variant in keyword_variants(keyword):
            keyword_results = collection.get(
                where=where_filter,
                where_document={"$contains": variant},
                limit=KEYWORD_CANDIDATE_COUNT,
                include=["documents", "metadatas"],
            )

            for chunk_id, doc, meta in zip(
                keyword_results["ids"],
                keyword_results["documents"],
                keyword_results["metadatas"],
            ):
                if chunk_id in matched_ids:
                    continue
                matched_ids.add(chunk_id)
                candidates.setdefault(
                    chunk_id,
                    {
                        "doc": doc,
                        "meta": meta,
                        "vector_similarity": 0,
                        "keyword_hits": 0,
                    },
                )
                candidates[chunk_id]["keyword_hits"] += 1

    reranked = []
    for candidate in candidates.values():
        score = candidate["vector_similarity"] + (candidate["keyword_hits"] * KEYWORD_BOOST)
        reranked.append((candidate["doc"], score, candidate["meta"], candidate["keyword_hits"]))

    reranked.sort(key=lambda item: item[1], reverse=True)
    return reranked


def main():
    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    doc_count = collection.count()
    if doc_count == 0:
        print("No documents found. Run 'python ingest.py' first.")
        return

    print(f"Loaded {doc_count} chunks from DB.\n")

    while True:
        query = input("\nYour question: ").strip()
        if query.lower() in ("quit", "exit", "q"):
            break

        query_embedding = embed_text(query)

        providers = extract_query_providers(query)
        conditions = []
        if len(providers) == 1:
            conditions.append({"provider": providers[0]})
        elif len(providers) > 1:
            conditions.append({"provider": {"$in": providers}})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$or": conditions}
        else:
            where_filter = None

        print_rewritten_query(query, query, where_filter)

        candidates = get_retrieval_candidates(
            collection,
            query_embedding,
            query,
            where_filter,
        )

        best_similarity = candidates[0][1] if candidates else 0
        drop_floor = best_similarity * SCORE_DROP_RATIO

        selected = []
        for doc, score, meta, keyword_hits in candidates:
            if score < SIMILARITY_THRESHOLD and keyword_hits == 0:
                break
            if score < drop_floor and keyword_hits == 0:
                break
            selected.append((doc, score, meta))
            if len(selected) >= MAX_CONTEXT_CHUNKS:
                break

        if not selected:
            print("No sufficiently relevant results found for that question.")
            continue

        # print(
        #     f"  Retrieved {len(selected)} chunks "
        #     f"(best: {selected[0][1]:.3f}, worst: {selected[-1][1]:.3f})"
        # )

        context = "\n\n---\n\n".join(doc for doc, _, _ in selected)
        user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

        # print(user_prompt)
        print_question(query)

        response = gemini_client.models.generate_content(
            model=LLM_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
        )
        print_answer(response.text)


if __name__ == "__main__":
    main()


# TODO
# option 1 Pre-process the records with keyword  like the book indexing
# option 2: summarize chunk using LLM and store the summary in the database
