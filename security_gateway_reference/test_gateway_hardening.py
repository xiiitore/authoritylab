import unittest

from security_gateway_reference.gateway import Claims, VerifiedToken, Gateway
from security_gateway_reference.test_gateway import NOW, claims


class GatewayHardeningTests(unittest.TestCase):
    def setUp(self):
        self.claims = claims()
        self.verifier = type("Verifier", (), {
            "verify_and_extract": lambda _self, token: (
                {"token": VerifiedToken(self.claims, True)}[token]
            )
        })()
        self.revocations = type("Revocations", (), {
            "is_revoked": lambda *_args: False
        })()
        self.clock = type("Clock", (), {"now": lambda _self: NOW})()
        self.gateway = Gateway(
            self.verifier, self.revocations, self.clock,
            issuer="issuer-A", audience="backend-service",
            allowed_operations={"read"}, permissions={"subject-1": {"read"}},
        )

    def test_blank_target_claim_is_rejected(self):
        c = claims(target_entity=" ")
        self.verifier.verify_and_extract = lambda _token: VerifiedToken(c, True)
        _claims, reason = self.gateway.authorize("token", "read", "DATA_REF_100")
        self.assertIsNone(_claims)
        self.assertEqual(reason, "CLAIMS_OR_TARGET_MISSING")

    def test_malformed_time_claim_is_rejected(self):
        c = Claims(**{**self.claims.__dict__, "issued_at": "not-a-datetime"})
        self.verifier.verify_and_extract = lambda _token: VerifiedToken(c, True)
        _claims, reason = self.gateway.authorize("token", "read", "DATA_REF_100")
        self.assertIsNone(_claims)
        self.assertEqual(reason, "TIME_CLAIM_TYPE_INVALID")

    def test_clock_exception_fails_closed(self):
        broken_clock = type("BrokenClock", (), {
            "now": lambda _self: (_ for _ in ()).throw(RuntimeError("clock offline"))
        })()
        gateway = Gateway(
            self.verifier, self.revocations, broken_clock,
            issuer="issuer-A", audience="backend-service",
            allowed_operations={"read"}, permissions={"subject-1": {"read"}},
        )
        _claims, reason = gateway.authorize("token", "read", "DATA_REF_100")
        self.assertIsNone(_claims)
        self.assertEqual(reason, "TRUSTED_TIME_UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
