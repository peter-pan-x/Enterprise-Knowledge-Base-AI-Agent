import unittest

from app.schemas.service_policy import PublicServicePolicy, ServicePolicy
from app.services.integration_service import get_business_adapter, list_channel_adapters
from app.services.service_policy_service import keyword_matches


class GenericCustomerServiceTests(unittest.TestCase):
    def test_keyword_matching_ignores_blanks_and_matches_case_insensitively(self):
        self.assertTrue(keyword_matches("请转人工客服", "人工客服,投诉"))
        self.assertTrue(keyword_matches("Need HELP", "help,人工"))
        self.assertFalse(keyword_matches("普通咨询", " , ,"))

    def test_generic_integration_starts_unconfigured(self):
        self.assertEqual(list_channel_adapters(), [])
        self.assertIsNone(get_business_adapter())

    def test_service_policy_has_safe_defaults_and_public_shape(self):
        policy = ServicePolicy()
        self.assertTrue(policy.auto_handoff_on_no_answer)
        public_policy = PublicServicePolicy(welcome_message=policy.welcome_message)
        self.assertEqual(public_policy.model_dump(), {"welcome_message": policy.welcome_message})


if __name__ == "__main__":
    unittest.main()
