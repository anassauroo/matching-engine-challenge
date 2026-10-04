"""Representação das ordens e conversão exata de preços."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
import re


def parse_price(text: str) -> int:
    """Converte preço decimal positivo com até duas casas em centavos."""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?|\.[0-9]{1,2}", text):
        raise ValueError("Preço deve ser positivo e finito, com ponto e até duas casas decimais.")
    price = Decimal(text)
    if not price.is_finite() or price <= 0:
        raise ValueError("Preço deve ser positivo e finito.")
    # A precisão local também preserva preços com mais de 28 dígitos.
    with localcontext() as context:
        context.prec = len(text) + 2
        return int(price * 100)


def format_price(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


@dataclass(frozen=True)
class LimitOrder:
    id: int
    side: str
    price_cents: int
    quantity: int
    arrival_sequence: int


@dataclass(frozen=True)
class Trade:
    price_cents: int
    quantity: int
    buy_order_id: int
    sell_order_id: int
