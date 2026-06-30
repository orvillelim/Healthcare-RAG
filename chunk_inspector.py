import argparse

import chromadb
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config import CHROMA_DB_PATH, COLLECTION_NAME

console = Console()
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# 1. See everything at a glance
def list_chunks(limit=20):
    results = collection.get(
        limit=limit,
        include=["documents", "metadatas"]
    )
    table = Table(title=f"Chunks ({collection.count()} total)")
    table.add_column("ID", width=15)
    table.add_column("Provider", width=12)
    table.add_column("Section", width=20)
    table.add_column("Preview", max_width=60)

    for id, doc, meta in zip(results["ids"], 
                              results["documents"], 
                              results["metadatas"]):
        table.add_row(
            id,
            meta.get("provider", "?"),
            meta.get("headings", "?"),
            doc[:100] + "..."
        )
    console.print(table)

# 2. Inspect a specific chunk in full detail
def inspect_chunk(chunk_id):
    results = collection.get(
        ids=[chunk_id],
        include=["documents", "metadatas", "embeddings"]
    )
    meta = results["metadatas"][0]
    doc = results["documents"][0]
    emb = results["embeddings"][0]

    console.print(Panel(doc, title=f"Chunk: {chunk_id}"))
    console.print(f"Embedding dims: {len(emb)}")
    console.print(f"Text length: {len(doc)} chars")
    for key, val in meta.items():
        console.print(f"  {key}: {val}")

# 3. Find all chunks for a specific provider
def chunks_by_provider(provider, limit=None):
    results = collection.get(
        where={"provider": provider},
        limit=limit,
        include=["documents", "metadatas"]
    )
    for id, doc, meta in zip(results["ids"],
                              results["documents"],
                              results["metadatas"]):
        console.print(Panel(
            doc[:300] + "...",
            title=f"{id} | {meta.get('headings', '?')}"
        ))

# 4. Search by text content
def find_chunks_containing(term, limit=None):
    results = collection.get(
        where_document={"$contains": term},
        limit=limit,
        include=["documents", "metadatas"]
    )
    console.print(f"Found {len(results['ids'])} chunks containing '{term}':\n")
    for id, doc, meta in zip(results["ids"],
                              results["documents"],
                              results["metadatas"]):
        console.print(Panel(
            doc,
            title=f"{id} | {meta.get('provider', '?')}"
        ))


def main():
    parser = argparse.ArgumentParser(description="Inspect chunks stored in ChromaDB.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List stored chunks.")
    list_parser.add_argument("--limit", type=int, default=20)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one chunk.")
    inspect_parser.add_argument("chunk_id")

    provider_parser = subparsers.add_parser("provider", help="Show chunks by provider.")
    provider_parser.add_argument("provider")
    provider_parser.add_argument("--limit", type=int, default=None)

    search_parser = subparsers.add_parser("search", help="Search stored document text.")
    search_parser.add_argument("term")
    search_parser.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    if args.command == "list":
        list_chunks(limit=args.limit)
    elif args.command == "inspect":
        inspect_chunk(args.chunk_id)
    elif args.command == "provider":
        chunks_by_provider(args.provider, limit=args.limit)
    elif args.command == "search":
        find_chunks_containing(args.term, limit=args.limit)


if __name__ == "__main__":
    main()
