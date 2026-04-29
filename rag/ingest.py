"""RAG ingestion — embed products and safety guidelines into ChromaDB."""

import json
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


def build_product_documents(products: list[dict]) -> list[tuple[str, str, dict]]:
    """Convert products into (id, text, metadata) tuples for embedding."""
    documents = []
    for p in products:
        text = (
            f"Product: {p['name_en']} / {p['name_ar']}. "
            f"Category: {p['category']}. "
            f"Price: {p['price_aed']} AED. "
            f"Age range: {p.get('min_age_months', 'N/A')}-{p.get('max_age_months', 'N/A')} months. "
            f"Max weight: {p.get('max_weight_kg', 'N/A')} kg. "
            f"Choking hazard: {p.get('choking_hazard', False)}. "
            f"Safety certifications: {', '.join(p.get('safety_certifications', []))}. "
            f"Materials: {', '.join(p.get('materials', []))}. "
            f"Description EN: {p['description_en']} "
            f"Description AR: {p['description_ar']}"
        )
        metadata = {
            "product_id": p["id"],
            "category": p["category"],
            "min_age_months": p.get("min_age_months") or -1,
            "max_age_months": p.get("max_age_months") or -1,
            "choking_hazard": p.get("choking_hazard", False),
            "price_aed": p["price_aed"],
        }
        documents.append((p["id"], text, metadata))
    return documents


def build_safety_documents(guidelines_path: Path) -> list[tuple[str, str, dict]]:
    """Split safety guidelines into sections for embedding."""
    text = guidelines_path.read_text(encoding="utf-8")
    sections = text.split("\n## ")
    documents = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        doc_id = f"safety-{i}"
        # Add the ## back for non-first sections
        if i > 0:
            section = "## " + section
        metadata = {"type": "safety_guideline", "section_index": i}
        documents.append((doc_id, section, metadata))
    return documents


def ingest():
    """Main ingestion: embed products + safety guidelines into ChromaDB."""
    print("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Initializing ChromaDB...")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Delete existing collections if they exist
    for name in ["products", "safety_guidelines"]:
        try:
            client.delete_collection(name)
        except Exception:
            pass

    # --- Products ---
    print("Loading products...")
    with open(DATA_DIR / "products.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    product_docs = build_product_documents(products)
    product_collection = client.create_collection(
        name="products",
        metadata={"hnsw:space": "cosine"},
    )

    ids = [d[0] for d in product_docs]
    texts = [d[1] for d in product_docs]
    metadatas = [d[2] for d in product_docs]

    print(f"Embedding {len(texts)} products...")
    embeddings = model.encode(texts).tolist()

    product_collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print(f"[OK] Ingested {len(ids)} products into ChromaDB.")

    # --- Safety Guidelines ---
    print("Loading safety guidelines...")
    safety_docs = build_safety_documents(DATA_DIR / "safety_guidelines.md")

    safety_collection = client.create_collection(
        name="safety_guidelines",
        metadata={"hnsw:space": "cosine"},
    )

    s_ids = [d[0] for d in safety_docs]
    s_texts = [d[1] for d in safety_docs]
    s_metadatas = [d[2] for d in safety_docs]

    print(f"Embedding {len(s_texts)} safety guideline sections...")
    s_embeddings = model.encode(s_texts).tolist()

    safety_collection.add(
        ids=s_ids,
        documents=s_texts,
        embeddings=s_embeddings,
        metadatas=s_metadatas,
    )
    print(f"[OK] Ingested {len(s_ids)} safety guideline sections into ChromaDB.")
    print("\n[DONE] Ingestion complete!")


if __name__ == "__main__":
    ingest()
