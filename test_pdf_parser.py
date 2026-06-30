"""Quick test for pdf_parser — parses a PDF and prints the chunks."""

import argparse

from pdf_parser import parse_and_chunk
from ingest import embed_batch, restructure_chunk


def print_chunks(chunks):
    """Print parsed chunks with headings."""
    print(f"\nTotal chunks: {len(chunks)}\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"{'=' * 60}")
        print(f"Chunk {i}")
        print(f"Headings: {chunk['headings']}")
        print(f"{'-' * 60}")
        print(chunk["text"])
        print()


def print_chunks_with_metadata(chunks, provider: str = "test"):
    """Print chunks with their restructured text and embedding dimensions."""
    print(f"\nTotal chunks: {len(chunks)}")
    print(f"{'=' * 60}\n")

    restructured_texts = []
    for chunk in chunks:
        heading = " > ".join(chunk["headings"]) if chunk["headings"] else ""
        restructured = restructure_chunk(chunk["text"], provider, heading)
        restructured_texts.append(restructured)

    embeddings = embed_batch(restructured_texts)

    for i, (chunk, text, embedding) in enumerate(zip(chunks, restructured_texts, embeddings), 1):
        heading = " > ".join(chunk["headings"]) if chunk["headings"] else ""

        print(f"Chunk {i}")
        print(f"  Headings:      {heading}")
        print(f"  Embedding:     {len(embedding)} dimensions")
        print(f"  Original:")
        preview = chunk["text"][:150].replace("\n", " ")
        print(f"    {preview}...")
        print(f"  Restructured:")
        print(f"    {text[:200]}...")
        print(f"{'-' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Test PDF parsing and chunking.")
    parser.add_argument("pdf_path", help="Path to a PDF file to parse")
    parser.add_argument("--provider", default="test", help="Provider name for metadata")
    parser.add_argument("--with-metadata", action="store_true",
                        help="Show keywords and embedding info per chunk")
    args = parser.parse_args()

    chunks = parse_and_chunk(args.pdf_path, provider=args.provider)

    if args.with_metadata:
        print_chunks_with_metadata(chunks, provider=args.provider)
    else:
        print_chunks(chunks)


if __name__ == "__main__":
    main()
