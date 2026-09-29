# app/services/order_tracking.py
"""
Suivi de commande : statut lu en base, jamais généré par le LLM (pas
d'hallucination possible sur un statut ou une date).

Appelé par dialogue_manager quand l'intent est "order_tracking" (voir
intent_classifier). Une seule relance : sans numéro, ou avec un numéro
introuvable, le client est invité à préciser ; si ça se reproduit juste
après, il est transféré à un conseiller (raison "order_tracking").

Messages en 4 langues (fr, en, ar, tn), repli sur le français.
"""

from typing import Optional

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.order import Order

# Clé du contexte de session Redis : une relance a déjà été faite
PROMPTED_CONTEXT_KEY = "order_tracking_prompted"

STATUS_LABELS = {
    "fr": {"recue": "reçue", "en_preparation": "en préparation", "expediee": "expédiée",
           "livree": "livrée", "annulee": "annulée"},
    "en": {"recue": "received", "en_preparation": "being prepared", "expediee": "shipped",
           "livree": "delivered", "annulee": "cancelled"},
    "ar": {"recue": "تم استلامها", "en_preparation": "قيد التحضير", "expediee": "تم شحنها",
           "livree": "تم تسليمها", "annulee": "ملغاة"},
    "tn": {"recue": "t9ablet", "en_preparation": "9a3da tet7adher", "expediee": "tba3thet",
           "livree": "wselt", "annulee": "tlghat"},
}

_TEXTS = {
    "fr": {
        "header": "Commande {number} : {status}.",
        "items": "Articles : {items}",
        "total": "Total : {total} DT",
        "eta": "Livraison estimée : {date}",
        "cancelled": "Pour toute question sur cette annulation, un conseiller peut vous aider.",
        "ask": ("Pour vous donner le statut de votre commande, j'ai besoin de son numéro (format "
                "CMD-2026-00123, indiqué dans l'e-mail de confirmation). Un lien de suivi vous est aussi "
                "envoyé par SMS et e-mail dès l'expédition. Si vous n'avez pas ce numéro, je peux vous "
                "mettre en relation avec un conseiller."),
        "not_found": ("Je ne trouve aucune commande {number}. Pouvez-vous vérifier le numéro (format "
                      "CMD-2026-00123) ? Sinon, je peux vous mettre en relation avec un conseiller."),
    },
    "en": {
        "header": "Order {number}: {status}.",
        "items": "Items: {items}",
        "total": "Total: {total} TND",
        "eta": "Estimated delivery: {date}",
        "cancelled": "If you have any question about this cancellation, an agent can help you.",
        "ask": ("To give you the status of your order, I need its number (format CMD-2026-00123, shown in "
                "your confirmation email). A tracking link is also sent by SMS and email as soon as it ships. "
                "If you don't have this number, I can connect you with an agent."),
        "not_found": ("I can't find any order {number}. Could you check the number (format CMD-2026-00123)? "
                      "Otherwise, I can connect you with an agent."),
    },
    "ar": {
        "header": "الطلبية {number} : {status}.",
        "items": "المنتجات : {items}",
        "total": "المجموع : {total} د.ت",
        "eta": "التسليم المتوقع : {date}",
        "cancelled": "لأي سؤال حول هذا الإلغاء، يمكن لأحد ممثلي خدمة العملاء مساعدتك.",
        "ask": ("لإعطائك حالة طلبيتك، أحتاج إلى رقمها (الصيغة CMD-2026-00123، الموجود في رسالة التأكيد). "
                "كما يُرسل إليك رابط التتبع عبر الرسائل القصيرة والبريد الإلكتروني عند الشحن. "
                "إذا لم يكن لديك هذا الرقم، يمكنني تحويلك إلى أحد ممثلي خدمة العملاء."),
        "not_found": ("لم أجد أي طلبية {number}. هل يمكنك التحقق من الرقم (الصيغة CMD-2026-00123)؟ "
                      "وإلا يمكنني تحويلك إلى أحد ممثلي خدمة العملاء."),
    },
    "tn": {
        "header": "Commande {number} : {status}.",
        "items": "Les articles : {items}",
        "total": "Total : {total} DT",
        "eta": "Livraison mte3ha nhar : {date}",
        "cancelled": "Ken 3andek sou2el 3al annulation, wa7ed conseiller ynajjem y3awnek.",
        "ask": ("Bch na3tik l'etat mta3 commande mte3ek, n7eb noumrou mte3ha (format CMD-2026-00123, "
                "mawjoud fel e-mail mta3 confirmation). Lien de suivi yousel zeda b SMS w e-mail ki tetba3eth. "
                "Ken ma3andekch noumrou, najjem na3addik l conseiller."),
        "not_found": ("Ma l9it 7atta commande {number}. Thabbet fel noumrou (format CMD-2026-00123) ? "
                      "Sinon najjem na3addik l conseiller."),
    },
}


def _texts(language: str) -> dict:
    return _TEXTS.get(language, _TEXTS["fr"])


def format_order(order: Order, language: str) -> str:
    t = _texts(language)
    labels = STATUS_LABELS.get(language, STATUS_LABELS["fr"])
    lines = [t["header"].format(number=order.order_number, status=labels.get(order.status, order.status))]
    items = ", ".join(f"{i.get('quantity', 1)} × {i.get('name', '?')}" for i in (order.items or []))
    if items:
        lines.append(t["items"].format(items=items))
    total = f"{order.total:.2f}"
    lines.append(t["total"].format(total=total.replace(".", ",") if language in ("fr", "tn") else total))
    if order.status not in ("livree", "annulee") and order.estimated_delivery:
        lines.append(t["eta"].format(date=order.estimated_delivery.strftime("%d/%m/%Y")))
    if order.status == "annulee":
        lines.append(t["cancelled"])
    return "\n".join(lines)


def ask_for_number(language: str) -> str:
    return _texts(language)["ask"]


def not_found(number: str, language: str) -> str:
    return _texts(language)["not_found"].format(number=number)


async def find_order(order_number: str) -> Optional[Order]:
    """La commande (numéro déjà normalisé), ou None. Les erreurs de base
    remontent à l'appelant (dialogue_manager transfère alors le client)."""
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(Order).where(Order.order_number == order_number))).scalar_one_or_none()
