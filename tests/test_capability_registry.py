import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "capability-registry.json"
SCHEMA_PATH = ROOT / "docs" / "capability-registry.schema.json"

class CapabilityRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_registry_and_schema_are_valid_json(self):
        self.assertIsInstance(self.registry, dict)
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_registry_has_required_root_contract(self):
        required = {"registry_schema_version", "generated_on", "source", "status",
                    "tool_count", "provider_counts", "classification_policy", "tools"}
        self.assertTrue(required.issubset(self.registry))
        self.assertEqual(self.registry["registry_schema_version"], "1.0.0")
        self.assertEqual(self.registry["status"], "INVENTORY_ONLY_NOT_EXECUTION_VERIFIED")

    def test_tool_count_matches_entries(self):
        self.assertEqual(self.registry["tool_count"], len(self.registry["tools"]))

    def test_tool_ids_are_unique_and_nonempty(self):
        ids = [item["tool_id"] for item in self.registry["tools"]]
        self.assertTrue(all(isinstance(item, str) and item for item in ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_provider_counts_match_entries(self):
        expected = dict(Counter(item["provider"] for item in self.registry["tools"]))
        self.assertEqual(self.registry["provider_counts"], expected)

    def test_every_entry_is_explicitly_unverified(self):
        self.assertTrue(all(item["execution_verified"] is False for item in self.registry["tools"]))

    def test_entry_fields_and_effect_classes_are_valid(self):
        required = {"tool_id", "provider", "description", "description_truncated",
                    "preliminary_effect_class", "execution_verified", "notes"}
        allowed = {"POTENTIAL_SIDE_EFFECT", "READ_OR_LOOKUP_BY_DESCRIPTION", "UNKNOWN_REQUIRES_REVIEW"}
        for item in self.registry["tools"]:
            self.assertTrue(required.issubset(item))
            self.assertIn(item["preliminary_effect_class"], allowed)
            self.assertIsInstance(item["description_truncated"], bool)

    def test_registry_schema_defines_closed_root_and_items(self):
        self.assertFalse(self.schema["additionalProperties"])
        self.assertFalse(self.schema["properties"]["tools"]["items"]["additionalProperties"])
        self.assertEqual(self.schema["properties"]["status"]["const"],
                         "INVENTORY_ONLY_NOT_EXECUTION_VERIFIED")

if __name__ == "__main__":
    unittest.main()
