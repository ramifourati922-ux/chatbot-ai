# tests/test_knowledge_base_structure.py
"""
Vérifie que la knowledge base respecte un format cohérent et parseable :
- data/knowledge_base/**/*.txt (Q/R) → source de vérité pour le RAG (Tâche 4)
- data/knowledge_base/ecommerce/produits.csv → catalogue produits (10 000+ lignes)
- data/knowledge_base/**/*.pdf → documents de présentation générés depuis les .txt
  (pas utilisés par le RAG directement, voir scripts/generate_policy_pdfs.py)
"""

import csv
import re
from pathlib import Path

import pytest

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

PDF_FILES = [
    "sav/retours.pdf",
    "sav/livraison.pdf",
    "sav/garantie.pdf",
    "ecommerce/paiement.pdf",
    "ecommerce/promotions.pdf",
    "general/faq.pdf",
]

PRODUCTS_CSV = "ecommerce/produits.csv"
MIN_PRODUCTS = 10000


@pytest.mark.parametrize("relative_path", QR_FILES)
def test_expected_qr_file_exists(relative_path):
    assert (KB_ROOT / relative_path).is_file(), f"Fichier manquant : {relative_path}"


def _blocks(text: str):
    """Découpe un fichier en blocs séparés par une ligne vide (hors commentaires)."""
    body = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )
    return [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]


@pytest.mark.parametrize("relative_path", QR_FILES)
def test_qr_format_is_well_formed(relative_path):
    """Chaque bloc doit contenir une ligne Q: et une ligne R:."""
    text = (KB_ROOT / relative_path).read_text(encoding="utf-8")
    blocks = _blocks(text)
    assert len(blocks) > 0, f"Aucun bloc Q/R trouvé dans {relative_path}"
    for block in blocks:
        assert block.startswith("Q:"), f"Bloc mal formé (doit commencer par 'Q:') dans {relative_path}:\n{block}"
        assert "R:" in block, f"Bloc sans réponse 'R:' dans {relative_path}:\n{block}"


@pytest.mark.parametrize("relative_path", PDF_FILES)
def test_expected_pdf_exists(relative_path):
    path = KB_ROOT / relative_path
    assert path.is_file(), f"PDF manquant : {relative_path} (relancer scripts/generate_policy_pdfs.py ?)"
    assert path.stat().st_size > 500, f"PDF suspicieusement petit/vide : {relative_path}"


def test_products_csv_exists_and_has_minimum_rows():
    path = KB_ROOT / PRODUCTS_CSV
    assert path.is_file(), f"CSV manquant : {PRODUCTS_CSV} (relancer scripts/generate_products_catalog.py ?)"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= MIN_PRODUCTS, f"Seulement {len(rows)} produits, minimum attendu {MIN_PRODUCTS}"


def test_products_csv_has_expected_columns():
    path = KB_ROOT / PRODUCTS_CSV
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["sku", "nom", "categorie", "prix_dt", "disponibilite", "caracteristiques", "description"]


def test_products_csv_skus_are_unique():
    path = KB_ROOT / PRODUCTS_CSV
    with open(path, encoding="utf-8") as f:
        skus = [row["sku"] for row in csv.DictReader(f)]
    assert len(skus) == len(set(skus)), "Des SKU sont dupliqués dans produits.csv"


def test_products_csv_prices_are_valid():
    path = KB_ROOT / PRODUCTS_CSV
    with open(path, encoding="utf-8") as f:
        prices = [float(row["prix_dt"]) for row in csv.DictReader(f)]
    assert all(p > 0 for p in prices), "Au moins un prix est <= 0 dans produits.csv"


def test_readme_exists():
    assert (KB_ROOT / "README.md").is_file()
