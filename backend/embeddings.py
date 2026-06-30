import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI
from config import get_settings
from typing import List, Dict, Any
import asyncio

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

# Global ChromaDB client (initialized once)
_chroma_client = None
_collection = None

COLLECTION_NAME = "legalassist_content"


def get_chroma() -> chromadb.EphemeralClient:
    global _chroma_client
    if _chroma_client is None:
        # Use in-memory ChromaDB — the auto-scrape on startup rebuilds the index
        # from legalassistglobal.com each time, so persistence is not needed here.
        _chroma_client = chromadb.EphemeralClient(
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _chroma_client


def get_collection():
    global _collection
    if _collection is None:
        chroma = get_chroma()
        _collection = chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


async def embed_text(text: str) -> List[float]:
    """Embed a single text string."""
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8000]  # Safety trim
    )
    return response.data[0].embedding


async def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts (OpenAI supports up to 2048 per call)."""
    chunks = [texts[i:i+100] for i in range(0, len(texts), 100)]
    all_embeddings = []
    for chunk in chunks:
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk
        )
        all_embeddings.extend([d.embedding for d in response.data])
        await asyncio.sleep(0.1)  # Rate limit courtesy
    return all_embeddings


async def index_chunks(chunks: List[Dict[str, Any]]) -> int:
    """Index all chunks into ChromaDB. Returns total indexed count."""
    if not chunks:
        return 0

    collection = get_collection()

    # Clear existing data
    try:
        collection.delete(where={"url": {"$ne": ""}})
    except Exception:
        pass  # Collection may be empty

    texts = [c["text"] for c in chunks]
    print(f"[Embeddings] Generating embeddings for {len(texts)} chunks...")
    embeddings = await embed_batch(texts)
    print(f"[Embeddings] Done. Inserting into ChromaDB...")

    # Insert in batches of 500
    batch_size = 500
    total = 0
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_embeddings = embeddings[i:i + batch_size]

        ids = [f"{c['url']}__chunk_{c['chunk_index']}" for c in batch_chunks]
        metadatas = [
            {
                "url": c["url"],
                "title": c["title"],
                "category": c["category"],
                "chunk_index": c["chunk_index"],
            }
            for c in batch_chunks
        ]
        documents = [c["text"] for c in batch_chunks]

        collection.upsert(
            ids=ids,
            embeddings=batch_embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        total += len(batch_chunks)

    print(f"[Embeddings] Indexed {total} chunks into ChromaDB")
    return total


async def search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search ChromaDB for the most relevant chunks."""
    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = await embed_text(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        similarity = 1 - dist  # cosine distance → similarity
        hits.append({
            "text": doc,
            "url": meta["url"],
            "title": meta["title"],
            "category": meta["category"],
            "similarity": similarity,
        })

    return hits


def get_collection_count() -> int:
    """Return number of indexed chunks."""
    try:
        return get_collection().count()
    except Exception:
        return 0
