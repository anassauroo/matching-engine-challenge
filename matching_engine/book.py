"""Livro simples: listas por lado e ordenação ao consultar."""

from itertools import zip_longest

from .order import LimitOrder, format_price


class OrderBook:
    def __init__(self) -> None:
        self._buys: list[LimitOrder] = []
        self._sells: list[LimitOrder] = []
        self._next_id = 1

    def add_limit(self, side: str, price_cents: int, quantity: int) -> LimitOrder:
        if side not in ("buy", "sell"):
            raise ValueError("Lado deve ser buy ou sell.")
        if type(price_cents) is not int or price_cents <= 0:
            raise ValueError("Preço em centavos deve ser inteiro positivo.")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Quantidade deve ser inteira positiva.")
        order = LimitOrder(self._next_id, side, price_cents, quantity, self._next_id)
        (self._buys if side == "buy" else self._sells).append(order)
        self._next_id += 1
        return order

    def buy_orders(self) -> list[LimitOrder]:
        return sorted(self._buys, key=lambda order: (-order.price_cents, order.arrival_sequence))

    def sell_orders(self) -> list[LimitOrder]:
        return sorted(self._sells, key=lambda order: (order.price_cents, order.arrival_sequence))

    def render(self) -> str:
        def describe(order: LimitOrder) -> str:
            return f"{order.quantity} @ {format_price(order.price_cents)} id {order.id}"

        buys = [describe(order) for order in self.buy_orders()]
        sells = [describe(order) for order in self.sell_orders()]
        width = max(len("Ordens de Compra"), *(len(row) for row in buys)) if buys else len("Ordens de Compra")
        lines = [f"{'Ordens de Compra':<{width}} | Ordens de Venda", f"{'-' * width}-|-----------------"]
        for buy, sell in zip_longest(buys, sells, fillvalue=""):
            lines.append(f"{buy:<{width}} | {sell}")
        return "\n".join(lines)
