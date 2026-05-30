import unittest
import json
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ThreatIndicator
from app.routers.admin import intelligence_cleanup, intelligence_export, intelligence_indicators, intelligence_summary
from app.services.intelligence_memory import (
    cleanup_old_indicators,
    hash_indicator_value,
    normalize_indicator_value,
    record_indicator,
    sanitize_display_value,
)


class IntelligenceMemoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_url_display_strips_query_and_fragment(self):
        display = sanitize_display_value(
            "url_hash",
            "https://Example.com/login?token=secret#step",
        )

        self.assertEqual(display, "https://example.com/login")

    def test_hashing_is_stable(self):
        first = hash_indicator_value("example.com/login")
        second = hash_indicator_value("example.com/login")
        other = hash_indicator_value("example.com/reset")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_same_indicator_increments_seen_count(self):
        record_indicator(
            self.db,
            "domain",
            "Example.com",
            risk_score=40,
            classification="suspicious",
            source="manual_analysis",
        )
        record_indicator(
            self.db,
            "domain",
            "example.com",
            risk_score=70,
            classification="dangerous",
            source="manual_analysis",
        )
        self.db.commit()

        items = self.db.query(ThreatIndicator).all()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].seen_count, 2)
        self.assertEqual(items[0].max_risk_score, 70)
        self.assertEqual(items[0].last_classification, "dangerous")

    def test_display_values_are_sanitized(self):
        sender_display = sanitize_display_value("sender", "user@example.com")
        otp_value = normalize_indicator_value("sender", "123456")

        self.assertEqual(sender_display, "us***@example.com")
        self.assertEqual(otp_value, "")

    def test_recording_failure_does_not_raise(self):
        self.assertIsNone(record_indicator(None, "domain", "example.com"))

    def test_admin_endpoint_caps_limit(self):
        for value in ("a.example", "b.example", "c.example"):
            record_indicator(self.db, "domain", value)
        self.db.commit()

        response = intelligence_indicators(
            indicator_type=None,
            min_seen_count=None,
            limit=500,
            db=self.db,
        )

        self.assertEqual(response["limit"], 200)
        self.assertEqual(len(response["items"]), 3)

    def test_admin_endpoint_type_filter(self):
        record_indicator(self.db, "domain", "example.com")
        record_indicator(self.db, "sender", "person@example.com")
        self.db.commit()

        response = intelligence_indicators(
            indicator_type="sender",
            min_seen_count=None,
            limit=50,
            db=self.db,
        )

        self.assertEqual(len(response["items"]), 1)
        self.assertEqual(response["items"][0]["indicator_type"], "sender")

    def test_admin_endpoint_min_seen_count_filter(self):
        record_indicator(self.db, "domain", "one.example")
        record_indicator(self.db, "domain", "two.example")
        record_indicator(self.db, "domain", "two.example")
        self.db.commit()

        response = intelligence_indicators(
            indicator_type="domain",
            min_seen_count=2,
            limit=50,
            db=self.db,
        )

        self.assertEqual(len(response["items"]), 1)
        self.assertEqual(response["items"][0]["display_value"], "two.example")
        self.assertEqual(response["items"][0]["seen_count"], 2)

    def test_admin_endpoint_invalid_type_is_safe_empty(self):
        record_indicator(self.db, "domain", "example.com")
        self.db.commit()

        response = intelligence_indicators(
            indicator_type="password",
            min_seen_count=None,
            limit=50,
            db=self.db,
        )

        self.assertEqual(response["items"], [])

    def test_admin_endpoint_does_not_expose_hash_or_query_strings(self):
        record_indicator(self.db, "url_hash", "https://example.com/login?token=secret")
        self.db.commit()

        response = intelligence_indicators(
            indicator_type="url_hash",
            min_seen_count=None,
            limit=50,
            db=self.db,
        )
        item = response["items"][0]

        self.assertNotIn("value_hash", item)
        self.assertEqual(item["display_value"], "https://example.com/login")
        self.assertNotIn("?", item["display_value"])
        self.assertNotIn("token", item["display_value"])

    def test_summary_endpoint_returns_safe_counts(self):
        record_indicator(self.db, "domain", "example.com")
        record_indicator(self.db, "domain", "example.com")
        record_indicator(self.db, "sender", "person@example.com")
        self.db.commit()

        response = intelligence_summary(db=self.db)

        self.assertEqual(response["total_indicators"], 2)
        self.assertEqual(response["top_repeated"], 2)
        self.assertTrue(response["latest_seen"])
        self.assertIn({"type": "domain", "count": 1}, response["top_types"])

    def test_cleanup_dry_run_does_not_delete(self):
        record_indicator(self.db, "domain", "old.example")
        item = self.db.query(ThreatIndicator).one()
        item.last_seen = datetime.utcnow() - timedelta(days=120)
        self.db.commit()

        response = cleanup_old_indicators(self.db, retention_days=90, dry_run=True)

        self.assertEqual(response["matched_count"], 1)
        self.assertEqual(response["deleted_count"], 0)
        self.assertEqual(self.db.query(ThreatIndicator).count(), 1)

    def test_cleanup_delete_requires_dry_run_false(self):
        record_indicator(self.db, "domain", "old.example")
        item = self.db.query(ThreatIndicator).one()
        item.last_seen = datetime.utcnow() - timedelta(days=120)
        self.db.commit()

        response = cleanup_old_indicators(self.db, retention_days=90, dry_run=False)
        self.db.commit()

        self.assertEqual(response["matched_count"], 1)
        self.assertEqual(response["deleted_count"], 1)
        self.assertEqual(self.db.query(ThreatIndicator).count(), 0)

    def test_cleanup_retention_days_minimum_enforced(self):
        with self.assertRaises(ValueError):
            cleanup_old_indicators(self.db, retention_days=6, dry_run=True)

        response = intelligence_cleanup(
            dry_run=True,
            retention_days=1,
            db=self.db,
        )

        self.assertEqual(response["retention_days"], 7)

    def test_export_json_is_sanitized(self):
        record_indicator(self.db, "url_hash", "https://example.com/login?token=secret")
        self.db.commit()

        response = intelligence_export(
            format="json",
            indicator_type="url_hash",
            min_seen_count=None,
            limit=1000,
            db=self.db,
            admin=None,
        )
        payload = json.loads(response.body.decode("utf-8"))
        item = payload["items"][0]

        self.assertNotIn("value_hash", item)
        self.assertEqual(item["display_value"], "https://example.com/login")
        self.assertNotIn("?", item["display_value"])
        self.assertNotIn("token", item["display_value"])

    def test_export_filters_type_and_min_seen_count(self):
        record_indicator(self.db, "domain", "one.example")
        record_indicator(self.db, "domain", "two.example")
        record_indicator(self.db, "domain", "two.example")
        record_indicator(self.db, "sender", "person@example.com")
        self.db.commit()

        response = intelligence_export(
            format="json",
            indicator_type="domain",
            min_seen_count=2,
            limit=1000,
            db=self.db,
            admin=None,
        )
        payload = json.loads(response.body.decode("utf-8"))

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["display_value"], "two.example")
        self.assertEqual(payload["items"][0]["indicator_type"], "domain")


if __name__ == "__main__":
    unittest.main()
