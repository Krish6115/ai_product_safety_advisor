"""RAG retriever — search products and safety guidelines from ChromaDB."""

import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Lazy-loaded singletons
_model: SentenceTransformer | None = None
_client: chromadb.ClientAPI | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def search_products(query: str, n_results: int = 5) -> list[dict]:
    """Search the product catalog using semantic similarity.

    Args:
        query: The user's search query (EN or AR).
        n_results: Maximum number of results to return.

    Returns:
        List of dicts with product document text, metadata, and similarity score.
    """
    model = _get_model()
    client = _get_client()

    collection = client.get_collection("products")
    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "product_id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    return output


def search_safety_guidelines(query: str, n_results: int = 3) -> list[dict]:
    """Search safety guidelines using semantic similarity.

    Args:
        query: The user's search query.
        n_results: Maximum number of guideline sections to return.

    Returns:
        List of dicts with guideline text and metadata.
    """
    model = _get_model()
    client = _get_client()

    collection = client.get_collection("safety_guidelines")
    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "section_id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })

    return output


def get_retrieval_context(query: str, n_products: int = 5, n_safety: int = 3) -> tuple[str, str, float]:
    """Get combined retrieval context for the advisor.

    Args:
        query: User's question.
        n_products: Number of products to retrieve.
        n_safety: Number of safety guideline sections to retrieve.

    Returns:
        Tuple of (product_context_str, safety_context_str, best_retrieval_score).
    """
    products = search_products(query, n_results=n_products)
    safety = search_safety_guidelines(query, n_results=n_safety)

    product_context = "\n\n".join(
        f"[Product {p['product_id']}] (similarity: {1 - p['distance']:.2f})\n{p['document']}"
        for p in products
    )

    safety_context = "\n\n".join(
        f"[Guideline Section]\n{s['document']}"
        for s in safety
    )

    # Best retrieval score (cosine similarity = 1 - distance)
    best_score = (1 - products[0]["distance"]) if products else 0.0

    return product_context, safety_context, best_score
