from io import StringIO
import random
from unittest import TestCase, main

from matching_engine.book import OrderBook
from matching_engine.cli import execute


class MarketTests(TestCase):
    def test_pdf_example_and_partial_execution(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 100)
        book.add_limit("sell", 2000, 100)
        book.add_limit("sell", 2000, 200)
        order, trades, unfilled = book.add_market("buy", 150)
        self.assertEqual(order.id, 4)
        self.assertEqual([(t.sell_order_id, t.quantity) for t in trades], [(2, 100), (3, 50)])
        self.assertEqual(unfilled, 0)
        self.assertEqual([(o.id, o.quantity) for o in book.sell_orders()], [(3, 150)])
        _, trades, unfilled = book.add_market("buy", 200)
        self.assertEqual([(t.price_cents, t.quantity) for t in trades], [(2000, 150)])
        self.assertEqual(unfilled, 50)
        _, trades, unfilled = book.add_market("sell", 200)
        self.assertEqual([(t.price_cents, t.quantity) for t in trades], [(1000, 100)])
        self.assertEqual(unfilled, 100)
        self.assertEqual(book.buy_orders() + book.sell_orders(), [])

    def test_best_price_and_fifo_both_sides(self):
        for side, prices, expected in [("buy", [1200, 1000, 1000], [2, 3, 1]),
                                       ("sell", [800, 1000, 1000], [2, 3, 1])]:
            with self.subTest(side=side):
                book = OrderBook()
                for price in prices:
                    book.add_limit("sell" if side == "buy" else "buy", price, 10)
                _, trades, unfilled = book.add_market(side, 35)
                ids = [t.sell_order_id if side == "buy" else t.buy_order_id for t in trades]
                self.assertEqual(ids, expected)
                self.assertEqual(unfilled, 5)
                self.assertEqual(book.buy_orders() + book.sell_orders(), [])

    def test_empty_market_never_rests_and_consumes_a_unique_id(self):
        book = OrderBook()
        first, trades, unfilled = book.add_market("buy", 10)
        self.assertEqual((first.id, trades, unfilled), (1, [], 10))
        second, _ = book.add_limit("sell", 1000, 5)
        self.assertEqual(second.id, 2)
        self.assertEqual(book.buy_orders(), [])
        with self.assertRaises(ValueError):
            book.cancel(first.id)


class AmendCancelTests(TestCase):
    def test_cancel_both_sides_and_unknown_ids(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 10)
        book.add_limit("sell", 1100, 10)
        self.assertEqual(book.cancel(1), [])
        self.assertEqual(book.cancel(2), [])
        self.assertEqual(book.buy_orders() + book.sell_orders(), [])
        for order_id in [1, 999, 0, -1, True]:
            with self.subTest(order_id=order_id), self.assertRaises(ValueError):
                book.cancel(order_id)

    def test_pdf_price_change_repositions_order(self):
        book = OrderBook()
        first, _ = book.add_limit("buy", 1000, 200)
        book.add_limit("buy", 999, 100)
        book.add_limit("sell", 1050, 100)
        updated, trades = book.amend(first.id, price_cents=998)
        self.assertEqual(trades, [])
        self.assertEqual([(o.id, o.price_cents) for o in book.buy_orders()], [(2, 999), (1, 998)])
        self.assertGreater(updated.arrival_sequence, first.arrival_sequence)
        self.assertEqual(updated.id, first.id)

    def test_price_change_to_existing_level_goes_to_back_on_both_sides(self):
        for side, prices in [("buy", [1000, 900]), ("sell", [1000, 1100])]:
            with self.subTest(side=side):
                book = OrderBook()
                book.add_limit(side, prices[0], 10)
                book.add_limit(side, prices[1], 10)
                book.amend(1, price_cents=prices[1])
                orders = book.buy_orders() if side == "buy" else book.sell_orders()
                self.assertEqual([o.id for o in orders], [2, 1])

    def test_quantity_decrease_preserves_and_increase_loses_priority(self):
        book = OrderBook()
        original, _ = book.add_limit("buy", 1000, 100)
        book.add_limit("buy", 1000, 100)
        updated, _ = book.amend(1, quantity=50)
        self.assertEqual(updated.arrival_sequence, original.arrival_sequence)
        self.assertEqual([o.id for o in book.buy_orders()], [1, 2])
        updated, _ = book.amend(1, quantity=60)
        self.assertGreater(updated.arrival_sequence, original.arrival_sequence)
        self.assertEqual([o.id for o in book.buy_orders()], [2, 1])
        same, _ = book.amend(1, price_cents=1000, quantity=60)
        self.assertEqual(same.arrival_sequence, updated.arrival_sequence)
        third, _ = book.add_limit("buy", 900, 10)
        self.assertEqual(third.id, 3)

    def test_amend_both_fields_can_execute_and_new_quantity_is_remaining(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 100)
        book.add_limit("sell", 1100, 40)
        updated, trades = book.amend(1, price_cents=1200, quantity=50)
        self.assertEqual(updated.quantity, 50)
        self.assertEqual([(t.price_cents, t.quantity) for t in trades], [(1100, 40)])
        self.assertEqual(book.buy_orders()[0].quantity, 10)
        book.amend(1, quantity=5)
        self.assertEqual(book.buy_orders()[0].quantity, 5)
        book.cancel(1)
        self.assertEqual(book.buy_orders(), [])

    def test_invalid_amend_is_atomic(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 100)
        before = book.render()
        for changes in [{}, {"price_cents": 0}, {"quantity": 0},
                        {"price_cents": 1100, "quantity": -1}, {"quantity": True}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                book.amend(1, **changes)
            self.assertEqual(book.render(), before)
        with self.assertRaises(ValueError):
            book.amend(999, quantity=1)
        updated, _ = book.amend(1, quantity=101)
        self.assertEqual(updated.arrival_sequence, 2)


class PeggedTests(TestCase):
    def test_pdf_bid_example_and_mirrored_offer_keep_arrival(self):
        for side, reference, initial, improved in [("buy", "bid", 1000, 1010),
                                                   ("sell", "offer", 1050, 1040)]:
            with self.subTest(reference=reference):
                book = OrderBook()
                book.add_limit(side, initial, 200)
                book.add_limit(side, initial - 1 if side == "buy" else initial + 1, 100)
                peg, _ = book.add_pegged(reference, side, 150)
                book.add_limit(side, improved, 300)
                orders = book.buy_orders() if side == "buy" else book.sell_orders()
                self.assertEqual([(o.id, o.price_cents) for o in orders],
                                 [(3, improved), (4, improved), (1, initial),
                                  (2, initial - 1 if side == "buy" else initial + 1)])
                self.assertEqual(orders[0].arrival_sequence, peg.arrival_sequence)

    def test_cancel_reference_moves_then_suspends_and_reactivates(self):
        for side, reference, best, worse in [("buy", "bid", 1000, 900),
                                             ("sell", "offer", 1000, 1100)]:
            with self.subTest(reference=reference):
                book = OrderBook()
                book.add_limit(side, best, 10)
                book.add_limit(side, worse, 10)
                peg, _ = book.add_pegged(reference, side, 5)
                book.cancel(1)
                orders = book.buy_orders() if side == "buy" else book.sell_orders()
                self.assertEqual(next(o for o in orders if o.id == peg.id).price_cents, worse)
                book.cancel(2)
                orders = book.buy_orders() if side == "buy" else book.sell_orders()
                self.assertIsNone(orders[0].price_cents)
                self.assertIn("inativa", book.render())
                _, trades, unfilled = book.add_market("sell" if side == "buy" else "buy", 100)
                self.assertEqual((trades, unfilled), ([], 100))
                book.add_limit(side, best, 10)
                orders = book.buy_orders() if side == "buy" else book.sell_orders()
                self.assertEqual(orders[0].id, peg.id)
                self.assertEqual(orders[0].price_cents, best)

    def test_no_reference_accepts_peg_without_circular_anchoring(self):
        book = OrderBook()
        book.add_pegged("bid", "buy", 10)
        book.add_pegged("offer", "sell", 20)
        self.assertIsNone(book.buy_orders()[0].price_cents)
        self.assertIsNone(book.sell_orders()[0].price_cents)
        book.add_limit("buy", 1000, 1)
        self.assertEqual(book.buy_orders()[0].price_cents, 1000)
        self.assertIsNone(book.sell_orders()[0].price_cents)

    def test_consumption_changes_reference_between_market_fills(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 10)
        book.add_limit("buy", 900, 20)
        peg, _ = book.add_pegged("bid", "buy", 30)
        _, trades, remaining = book.add_market("sell", 25)
        self.assertEqual([(t.buy_order_id, t.price_cents, t.quantity) for t in trades],
                         [(1, 1000, 10), (2, 900, 15)])
        self.assertEqual(remaining, 0)
        self.assertEqual([(o.id, o.quantity, o.price_cents) for o in book.buy_orders()],
                         [(2, 5, 900), (peg.id, 30, 900)])

    def test_market_consumes_peg_before_new_reference_with_partial_fill(self):
        book = OrderBook()
        peg, _ = book.add_pegged("offer", "sell", 20)
        book.add_limit("sell", 1000, 30)
        _, trades, unfilled = book.add_market("buy", 25)
        self.assertEqual([(t.sell_order_id, t.quantity) for t in trades], [(peg.id, 20), (2, 5)])
        self.assertEqual(unfilled, 0)
        self.assertEqual(book.sell_orders()[0].quantity, 25)

    def test_opposite_reference_pegs_match_on_creation_or_activation(self):
        for reference, peg_side, limit_side in [("bid", "sell", "buy"),
                                                ("offer", "buy", "sell")]:
            for peg_first in [False, True]:
                with self.subTest(reference=reference, peg_first=peg_first):
                    book = OrderBook()
                    if peg_first:
                        book.add_pegged(reference, peg_side, 10)
                        _, trades = book.add_limit(limit_side, 1000, 20)
                    else:
                        book.add_limit(limit_side, 1000, 20)
                        _, trades = book.add_pegged(reference, peg_side, 10)
                    self.assertEqual([(t.price_cents, t.quantity) for t in trades], [(1000, 10)])
                    orders = book.buy_orders() + book.sell_orders()
                    self.assertEqual(len(orders), 1)
                    self.assertEqual(orders[0].quantity, 10)

    def test_multiple_pegs_update_and_amend_quantity_uses_priority_rules(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 100)
        peg, _ = book.add_pegged("bid", "buy", 10)
        book.add_pegged("bid", "buy", 20)
        book.amend(1, price_cents=1100)
        self.assertEqual([o.price_cents for o in book.buy_orders()], [1100, 1100, 1100])
        self.assertEqual([o.id for o in book.buy_orders()], [2, 3, 1])
        updated, _ = book.amend(peg.id, quantity=5)
        self.assertEqual(updated.arrival_sequence, peg.arrival_sequence)
        book.amend(peg.id, quantity=15)
        self.assertEqual([o.id for o in book.buy_orders()], [3, 1, 2])
        before = book.render()
        with self.assertRaises(ValueError):
            book.amend(peg.id, price_cents=1200, quantity=100)
        self.assertEqual(book.render(), before)

    def test_cancel_peg_does_not_change_limit_reference(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 10)
        book.add_pegged("bid", "buy", 5)
        book.add_pegged("bid", "buy", 6)
        book.cancel(2)
        self.assertEqual([(o.id, o.price_cents) for o in book.buy_orders()], [(1, 1000), (3, 1000)])

    def test_invalid_pegs_do_not_consume_identifiers(self):
        book = OrderBook()
        for reference, side, quantity in [("last", "buy", 1), ("bid", "bad", 1),
                                           ("offer", "sell", 0)]:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                book.add_pegged(reference, side, quantity)
        order, _ = book.add_pegged("bid", "buy", 1)
        self.assertEqual((order.id, order.arrival_sequence), (1, 1))


class CompleteCliTests(TestCase):
    def test_pdf_output_groups_same_price_and_reports_unfilled(self):
        book, output = OrderBook(), StringIO()
        for line in ["limit buy 10 100", "limit sell 20 100", "limit sell 20 200",
                     "market buy 150", "market buy 200", "market sell 200"]:
            execute(line, book, output)
        text = output.getvalue()
        self.assertEqual(text.count("Trade, price: 20.00, qty: 150"), 2)
        self.assertIn("Trade, price: 10.00, qty: 100", text)
        self.assertIn("Unfilled quantity cancelled: 50", text)
        self.assertIn("Unfilled quantity cancelled: 100", text)

    def test_cancel_amend_and_peg_commands(self):
        book, output = OrderBook(), StringIO()
        for line in ["limit buy 10 100", "peg bid buy 20", "amend order 1 price 11 qty 50",
                     "amend order 2 qty 10", "print book", "cancel order 2", "cancel order 1"]:
            self.assertTrue(execute(line, book, output))
        self.assertNotIn("Erro:", output.getvalue())
        self.assertIn("10 @ 11.00 id 2 peg bid", output.getvalue())
        self.assertEqual(output.getvalue().count("Order cancelled"), 2)
        self.assertEqual(book.buy_orders(), [])

    def test_invalid_commands_preserve_book_and_sequence(self):
        book = OrderBook()
        book.add_limit("buy", 1000, 100)
        book.add_pegged("bid", "buy", 10)
        before = book.render()
        invalid = ["market", "market buy 1 extra", "market bad 1", "market sell 0",
                   "market sell 1.5", "peg", "peg bid buy", "peg last buy 1",
                   "peg bid bad 1", "peg bid buy -1", "peg bid buy 1 extra",
                   "cancel", "cancel order", "cancel orders 1", "cancel order 0",
                   "cancel order 999", "cancel order 1 extra", "amend order 1",
                   "amend order 1 price", "amend order 1 price 0", "amend order 1 qty 0",
                   "amend order 1 price 11 qty -1", "amend order 1 qty 10 price 1.001",
                   "amend order 1 qty 10 qty 20", "amend order 1 side sell",
                   "amend order 1 price 11 extra 1", "amend order 999 qty 1",
                   "amend order 2 price 11 qty 20", "amend order 1 qty 1 extra"]
        for line in invalid:
            with self.subTest(line=line):
                output = StringIO()
                self.assertTrue(execute(line, book, output))
                self.assertIn("Erro:", output.getvalue())
                self.assertEqual(book.render(), before)
        third, _ = book.add_limit("buy", 900, 1)
        self.assertEqual((third.id, third.arrival_sequence), (3, 3))

    def test_amend_fields_in_reverse_order(self):
        book, output = OrderBook(), StringIO()
        execute("limit sell 20 10", book, output)
        execute("amend order 1 qty 30 price 19", book, output)
        self.assertNotIn("Erro:", output.getvalue())
        self.assertEqual((book.sell_orders()[0].quantity, book.sell_orders()[0].price_cents), (30, 1900))


class InteractionTests(TestCase):
    def test_seeded_mixed_operations_conserve_quantity_and_leave_no_crossed_book(self):
        rng = random.Random(42)
        book = OrderBook()
        created_ids = []
        for step in range(400):
            orders = book.buy_orders() + book.sell_orders()
            before = sum(o.quantity for o in orders)
            action = rng.choice(["limit", "market", "peg", "cancel", "amend"])
            side, qty = rng.choice(["buy", "sell"]), rng.randint(1, 30)
            with self.subTest(step=step, action=action):
                unfilled = 0
                if action == "cancel" and orders:
                    order = rng.choice(orders)
                    delta = -order.quantity
                    trades = book.cancel(order.id)
                elif action == "amend" and orders:
                    order = rng.choice(orders)
                    delta = qty - order.quantity
                    price = rng.randint(900, 1100) if order.order_type == "limit" else None
                    _, trades = book.amend(order.id, quantity=qty, price_cents=price)
                else:
                    delta = qty
                    if action == "market":
                        order, trades, unfilled = book.add_market(side, qty)
                    elif action == "peg":
                        order, trades = book.add_pegged(rng.choice(["bid", "offer"]), side, qty)
                    else:
                        order, trades = book.add_limit(side, rng.randint(900, 1100), qty)
                    created_ids.append(order.id)
                orders = book.buy_orders() + book.sell_orders()
                self.assertEqual(sum(o.quantity for o in orders),
                                 before + delta - 2 * sum(t.quantity for t in trades) - unfilled)
                self.assertTrue(all(o.quantity > 0 and o.order_type != "market" for o in orders))
                active_buys = [o for o in book.buy_orders() if o.price_cents is not None]
                active_sells = [o for o in book.sell_orders() if o.price_cents is not None]
                if active_buys and active_sells:
                    self.assertLess(active_buys[0].price_cents, active_sells[0].price_cents)
                bids = [o.price_cents for o in orders if o.order_type == "limit" and o.side == "buy"]
                offers = [o.price_cents for o in orders if o.order_type == "limit" and o.side == "sell"]
                for order in orders:
                    if order.order_type == "pegged":
                        expected = max(bids, default=None) if order.peg_reference == "bid" else min(offers, default=None)
                        self.assertEqual(order.price_cents, expected)
        self.assertEqual(created_ids, list(range(1, len(created_ids) + 1)))


if __name__ == "__main__":
    main()
