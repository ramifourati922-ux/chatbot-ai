# scripts/ingest_knowledge_base.py
"""
Indexe toute la knowledge base (data/knowledge_base/) dans ChromaDB :
- les fichiers .txt (Q/R) → un chunk par bloc Q/R, metadata type="policy"
- produits.csv → un chunk par produit, metadata type="product"

Les .pdf ne sont PAS indexés (voir data/knowledge_base/README.md — ce
sont des artefacts de présentation générés depuis les .txt, pas la
source de vérité RAG).

Usage :
    ./venv/Scripts/python.exe scripts/ingest_knowledge_base.py [--reset]

--reset : vide la collection avant de ré-indexer (utile après avoir
          modifié/supprimé du contenu, sinon les anciens chunks restent).
"""

import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rag.embedding_service import embed_batch
from app.services.rag import vector_store

KB_ROOT = Path(__file__).parent.parent / "data" / "knowledge_base"

QR_FILES = [
    "sav/retours.txt",
    "sav/livraison.txt",
    "sav/garantie.txt",
    "sav/reclamations.txt",
    "ecommerce/paiement.txt",
    "ecommerce/promotions.txt",
    "general/faq.txt",
]

PRODUCTS_CSV = "ecommerce/produits.csv"


def _blocks(text: str):
    body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    return [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]


def load_policy_chunks():
    ids, documents, metadatas = [], [], []
    for relpath in QR_FILES:
        path = KB_ROOT / relpath
        text = path.read_text(encoding="utf-8")
        domain, filename = relpath.split("/")
        category = filename.replace(".txt", "")

        for i, block in enumerate(_blocks(text)):
            m = re.match(r"Q:\s*(.+?)\nR:\s*(.+)", block, re.DOTALL)
            if not m:
                continue
            question, reponse = m.group(1).strip(), m.group(2).strip()
            doc = f"Q: {question}\nR: {reponse}"
            chunk_id = f"policy-{domain}-{category}-{i:04d}"
            ids.append(chunk_id)
            documents.append(doc)
            metadatas.append({"type": "policy", "domain": domain, "category": category, "source": relpath})

    return ids, documents, metadatas


def load_product_chunks():
    ids, documents, metadatas = [], [], []
    path = KB_ROOT / PRODUCTS_CSV
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doc = (
                f"{row['nom']} | Catégorie: {row['categorie']} | Prix: {row['prix_dt']} DT | "
                f"Disponibilité: {row['disponibilite']} | Caractéristiques: {row['caracteristiques']} | "
                f"{row['description']}"
            )
            ids.append(f"product-{row['sku']}")
            documents.append(doc)
            metadatas.append({
                "type": "product",
                "category": row["categorie"],
                "sku": row["sku"],
                "prix_dt": float(row["prix_dt"]),
                "disponibilite": row["disponibilite"],
            })
    return ids, documents, metadatas


def main():
    reset = "--reset" in sys.argv

    if reset:
        print("♻️  Réinitialisation de la collection ChromaDB...")
        vector_store.reset_collection()

    print("📖 Lecture de la knowledge base...")
    policy_ids, policy_docs, policy_meta = load_policy_chunks()
    product_ids, product_docs, product_meta = load_product_chunks()

    all_ids = policy_ids + product_ids
    all_docs = policy_docs + product_docs
    all_meta = policy_meta + product_meta

    print(f"   {len(policy_ids)} chunks de politiques (SAV/e-commerce/FAQ)")
    print(f"   {len(product_ids)} chunks de produits")
    print(f"   {len(all_ids)} chunks au total à indexer")

    print("🧮 Calcul des embeddings (peut prendre plusieurs minutes pour 10 000+ produits)...")
    t0 = time.time()
    embeddings = embed_batch(all_docs)
    t1 = time.time()
    print(f"   ✅ {len(embeddings)} embeddings calculés en {t1 - t0:.1f}s")

    print("💾 Indexation dans ChromaDB...")
    vector_store.upsert(all_ids, embeddings, all_docs, all_meta)
    t2 = time.time()
    print(f"   ✅ Indexation terminée en {t2 - t1:.1f}s")

    total_in_collection = vector_store.count()
    print(f"\n✅ Terminé. Collection '{vector_store.get_collection().name}' contient {total_in_collection} documents.")


if __name__ == "__main__":
    main()
