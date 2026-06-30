# HMO-RAG Codebase Documentation

## Overview

This repository is a Python RAG pipeline for Philippine HMO documents. It has three main stages:

1. `main.py`: scrape PDF documents from provider websites into local provider folders under `data/`
2. `ingest.py`: parse those PDFs, chunk them, rewrite chunks with an LLM, embed them, and store them in ChromaDB
3. `starter.py`: run an interactive retrieval + answer loop against the Chroma collection

At a high level, the project turns public HMO PDFs into a searchable local vector store, then answers user questions using retrieved document context.

## Repository Structure

```text
.
|- main.py                  # scraper CLI entry point
|- ingest.py                # ingestion CLI entry point
|- starter.py               # interactive RAG query loop
|- config.py                # shared paths, provider definitions, model names
|- pdf_parser.py            # PDF parsing + chunking with Docling
|- pdf_parser_semantic.py   # duplicate of pdf_parser.py at the moment
|- console_formatter.py     # Rich console output helpers for starter.py
|- test_pdf_parser.py       # local parser/debug CLI
|- scrapers/
|  |- __init__.py           # scraper registry
|  |- base_scraper.py       # shared HTTP/download behavior
|  |- maxicare.py           # provider-specific PDF discovery
|  |- medicard.py
|  |- intellicare.py
|  |- pacific_cross.py
|  |- cocolife.py
|  |- philcare.py
|  `- insurance_gov.py
|- chroma_db/               # persisted Chroma collection data
|- data/                    # downloaded provider PDFs
`- data_excluded/           # PDFs kept out of the main ingest flow
```

## Core Workflow

### 1. Scrape PDFs

`main.py` is the scraper CLI. It chooses one scraper class from `scrapers.SCRAPER_MAP` or runs all of them, then downloads discovered PDFs into provider-specific directories.

### 2. Parse and Ingest PDFs

`ingest.py` reads PDFs from `data/<provider>/`, converts them into structured chunks with Docling, rewrites each chunk into cleaner natural language using OpenRouter/DeepSeek, generates embeddings with Ollama, and upserts everything into a persistent Chroma collection.

### 3. Query the Vector Store

`starter.py` accepts free-text questions, embeds the query, filters by provider names when present, retrieves the nearest chunks from Chroma, then asks Gemini to answer using only the retrieved context.

## Main Modules

## `config.py`

Central configuration lives here:

- `BASE_DIR`, `DATA_DIR`, `CHROMA_DB_PATH`
- embedding/LLM model names:
  - `EMBEDDING_MODEL = "nomic-embed-text"`
  - `LLM_MODEL = "gemini-3.5-flash"`
- `COLLECTION_NAME = "hmo_docs"`
- `PROVIDERS`: provider metadata for scraping
- `PROVIDERS_NAMES`: provider folder names used by `ingest.py` and `starter.py`
- `setup_logging()`: shared logging bootstrap for the scraper CLI

### Provider Configuration

Each entry in `PROVIDERS` contains:

- provider display name
- site base URL
- seed URLs to crawl
- optional `known_pdfs`
- output directory under `data/`

Current configured providers:

- `maxicare`
- `medicard`
- `intellicare`
- `pacific_cross`
- `cocolife`
- `philcare`
- `insurance_gov`

### Important Current Inconsistencies

These matter operationally:

- `scrapers/base_scraper.py` imports `CHUNK_SIZE`, `MAX_RETRIES`, `REQUEST_DELAY`, `REQUEST_TIMEOUT`, and `RETRY_BACKOFF` from `config.py`, but those constants are not currently defined there.
- `SCRAPER_MAP` and `PROVIDERS` use `pacific_cross`, but `PROVIDERS_NAMES` uses `pacificcross`.
- `config.py` sets `PROVIDERS["pacific_cross"]["output_dir"]` to `data/pacific_cross`, while the current workspace contains `data/pacificcross`.
- `PROVIDERS_NAMES` currently excludes `philcare` and `insurance_gov`, so `ingest.py` and `starter.py` do not include them by default.

The scraper and ingest/query sides are therefore not fully aligned today.

## `scrapers/base_scraper.py`

`BaseScraper` implements the shared scraping behavior:

- creates a `requests.Session`
- applies browser-like request headers
- disables SSL verification because some target sites have broken certs
- retries fetches and downloads with exponential backoff
- parses HTML with BeautifulSoup + `lxml`
- detects PDF links from `<a href="...pdf">`
- sanitizes filenames before saving locally
- skips duplicate URLs and already-downloaded files
- supports `dry_run`

Key methods:

- `fetch_page(url)`: fetch HTML and return a BeautifulSoup object
- `find_pdf_links(soup, page_url)`: collect PDF URLs from a page
- `download_pdf(url)`: stream a PDF to disk
- `scrape_seed_pages()`: generic seed-page crawl helper
- `discover_pdfs()`: abstract hook implemented by each provider scraper
- `run()`: full lifecycle for one provider, including final summary data

### Provider Scrapers

Each scraper only customizes discovery logic:

- `MaxicareScraper`: crawls plan pages, follows subpages, and checks CDN-hosted brochure URLs
- `MedicardScraper`: finds healthcare program pages and MOA / Terms & Conditions PDFs
- `IntellicareScraper`: crawls "steps-and-forms" pages and adds known guidebooks
- `PacificCrossScraper`: searches claim/download/product pages for PDFs
- `CocolifeScraper`: follows healthcare-related internal links and adds known PDFs
- `PhilcareScraper`: explores product pages from both the main site and shop
- `InsuranceGovScraper`: targets HMO-related regulatory PDFs from the Insurance Commission site

## `main.py`

This is the scraper CLI entry point.

### CLI Arguments

```bash
python main.py --all
python main.py --provider maxicare
python main.py --all --dry-run
python main.py --provider medicard --verbose
```

Arguments:

- `--provider <name>`: scrape one provider
- `--all`: scrape all providers in `SCRAPER_MAP`
- `--dry-run`: discover URLs without downloading files
- `--verbose` / `-v`: enable debug logging

### Runtime Flow

1. Parse CLI args
2. Initialize logging with `setup_logging()`
3. Resolve provider keys from `SCRAPER_MAP`
4. Instantiate the matching scraper with provider config and `dry_run`
5. Call `scraper.run()`
6. Print a summary table and failed URLs
7. Exit with status code `1` if any downloads failed, otherwise `0`

## `pdf_parser.py`

This module handles document parsing and chunk generation.

### Stack

- `docling.document_converter.DocumentConverter`
- `docling.chunking.HybridChunker`
- `MarkdownTableSerializer`

### Behavior

- converts each PDF into a Docling document
- chunks the document with a 512-token target
- tries to use `chunker.contextualize()` so each chunk contains section context
- falls back to a shorter heading-prefixed chunk if contextualized text exceeds the token limit
- truncates to 512 tokens as a last resort

### Return Shape

`parse_and_chunk(pdf_path, provider)` returns:

```python
[
    {
        "text": "...chunk text...",
        "headings": ["provider", "section", "subsection"],
        "provider": "maxicare",
    },
]
```

This output is consumed directly by `ingest.py`.

## `pdf_parser_semantic.py`

Right now this file is functionally the same as `pdf_parser.py`. It appears to be a placeholder for a future semantic parsing or chunking variant, but it does not currently add different behavior.

## `ingest.py`

`ingest.py` is the ingestion CLI and the center of the indexing pipeline.

## What It Does

For each PDF it ingests, it:

1. parses the PDF into chunks via `parse_and_chunk()`
2. rewrites each chunk into a cleaner paragraph using DeepSeek through OpenRouter
3. embeds the rewritten text using Ollama
4. stores the embedding, rewritten text, and metadata in ChromaDB

## External Services Used

- `OpenRouter` via the `openai` SDK:
  - required env var: `OPENROUTER_API_KEY`
  - model used: `deepseek/deepseek-chat`
- `Ollama`:
  - used for embeddings
  - model name from `config.EMBEDDING_MODEL`
- `ChromaDB`:
  - persistent local vector store under `chroma_db/`

## CLI Usage

### Ingest all configured provider folders

```bash
python ingest.py
```

This reads provider folder names from `config.PROVIDERS_NAMES`.

### Ingest one provider folder

```bash
python ingest.py --provider maxicare
```

This limits the full-folder ingestion run to one provider directory under `data/`.

### Ingest one specific file

```bash
python ingest.py --file data/maxicare/sample.pdf --provider maxicare
```

`--file` requires `--provider`. The provider value is used as metadata in the stored records.

## CLI Arguments

- `--file`: path to a single PDF to ingest
- `--provider`: either:
  - the provider tag for `--file`, or
  - the folder name to limit a bulk run

If `--file` is supplied without `--provider`, the script aborts with:

```text
--file requires --provider
```

## Ingestion Runtime Flow

### Startup

On startup, `ingest.py`:

1. loads `.env` with `load_dotenv()`
2. reads `OPENROUTER_API_KEY`
3. creates an OpenAI-compatible client pointed at `https://openrouter.ai/api/v1`
4. opens a Chroma persistent client at `config.CHROMA_DB_PATH`
5. gets or creates the collection named `config.COLLECTION_NAME`

### Single File Path: `ingest_single_pdf()`

When `--file` is provided:

1. validate the file exists
2. parse it with `parse_and_chunk(pdf_path, provider=provider)`
3. build metadata:
   - `provider`
   - `source_file`
4. call `embed_and_store(collection, chunks, metadata)`
5. print the number of inserted chunks

This path avoids multiprocessing and is the easiest way to debug a single PDF.

### Folder Path: `pdf_to_vector()`

When `--file` is not provided:

1. determine provider folders from `--provider` or `PROVIDERS_NAMES`
2. choose `max_workers = min(len(providers), os.cpu_count() or 4)` unless overridden internally
3. launch a `ProcessPoolExecutor`
4. submit one `process_folder(provider)` task per provider
5. each worker:
   - scans `data/<provider>/*.pdf`
   - parses each PDF with `parse_and_chunk()`
   - returns chunk results to the parent process
6. the parent process then:
   - iterates completed futures
   - calls `embed_and_store()` for each parsed PDF
   - upserts each batch into Chroma

Parsing is parallelized by provider folder. Embedding and Chroma writes happen in the main process.

## Chunk Rewrite and Embedding

### `restructure_chunk()`

Before embedding, each chunk is rewritten by an LLM prompt that instructs the model to:

- produce a clear natural paragraph
- preserve condition names, limits, peso amounts, exclusions, and session counts
- avoid adding information not present in the source

Inputs:

- raw chunk text
- provider name
- joined heading path

Output:

- rewritten text string used as the stored `document` in Chroma

### `embed_batch()`

Embeddings are created with Ollama in batches:

- batch size: `64`
- every text is prefixed with `search_document: `
- the script calls `ollama.embed(model=EMBEDDING_MODEL, input=prefixed)`

### `embed_and_store()`

This is the core indexing function:

1. slice chunks into batches of 64
2. rewrite every chunk in the batch with `restructure_chunk()`
3. embed the rewritten batch with `embed_batch()`
4. construct Chroma records:
   - `id = "{provider}_{source_file}_{idx}"`
   - `document = rewritten text`
   - `metadata`:
     - `provider`
     - `source_file`
     - `headings`
     - `original_text`
5. call `collection.upsert(...)`

This means the vector store keeps both:

- the rewritten retrieval text as `document`
- the raw parser output as `metadata["original_text"]`

## Chroma Data Model

Each stored vector entry contains:

- `id`: provider + filename + chunk index
- `embedding`: produced by Ollama
- `document`: rewritten paragraph
- `metadata`:
  - `provider`
  - `source_file`
  - `headings`
  - `original_text`

The collection is persisted on disk, so repeated runs append/update records in `chroma_db/`.

## `starter.py`

This is the interactive local RAG loop.

### Inputs and Dependencies

- env var: `GEMINI_API_KEY`
- Gemini client from `google.genai`
- Ollama for query embeddings
- ChromaDB for retrieval
- Rich for terminal formatting

### Runtime Flow

1. connect to ChromaDB
2. abort if the collection is empty
3. prompt the user for a question in a loop
4. embed the raw query with Ollama
5. infer provider filters by checking whether provider names appear in the query
6. query Chroma for the top 10 matches
7. drop low-quality results using:
   - `SIMILARITY_THRESHOLD = 0.30`
   - `SCORE_DROP_RATIO = 0.70`
   - `MAX_CONTEXT_CHUNKS = 5`
8. join selected chunks into a context block
9. ask Gemini to answer using only that context
10. print the context and answer with Rich panels

### Query Rewriting

`starter.py` contains a `rewrite_query()` function that uses Gemini to rewrite questions for retrieval, but the current main loop does not use it. The code embeds the original user query directly.

## `console_formatter.py`

Pure presentation helpers for `starter.py`:

- `print_rewritten_query()`
- `print_context()`
- `print_question()`
- `print_answer()`

These wrap output in `rich.Panel` and `rich.Rule` objects for a more readable terminal UX.

## `test_pdf_parser.py`

This is a utility/debug CLI for validating PDF parsing and metadata generation.

### Usage

```bash
python test_pdf_parser.py path/to/file.pdf
python test_pdf_parser.py path/to/file.pdf --provider maxicare
python test_pdf_parser.py path/to/file.pdf --with-metadata
```

### Behavior

- default mode: print chunk count, headings, and chunk text
- `--with-metadata`: also rewrite chunks and create embeddings so you can inspect:
  - heading path
  - embedding dimension count
  - original chunk preview
  - rewritten chunk preview

This script depends on the same parser and ingest helpers as the main pipeline.

## Data Directories

### `data/`

Intended location for scraped PDFs, organized per provider.

Current folders in the workspace:

- `data/cocolife`
- `data/intellicare`
- `data/maxicare`
- `data/medicard`
- `data/pacificcross`

### `chroma_db/`

Persistent Chroma storage. The repository currently contains an existing local database:

- `chroma_db/chroma.sqlite3`
- segment files under `chroma_db/<uuid>/`

### `data_excluded/`

Contains PDFs that are currently excluded from the main indexed flow. These look like provider lists or facility lists rather than the main scraped policy set.

## Environment and Setup

## Python Dependencies

From `requirements.txt`:

- `requests`
- `beautifulsoup4`
- `lxml`
- `selenium`
- `webdriver-manager`
- `docling`
- `chromadb`
- `ollama`
- `google-genai`
- `keybert`
- `openai`
- `python-dotenv`

## Environment Variables

Required by the current code:

- `OPENROUTER_API_KEY` for `ingest.py`
- `GEMINI_API_KEY` for `starter.py`

## Expected Local Services

- Ollama must be running locally with the embedding model available:
  - `nomic-embed-text`

## Typical End-to-End Usage

```bash
# 1. scrape PDFs
python main.py --all

# 2. ingest PDFs into Chroma
python ingest.py

# 3. run the interactive RAG loop
python starter.py
```

## Operational Notes

- The repo already includes a populated `chroma_db/`, so `starter.py` may work without re-ingestion if the existing collection is valid.
- `main.py` may currently fail until the missing scraper constants are added to `config.py`.
- The provider naming mismatch around `pacific_cross` vs `pacificcross` should be resolved before relying on scrape -> ingest continuity for that provider.
- `pdf_parser_semantic.py` is currently duplicate code and does not provide a second parsing strategy yet.
- `starter.py` defines a Gemini rewrite step but leaves it disabled in the main query path.

## Suggested Cleanup Targets

These are the main structural issues worth addressing next:

1. unify provider keys across scraping, ingestion, and retrieval
2. move scraper runtime constants into `config.py` or stop importing them from there
3. decide whether `pdf_parser_semantic.py` should diverge or be removed
4. decide whether `philcare` and `insurance_gov` should be part of default ingestion
5. consider caching or batching `restructure_chunk()` calls more aggressively, since each chunk currently triggers an LLM call before embedding
