# HMO-RAG

A local Retrieval-Augmented Generation (RAG) pipeline for Philippine HMO documents. It parses HMO benefit PDFs, rewrites and embeds them into a local vector store, and answers natural-lang

uage questions using the retrieved document context.

## Demo
<img width="2023" height="809" alt="Screenshot 2026-06-30 at 9 50 49 AM" src="https://github.com/user-attachments/assets/50bb42dd-48b7-409f-ae0c-46c437dc186f" />

## What is it

HMO benefit guidebooks are dense, inconsistent PDFs. This project turns them into a searchable knowledge base:

1. **Ingest** — parse PDFs into chunks, rewrite each chunk into clean natural language with an LLM, embed them, and store them in ChromaDB.
2. **Query** — embed your question, retrieve and rerank the most relevant chunks, then ask Gemini to answer using only that context.

PDFs are expected to live under `data/<provider>/*.pdf`, organized per provider (e.g. `data/maxicare/`, `data/medicard/`).

## Tech stack

| Component | Used for |
|-----------|----------|
| **Docling** | PDF parsing and structure-aware chunking |
| **Ollama** (`nomic-embed-text`) | Local embeddings for both documents and queries |
| **OpenRouter** (`deepseek/deepseek-chat`) | Rewriting raw chunks into clean text during ingestion |
| **ChromaDB** | Persistent local vector store (`chroma_db/`) |
| **Gemini** (`gemini-3.5-flash`) | Final answer generation from retrieved context |

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally with the embedding model pulled:
  ```bash
  ollama pull nomic-embed-text
  ```
- API keys for OpenRouter (ingestion) and Gemini (querying).

## Setup

```bash
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```bash
# Required by ingest.py — rewrites chunks via OpenRouter/DeepSeek
OPENROUTER_API_KEY=sk-or-...

# Required by starter.py — generates answers via Gemini
GEMINI_API_KEY=...
```

`OPENROUTER_API_KEY` is only needed for ingestion; `GEMINI_API_KEY` is only needed for querying. Both are loaded automatically via `python-dotenv`.

## How to run

**Ingest first** to embed your PDFs into ChromaDB, then run the query loop. The query loop will refuse to start if the collection is empty.

### 1. Ingest (embed PDFs)

```bash
# Ingest every provider folder listed in config.PROVIDERS_NAMES
python ingest.py

# Ingest a single provider folder under data/
python ingest.py --provider maxicare

# Ingest one specific PDF (requires --provider as a metadata tag)
python ingest.py --file data/maxicare/sample.pdf --provider maxicare
```

### 2. Query (interactive RAG loop)

```bash
python starter.py
```

Type a question at the prompt; type `quit`, `exit`, or `q` to leave. Mentioning a provider name in your question (e.g. "What does **maxicare** cover for dental?") automatically scopes retrieval to that provider.

## Important files

### `ingest.py` — indexing pipeline

The ingestion entry point. Parses PDFs into chunks, rewrites each chunk into clean text via OpenRouter/DeepSeek, embeds them with Ollama, and upserts the records into ChromaDB.

### `starter.py` — interactive query loop

The query entry point. Embeds your question, retrieves and reranks the most relevant chunks from ChromaDB, then asks Gemini to answer using only that context.

### `config.py` — shared configuration

Model names, paths (`CHROMA_DB_PATH`, `DATA_DIR`), `COLLECTION_NAME`, and the `PROVIDERS_NAMES` list that drives default ingestion and provider filtering.

### `pdf_parser.py` — PDF parsing and chunking

Converts PDFs to Docling documents and emits ~512-token, heading-contextualized chunks consumed by `ingest.py`.

## Re-ranking and metadata filtering

Both live in `starter.py`.

### Metadata filtering

Before retrieval, `extract_query_providers()` scans the question for any provider names in `PROVIDERS_NAMES`. In `main()`, matched providers are turned into a Chroma `where_filter`:

- one provider → `{"provider": "maxicare"}`
- multiple providers → `{"provider": {"$in": [...]}}`
- none → no filter (search across all providers)

This `where_filter` is passed to both the vector query and the keyword lookups, so retrieval is scoped to the relevant provider(s).

### Re-ranking

`get_retrieval_candidates()` performs **hybrid retrieval** and reranks:

1. Pull up to `VECTOR_CANDIDATE_COUNT = 25` candidates by vector similarity (`1 - distance`).
2. Pull exact **keyword** matches via Chroma's `where_document={"$contains": ...}`, trying casing variants, for meaningful query terms (stopwords/provider terms excluded).
3. Score each candidate: `vector_similarity + keyword_hits * KEYWORD_BOOST` (`KEYWORD_BOOST = 0.65`), then sort descending.

## Debugging with `chunk_inspector.py`

Inspect what actually landed in ChromaDB:

```bash
# List stored chunks (id, provider, section, preview)
python chunk_inspector.py list --limit 20

# Inspect one chunk in full, including embedding dimensions
 python chunk_inspector.py inspect intellicare_Standard-Guidebook_Benefits_July.pdf_1

# Show all chunks for a provider
python chunk_inspector.py provider maxicare --limit 10

# Find chunks whose document text contains a term
python chunk_inspector.py search "dental"
```

Use `list` to find chunk IDs, `inspect` to see the full rewritten text + metadata + embedding size, `provider` to audit a single source, and `search` to verify keyword retrieval will hit the chunks you expect.
