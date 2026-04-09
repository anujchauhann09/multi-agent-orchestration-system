from typing import List
from pinecone import Pinecone
from google import genai
from app.core.settings import settings

_pc = Pinecone(api_key=settings.PINECONE_API_KEY)
_index = _pc.Index(settings.PINECONE_INDEX)
_client = genai.Client(api_key=settings.GOOGLE_API_KEY)

_CHUNK_SIZE = 500  # characters per chunk
_TOP_K = 5         # number of relevant chunks to retrieve


def _chunk_text(text: str, size: int = _CHUNK_SIZE) -> List[str]:
    """Split text into fixed-size chunks — deterministic, no LLM."""
    return [text[i:i + size] for i in range(0, len(text), size)]


def _embed(text: str) -> List[float]:
    """Get embedding vector from Gemini truncated to match Pinecone index dimension."""
    response = _client.models.embed_content(
        model=settings.GOOGLE_EMBEDDING_MODEL,
        contents=text,
        config={"output_dimensionality": 768},
    )
    return response.embeddings[0].values


def index_repo_files(task_id: int, files: List[dict]) -> None:
    """
    Chunk and embed all repo files, store in Pinecone.
    Deterministic — no LLM involved.
    Each vector is namespaced by task_id to isolate per-task context.
    """
    vectors = []
    namespace = f"task-{task_id}"

    for file in files:
        chunks = _chunk_text(file["content"])
        for i, chunk in enumerate(chunks):
            vector_id = f"{file['path']}::chunk-{i}"
            embedding = _embed(chunk)
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "path": file["path"],
                    "chunk": chunk,
                    "task_id": task_id,
                },
            })

    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        _index.upsert(vectors=vectors[i:i + 100], namespace=namespace)


def search_relevant_chunks(task_id: int, query: str, top_k: int = _TOP_K) -> List[dict]:
    """
    Vector search — find top-k relevant code chunks for a query.
    Returns list of {path, chunk} dicts.
    """
    namespace = f"task-{task_id}"
    query_vector = _embed(query)
    results = _index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
        namespace=namespace,
    )
    return [
        {"path": m.metadata["path"], "chunk": m.metadata["chunk"]}
        for m in results.matches
    ]


def delete_task_vectors(task_id: int) -> None:
    """Clean up Pinecone namespace after task completes."""
    namespace = f"task-{task_id}"
    _index.delete(delete_all=True, namespace=namespace)
