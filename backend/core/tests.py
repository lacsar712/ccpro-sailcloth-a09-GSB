from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, APITestCase

from accounts.models import User
from core.models import ClothRoll, DipRun, Loft, PassToken


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


class PassTokenGateTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin1", password="x", role=User.ROLE_ADMIN
        )
        self.worker = User.objects.create_user(
            "worker1", password="x", role=User.ROLE_WORKER
        )
        self.loft = Loft.objects.create(name="测试帆布间")
        self.roll = ClothRoll.objects.create(
            loft=self.loft, roll_code="R-1", status=ClothRoll.STATUS_RAW
        )
        self.now = timezone.now()

    def token(self, **kw):
        defaults = dict(
            loft=self.loft,
            passphrase="p",
            valid_from=self.now - timedelta(hours=1),
            valid_until=self.now + timedelta(hours=1),
            issued_by=self.admin,
        )
        defaults.update(kw)
        return PassToken.objects.create(**defaults)

    def issue(self, as_user, valid_from, valid_until, loft=None, passphrase="p"):
        self.client.force_authenticate(as_user)
        return self.client.post(
            "/api/pass-tokens/",
            {
                "loftId": (loft or self.loft).id,
                "passphrase": passphrase,
                "validFrom": iso(valid_from),
                "validUntil": iso(valid_until),
            },
            format="json",
        )

    def patch_status(self, status):
        self.client.force_authenticate(self.worker)
        return self.client.patch(
            f"/api/rolls/{self.roll.id}/", {"status": status}, format="json"
        )

    # ---- 浸渍中口令闸门 ----

    def test_dipping_blocked_without_any_token(self):
        res = self.patch_status("dipping")
        self.assertEqual(res.status_code, 400)
        self.assertIn("口令牌", res.data["status"][0])

    def test_dipping_blocked_when_only_expired_token(self):
        self.token(
            valid_from=self.now - timedelta(days=3),
            valid_until=self.now - timedelta(days=1),
        )
        res = self.patch_status("dipping")
        self.assertEqual(res.status_code, 400)
        self.assertIn("口令牌", res.data["status"][0])

    def test_dipping_blocked_when_token_revoked(self):
        self.token(revoked_at=self.now - timedelta(minutes=1))
        res = self.patch_status("dipping")
        self.assertEqual(res.status_code, 400)

    def test_dipping_blocked_when_token_not_yet_valid(self):
        self.token(
            valid_from=self.now + timedelta(hours=1),
            valid_until=self.now + timedelta(hours=2),
        )
        res = self.patch_status("dipping")
        self.assertEqual(res.status_code, 400)

    def test_dipping_allowed_with_covering_active_token(self):
        self.token()
        res = self.patch_status("dipping")
        self.assertEqual(res.status_code, 200, res.data)
        self.roll.refresh_from_db()
        self.assertEqual(self.roll.status, "dipping")

    def test_token_in_other_loft_does_not_help(self):
        other = Loft.objects.create(name="别的帆布间")
        self.token(loft=other)
        res = self.patch_status("dipping")
        self.assertEqual(res.status_code, 400)

    # ---- 固化不受口令影响 ----

    def test_cured_needs_only_duration_not_token(self):
        roll_c = ClothRoll.objects.create(
            loft=self.loft, roll_code="R-2", status=ClothRoll.STATUS_DIPPING
        )
        DipRun.objects.create(
            roll=roll_c,
            started_at=self.now - timedelta(hours=13),
            resin_pct=Decimal("28"),
            cure_hours=Decimal("13"),
        )
        self.client.force_authenticate(self.worker)
        res = self.client.patch(
            f"/api/rolls/{roll_c.id}/", {"status": "cured"}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.data)

    def test_cured_blocked_even_with_valid_token_when_duration_short(self):
        self.token()
        roll_c = ClothRoll.objects.create(
            loft=self.loft, roll_code="R-2", status=ClothRoll.STATUS_DIPPING
        )
        DipRun.objects.create(
            roll=roll_c,
            started_at=self.now - timedelta(hours=3),
            resin_pct=Decimal("28"),
            cure_hours=Decimal("3"),
        )
        self.client.force_authenticate(self.worker)
        res = self.client.patch(
            f"/api/rolls/{roll_c.id}/", {"status": "cured"}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    # ---- 签发 / 作废权限 ----

    def test_worker_cannot_issue(self):
        res = self.issue(
            self.worker,
            self.now - timedelta(hours=1),
            self.now + timedelta(hours=1),
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(PassToken.objects.count(), 0)

    def test_worker_cannot_revoke(self):
        t = self.token()
        self.client.force_authenticate(self.worker)
        res = self.client.post(f"/api/pass-tokens/{t.id}/revoke/")
        self.assertEqual(res.status_code, 403)
        t.refresh_from_db()
        self.assertIsNone(t.revoked_at)

    def test_admin_can_issue_and_revoke(self):
        res = self.issue(
            self.admin,
            self.now - timedelta(hours=1),
            self.now + timedelta(hours=1),
        )
        self.assertEqual(res.status_code, 201, res.data)
        t = PassToken.objects.get()
        self.assertEqual(t.issued_by, self.admin)
        self.assertIsNone(t.revoked_at)

        self.client.force_authenticate(self.admin)
        res = self.client.post(f"/api/pass-tokens/{t.id}/revoke/")
        self.assertEqual(res.status_code, 200, res.data)
        t.refresh_from_db()
        self.assertIsNotNone(t.revoked_at)

    def test_any_authenticated_user_can_list_tokens(self):
        self.token()
        self.client.force_authenticate(self.worker)
        res = self.client.get("/api/pass-tokens/")
        self.assertEqual(res.status_code, 200)

    # ---- 字段与重叠规则 ----

    def test_valid_until_must_be_after_valid_from(self):
        res = self.issue(
            self.admin,
            self.now + timedelta(hours=2),
            self.now + timedelta(hours=1),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("validUntil", res.data)

    def test_overlapping_active_tokens_rejected(self):
        r1 = self.issue(
            self.admin,
            self.now - timedelta(hours=1),
            self.now + timedelta(hours=1),
            passphrase="a",
        )
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.issue(
            self.admin,
            self.now - timedelta(minutes=30),
            self.now + timedelta(minutes=30),
            passphrase="b",
        )
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(PassToken.objects.active().count(), 1)

    def test_race_recheck_inside_transaction_rejects_late_clash(self):
        # 模拟两名管理员交叉签发：序列化器校验通过后、事务内复查前，
        # 另一事务已写入重叠口令 —— 事务内复查必须把第二张挡下。
        from core.serializers import PassTokenSerializer
        from core.views import PassTokenViewSet

        factory = APIRequestFactory()
        request = factory.post("/api/pass-tokens/")
        request.user = self.admin

        data = {
            "loftId": self.loft.id,
            "passphrase": "late",
            "validFrom": iso(self.now - timedelta(hours=1)),
            "validUntil": iso(self.now + timedelta(hours=1)),
        }
        serializer = PassTokenSerializer(data=data, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # “另一事务”此刻抢先落库一张重叠口令
        self.token(passphrase="first")

        view = PassTokenViewSet()
        view.request = request
        view.format_kwarg = None
        with self.assertRaises(serializers.ValidationError):
            view.perform_create(serializer)
        self.assertEqual(PassToken.objects.active().count(), 1)

    def test_back_to_back_windows_are_not_overlap(self):
        boundary = self.now + timedelta(hours=1)
        self.issue(
            self.admin, self.now - timedelta(hours=1), boundary, passphrase="a"
        )
        r2 = self.issue(
            self.admin, boundary, self.now + timedelta(hours=3), passphrase="b"
        )
        self.assertEqual(r2.status_code, 201, r2.data)

    def test_overlap_allowed_after_revoke(self):
        t = self.token(
            valid_from=self.now - timedelta(hours=2),
            valid_until=self.now + timedelta(hours=2),
        )
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/pass-tokens/{t.id}/revoke/")
        res = self.issue(
            self.admin,
            self.now - timedelta(hours=1),
            self.now + timedelta(hours=1),
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_overlap_scoped_per_loft(self):
        other = Loft.objects.create(name="另一间")
        self.issue(
            self.admin,
            self.now - timedelta(hours=1),
            self.now + timedelta(hours=1),
        )
        res = self.issue(
            self.admin,
            self.now - timedelta(hours=1),
            self.now + timedelta(hours=1),
            loft=other,
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_list_state_filter(self):
        self.token(
            valid_from=self.now - timedelta(days=3),
            valid_until=self.now - timedelta(days=1),
            passphrase="过期",
        )
        self.token(passphrase="有效")
        self.client.force_authenticate(self.worker)
        res = self.client.get("/api/pass-tokens/?state=active")
        results = res.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["state"], "active")

    def test_rack_read_endpoints_still_open_for_worker(self):
        # 被挡之后晾晒架仍能开：所有读接口正常
        self.client.force_authenticate(self.worker)
        for url in ("/api/lofts/", "/api/rolls/", "/api/dips/", "/api/dashboard/"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
