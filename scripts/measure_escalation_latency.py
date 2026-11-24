"""
Latence de bout en bout des trois déclencheurs d'escalade à règles
(demande explicite, frustration, suivi de commande), mesurée sur POST /chat/.

1. Sélection : messages de data/intents/test.json que la règle concernée
   détecte RÉELLEMENT (IntentClassifier, sans LLM). Peu de messages sont
   détectés : chacun est réutilisé, dans une session neuve à chaque fois,
   jusqu'à N_CALLS appels par catégorie.
2. Mesure : un appel POST /chat/ par message (session neuve attribuée par le
   serveur), chronométré côté client (time.perf_counter, réponse complète).
   Suivi de commande : le transfert n'a lieu qu'au 2e message sans numéro
   valide (1er message = relance) ; on mesure le 2e, et la relance à part.
   Appels espacés pour rester sous la limite de débit (RATE_LIMIT_CHAT).
3. Vérification : escalated / escalation_reason dans la réponse, réponse
   identique au message fixe d'escalade (pas d'appel au LLM), puis
   conversation au statut « escalated » et motif enregistré en base.
4. Nettoyage : suppression des seules lignes créées (users par external_id
   exact, leurs conversations et messages, par identifiant) et des sessions
   Redis correspondantes ; relecture pour confirmer.

Usage (API démarrée sur http://127.0.0.1:8000) :
    python scripts/measure_escalation_latency.py
"""
import asyncio
import json
import platform
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import numpy as np  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.database import AsyncSessionLocal  # noqa: E402
from app.models.conversation import Conversation, Message  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.dialogue_manager import _get_escalation_message  # noqa: E402
from app.services.intent_classifier import IntentClassifier  # noqa: E402
from app.services.language_detector import detect_language  # noqa: E402

URL = "http://127.0.0.1:8000/chat/"
N_CALLS = 20
SPACING_S = 3.2  # 20 requêtes / minute / IP au maximum
OUT_MD = ROOT / "docs" / "evaluation" / "latence_declencheurs.md"
OUT_JSON = ROOT / "docs" / "evaluation" / "latence_declencheurs.json"
CATS = {"explicit": "human_agent", "frustration": "frustration", "order_tracking": "order_tracking"}
LABEL = {"explicit": "Demande explicite", "frustration": "Frustration", "order_tracking": "Suivi de commande"}


def select_messages():
    clf = IntentClassifier()
    msgs = json.loads((ROOT / "data" / "intents" / "test.json").read_text(encoding="utf-8"))["messages"]
    out = {c: [] for c in CATS}
    for m in msgs:
        r = clf.classify(m["text"])
        if r.requires_escalation and r.escalation_reason in ("explicit", "frustration") and m["intent"] == CATS[r.escalation_reason]:
            out[r.escalation_reason].append(m["text"])
        elif r.intent == "order_tracking" and m["intent"] == "order_tracking" and not (r.entities or {}).get("order_reference"):
            out["order_tracking"].append(m["text"])
    return out


class Bench:
    def __init__(self):
        self.client = httpx.Client(timeout=60)
        self.sessions = []  # session_id renvoyés par le serveur (sans préfixe "web:")
        self.last = 0.0

    def post(self, text, session=None):
        wait = SPACING_S - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        body = {"message": text, "channel": "web"}
        if session:
            body["session_id"], body["session_signature"] = session
        t0 = time.perf_counter()
        r = self.client.post(URL, json=body)
        ms = (time.perf_counter() - t0) * 1000
        self.last = time.monotonic()
        r.raise_for_status()
        data = r.json()
        if data["session_id"] not in self.sessions:
            self.sessions.append(data["session_id"])
        return ms, data


def stats(values):
    return {"n": len(values), "mediane": round(statistics.median(values), 1),
            "p95": round(float(np.percentile(values, 95)), 1), "min": round(min(values), 1), "max": round(max(values), 1)}


async def db_check(session_ids):
    ext = [f"web:{s}" for s in session_ids]
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User).where(User.external_id.in_(ext)))).scalars().all()
        uids = [u.id for u in users]
        convs = (await db.execute(select(Conversation).where(Conversation.user_id.in_(uids)))).scalars().all() if uids else []
        cids = [c.id for c in convs]
        msgs = (await db.execute(select(Message).where(Message.conversation_id.in_(cids)))).scalars().all() if cids else []
        by_user = {u.id: u.external_id[4:] for u in users}
        info = {}
        for c in convs:
            reasons = [(m.metadata_ or {}).get("escalation_reason")
                       for m in msgs if m.conversation_id == c.id and m.role == "assistant"]
            info[by_user[c.user_id]] = {"statut": c.status, "motifs": [x for x in reasons if x]}
        return {"users": [str(u) for u in uids], "conversations": [str(c) for c in cids],
                "messages": len(msgs), "par_session": info}


async def cleanup(session_ids):
    ext = [f"web:{s}" for s in session_ids]
    async with AsyncSessionLocal() as db:
        uids = (await db.execute(select(User.id).where(User.external_id.in_(ext)))).scalars().all()
        cids = (await db.execute(select(Conversation.id).where(Conversation.user_id.in_(uids)))).scalars().all() if uids else []
        n_m = (await db.execute(delete(Message).where(Message.conversation_id.in_(cids)))).rowcount if cids else 0
        n_c = (await db.execute(delete(Conversation).where(Conversation.id.in_(cids)))).rowcount if cids else 0
        n_u = (await db.execute(delete(User).where(User.id.in_(uids)))).rowcount if uids else 0
        await db.commit()
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL)
    keys = [f"session:web:{s}" for s in session_ids]
    n_r = await r.delete(*keys) if keys else 0
    left_r = sum([await r.exists(k) for k in keys])
    await r.aclose()
    after = await db_check(session_ids)
    return {"supprimes": {"messages": n_m, "conversations": n_c, "users": n_u, "sessions_redis": n_r},
            "restants": {"users": len(after["users"]), "conversations": len(after["conversations"]),
                         "messages": after["messages"], "sessions_redis": left_r}}


def main():
    selected = select_messages()
    for c, ms in selected.items():
        print(f"{c} : {len(ms)} messages détectés {dict(Counter(detect_language(m) for m in ms))}", flush=True)
        if not ms:
            sys.exit(f"aucun message détecté pour {c}")

    b = Bench()
    for _ in range(2):  # échauffement, non compté
        b.post("bonjour")
    results, samples = {}, {}
    relance = []
    for cat, msgs in selected.items():
        times, server_ms, ok, fixed, langs = [], [], 0, 0, Counter()
        for i in range(N_CALLS):
            text = msgs[i % len(msgs)]
            lang = detect_language(text)
            if cat == "order_tracking":
                ms1, d1 = b.post(text)  # relance
                relance.append(ms1)
                ms, d = b.post(text, (d1["session_id"], d1["session_signature"]))
            else:
                ms, d = b.post(text)
            times.append(ms)
            server_ms.append(d["processing_time_ms"])
            langs[lang] += 1
            ok += bool(d["escalated"] and d["escalation_reason"] == cat)
            fixed += d["response"] == _get_escalation_message(cat, lang) and not d["sources"]
            samples.setdefault(cat, {"message": text, "reponse": d["response"], "intent": d["intent"],
                                     "escalation_reason": d["escalation_reason"]})
        results[cat] = {"client_ms": stats(times), "serveur_ms": stats(server_ms),
                        "messages_distincts": len(msgs), "langues_appels": dict(langs),
                        "langues_messages": dict(Counter(detect_language(m) for m in msgs)),
                        "escalades_confirmees_reponse": ok, "reponse_fixe_sans_llm": fixed}
        print(cat, results[cat], flush=True)

    # liste exacte des sessions créées, sauvegardée AVANT tout accès à la base
    OUT_JSON.with_name("latence_declencheurs_sessions.json").write_text(json.dumps(b.sessions), encoding="utf-8")
    time.sleep(3)  # écritures PostgreSQL en tâche de fond

    async def post_process():  # une seule boucle asyncio pour la base
        before = await db_check(b.sessions)
        return before, await cleanup(b.sessions)
    db_before, clean = asyncio.run(post_process())
    print("vérification base :", len(db_before["users"]), "users,", len(db_before["conversations"]), "conversations",
          flush=True)
    print("nettoyage :", clean, flush=True)

    R = {"selection": selected, "resultats": results, "relance_suivi_ms": stats(relance), "exemples": samples,
         "base_avant_nettoyage": {"users": len(db_before["users"]), "conversations": len(db_before["conversations"]),
                                  "messages": db_before["messages"],
                                  "statuts": dict(Counter(v["statut"] for v in db_before["par_session"].values())),
                                  "motifs": dict(Counter(m for v in db_before["par_session"].values() for m in v["motifs"]))},
         "nettoyage": clean, "sessions_creees": len(b.sessions),
         "versions": {"python": platform.python_version(), "httpx": httpx.__version__}}
    OUT_JSON.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: R[k] for k in ("base_avant_nettoyage", "nettoyage", "relance_suivi_ms")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
