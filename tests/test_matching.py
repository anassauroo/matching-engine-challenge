from io import StringIO
from unittest import TestCase, main

from matching_engine.book import OrderBook
from matching_engine.cli import execute


class MatchingTests(TestCase):
    def test_buy_consumes_best_prices_then_oldest_order(self):
        book = OrderBook()
        book.add_limit("sell", 1100, 20)  # id 1: pior preço, apesar de mais antiga
        book.add_limit("sell", 1000, 30)  # id 2
        book.add_limit("sell", 1000, 40)  # id 3
        book.add_limit("sell", 1200, 50)  # id 4: fora do limite
        incoming, trades = book.add_limit("buy", 1100, 80)
        self.assertEqual([(t.sell_order_id, t.price_cents, t.quantity) for t in trades],
                         [(2, 1000, 30), (3, 1000, 40), (1, 1100, 10)])
        self.assertTrue(all(t.buy_order_id == incoming.id for t in trades))
        self.assertEqual([(o.id, o.quantity) for o in book.sell_orders()], [(1, 10), (4, 50)])
        self.assertEqual(book.buy_orders(), [])
        self.assertEqual(sum(t.quantity for t in trades), incoming.quantity)

    def test_sell_consumes_highest_bids_and_respects_limit(self):
        book = OrderBook()
        book.add_limit("buy", 900, 20)
        book.add_limit("buy", 1100, 30)
        book.add_limit("buy", 1100, 40)
        book.add_limit("buy", 1000, 50)
        incoming, trades = book.add_limit("sell", 1000, 150)
        self.assertEqual([(t.buy_order_id, t.price_cents, t.quantity) for t in trades],
                         [(2, 1100, 30), (3, 1100, 40), (4, 1000, 50)])
        self.assertTrue(all(t.sell_order_id == incoming.id for t in trades))
        self.assertEqual([(o.id, o.quantity) for o in book.buy_orders()], [(1, 20)])
        residual = book.sell_orders()[0]
        self.assertEqual((residual.id, residual.price_cents, residual.quantity,
                          residual.arrival_sequence), (incoming.id, 1000, 30, incoming.arrival_sequence))
        self.assertEqual(sum(t.quantity for t in trades) + residual.quantity, incoming.quantity)

    def test_equal_price_and_partial_fill_preserve_fifo(self):
        for incoming_side, resting_side in [("buy", "sell"), ("sell", "buy")]:
            with self.subTest(side=incoming_side):
                book = OrderBook()
                first, _ = book.add_limit(resting_side, 1000, 100)
                second, _ = book.add_limit(resting_side, 1000, 100)
                _, trades = book.add_limit(incoming_side, 1000, 40)
                self.assertEqual([(t.price_cents, t.quantity) for t in trades], [(1000, 40)])
                orders = book.sell_orders() if resting_side == "sell" else book.buy_orders()
                self.assertEqual([(o.id, o.quantity, o.arrival_sequence) for o in orders],
                                 [(first.id, 60, first.arrival_sequence),
                                  (second.id, 100, second.arrival_sequence)])
                _, trades = book.add_limit(incoming_side, 1000, 80)
                ids = [t.sell_order_id if resting_side == "sell" else t.buy_order_id for t in trades]
                self.assertEqual(ids, [first.id, second.id])
                self.assertEqual([t.quantity for t in trades], [60, 20])

    def test_no_compatible_price_and_empty_book(self):
        book = OrderBook()
        _, trades = book.add_limit("buy", 1000, 10)
        self.assertEqual(trades, [])
        _, trades = book.add_limit("sell", 1001, 20)
        self.assertEqual(trades, [])
        self.assertEqual([o.quantity for o in book.buy_orders()], [10])
        self.assertEqual([o.quantity for o in book.sell_orders()], [20])

    def test_invalid_orders_do_not_execute_or_consume_ids(self):
        book = OrderBook()
        book.add_limit("sell", 1000, 100)
        before = book.render()
        for side, price, quantity in [("bad", 1000, 1), ("buy", 0, 1),
                                      ("buy", 1000, 0), ("buy", 1000, 1.5),
                                      ("buy", True, 1), ("buy", 1000, True)]:
            with self.subTest(side=side, price=price, quantity=quantity):
                with self.assertRaises(ValueError):
                    book.add_limit(side, price, quantity)
                self.assertEqual(book.render(), before)
        output = StringIO()
        execute("limit buy 10 2 extra", book, output)
        self.assertIn("Erro:", output.getvalue())
        self.assertEqual(book.render(), before)
        order, trades = book.add_limit("buy", 1000, 10)
        self.assertEqual(order.id, 2)
        self.assertEqual(trades[0].quantity, 10)

    def test_cli_reports_each_trade_and_renders_only_remaining_quantity(self):
        book, output = OrderBook(), StringIO()
        for line in ["limit sell 10 30", "limit sell 11 40", "limit buy 11 100", "print book"]:
            execute(line, book, output)
        self.assertIn("Order created: buy 100 @ 11.00 id 3\n"
                      "Trade, price: 10.00, qty: 30\n"
                      "Trade, price: 11.00, qty: 40\n", output.getvalue())
        self.assertIn("30 @ 11.00 id 3", book.render())
        self.assertEqual(book.sell_orders(), [])


if __name__ == "__main__":
    main()
