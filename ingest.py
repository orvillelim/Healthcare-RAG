"""
Ingest: Parse PDFs, embed, and store into ChromaDB
====================================================
Run separately from the interactive query loop:
  python ingest.py                                   # ingest all provider folders
  python ingest.py --provider maxicare                # ingest one provider folder
  python ingest.py --file path/to/file.pdf --provider maxicare   # ingest a single PDF
"""

import argparse
import os
import glob
import re
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

import ollama
import chromadb
import openai
from dotenv import load_dotenv
from pdf_parser import parse_and_chunk
from config import CHROMA_DB_PATH, EMBEDDING_MODEL, COLLECTION_NAME, DATA_DIR, PROVIDERS_NAMES

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY not set. Add it to your .env file.")

openrouter_client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

DEEPSEEK_MODEL = "deepseek/deepseek-chat"

EMBED_BATCH_SIZE = 64
REWRITE_MAX_WORKERS = 8

LEADING_META_PATTERNS = (
    re.compile(r"^here(?:['’])?s\b.*?:\s*$", re.IGNORECASE),
    re.compile(r"^(?:rewrite|rewritten|revised|cleaned|natural)\s+(?:text|version|rewrite)\s*:?\s*$", re.IGNORECASE),
)
TRAILING_META_PATTERNS = (
    re.compile(r"^let me know\b.*$", re.IGNORECASE),
    re.compile(r"^if you(?:['’])?d like\b.*$", re.IGNORECASE),
    re.compile(r"^i can also\b.*$", re.IGNORECASE),
)


def embed_batch(texts):
    """Embed a batch of texts using Ollama in one call."""
    prefixed = ["search_document: " + t for t in texts]
    result = ollama.embed(model=EMBEDDING_MODEL, input=prefixed)
    return result["embeddings"]


def clean_restructured_text(text: str) -> str:
    """Keep only the rewritten chunk content, not assistant framing."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[\w-]*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```$", "", cleaned)

    lines = [line.strip() for line in cleaned.splitlines()]

    while lines and (not lines[0] or lines[0] == "---" or any(p.match(lines[0]) for p in LEADING_META_PATTERNS)):
        lines.pop(0)

    while lines and (not lines[-1] or lines[-1] == "---" or any(p.match(lines[-1]) for p in TRAILING_META_PATTERNS)):
        lines.pop()

    cleaned = "\n".join(lines).strip()

    if cleaned.startswith("**") and cleaned.endswith("**") and len(cleaned) > 4:
        cleaned = cleaned[2:-2].strip()

    return cleaned or text.strip()


def rewrite_chunk_with_fallback(chunk, metadata: dict) -> str:
    """Rewrite a chunk with the LLM, falling back to the original text on failure."""
    heading = " > ".join(chunk["headings"]) if chunk["headings"] else ""
    try:
        rewritten = restructure_chunk(
            chunk["text"],
            metadata["provider"],
            heading,
        )
    except Exception as e:
        print(
            f"    Warning: failed to restructure chunk "
            f"from {metadata['source_file']} ({heading or 'no heading'}): {e}"
        )
        rewritten = chunk["text"]

    prefix = f"Provider: {metadata['provider']}"
    if heading:
        prefix += f"\nSection: {heading}"
    return prefix + "\n\n" + rewritten


def embed_and_store(collection, chunks, metadata: dict):
    """Restructure chunks with the LLM, embed, and upsert into ChromaDB."""
    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch_number = (batch_start // EMBED_BATCH_SIZE) + 1
        batch = chunks[batch_start:batch_start + EMBED_BATCH_SIZE]
        rewrite_workers = min(REWRITE_MAX_WORKERS, len(batch))

        print(
            f"    [{metadata['source_file']}] Batch {batch_number}: "
            f"rewriting {len(batch)} chunk(s) with {rewrite_workers} worker(s)..."
        )
        rewrite_started = time.perf_counter()

        with ThreadPoolExecutor(max_workers=rewrite_workers) as pool:
            restructured_texts = list(
                pool.map(
                    lambda chunk: rewrite_chunk_with_fallback(chunk, metadata),
                    batch,
                )
            )

        rewrite_elapsed = time.perf_counter() - rewrite_started
        print(
            f"    [{metadata['source_file']}] Batch {batch_number}: "
            f"rewrite complete in {rewrite_elapsed:.2f}s"
        )

        print(
            f"    [{metadata['source_file']}] Batch {batch_number}: "
            f"embedding {len(restructured_texts)} chunk(s)..."
        )
        embed_started = time.perf_counter()
        embeddings = embed_batch(restructured_texts)
        embed_elapsed = time.perf_counter() - embed_started
        print(
            f"    [{metadata['source_file']}] Batch {batch_number}: "
            f"embedding complete in {embed_elapsed:.2f}s"
        )

        ids = []
        documents = []
        metadatas = []
        for i, (chunk, text) in enumerate(zip(batch, restructured_texts)):
            idx = batch_start + i
            ids.append(f"{metadata['provider']}_{metadata['source_file']}_{idx}")
            documents.append(text)
            metadatas.append({
                **metadata,
                "headings": " > ".join(chunk["headings"]) if chunk["headings"] else "",
                "original_text": chunk["text"],
            })

        print(
            f"    [{metadata['source_file']}] Batch {batch_number}: "
            f"storing {len(ids)} chunk(s) in ChromaDB..."
        )
        store_started = time.perf_counter()
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        store_elapsed = time.perf_counter() - store_started
        print(
            f"    [{metadata['source_file']}] Batch {batch_number}: "
            f"store complete in {store_elapsed:.2f}s"
        )



def restructure_chunk(chunk_text: str, provider: str, heading: str) -> str:
    """Rewrite a raw chunk into a clear natural paragraph using DeepSeek via OpenRouter."""
    prompt = f"""Rewrite this HMO benefits text as a clear, natural paragraph. Keep ALL specific details: condition names, coverage limits, peso amounts, session limits, exclusions.
Do not add information that isn't in the original.
Return only the rewritten paragraph text.
Do not include any introduction, explanation, quotation marks, markdown, bullets, or closing remarks.

Provider: {provider}
Section: {heading}

Original text:
{chunk_text}"""

    response = openrouter_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return clean_restructured_text(response.choices[0].message.content)


def process_folder(folder):
    """Parse all PDFs in a folder and return chunked results. Runs in a worker process."""
    folder_path = os.path.join(DATA_DIR, folder)
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))

    if not pdf_files:
        return folder, []

    results = []
    for i, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        print(f"    [{folder}] ({i}/{len(pdf_files)}) Parsing: {filename}")
        try:
            chunks = parse_and_chunk(pdf_path, provider=folder)
            results.append({"filename": filename, "chunks": chunks})
        except Exception as e:
            print(f"    [{folder}] ERROR parsing {filename}: {e}")

    return folder, results


def ingest_single_pdf(collection, pdf_path, provider):
    """Parse and embed a single PDF directly, without the process pool."""
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"No such file: {pdf_path}")

    filename = os.path.basename(pdf_path)
    print(f"  Parsing: {filename}")
    chunks = parse_and_chunk(pdf_path, provider=provider)

    metadata = {"provider": provider, "source_file": filename}
    embed_and_store(collection, chunks, metadata)
    print(f"  Inserted {len(chunks)} chunks from {filename}")
    return len(chunks)


def pdf_to_vector(collection, providers=None, max_workers=None):
    """Parse PDFs in parallel per folder, then embed and store."""
    providers = providers or PROVIDERS_NAMES
    if max_workers is None:
        max_workers = min(len(providers), os.cpu_count() or 4)

    total_chunks = 0

    print(f"  Parsing with {max_workers} worker processes...")

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(process_folder, folder): folder for folder in providers}

        for future in as_completed(futures):
            folder, results = future.result()

            if not results:
                print(f"  [{folder}] No PDFs or no results, skipping.")
                continue

            print(f"\n  [{folder}] Parsed {len(results)} PDF(s), embedding...")

            for item in results:
                metadata = {"provider": folder, "source_file": item["filename"]}
                embed_and_store(collection, item["chunks"], metadata)
                print(f"    Inserted {len(item['chunks'])} chunks from {item['filename']}")
                total_chunks += len(item["chunks"])

    return total_chunks


def main():
    parser = argparse.ArgumentParser(
        description="Parse PDFs, embed, and store them into ChromaDB."
    )
    parser.add_argument(
        "--file",
        help="Path to a single PDF file to ingest (requires --provider).",
    )
    parser.add_argument(
        "--provider",
        help="Tag for --file, or limit a full run to a single provider folder.",
    )
    args = parser.parse_args()

    if args.file and not args.provider:
        parser.error("--file requires --provider")

    print("Setting up ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    if args.file:
        total = ingest_single_pdf(collection, args.file, args.provider)
    else:
        providers = [args.provider] if args.provider else PROVIDERS_NAMES
        print(f"Ingesting PDFs from {len(providers)} folder(s)...")
        total = pdf_to_vector(collection, providers=providers)

    print(f"\nDone! {total} chunks ingested. {collection.count()} total in DB.")


if __name__ == "__main__":
    main()
