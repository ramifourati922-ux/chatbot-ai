"""
Purge de rétention (proposition, contre-mesure D7) : supprime les messages et
conversations plus anciens que N jours, puis les clients sans conversation.
Les commandes sont conservées, détachées du client (orders.user_id ON DELETE
SET NULL). Par défaut : simulation (comptage seul) ; --apply pour supprimer.

    python scripts/purge_retention.py --days 365            # simulation
    python scripts/purge_retention.py --days 365 --apply

La durée N est une décision de l'entreprise (et de la déclaration à
l'INPDP), pas du code : 365 n'est qu'un exemple.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, exists, func, select  # noqa: E402

from app.db.database import AsyncSessionLocal  # noqa: E402
from app.models.conversation import Conversation, Message  # noqa: E402
from app.models.user import User  # noqa: E402


async def purge(days: int, apply: bool) -> None:
    limit = datetime.now(timezone.utc) - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        # Conversation ancienne = dernière activité (ended_at, sinon started_at) avant la limite
        last = func.coalesce(Conversation.ended_at, Conversation.started_at)
        old = select(Conversation.id).where(last < limit)
        n_conv = await db.scalar(select(func.count()).select_from(old.subquery()))
        n_msg = await db.scalar(select(func.count()).where(Message.conversation_id.in_(old)))
        orphan = ~exists().where(Conversation.user_id == User.id, last >= limit)
        n_users = await db.scalar(select(func.count()).select_from(User).where(orphan, User.created_at < limit))
        print(f"avant le {limit:%d/%m/%Y} : {n_conv} conversations, {n_msg} messages, {n_users} clients")
        if not apply:
            print("simulation : rien n'est supprimé (--apply pour supprimer)")
            return
        await db.execute(delete(Message).where(Message.conversation_id.in_(old)))
        await db.execute(delete(Conversation).where(last < limit))
        await db.execute(delete(User).where(orphan, User.created_at < limit))
        await db.commit()
        print("supprimé")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    asyncio.run(purge(a.days, a.apply))
