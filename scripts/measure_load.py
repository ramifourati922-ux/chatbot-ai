"""
Remarque 49 : test de charge (clients simultanés) du chat web.

Serveur : le vrai app.main:app, lancé DANS ce processus par uvicorn.Server
(un seul processus, comme le Dockerfile), pour que la sonde de blocage
tourne dans la même boucle d'événements. Point d'entrée : le WebSocket
/ws/{client_id} utilisé par static/chat.html (GET /chat/session pour obtenir
l'identifiant signé, puis un message par connexion, session neuve à chaque
requête : pas d'historique d'une requête à l'autre).

Modifié EN MÉMOIRE seulement (jamais sur disque) :
- limites de débit WebSocket (RATE_LIMIT_WS_MESSAGES, RATE_LIMIT_WS_CONNECTIONS),
  sinon le limiteur de l'API (par IP) renverrait lui-même des refus : tous
  les clients du test partagent l'IP 127.0.0.1 ;
- mode B : dialogue_manager.ask remplacé par une fonction qui dort 0,83 s
  (time.sleep, car ask est exécuté dans un thread par asyncio.to_thread :
  une coroutine asyncio.sleep ne peut pas y être passée) et renvoie un texte fixe.

Sonde de blocage : une tâche de la boucle du serveur dort 10 ms en boucle et
enregistre son retard. Mesures lues en base (retrieval_ms, llm_ms) avant le
nettoyage ; lignes créées supprimées par identifiant exact. Les 429 Groq sont
comptés via le journal de llm_factory (bascule sur le modèle de secours) ;
au premier 429, la montée en charge du mode A s'arrête.

Usage : python scripts/measure_load.py
"""
import asyncio
import json
import logging
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx  # noqa: E402
import numpy as np  # noqa: E402
import uvicorn  # noqa: E402
import websockets  # noqa: E402

from app.config import settings  # noqa: E402

OUT_JSON = ROOT / "data" / "evaluation" / "test_charge.json"
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"
ORIGIN = "http://127.0.0.1:8000"
SEED = 42
LLM_SIM_S = 0.83
B_LEVELS = (1, 5, 10, 20, 50)
A_LEVELS = (1, 5, 10, 20)
A_N1_REQUESTS = 60


class Groq429(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.events = []

    def emit(self, record):
        msg = record.getMessage()
        if "indisponible" in msg or "429" in msg or "RateLimit" in msg:
            self.events.append({"t": time.time(), "rate_limit": ("429" in msg or "RateLimit" in msg),
                                "texte": msg.split("(")[0][:120]})


def pick_questions():
    """20 questions distinctes des bancs, qui passent par le RAG puis le LLM
    (aucune règle, confiance >= seuil), tirées avec une graine fixe."""
    from app.services import arabizi
    from app.services.intent_classifier import Category, IntentClassifier
    from app.services.language_detector import detect_language
    from app.services.rag import retriever
    ev = ROOT / "data" / "evaluation"
    cands = [it[l] for it in json.loads((ev / "recherche.json").read_text(encoding="utf-8"))["questions"]
             for l in ("fr", "en", "ar", "tn") if l in it]
    cands += [it["tn"] for it in json.loads((ev / "recherche_tunisien_nouvelles.json").read_text(encoding="utf-8"))["questions"]]
    cands += [r["question"] for r in json.loads((ROOT / "docs/evaluation/ragas_results.json").read_text(encoding="utf-8"))["results"]
              if r["sources"]]
    cands = sorted(set(cands))
    random.Random(SEED).shuffle(cands)
    clf, chosen = IntentClassifier(), []
    for q in cands:
        if clf.classify(q).category != Category.GENERAL:
            continue
        rq = arabizi.expand(q) if detect_language(q) == "tn" and settings.RAG_ARABIZI_EXPANSION else q
        hits = retriever.search(rq, 4)
        if retriever.get_best_confidence(hits) < retriever.get_confidence_threshold(hits):
            continue
        chosen.append(q)
        if len(chosen) == 20:
            break
    return chosen, len(cands)


async def one_request(http, q):
    t0 = time.perf_counter()
    s = (await http.get(f"{BASE}/chat/session")).json()
    url = f"ws://127.0.0.1:{PORT}/ws/{s['client_id']}?signature={s['signature']}"
    async with websockets.connect(url, origin=ORIGIN, open_timeout=30, max_size=2**22) as ws:
        t1 = time.perf_counter()
        await ws.send(q)
        data = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
        t2 = time.perf_counter()
    return {"client_id": s["client_id"], "question": q, "latence_ms": (t2 - t1) * 1000,
            "connexion_ms": (t1 - t0) * 1000, "serveur_ms": data.get("processing_time_ms"),
            "escalated": data.get("escalated"), "reason": data.get("escalation_reason"),
            "erreur": data.get("error")}


async def palier(http, n, plan, probe):
    queue = asyncio.Queue()
    for q in plan:
        queue.put_nowait(q)
    rows = []

    async def client():
        while True:
            try:
                q = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                rows.append(await one_request(http, q))
            except Exception as e:
                rows.append({"question": q, "erreur": f"{type(e).__name__}: {str(e)[:120]}"})
    probe.clear()
    t0 = time.perf_counter()
    await asyncio.gather(*[client() for _ in range(n)])
    wall = time.perf_counter() - t0
    return rows, wall, list(probe)


def pct(v, p):
    return round(float(np.percentile(v, p)), 1) if v else None


async def main():
    from app.main import app
    from app.services import dialogue_manager
    from app.db.database import AsyncSessionLocal
    from scripts.measure_escalation_latency import cleanup
    from sqlalchemy import text, select
    from app.models.conversation import Conversation, Message
    from app.models.user import User

    questions, n_cands = pick_questions()
    print("questions retenues :", len(questions), "sur", n_cands, flush=True)
    settings.RATE_LIMIT_WS_MESSAGES = "100000/minute"
    settings.RATE_LIMIT_WS_CONNECTIONS = 10000
    h429 = Groq429()
    logging.getLogger("app.services.rag.llm_factory").addHandler(h429)

    async def totals():
        async with AsyncSessionLocal() as db:
            return {t: (await db.execute(text(f"select count(*) from {t}"))).scalar() for t in ("users", "conversations", "messages")}
    before = await totals()
    print("base avant :", before, flush=True)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="on"))
    srv = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.2)

    probe = []

    async def probe_task():
        while True:
            t = time.perf_counter()
            await asyncio.sleep(0.010)
            probe.append((time.perf_counter() - t - 0.010) * 1000)
    ptask = asyncio.create_task(probe_task())

    real_ask = dialogue_manager.ask

    def fake_ask(*a, **k):
        time.sleep(LLM_SIM_S)
        return "Réponse simulée pour le test de charge."

    results, sessions = [], []
    async with httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=200)) as http:
        warm = await one_request(http, "bonjour")  # échauffement (règle : politesse, pas de LLM)
        sessions.append(warm["client_id"])
        for mode, levels in (("B", B_LEVELS), ("A", A_LEVELS)):
            dialogue_manager.ask = fake_ask if mode == "B" else real_ask
            for n in levels:
                n_req = A_N1_REQUESTS if (mode == "A" and n == 1) else 3 * n
                plan = [questions[i % len(questions)] for i in range(n_req)]
                k429 = len([e for e in h429.events if e["rate_limit"]])
                rows, wall, lags = await palier(http, n, plan, probe)
                await asyncio.sleep(3)  # écritures PostgreSQL en tâche de fond
                new429 = [e for e in h429.events[k429:] if e["rate_limit"]] if mode == "A" else []
                sessions += [r["client_id"] for r in rows if r.get("client_id")]
                results.append({"mode": mode, "n": n, "requetes": n_req, "lignes": rows, "duree_palier_s": wall,
                                "sonde_retard_ms": {"n": len(lags), "p95": pct(lags, 95), "max": round(max(lags), 1) if lags else None,
                                                    "mediane": pct(lags, 50)},
                                "groq_429": len(new429), "bascules_llm": len(h429.events) - k429 if mode == "A" else 0})
                lat = [r["latence_ms"] for r in rows if "latence_ms" in r]
                print(f"{mode} N={n}: {len(rows)} req, erreurs {sum(1 for r in rows if 'latence_ms' not in r)}, "
                      f"p50 {pct(lat, 50)} p90 {pct(lat, 90)} max {round(max(lat), 0) if lat else None} ms, "
                      f"palier {wall:.1f}s, sonde p95 {pct(lags, 95)} max {round(max(lags), 1) if lags else None} ms, "
                      f"429 {len(new429)}", flush=True)
                if mode == "A" and new429:
                    print("429 Groq : arrêt de la montée en charge", flush=True)
                    break
        dialogue_manager.ask = real_ask

    # métadonnées (retrieval_ms, llm_ms) puis nettoyage, dans la même boucle
    meta = {}
    async with AsyncSessionLocal() as db:
        for s in set(sessions):
            u = (await db.execute(select(User).where(User.external_id == f"web:{s}"))).scalars().first()
            if not u:
                continue
            cids = (await db.execute(select(Conversation.id).where(Conversation.user_id == u.id))).scalars().all()
            ms = (await db.execute(select(Message).where(Message.conversation_id.in_(cids), Message.role == "assistant"))).scalars().all()
            if ms:
                meta[s] = ms[0].metadata_ or {}
    clean = await cleanup(list(set(sessions)))
    after = await totals()
    print("nettoyage :", clean, "| base après :", after, flush=True)
    ptask.cancel()
    server.should_exit = True
    await srv

    for res in results:
        for r in res["lignes"]:
            m = meta.get(r.get("client_id"), {})
            r["retrieval_ms"], r["llm_ms"] = m.get("retrieval_ms"), m.get("llm_ms")
    out = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "questions": questions, "candidats": n_cands, "graine": SEED,
           "llm_simule_s": LLM_SIM_S, "base_avant": before, "base_apres": after, "nettoyage": clean,
           "groq_evenements": h429.events, "resultats": results,
           "config": {"mode": settings.RAG_RETRIEVAL_MODE, "arabizi": settings.RAG_ARABIZI_EXPANSION,
                      "modele": settings.GROQ_MODEL, "secours": settings.GROQ_FALLBACK_MODEL,
                      "pool_threads_defaut": min(32, (os.cpu_count() or 1) + 4), "cpu_count": os.cpu_count()},
           "versions": {"python": platform.python_version(), "uvicorn": uvicorn.__version__,
                        "websockets": websockets.__version__, "httpx": httpx.__version__}}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("écrit", OUT_JSON, flush=True)



if __name__ == "__main__":
    asyncio.run(main())
