#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = Path(os.environ["EN_PAYLOAD_ROOT"]).resolve()
PUBLISHER = REPO / "scripts" / "publish_scheduled_blog_en.py"


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts):
        result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def sitemap_urls(root: Path) -> set[str]:
    import re
    return set(re.findall(r"<loc>([^<]+)</loc>", (root / "sitemap.xml").read_text()))


class EnglishSchedulerTest(unittest.TestCase):
    def fresh_root(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="dream-en-publisher-test-"))
        shutil.copytree(REPO, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
        return target

    def run_publisher(self, root: Path, now: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(PUBLISHER), "--root", str(root), "--payload", str(PAYLOAD), "--now", now],
            check=True,
            text=True,
            capture_output=True,
        )

    def test_zero_due_is_bit_for_bit_noop(self):
        root = self.fresh_root()
        before = snapshot(root)
        result = self.run_publisher(root, "2026-08-22T03:29:00Z")
        self.assertEqual(result.stdout, "")
        self.assertEqual(snapshot(root), before)

    def test_dragon_is_the_only_first_due_promotion(self):
        root = self.fresh_root()
        baseline = sitemap_urls(root)
        self.run_publisher(root, "2026-08-22T03:31:00Z")
        state = json.loads((root / ".scheduled-blog-state-en.json").read_text())
        self.assertEqual(state["applied"], ["en-000", "en-001"])
        self.assertTrue((root / "en/blog/dragon-dream/index.html").exists())
        self.assertFalse((root / "en/blog/dog-dream/index.html").exists())
        tiger = (root / "en/blog/tiger-dream/index.html").read_text()
        self.assertIn('aria-label="Language switcher"', tiger)
        self.assertIn("Current language: English", tiger)
        self.assertIn("grid-template-columns:1fr auto", tiger)
        index = (root / "en/blog/index.html").read_text()
        self.assertIn('/en/blog/dragon-dream/', index)
        self.assertIn('/en/blog/tiger-dream/', index)
        self.assertNotIn('/en/blog/dog-dream/', index)
        korean = (root / "blog/dragon-dream/index.html").read_text()
        self.assertIn('href="/en/blog/dragon-dream/"', korean)
        self.assertIn('hreflang="en" href="https://dream.mypawstory.com/en/blog/dragon-dream/"', korean)
        additions = sitemap_urls(root) - baseline
        self.assertEqual(additions, {"https://dream.mypawstory.com/en/blog/dragon-dream/"})
        self.assertNotIn("/blog/en/", (root / "sitemap.xml").read_text())

    def test_next_tick_adds_dog_but_not_cat(self):
        root = self.fresh_root()
        self.run_publisher(root, "2026-08-22T03:31:00Z")
        self.run_publisher(root, "2026-08-23T00:31:00Z")
        state = json.loads((root / ".scheduled-blog-state-en.json").read_text())
        self.assertEqual(state["applied"], ["en-000", "en-001", "en-002"])
        self.assertTrue((root / "en/blog/dog-dream/index.html").exists())
        self.assertFalse((root / "en/blog/cat-dream/index.html").exists())

    def test_missing_korean_counterpart_stays_blocked_without_writes(self):
        root = self.fresh_root()
        manifest = json.loads((PAYLOAD / "manifest-en.json").read_text())
        prior = [entry["id"] for entry in manifest if entry["slug"] != "childbirth-dream"]
        (root / ".scheduled-blog-state-en.json").write_text(json.dumps({"applied": prior}, indent=2) + "\n")
        before = snapshot(root)
        result = self.run_publisher(root, "2026-10-02T00:00:00Z")
        self.assertIn("childbirth-dream: Korean counterpart is not live", result.stdout)
        self.assertEqual(snapshot(root), before)

    def test_payload_packages_are_narrow(self):
        manifest = json.loads((PAYLOAD / "manifest-en.json").read_text())
        self.assertEqual(len(manifest), 40)
        for entry in manifest:
            package = PAYLOAD / "packages" / entry["package"]
            files = sorted(str(path.relative_to(package)) for path in package.rglob("*") if path.is_file())
            self.assertEqual(files, ["card.html", f"site/en/blog/{entry['slug']}/index.html"])
        workflow = (REPO / ".github/workflows/publish-scheduled-blog-en.yml").read_text()
        self.assertIn("group: dream-blog-scheduled-publisher", workflow)
        self.assertIn("cancel-in-progress: false", workflow)


if __name__ == "__main__":
    unittest.main()
