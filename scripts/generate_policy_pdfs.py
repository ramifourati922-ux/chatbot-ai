# scripts/generate_policy_pdfs.py
"""
Génère des PDF "professionnels" à partir des fichiers .txt (Q/R) de la
knowledge base — pour affichage/téléchargement client (site web, appli),
PAS comme source pour le RAG.

⚠️ IMPORTANT (RAG) : les fichiers .txt Q/R restent la SOURCE DE VÉRITÉ
utilisée par le pipeline d'ingestion RAG (Tâche 4). Un PDF doit d'abord
être re-converti en texte avant d'être découpé en chunks, ce qui casse
la garantie "un bloc Q/R = un chunk propre" (la conversion PDF→texte
peut fusionner/couper les lignes différemment selon l'outil utilisé).
Le PDF est donc un ARTEFACT DE PRÉSENTATION généré à partir du .txt,
pas un remplacement. Si le contenu .txt change, relance ce script pour
régénérer les PDF à jour.

Usage :
    ./venv/Scripts/python.exe scripts/generate_policy_pdfs.py
"""

import re
from pathlib import Path

from fpdf import FPDF

KB_ROOT = Path(__file__).parent.parent / "data" / "knowledge_base"

DOCS = [
    ("sav/retours.txt", "sav/retours.pdf", "Politique de retour", "Service Après-Vente"),
    ("sav/livraison.txt", "sav/livraison.pdf", "Politique de livraison", "Service Après-Vente"),
    ("sav/garantie.txt", "sav/garantie.pdf", "Politique de garantie", "Service Après-Vente"),
    ("ecommerce/paiement.txt", "ecommerce/paiement.pdf", "Moyens de paiement", "E-commerce"),
    ("ecommerce/promotions.txt", "ecommerce/promotions.pdf", "Promotions & Fidélité", "E-commerce"),
    ("general/faq.txt", "general/faq.pdf", "Foire Aux Questions", "Informations générales"),
]

BRAND_NAME = "Liss Strike"
BRAND_COLOR = (0, 90, 140)   # bleu professionnel
LIGHT_GRAY = (245, 246, 248)
TEXT_GRAY = (90, 90, 90)


def parse_qr_blocks(text: str):
    """Même logique que tests/test_knowledge_base_structure.py::_blocks."""
    body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    qr = []
    for block in blocks:
        m = re.match(r"Q:\s*(.+?)\nR:\s*(.+)", block, re.DOTALL)
        if m:
            qr.append((m.group(1).strip(), m.group(2).strip()))
    return qr


class PolicyPDF(FPDF):
    def __init__(self, titre, sous_titre):
        super().__init__(format="A4")
        self.titre = titre
        self.sous_titre = sous_titre
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        self.set_fill_color(*BRAND_COLOR)
        self.rect(0, 0, 210, 28, style="F")
        self.set_xy(15, 8)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, to_latin1(BRAND_NAME), ln=1)
        self.set_x(15)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, to_latin1(self.sous_titre), ln=1)
        self.ln(8)
        self.set_text_color(30, 30, 30)
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, to_latin1(self.titre), ln=1)
        self.set_draw_color(*BRAND_COLOR)
        self.set_line_width(0.6)
        y = self.get_y() + 1
        self.line(15, y, 195, y)
        self.ln(6)

    def footer(self):
        self.set_y(-18)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, to_latin1(f"{BRAND_NAME} — Service Client"), ln=1, align="C")
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")

    def disclaimer_banner(self):
        self.set_fill_color(255, 244, 214)
        self.set_draw_color(230, 180, 80)
        self.set_text_color(120, 90, 10)
        self.set_font("Helvetica", "B", 9)
        x, y = self.get_x(), self.get_y()
        text = to_latin1("CONTENU D'EXEMPLE — document généré automatiquement pour la démo/les tests du projet. "
                          "À valider et remplacer par les informations réelles de Liss Strike avant toute diffusion aux clients.")
        self.multi_cell(180, 5, text, border=1, fill=True, align="L")
        self.ln(4)
        self.set_text_color(30, 30, 30)

    def qr_block(self, question, reponse):
        self.set_fill_color(*LIGHT_GRAY)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*BRAND_COLOR)
        self.multi_cell(180, 7, f"Q.  {question}", fill=True)
        self.ln(1)
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(40, 40, 40)
        self.multi_cell(180, 6, reponse)
        self.ln(5)


def to_latin1(s: str) -> str:
    """Les polices core PDF (Helvetica) ne supportent que Latin-1 —
    on remplace les caractères hors Latin-1 (tirets typographiques,
    apostrophe courbe, etc.) par leur équivalent ASCII le plus proche."""
    replacements = {
        "’": "'", "‘": "'", "œ": "oe", "€": "EUR",
        "—": "-", "–": "-", "…": "...", "“": '"', "”": '"',
    }
    for src, dst in replacements.items():
        s = s.replace(src, dst)
    return s.encode("latin-1", "replace").decode("latin-1")


def build_pdf(src_relpath, out_relpath, titre, sous_titre):
    src = KB_ROOT / src_relpath
    out = KB_ROOT / out_relpath
    text = src.read_text(encoding="utf-8")
    qr_pairs = parse_qr_blocks(text)

    pdf = PolicyPDF(titre, sous_titre)
    pdf.add_page()
    pdf.disclaimer_banner()
    for question, reponse in qr_pairs:
        pdf.qr_block(to_latin1(question), to_latin1(reponse))

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    print(f"✅ {out.relative_to(KB_ROOT.parent.parent)} ({len(qr_pairs)} questions, {pdf.page_no()} page(s))")


if __name__ == "__main__":
    for src, out, titre, sous_titre in DOCS:
        build_pdf(src, out, titre, sous_titre)
