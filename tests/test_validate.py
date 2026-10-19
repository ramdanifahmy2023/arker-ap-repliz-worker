from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.validate import candidate_files, link_issues, publication_issues


class PublicationChecks(unittest.TestCase):
    def test_private_files_blocked_even_when_content_is_empty(self):
        for filename in ("Credential/provider.md", "credentials/nested/file.txt", "cache/state.sqlite3", ".env.prod"):
            with self.subTest(filename=filename):
                self.assertTrue(publication_issues(filename, ""))

    def test_secret_detection_does_not_return_the_secret(self):
        fake_secret = "gh" + "p_" + "a" * 40
        issues = publication_issues("README.md", fake_secret)
        self.assertIn("sensitive-content", issues)
        self.assertNotIn(fake_secret, repr(issues))

    def test_private_absolute_path_is_blocked(self):
        private_path = "/" + "Users" + "/private-person/token"
        self.assertIn("sensitive-content", publication_issues("docs/config.md", private_path))

    def test_reference_is_not_a_secret_value(self):
        self.assertEqual(publication_issues("config/example.toml", 'credential_ref = "repliz-default"'), [])

    def test_links_with_spaces_and_parent_directory(self):
        with tempfile.TemporaryDirectory(prefix="arker docs ") as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "README.md").write_text("# Readme\n", encoding="utf-8")
            (root / "docs" / "A plan.md").write_text("# Plan\n", encoding="utf-8")
            self.assertEqual(link_issues(root, "docs/index.md", "[root](../README.md) [plan](<A plan.md>)"), [])
            self.assertTrue(link_issues(root, "docs/index.md", "[missing](missing.md)"))
            self.assertTrue(link_issues(root, "docs/index.md", "[outside](../../outside.md)"))

    def test_force_tracked_secret_still_enters_review(self):
        with tempfile.TemporaryDirectory(prefix="arker git ") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / ".gitignore").write_text("Credential/\n", encoding="utf-8")
            (root / "Credential").mkdir()
            (root / "Credential" / "example.txt").write_text("synthetic", encoding="utf-8")
            self.assertNotIn("Credential/example.txt", candidate_files(root))
            subprocess.run(["git", "add", "-f", "Credential/example.txt"], cwd=root, check=True)
            self.assertIn("Credential/example.txt", candidate_files(root))
            self.assertTrue(publication_issues("Credential/example.txt", "synthetic"))


if __name__ == "__main__":
    unittest.main()
