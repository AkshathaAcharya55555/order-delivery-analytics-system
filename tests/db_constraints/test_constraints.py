"""
Database-constraint tests: verify Postgres itself rejects invalid data,
independent of any application-layer validation. Each test attempts an
insert that should violate a specific CHECK/NOT NULL/FK/UNIQUE constraint
from database/schema.sql and asserts Postgres raises the expected error
class. Every test runs in its own rolled-back transaction (see conftest.py's
db_conn fixture) so nothing is left behind in the shared database.
"""

import psycopg2
import psycopg2.errors
import pytest


def _existing_customer_and_location(cur):
    cur.execute("SELECT customer_id FROM customers LIMIT 1")
    customer_id = cur.fetchone()[0]
    cur.execute("SELECT location_id FROM locations LIMIT 1")
    location_id = cur.fetchone()[0]
    return customer_id, location_id


def _insert_valid_order(cur, customer_id, location_id, **overrides):
    fields = {
        "customer_id": customer_id,
        "delivery_location_id": location_id,
        "status": "'PLACED'",
        "order_placed_at": "now()",
        "total_amount": "10.00",
        "payment_method": "'card'",
    }
    fields.update(overrides)
    cols = ", ".join(fields.keys())
    # order_placed_at uses the now() SQL function, not a bind param, so build
    # the VALUES list directly rather than parameterizing every field.
    vals = ", ".join(str(v) if not isinstance(v, str) or v in ("now()",) else v for v in fields.values())
    cur.execute(f"INSERT INTO orders ({cols}) VALUES ({vals}) RETURNING order_id")
    return cur.fetchone()[0]


class TestOrdersConstraints:
    def test_negative_total_amount_rejected(self, db_conn):
        cur = db_conn.cursor()
        customer_id, location_id = _existing_customer_and_location(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insert_valid_order(cur, customer_id, location_id, total_amount="-5.00")

    def test_invalid_status_value_rejected(self, db_conn):
        cur = db_conn.cursor()
        customer_id, location_id = _existing_customer_and_location(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insert_valid_order(cur, customer_id, location_id, status="'NOT_A_REAL_STATUS'")

    def test_invalid_payment_method_rejected(self, db_conn):
        cur = db_conn.cursor()
        customer_id, location_id = _existing_customer_and_location(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            _insert_valid_order(cur, customer_id, location_id, payment_method="'bitcoin'")

    def test_missing_customer_id_rejected(self, db_conn):
        cur = db_conn.cursor()
        with pytest.raises(psycopg2.errors.NotNullViolation):
            cur.execute(
                "INSERT INTO orders (delivery_location_id, status, order_placed_at, total_amount, payment_method) "
                "VALUES (%s, 'PLACED', now(), 10.00, 'card')",
                (1,),
            )

    def test_nonexistent_customer_id_rejected(self, db_conn):
        cur = db_conn.cursor()
        _, location_id = _existing_customer_and_location(cur)
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) "
                "VALUES (999999999, %s, 'PLACED', now(), 10.00, 'card')",
                (location_id,),
            )

    def test_nonexistent_location_id_rejected(self, db_conn):
        cur = db_conn.cursor()
        customer_id, _ = _existing_customer_and_location(cur)
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) "
                "VALUES (%s, 999999999, 'PLACED', now(), 10.00, 'card')",
                (customer_id,),
            )

    def test_valid_order_is_accepted(self, db_conn):
        """Control case: proves the test harness itself is correct - a
        legitimate insert must NOT raise, so the CHECK-violation tests above
        are really testing the constraint, not a typo in the test SQL."""
        cur = db_conn.cursor()
        customer_id, location_id = _existing_customer_and_location(cur)
        order_id = _insert_valid_order(cur, customer_id, location_id)
        assert order_id is not None


class TestOrderItemsConstraints:
    def _existing_order_id(self, cur):
        cur.execute("SELECT order_id FROM orders LIMIT 1")
        return cur.fetchone()[0]

    def test_zero_quantity_rejected(self, db_conn):
        cur = db_conn.cursor()
        order_id = self._existing_order_id(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO order_items (order_id, product_name, category, unit_price, quantity) "
                "VALUES (%s, 'Test', 'food', 5.00, 0)",
                (order_id,),
            )

    def test_negative_quantity_rejected(self, db_conn):
        cur = db_conn.cursor()
        order_id = self._existing_order_id(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO order_items (order_id, product_name, category, unit_price, quantity) "
                "VALUES (%s, 'Test', 'food', 5.00, -3)",
                (order_id,),
            )

    def test_negative_unit_price_rejected(self, db_conn):
        cur = db_conn.cursor()
        order_id = self._existing_order_id(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO order_items (order_id, product_name, category, unit_price, quantity) "
                "VALUES (%s, 'Test', 'food', -5.00, 1)",
                (order_id,),
            )

    def test_orphan_order_id_rejected(self, db_conn):
        cur = db_conn.cursor()
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cur.execute(
                "INSERT INTO order_items (order_id, product_name, category, unit_price, quantity) "
                "VALUES (999999999, 'Test', 'food', 5.00, 1)"
            )


class TestRidersConstraints:
    def test_invalid_vehicle_type_rejected(self, db_conn):
        cur = db_conn.cursor()
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO riders (first_name, last_name, phone, vehicle_type, city, joined_date) "
                "VALUES ('T', 'R', '555-0000', 'hovercraft', 'Austin', now())"
            )

    def test_rating_above_five_rejected(self, db_conn):
        cur = db_conn.cursor()
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO riders (first_name, last_name, phone, vehicle_type, city, rating, joined_date) "
                "VALUES ('T', 'R', '555-0000', 'bike', 'Austin', 5.9, now())"
            )

    def test_negative_rating_rejected(self, db_conn):
        cur = db_conn.cursor()
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO riders (first_name, last_name, phone, vehicle_type, city, rating, joined_date) "
                "VALUES ('T', 'R', '555-0000', 'bike', 'Austin', -1.0, now())"
            )


class TestDeliveriesConstraints:
    def _fresh_order_and_rider(self, cur):
        cur.execute("SELECT customer_id FROM customers LIMIT 1")
        customer_id = cur.fetchone()[0]
        cur.execute("SELECT location_id FROM locations LIMIT 1")
        location_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO orders (customer_id, delivery_location_id, status, order_placed_at, total_amount, payment_method) "
            "VALUES (%s, %s, 'PLACED', now(), 10.00, 'card') RETURNING order_id",
            (customer_id, location_id),
        )
        order_id = cur.fetchone()[0]
        cur.execute("SELECT rider_id FROM riders LIMIT 1")
        rider_id = cur.fetchone()[0]
        return order_id, rider_id

    def test_pickup_before_assignment_rejected(self, db_conn):
        cur = db_conn.cursor()
        order_id, rider_id = self._fresh_order_and_rider(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO deliveries (order_id, rider_id, assigned_at, picked_up_at, delivery_status) "
                "VALUES (%s, %s, now(), now() - interval '1 hour', 'picked_up')",
                (order_id, rider_id),
            )

    def test_delivered_before_pickup_rejected(self, db_conn):
        cur = db_conn.cursor()
        order_id, rider_id = self._fresh_order_and_rider(cur)
        with pytest.raises(psycopg2.errors.CheckViolation):
            cur.execute(
                "INSERT INTO deliveries (order_id, rider_id, assigned_at, picked_up_at, delivered_at, delivery_status) "
                "VALUES (%s, %s, now() - interval '2 hour', now() - interval '1 hour', now() - interval '90 minutes', 'delivered')",
                (order_id, rider_id),
            )

    def test_duplicate_order_id_rejected(self, db_conn):
        """deliveries.order_id is UNIQUE - a second delivery row for the same
        order must be rejected (one order has at most one delivery leg)."""
        cur = db_conn.cursor()
        order_id, rider_id = self._fresh_order_and_rider(cur)
        cur.execute(
            "INSERT INTO deliveries (order_id, rider_id, assigned_at, delivery_status) "
            "VALUES (%s, %s, now(), 'assigned')",
            (order_id, rider_id),
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO deliveries (order_id, rider_id, assigned_at, delivery_status) "
                "VALUES (%s, %s, now(), 'assigned')",
                (order_id, rider_id),
            )

    def test_valid_delivery_is_accepted(self, db_conn):
        cur = db_conn.cursor()
        order_id, rider_id = self._fresh_order_and_rider(cur)
        cur.execute(
            "INSERT INTO deliveries (order_id, rider_id, assigned_at, picked_up_at, delivered_at, delivery_status) "
            "VALUES (%s, %s, now() - interval '2 hour', now() - interval '90 minutes', now() - interval '1 hour', 'delivered') "
            "RETURNING delivery_id",
            (order_id, rider_id),
        )
        assert cur.fetchone()[0] is not None


class TestCustomersConstraints:
    def test_duplicate_email_rejected(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("SELECT email FROM customers LIMIT 1")
        existing_email = cur.fetchone()[0]
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO customers (first_name, last_name, email, signup_date) "
                "VALUES ('Dup', 'Licate', %s, now())",
                (existing_email,),
            )
