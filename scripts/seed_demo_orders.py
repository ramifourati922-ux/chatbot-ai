"""
Commandes fictives pour tester le suivi de commande en conditions
réalistes (un statut par commande), rattachées au client de démo
"test-demo-client".

Le préfixe "test-" permet à scripts/cleanup_test_data.py de retrouver ce
client et de supprimer ses commandes. Relançable : les commandes déjà
présentes ne sont pas recréées.

    python scripts/seed_demo_orders.py

Puis, dans le chat : « où est ma commande CMD-2026-00103 ? »
"""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.order import Order
from app.models.user import User

DEMO_CUSTOMER = "test-demo-client"
TODAY = date.today()

DEMO_ORDERS = [
    ("CMD-2026-00101", "recue", [("Arduino Uno R3", 1), ("Câble USB-B (1 m)", 1)], "62.40", TODAY + timedelta(days=5)),
    ("CMD-2026-00102", "en_preparation", [("Kit capteurs 37 en 1", 1)], "118.90", TODAY + timedelta(days=4)),
    ("CMD-2026-00103", "expediee", [("Capteur DHT22", 2), ("Module relais 5V", 1)], "47.80", TODAY + timedelta(days=2)),
    ("CMD-2026-00104", "livree", [("Imprimante 3D Ender-3 V2", 1)], "2368.82", TODAY - timedelta(days=3)),
    ("CMD-2026-00105", "annulee", [("ESP32 DevKit V1", 3)], "89.70", None),
]


async def main():
    async with AsyncSessionLocal() as db:
        customer = (await db.execute(select(User).where(User.external_id == DEMO_CUSTOMER))).scalar_one_or_none()
        if customer is None:
            customer = User(external_id=DEMO_CUSTOMER, channel="web", display_name="Client de démo")
            db.add(customer)
            await db.flush()
        created = 0
        for number, status, items, total, eta in DEMO_ORDERS:
            if await db.scalar(select(Order).where(Order.order_number == number)):
                print(f"  = {number} existe déjà")
                continue
            db.add(Order(
                order_number=number, user_id=customer.id, status=status, total=Decimal(total),
                items=[{"name": name, "quantity": qty} for name, qty in items], estimated_delivery=eta,
            ))
            created += 1
            print(f"  + {number} : {status}")
        await db.commit()
    print(f"{created} commande(s) créée(s) pour le client de démo « {DEMO_CUSTOMER} ».")


if __name__ == "__main__":
    asyncio.run(main())
