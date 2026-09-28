"""
Nettoyage des données de test de la base de démo (PostgreSQL + Redis).

Les tests d'intégration et les vérifications manuelles laissent des
utilisateurs, conversations et sessions dans la base locale (voir la
limite « Suite de tests » du README). Ce script ne supprime QUE ce qui
correspond à une règle explicite, jamais la base entière :

    - identifiant commençant par "diag-" ou "test-" (avec ou sans le
      préfixe de session web "web:") ;
    - numéro WhatsApp fictif 216000000xx (avec ou sans "web:") ;
    - identifiants passés explicitement avec --id (cas ponctuels
      identifiés à la main, ex. une session /chat-demo de test).

Côté PostgreSQL, la suppression d'un utilisateur supprime ses
conversations et leurs messages (clés étrangères ON DELETE CASCADE).
Côté Redis, les clés session:<identifiant> correspondantes.

Par défaut, simulation : affiche ce qui serait supprimé. --apply
supprime réellement.

    python scripts/cleanup_test_data.py                 # simulation
    python scripts/cleanup_test_data.py --apply
    python scripts/cleanup_test_data.py --id <uuid> --id <uuid> --apply
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
import redis

from app.config import settings

TEST_ID_PATTERN = re.compile(r"^(web:)?(diag-|test-|216000000\d{2}$)")
SESSION_PREFIX = "session:"


def is_test_id(external_id: str, extra_ids: set) -> bool:
    bare = external_id.removeprefix("web:")
    return bool(TEST_ID_PATTERN.match(external_id)) or external_id in extra_ids or bare in extra_ids


async def clean_postgres(extra_ids: set, apply: bool) -> None:
    db = await asyncpg.connect(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        users = await db.fetch("""
            select u.id, u.external_id, u.channel,
                   count(distinct c.id) as convs, count(m.id) as msgs
            from users u
            left join conversations c on c.user_id = u.id
            left join messages m on m.conversation_id = c.id
            group by u.id order by u.created_at""")
        targets = [u for u in users if u["external_id"] and is_test_id(u["external_id"], extra_ids)]
        print(f"PostgreSQL : {len(targets)} utilisateur(s) de test sur {len(users)}, "
              f"{sum(u['convs'] for u in targets)} conversation(s), {sum(u['msgs'] for u in targets)} message(s)")
        for u in targets:
            print(f"  - {u['channel']:9} {u['external_id']} ({u['convs']} conv., {u['msgs']} msg.)")
        missing = extra_ids - {u["external_id"] for u in users} - {u["external_id"].removeprefix("web:") for u in users if u["external_id"]}
        for ext in sorted(missing):
            print(f"  ? --id {ext} : aucun utilisateur correspondant en base")

        if apply and targets:
            async with db.transaction():
                deleted = await db.execute("delete from users where id = any($1::uuid[])", [u["id"] for u in targets])
            print(f"  → supprimé : {deleted}")
        orphan_convs = await db.fetchval(
            "select count(*) from conversations c left join users u on u.id = c.user_id where u.id is null")
        orphan_msgs = await db.fetchval(
            "select count(*) from messages m left join conversations c on c.id = m.conversation_id where c.id is null")
        print(f"  Orphelins : {orphan_convs} conversation(s), {orphan_msgs} message(s)")
    finally:
        await db.close()


def clean_redis(extra_ids: set, apply: bool) -> None:
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    keys = sorted(r.scan_iter(f"{SESSION_PREFIX}*"))
    targets = [k for k in keys if is_test_id(k.removeprefix(SESSION_PREFIX), extra_ids)]
    print(f"Redis : {len(targets)} session(s) de test sur {len(keys)}")
    for k in targets:
        print(f"  - {k}")
    if apply and targets:
        print(f"  → supprimé : {r.delete(*targets)} clé(s)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="supprimer réellement (sinon simulation)")
    parser.add_argument("--id", action="append", default=[], dest="ids",
                        help="identifiant externe supplémentaire à supprimer (répétable)")
    args = parser.parse_args()
    extra_ids = set(args.ids)

    print("=== SUPPRESSION ===" if args.apply else "=== SIMULATION (rien n'est supprimé, --apply pour supprimer) ===")
    asyncio.run(clean_postgres(extra_ids, args.apply))
    clean_redis(extra_ids, args.apply)


if __name__ == "__main__":
    main()
