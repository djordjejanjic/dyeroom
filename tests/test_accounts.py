"""Accounts, frames, Paddle webhooks and sign-in tokens.

Run:  .venv/bin/python -m unittest discover -s tests
"""
import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from dyeroom.web import accounts, alerts, billing, sso


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = accounts.Store(Path(self.dir.name) / "accounts.db")
        self.user = self.store.sign_in("google", "123", "ana@example.com", "Ana")

    def tearDown(self):
        self.store.db.close()
        self.dir.cleanup()

    def photo(self, n):
        upload_id = f"{n:032x}"
        self.store.add_photo(upload_id, self.user)
        return upload_id


class Frames(StoreCase):
    def test_welcome_frames_once(self):
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES)
        again = self.store.sign_in("google", "123", None, None)
        self.assertEqual(again, self.user)
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES)
        self.assertEqual(self.store.user(self.user)["name"], "Ana")  # kept when the provider sends none

    def test_each_photograph_costs_one_frame_then_out_of_film(self):
        for n in range(accounts.FREE_FRAMES):
            self.assertEqual(self.store.charge(self.photo(n), self.user), "frame")
        self.assertEqual(self.store.summary(self.user)["available"], 0)
        with self.assertRaises(accounts.NoFilm):
            self.store.charge(self.photo(99), self.user)

    def test_developing_again_is_free(self):
        p = self.photo(1)
        self.store.charge(p, self.user)
        self.store.settle(p, True)
        self.store.charge(p, self.user)
        self.store.settle(p, True)
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES - 1)

    def test_failed_photograph_gets_its_frame_back(self):
        p = self.photo(1)
        self.store.charge(p, self.user)
        self.store.settle(p, False)
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES)
        self.store.charge(p, self.user)  # trying again costs again
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES - 1)

    def test_no_refund_while_another_job_runs_or_after_success(self):
        p = self.photo(1)
        self.store.charge(p, self.user)
        self.store.charge(p, self.user)  # developed again before the first finished
        self.store.settle(p, False)
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES - 1)
        self.store.settle(p, True)
        self.store.charge(p, self.user)
        self.store.settle(p, False)  # a later attempt failing does not undo the developed one
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES - 1)

    def test_someone_elses_photograph(self):
        other = self.store.sign_in("apple", "xyz")
        with self.assertRaises(LookupError):
            self.store.charge(self.photo(1), other)

    def test_restart_refunds_unfinished(self):
        done, cut = self.photo(1), self.photo(2)
        self.store.charge(done, self.user)
        self.store.settle(done, True)
        self.store.charge(cut, self.user)
        self.store.recover()
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES - 1)
        self.assertIsNone(self.store.photo(cut)["paid"])

    def test_deleted_account_gets_no_second_welcome(self):
        self.store.delete_user(self.user)
        self.assertIsNone(self.store.user(self.user))
        back = self.store.sign_in("google", "123", "ana@example.com", None)
        self.assertEqual(back, self.user)
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES)

    def test_sessions(self):
        token = self.store.new_session(self.user)
        self.assertEqual(self.store.user_for(token)["id"], self.user)
        self.store.end_session(token)
        self.assertIsNone(self.store.user_for(token))

    def test_login_state_used_once(self):
        state, nonce = self.store.begin_login("google")
        self.assertEqual(self.store.finish_login(state), ("google", nonce))
        self.assertIsNone(self.store.finish_login(state))


class SameFileAgain(StoreCase):
    FILE = "ab" * 32  # SHA-256 of a file, as hex

    def add(self, n, user=None, sha=FILE):
        upload_id = f"{n:032x}"
        self.store.add_photo(upload_id, user or self.user, sha)
        return upload_id

    def test_same_file_added_again_is_free(self):
        first = self.add(1)
        self.assertEqual(self.store.charge(first, self.user), "frame")
        self.assertFalse(self.store.is_free(self.user, self.FILE))  # not developed yet
        self.store.settle(first, True)
        self.assertTrue(self.store.is_free(self.user, self.FILE))
        again = self.add(2)
        self.assertEqual(self.store.charge(again, self.user), "again")
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES - 1)
        self.assertEqual(self.store.charge(self.add(3, sha="cd" * 32), self.user), "frame")  # another file

    def test_only_after_a_successful_development(self):
        first = self.add(1)
        self.store.charge(first, self.user)
        self.store.settle(first, False)  # could not be developed: refunded, so not free later
        self.assertEqual(self.store.charge(self.add(2), self.user), "frame")

    def test_not_shared_between_accounts(self):
        first = self.add(1)
        self.store.charge(first, self.user)
        self.store.settle(first, True)
        other = self.store.sign_in("apple", "someone-else")
        self.assertFalse(self.store.is_free(other, self.FILE))
        self.assertNotEqual(self.store.fingerprint(other, self.FILE), self.store.fingerprint(self.user, self.FILE))
        self.assertEqual(self.store.charge(self.add(2, other), other), "frame")

    def test_fingerprints_expire_and_go_with_the_account(self):
        first = self.add(1)
        self.store.charge(first, self.user)
        self.store.settle(first, True)
        self.store.db.execute("UPDATE photos SET created = created - ?", ((accounts.FINGERPRINT_DAYS + 1) * 86400,))
        self.store.recover()
        self.assertFalse(self.store.is_free(self.user, self.FILE))
        again = self.add(2)
        self.store.charge(again, self.user)
        self.store.settle(again, True)
        self.store.delete_user(self.user)
        self.assertIsNone(self.store.photo(again)["fingerprint"])

    def test_raw_hash_is_never_stored(self):
        self.add(1)
        stored = self.store.photo(f"{1:032x}")["fingerprint"]
        self.assertNotEqual(stored, self.FILE)
        self.assertEqual(len(stored), 64)


class Presets(StoreCase):
    def test_save_replace_list_delete(self):
        first = self.store.save_preset(self.user, "Street", {"film": "monday400", "grade": 4})
        self.assertEqual(self.store.save_preset(self.user, "Street", {"film": "monday400", "grade": 5}), first)
        self.store.save_preset(self.user, "beach", {"film": "sunday64"})
        listed = self.store.presets(self.user)
        self.assertEqual([p["name"] for p in listed], ["beach", "Street"])
        self.assertEqual(listed[1]["settings"]["grade"], 5)
        self.assertEqual(self.store.presets(self.store.sign_in("apple", "x")), [])
        self.store.delete_preset(self.user, first)
        self.assertEqual([p["name"] for p in self.store.presets(self.user)], ["beach"])

    def test_limit_and_account_deletion(self):
        for n in range(accounts.MAX_PRESETS):
            self.assertIsNotNone(self.store.save_preset(self.user, f"p{n}", {}))
        self.assertIsNone(self.store.save_preset(self.user, "one more", {}))
        self.assertIsNotNone(self.store.save_preset(self.user, "p3", {"grade": 2}))  # replacing is fine
        self.store.delete_user(self.user)
        self.assertEqual(self.store.presets(self.user), [])


class Plans(StoreCase):
    def setUp(self):
        super().setUp()
        self.cap, accounts.PLAN_CAP = accounts.PLAN_CAP, 2
        now = time.time()
        self.store.put_subscription("sub_1", self.user, "active", "monthly", now - 10, now + 86400, None,
                                    "2026-10-30T10:00:00Z")

    def tearDown(self):
        accounts.PLAN_CAP = self.cap
        super().tearDown()

    def test_plan_first_then_frames(self):
        self.assertEqual(self.store.charge(self.photo(1), self.user), "plan")
        self.assertEqual(self.store.charge(self.photo(2), self.user), "plan")
        self.assertEqual(self.store.charge(self.photo(3), self.user), "frame")
        s = self.store.summary(self.user)
        self.assertEqual((s["plan"]["used"], s["frames"]), (2, accounts.FREE_FRAMES - 1))

    def test_older_event_does_not_overwrite(self):
        self.assertFalse(self.store.put_subscription("sub_1", self.user, "canceled", None, None, None, None,
                                                     "2026-10-30T09:00:00Z"))
        self.assertEqual(self.store.summary(self.user)["plan"]["status"], "active")

    def test_cancelled_plan_stops(self):
        self.store.put_subscription("sub_1", self.user, "canceled", None, None, None, None, "2026-10-30T11:00:00Z")
        self.assertIsNone(self.store.summary(self.user)["plan"])

    def test_expired_period_stops_after_grace(self):
        old = time.time() - accounts.GRACE - 10
        self.store.put_subscription("sub_1", self.user, "active", "monthly", old - 86400, old, None,
                                    "2026-10-30T12:00:00Z")
        self.assertIsNone(self.store.summary(self.user)["plan"])


def signed(body, secret="pdl_secret", ts=None):
    ts = str(ts or int(time.time()))
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


class Webhooks(StoreCase):
    def setUp(self):
        super().setUp()
        self.prices = dict(billing.PRICE_IDS)
        billing.PRICE_IDS.update(roll="pri_roll", monthly="pri_month", yearly="pri_year")

    def tearDown(self):
        billing.PRICE_IDS.update(self.prices)
        super().tearDown()

    def test_signature(self):
        body = b'{"event_id":"evt_1"}'
        self.assertTrue(billing.verify_signature(body, signed(body), "pdl_secret"))
        self.assertFalse(billing.verify_signature(body + b" ", signed(body), "pdl_secret"))
        self.assertFalse(billing.verify_signature(body, signed(body, "other"), "pdl_secret"))
        self.assertFalse(billing.verify_signature(body, signed(body, ts=int(time.time()) - 3600), "pdl_secret"))
        rotating = signed(body, "old") + ";h1=" + signed(body).split("h1=")[1]
        self.assertTrue(billing.verify_signature(body, rotating, "pdl_secret"))
        self.assertFalse(billing.verify_signature(body, "", "pdl_secret"))

    def roll_event(self, event_id, txn="txn_1", quantity=1):
        return {"event_id": event_id, "event_type": "transaction.completed", "occurred_at": "2026-10-30T10:00:00Z",
                "data": {"id": txn, "customer_id": "ctm_1", "subscription_id": None,
                         "custom_data": {"user_id": self.user},
                         "items": [{"price": {"id": "pri_roll"}, "quantity": quantity}]}}

    def test_roll_bought_once(self):
        start = self.store.summary(self.user)["frames"]
        self.assertEqual(billing.handle(self.roll_event("evt_1"), self.store), "36 frames")
        self.assertEqual(billing.handle(self.roll_event("evt_1"), self.store), "already handled")
        self.assertEqual(billing.handle(self.roll_event("evt_2"), self.store), "already granted")  # same transaction
        s = self.store.summary(self.user)
        self.assertEqual(s["frames"], start + 36)
        self.assertTrue(s["customer"])

    def test_roll_found_by_customer_when_no_custom_data(self):
        self.store.set_customer(self.user, "ctm_1")
        event = self.roll_event("evt_3", "txn_2", quantity=2)
        event["data"]["custom_data"] = None
        billing.handle(event, self.store)
        self.assertEqual(self.store.summary(self.user)["frames"], accounts.FREE_FRAMES + 72)

    def test_subscription_lifecycle(self):
        sub = {"id": "sub_9", "status": "active", "customer_id": "ctm_1", "custom_data": {"user_id": self.user},
               "items": [{"price": {"id": "pri_year"}, "quantity": 1}],
               "current_billing_period": {"starts_at": "2026-10-30T10:00:00.123456789Z",
                                          "ends_at": "2027-10-30T10:00:00Z"},
               "scheduled_change": None}
        billing.handle({"event_id": "evt_a", "event_type": "subscription.created",
                        "occurred_at": "2026-10-30T10:00:01Z", "data": sub}, self.store)
        plan = self.store.summary(self.user)["plan"]
        self.assertEqual((plan["id"], plan["status"]), ("yearly", "active"))
        self.assertIsNotNone(plan["renews"])
        sub = dict(sub, scheduled_change={"action": "cancel", "effective_at": "2027-10-30T10:00:00Z"})
        billing.handle({"event_id": "evt_b", "event_type": "subscription.updated",
                        "occurred_at": "2026-11-02T10:00:00Z", "data": sub}, self.store)
        plan = self.store.summary(self.user)["plan"]
        self.assertIsNone(plan["renews"])
        self.assertIsNotNone(plan["ends"])
        sub = dict(sub, status="canceled", current_billing_period=None, scheduled_change=None)
        billing.handle({"event_id": "evt_c", "event_type": "subscription.canceled",
                        "occurred_at": "2027-10-30T10:00:01Z", "data": sub}, self.store)
        self.assertIsNone(self.store.summary(self.user)["plan"])

    def test_unknown_account_is_reported_not_granted(self):
        event = self.roll_event("evt_x", "txn_x")
        event["data"]["custom_data"] = {"user_id": "nobody"}
        event["data"]["customer_id"] = "ctm_unknown"
        alerts._last.clear()
        with self.assertLogs("dyeroom.alerts", "ERROR"):
            self.assertEqual(billing.handle(event, self.store), "no account")

    def refund(self, event_id, txn, status="approved", kind="full", action="refund"):
        return {"event_id": event_id, "event_type": "adjustment.updated", "occurred_at": "2026-11-01T10:00:00Z",
                "data": {"id": f"adj_{event_id}", "action": action, "status": status, "type": kind,
                         "transaction_id": txn, "customer_id": "ctm_1", "subscription_id": None}}

    def test_refunded_roll_takes_back_only_unused_frames(self):
        billing.handle(self.roll_event("evt_1", "txn_r"), self.store)
        start = self.store.summary(self.user)["frames"]
        self.assertEqual(billing.handle(self.refund("evt_p", "txn_r", status="pending_approval"), self.store), "ignored")
        for n in range(start - 10):  # all but ten frames used
            upload = self.photo(n)
            self.store.charge(upload, self.user)
        self.assertEqual(billing.handle(self.refund("evt_r", "txn_r"), self.store), "10 frames taken back")
        self.assertEqual(self.store.summary(self.user)["frames"], 0)
        self.assertEqual(billing.handle(self.refund("evt_r2", "txn_r"), self.store), "0 frames taken back")
        self.assertEqual(billing.handle(self.refund("evt_c", "txn_none", action="chargeback"), self.store), "not a roll")

    def test_partial_refund_left_to_the_owner(self):
        billing.handle(self.roll_event("evt_1", "txn_r"), self.store)
        start = self.store.summary(self.user)["frames"]
        alerts._last.clear()
        with self.assertLogs("dyeroom.alerts", "ERROR"):
            self.assertEqual(billing.handle(self.refund("evt_r", "txn_r", kind="partial"), self.store), "partial: by hand")
        self.assertEqual(self.store.summary(self.user)["frames"], start)


class Backups(StoreCase):
    def test_snapshot_restores_accounts_and_fingerprint_key(self):
        self.store.grant(self.user, 36, "roll", "txn_b")
        copy = self.store.snapshot(Path(self.dir.name) / "backups")
        if os.name != "nt":  # Windows files have no owner-only mode bits
            self.assertEqual(oct(copy.stat().st_mode & 0o777), "0o600")
        restored = accounts.Store(copy)
        self.assertEqual(restored.summary(self.user)["frames"], self.store.summary(self.user)["frames"])
        self.assertEqual(restored.key, self.store.key)  # free re-adds keep working after a restore
        restored.db.close()
        self.assertGreater(self.store.last_snapshot(Path(self.dir.name) / "backups"), time.time() - 60)

    def test_old_key_file_is_taken_in(self):
        folder = Path(self.dir.name) / "old"
        folder.mkdir()
        (folder / "fingerprint.key").write_bytes(b"k" * 32)
        old = accounts.Store(folder / "accounts.db")
        self.assertEqual(old.key, b"k" * 32)
        old.db.close()

    def test_new_identity_without_welcome_frames(self):
        self.assertTrue(self.store.known("google", "123"))
        self.assertFalse(self.store.known("google", "456"))
        other = self.store.sign_in("google", "456", "b@example.com", "B", welcome=False)
        self.assertEqual(self.store.summary(other)["frames"], 0)


class IdTokens(unittest.TestCase):
    """Sign-in tokens signed with a local key standing in for Google's."""

    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = self.key.public_key()

        class Keys:
            def get_signing_key_from_jwt(self, token):
                return type("Key", (), {"key": public})()

        sso._key_sets["google"] = Keys()
        self.env = {k: sso.os.environ.get(k) for k in ("DYEROOM_GOOGLE_CLIENT_ID",)}
        sso.os.environ["DYEROOM_GOOGLE_CLIENT_ID"] = "client-1"

    def tearDown(self):
        sso._key_sets.pop("google", None)
        for k, v in self.env.items():
            if v is None:
                sso.os.environ.pop(k, None)
            else:
                sso.os.environ[k] = v

    def token(self, **changes):
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "sub": "g-1", "aud": "client-1", "iat": now,
                  "exp": now + 300, "nonce": "n-1", "email": "ana@example.com", "email_verified": True}
        claims.update(changes)
        return jwt.encode({k: v for k, v in claims.items() if v is not None}, self.key, algorithm="RS256")

    def test_good_token(self):
        self.assertEqual(sso.verify("google", self.token(), "n-1")["sub"], "g-1")

    def test_bad_tokens(self):
        for bad in ({"aud": "someone-else"}, {"iss": "https://evil.example"}, {"nonce": "other"},
                    {"exp": int(time.time()) - 3600}, {"sub": None}):
            with self.subTest(bad=bad), self.assertRaises(sso.SignInError):
                sso.verify("google", self.token(**bad), "n-1")

    def test_other_key(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        forged = jwt.encode({"iss": "https://accounts.google.com", "sub": "g-1", "aud": "client-1",
                             "iat": int(time.time()), "exp": int(time.time()) + 300, "nonce": "n-1"},
                            other, algorithm="RS256")
        with self.assertRaises(sso.SignInError):
            sso.verify("google", forged, "n-1")


if __name__ == "__main__":
    unittest.main()
