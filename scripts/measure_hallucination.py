"""
Remarque 46 : interception des questions de suivi de commande et taux
d'hallucination sur un jeu de questions (data/evaluation/hallucination.json).

    python scripts/measure_hallucination.py plan     # chemin prévu, sans LLM
    python scripts/measure_hallucination.py run      # POST /chat/ (API locale)
    python scripts/measure_hallucination.py report   # taux, après jugement manuel

plan   : classifieur à règles + recherche (comme dialogue_manager) pour
         prévoir le chemin (règle / seuil / LLM) et annoncer le nombre
         d'appels LLM. Aucun appel LLM.
run    : 8 messages de la partie A2, puis les questions du jeu, une session
         neuve par message (POST /chat/, pipeline réel), appels espacés de
         3,2 s (limite RATE_LIMIT_CHAT). 2e génération pour les questions
         arrivées au LLM (variabilité). Chemin lu dans la base : un message
         du bot avec « llm_ms » dans ses métadonnées = LLM appelé. Contexte
         récupéré recalculé (recherche déterministe) pour la détection
         automatique. Nettoyage : lignes PostgreSQL et sessions Redis créées,
         par identifiant exact (measure_escalation_latency.cleanup).
report : lit le jugement manuel (docs/evaluation/hallucination_jugement.json),
         calcule les taux et les intervalles de Wilson à 95 %.
"""
import asyncio
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATASET = ROOT / "data" / "evaluation" / "hallucination.json"
OUT_RUN = ROOT / "docs" / "evaluation" / "hallucination_reponses.json"
JUDGE = ROOT / "docs" / "evaluation" / "hallucination_jugement.json"
OUT_RATES = ROOT / "docs" / "evaluation" / "hallucination_taux.json"
A2_MESSAGES = ["Où est ma commande #CMD12345 ?", "Où est ma commande ?", "Where is my order #CMD12345?",
               "وين طلبيتي #CMD12345 ؟", "win commande mte3i #CMD12345 ?", "suivi de ma commande CMD12345",
               "#CMD12345", "ma commande n'est pas arrivée"]

# Détection automatique (signalement, pas verdict), règles fixées avant la mesure
FLAGS = {
    "numero": r"\b(?:CMD[-\s]?\d[\d-]*|[A-Z]{2,}[-]?\d{5,})\b",
    "date": (r"\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b|\b\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|"
             r"septembre|octobre|novembre|décembre|january|february|march|april|may|june|july|august|september|"
             r"october|november|december)\b|\b(?:demain|tomorrow|ghodwa|غدا)\b"),
    "montant": r"\b\d+(?:[.,]\d+)?\s?(?:DT|TND|dinars?|€|\$|دينار)",
    "quantite": r"\b\d+\s?(?:unités?|pièces?|units?|pcs|قطعة|قطع)\b",
    "statut": (r"\b(?:expédiée?s?|livrée?s?|en cours de livraison|en préparation|shipped|delivered|in transit|"
               r"out for delivery)\b|تم الشحن|تم التوصيل|في الطريق"),
}


def norm(s):
    return re.sub(r"\s+", " ", s.lower())


def auto_flags(response, question, context):
    base = norm(question + " " + context)
    out = []
    for fam, pat in FLAGS.items():
        for m in re.finditer(pat, response, re.IGNORECASE):
            tok = norm(m.group(0))
            num = re.sub(r"\D", "", tok)
            if tok in base or (num and len(num) >= 2 and num in re.sub(r"\D", " ", base).split()):
                continue
            out.append({"famille": fam, "texte": m.group(0)})
    return out


def rag_query(message):
    from app.config import settings
    from app.services import arabizi
    from app.services.language_detector import detect_language
    if detect_language(message) == "tn" and settings.RAG_ARABIZI_EXPANSION:
        return arabizi.expand(message)
    return message


def predicted_path(message):
    from app.config import settings
    from app.services.intent_classifier import Category, IntentClassifier
    from app.services.rag import retriever
    r = IntentClassifier().classify(message)
    if r.requires_escalation:
        return f"règle (escalade {r.escalation_reason})", None
    if r.category == Category.ORDER_TRACKING:
        return "règle (suivi de commande)", None
    if r.category != Category.GENERAL:
        return f"règle ({r.intent})", None
    hits = retriever.search(rag_query(message), 4)
    conf = retriever.get_best_confidence(hits)
    if conf < retriever.get_confidence_threshold(hits):
        return "seuil de confiance", round(conf, 3)
    return "LLM", round(conf, 3)


def plan():
    from app.config import settings
    settings.RAG_RETRIEVAL_MODE = "advanced"
    qs = json.loads(DATASET.read_text(encoding="utf-8"))["questions"]
    n_llm = 0
    for label, items in (("A2", [{"id": f"a2-{i}", "question": m} for i, m in enumerate(A2_MESSAGES)]), ("B", qs)):
        for q in items:
            p, c = predicted_path(q["question"])
            n_llm += p == "LLM"
            print(f"{label} {q['id']:28s} {p:28s} conf={c} | {q['question']}", flush=True)
    n_b_llm = sum(1 for q in qs if predicted_path(q["question"])[0] == "LLM")
    print(f"\nAppels /chat/ : {len(A2_MESSAGES)} (A2) + {len(qs)} (B) + {n_b_llm} (2e génération B)"
          f"\nAppels LLM prévus : {n_llm} (A2 + B, 1re génération) + {n_b_llm} (2e génération) = {n_llm + n_b_llm}")


async def read_paths(sessions):
    """Métadonnées du message du bot de chaque session (llm_ms = LLM appelé)."""
    from sqlalchemy import select
    from app.db.database import AsyncSessionLocal
    from app.models.conversation import Conversation, Message
    from app.models.user import User
    out = {}
    async with AsyncSessionLocal() as db:
        for s in sessions:
            u = (await db.execute(select(User).where(User.external_id == f"web:{s}"))).scalars().first()
            if not u:
                continue
            cids = (await db.execute(select(Conversation.id).where(Conversation.user_id == u.id))).scalars().all()
            msgs = (await db.execute(select(Message).where(Message.conversation_id.in_(cids), Message.role == "assistant")
                                     )).scalars().all() if cids else []
            out[s] = [m.metadata_ or {} for m in msgs]
    return out


def path_from(meta, d):
    if any("llm_ms" in m for m in meta):
        return "LLM"
    if d["escalation_reason"] == "low_rag_confidence":
        return "seuil de confiance"
    if d["intent"] == "order_tracking":
        return "règle (suivi de commande)" + (" → transfert" if d["escalated"] else "")
    if d["escalated"]:
        return f"règle (escalade {d['escalation_reason']})"
    return f"autre ({d['intent']})"


async def read_all(sessions):
    """Pour chaque session : message client et réponse du bot (texte + métadonnées)."""
    from sqlalchemy import select
    from app.db.database import AsyncSessionLocal
    from app.models.conversation import Conversation, Message
    from app.models.user import User
    out = {}
    async with AsyncSessionLocal() as db:
        for s in sessions:
            u = (await db.execute(select(User).where(User.external_id == f"web:{s}"))).scalars().first()
            if not u:
                continue
            cids = (await db.execute(select(Conversation.id).where(Conversation.user_id == u.id))).scalars().all()
            msgs = (await db.execute(select(Message).where(Message.conversation_id.in_(cids)).order_by(Message.created_at)
                                     )).scalars().all() if cids else []
            out[s] = [{"role": m.role, "content": m.content, "meta": m.metadata_ or {}} for m in msgs]
    return out


def finalize(sessions, t_start):
    """Une seule boucle asyncio : relecture complète en base, PUIS nettoyage par identifiants."""
    import hashlib
    from app.config import settings
    from app.services.rag import retriever
    from scripts.measure_escalation_latency import cleanup
    settings.RAG_RETRIEVAL_MODE = "advanced"
    qs = {q["question"]: q for q in json.loads(DATASET.read_text(encoding="utf-8"))["questions"]}
    a2 = {m: i for i, m in enumerate(A2_MESSAGES)}

    async def go():
        return await read_all(sessions), await cleanup(sessions)
    data, clean = asyncio.run(go())
    rows, seen, a2_done = [], defaultdict(int), set()
    for s in sessions:
        msgs = data.get(s, [])
        user = next((m["content"] for m in msgs if m["role"] == "user"), None)
        bot = next((m for m in msgs if m["role"] == "assistant"), None)
        if user is None or bot is None or user == "bonjour":
            continue
        meta = bot["meta"]
        d = {"response": bot["content"], "session_id": s, "intent": meta.get("intent"),
             "confidence": meta.get("confidence"), "sources": meta.get("sources"), "escalated": meta.get("escalated"),
             "escalation_reason": meta.get("escalation_reason"), "llm_ms": meta.get("llm_ms")}
        if user in a2 and user not in a2_done:  # A2 envoyé avant B : 1re occurrence = A2
            a2_done.add(user)
            row = {"partie": "A2", "id": f"a2-{a2[user]}", "question": user, "generation": 1}
        elif user in qs and seen[user] < 2:
            seen[user] += 1
            q = qs[user]
            row = {"partie": "B", **{k: q[k] for k in ("id", "langue", "type", "attendu", "question")},
                   "generation": seen[user]}
        else:
            continue
        row["reponse"] = d
        row["chemin"] = path_from([meta], d)
        rows.append(row)
    # A2 et B partagent 2 messages identiques : les sessions A2 viennent en premier (ordre d'envoi)
    for r in rows:
        hits = retriever.search(rag_query(r["question"]), 4) if r["chemin"] == "LLM" else []
        ctx = "\n".join(h["document"] for h in hits)
        r["contexte_sources"] = [h["metadata"].get("source") or h["metadata"].get("sku") for h in hits]
        r["signalements"] = auto_flags(r["reponse"]["response"], r["question"], ctx) if r["chemin"] == "LLM" else []
    out = {"debut": t_start, "fin": time.strftime("%Y-%m-%d %H:%M:%S"),
           "sha256_jeu": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
           "sessions": len(sessions), "appels_llm": sum(r["chemin"] == "LLM" for r in rows),
           "modele_principal": settings.GROQ_MODEL, "modele_secours": settings.GROQ_FALLBACK_MODEL,
           "nettoyage": clean, "lignes": rows}
    OUT_RUN.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("lignes :", len(rows), "| appels LLM :", out["appels_llm"], "| nettoyage :", clean, flush=True)


def run():
    from app.config import settings
    from scripts.measure_escalation_latency import Bench
    settings.RAG_RETRIEVAL_MODE = "advanced"
    qs = json.loads(DATASET.read_text(encoding="utf-8"))["questions"]
    b = Bench()
    b.post("bonjour")  # échauffement (règle : politesse, pas de LLM)
    t_start = time.strftime("%Y-%m-%d %H:%M:%S")
    first = {}
    for m in A2_MESSAGES:
        _, d = b.post(m)
        print("A2", d["intent"], d["escalated"], d["escalation_reason"], "|", d["response"][:100].replace("\n", " "), flush=True)
    for q in qs:
        _, d = b.post(q["question"])
        first[q["id"]] = d
        print("B1", q["id"], d["intent"], d["escalated"], "|", d["response"][:100].replace("\n", " "), flush=True)
    OUT_RUN.with_name("hallucination_sessions.json").write_text(json.dumps(b.sessions), encoding="utf-8")
    # 2e génération : questions dont la 1re réponse vient du LLM (sources RAG, pas d'escalade, pas une règle)
    for q in qs:
        d = first[q["id"]]
        if d["sources"] and not d["escalated"] and d["intent"] != "order_tracking":
            _, d2 = b.post(q["question"])
            print("B2", q["id"], d2["escalated"], "|", d2["response"][:100].replace("\n", " "), flush=True)
    OUT_RUN.with_name("hallucination_sessions.json").write_text(json.dumps(b.sessions), encoding="utf-8")
    time.sleep(3)
    finalize(b.sessions, t_start)


def recover():
    """Reprise après un arrêt du script : relit la base pour les sessions enregistrées, puis nettoie."""
    sessions = json.loads(OUT_RUN.with_name("hallucination_sessions.json").read_text(encoding="utf-8"))
    finalize(sessions, "(reprise : voir journal de la mesure)")


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def report():
    run_ = json.loads(OUT_RUN.read_text(encoding="utf-8"))
    judge = json.loads(JUDGE.read_text(encoding="utf-8"))  # {"id|generation": {"classe": ..., "motif": ...}}
    rows = [r for r in run_["lignes"] if r["partie"] == "B"]
    for r in rows:
        r["classe"] = judge[f"{r['id']}|{r['generation']}"]["classe"]
    g1 = [r for r in rows if r["generation"] == 1]

    def rate(sel):
        n = len(sel)
        k = sum(r["classe"] == "hallucination" for r in sel)
        a = sum(r["classe"] == "ambiguë" for r in sel)
        return {"n": n, "hallucinations": k, "ambigues": a, "taux": round(k / n, 3) if n else None, "wilson95": wilson(k, n),
                "taux_strict_ambigues_comptees": round((k + a) / n, 3) if n else None, "wilson95_strict": wilson(k + a, n)}
    R = {"global_1re_generation": rate(g1),
         "arrivees_au_llm_1re_generation": rate([r for r in g1 if r["chemin"] == "LLM"]),
         "interceptees_1re_generation": rate([r for r in g1 if r["chemin"] != "LLM"]),
         "arrivees_au_llm_2e_generation": rate([r for r in rows if r["generation"] == 2]),
         "par_langue": {lg: rate([r for r in g1 if r["langue"] == lg]) for lg in ("fr", "en", "ar", "tn")},
         "par_type": {}}
    by = defaultdict(list)
    for r in g1:
        by[r["type"].split(" (")[0]].append(r)
    R["par_type"] = {t: rate(v) for t, v in by.items()}
    pairs = defaultdict(dict)
    for r in rows:
        pairs[r["id"]][r["generation"]] = r["classe"]
    R["variabilite"] = {"questions_2_generations": sum(1 for v in pairs.values() if 2 in v),
                        "classe_differente": sum(1 for v in pairs.values() if 2 in v and v[1] != v[2])}
    OUT_RATES.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(R, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"plan": plan, "run": run, "recover": recover, "report": report}[sys.argv[1]]()
