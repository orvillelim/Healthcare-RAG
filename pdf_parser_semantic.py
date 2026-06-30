import warnings

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.serializer.markdown import MarkdownTableSerializer


class MDTableSerializerProvider(ChunkingSerializerProvider):
    def get_serializer(self, doc):
        return ChunkingDocSerializer(
            doc=doc,
            table_serializer=MarkdownTableSerializer(),
        )


MAX_TOKENS = 512

converter = DocumentConverter()
chunker = HybridChunker(
    max_tokens=MAX_TOKENS,
    merge_peers=True,
    serializer_provider=MDTableSerializerProvider(),
)

_tokenizer = chunker.tokenizer


def _contextualize_chunk(chunk):
    """Use full contextualize if it fits; otherwise fall back to short heading prefix."""
    enriched = chunker.contextualize(chunk=chunk)
    token_count = _tokenizer.count_tokens(enriched)

    if token_count <= MAX_TOKENS:
        return enriched

    print(f"  [FALLBACK] Contextualized text too long ({token_count} tokens), "
          f"using short heading prefix: {chunk.meta.headings}")

    heading_prefix = " > ".join(chunk.meta.headings) + "\n" if chunk.meta.headings else ""
    fallback_text = heading_prefix + chunk.text

    if _tokenizer.count_tokens(fallback_text) <= MAX_TOKENS:
        return fallback_text

    hf_tok = _tokenizer.get_tokenizer()
    token_ids = hf_tok.encode(fallback_text, add_special_tokens=False)[:MAX_TOKENS]
    return hf_tok.decode(token_ids, skip_special_tokens=True)


def parse_and_chunk(pdf_path: str, provider: str = "") -> list[dict]:
    """Parse a PDF and return a list of chunks with text and metadata."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        doc = converter.convert(pdf_path).document
        raw_chunks = list(chunker.chunk(dl_doc=doc))

    chunks = []
    for chunk in raw_chunks:
        chunks.append({
            "text": _contextualize_chunk(chunk),
            "headings": [provider] + (chunk.meta.headings or []),
            "provider": provider,
        })

    return chunks
