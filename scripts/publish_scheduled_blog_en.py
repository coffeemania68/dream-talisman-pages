#!/usr/bin/env python3
"""Promote due English dream-blog packages into the latest Pages main checkout."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ORIGIN = "https://dream.mypawstory.com"
OLD_MOBILE_CSS = '@media(max-width:640px){.blog-topbar{gap:6px}.blog-actions{gap:8px;min-width:0}.blog-topbar nav{gap:10px;font-size:12px}.language-switch{min-height:44px;font-size:12px;letter-spacing:.02em}}'
NEW_MOBILE_CSS = '@media(max-width:640px){.blog-topbar{display:grid;grid-template-columns:1fr auto;align-items:center;row-gap:8px}.blog-actions{display:contents}.language-switcher{grid-column:2}.blog-topbar nav{grid-column:1/-1;grid-row:2;justify-content:flex-end;gap:16px;font-size:12px}.blog-topbar nav a{white-space:nowrap}.language-switch{min-height:44px;font-size:12px;letter-spacing:.02em}}'
LANGUAGE_CSS = (
    '.blog-actions{display:flex;align-items:center;gap:14px}'
    '.language-switcher{display:inline-flex;align-items:center}'
    '.language-switch{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:44px;padding:0 2px;border-bottom:1px solid var(--gold);color:var(--ink);font-size:12px;font-weight:800;letter-spacing:.04em;line-height:1;text-decoration:none;white-space:nowrap}'
    '.language-switch::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--gold);box-shadow:0 0 0 3px rgba(162,112,30,.12)}'
    '.language-switch-arrow{font-size:13px;color:var(--teal);line-height:1}'
    '.language-switch:focus-visible{outline:2px solid var(--accent);outline-offset:4px}'
    '.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}'
    + NEW_MOBILE_CSS
)
KO_NAV = '<nav><a href="/blog/">블로그</a><a href="/dreams">꿈 목록</a><a href="/">앱 열기</a></nav>'
CSS_ANCHOR = '.blog-topbar nav{display:flex;gap:18px;font-size:13px;color:var(--ink-soft)}'


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def article_urls(slug: str) -> tuple[str, str]:
    return f"{ORIGIN}/blog/{slug}/", f"{ORIGIN}/en/blog/{slug}/"


def alternate_tags(slug: str = "") -> str:
    suffix = f"{slug}/" if slug else ""
    return (
        f'<link rel="alternate" hreflang="ko" href="{ORIGIN}/blog/{suffix}">\n'
        f'<link rel="alternate" hreflang="en" href="{ORIGIN}/en/blog/{suffix}">\n'
        f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/blog/{suffix}">'
    )


def switch_html(counterpart: str) -> str:
    return (
        '<div class="language-switcher" role="group" aria-label="언어 전환">'
        '<span class="sr-only" aria-current="page">현재 언어: 한국어</span>'
        f'<a class="language-switch" href="{counterpart}" lang="en" aria-label="English 페이지로 전환">'
        '<span>English</span><span class="language-switch-arrow" aria-hidden="true">↗</span></a></div>'
    )


def patch_korean_html(path: Path, slug: str = "") -> None:
    html = path.read_text(encoding="utf-8")
    canonical = f'<link rel="canonical" href="{ORIGIN}/blog/{slug + "/" if slug else ""}">'
    if canonical not in html:
        raise RuntimeError(f"canonical anchor missing in {path}")
    ko_url, en_url = article_urls(slug) if slug else (f"{ORIGIN}/blog/", f"{ORIGIN}/en/blog/")
    del ko_url
    if f'hreflang="en" href="{en_url}"' not in html:
        html = html.replace(canonical, f"{canonical}\n{alternate_tags(slug)}", 1)
    elif f'hreflang="x-default" href="{ORIGIN}/blog/{slug + "/" if slug else ""}"' not in html:
        html = html.replace(canonical, f"{canonical}\n" + f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/blog/{slug + "/" if slug else ""}">', 1)
    if OLD_MOBILE_CSS in html:
        html = html.replace(OLD_MOBILE_CSS, NEW_MOBILE_CSS)
    if 'class="language-switcher"' not in html:
        if CSS_ANCHOR not in html or KO_NAV not in html:
            raise RuntimeError(f"language-switch anchors missing in {path}")
        html = html.replace(CSS_ANCHOR, CSS_ANCHOR + LANGUAGE_CSS, 1)
        counterpart = f"/en/blog/{slug}/" if slug else "/en/blog/"
        html = html.replace(KO_NAV, f'<div class="blog-actions">{switch_html(counterpart)}{KO_NAV}</div>', 1)
    path.write_text(html, encoding="utf-8")


def sitemap_links(slug: str = "") -> str:
    suffix = f"{slug}/" if slug else ""
    return (
        f'<xhtml:link rel="alternate" hreflang="ko" href="{ORIGIN}/blog/{suffix}" />'
        f'<xhtml:link rel="alternate" hreflang="en" href="{ORIGIN}/en/blog/{suffix}" />'
    )


def patch_sitemap(root: Path, slugs: list[str]) -> None:
    path = root / "sitemap.xml"
    xml = path.read_text(encoding="utf-8")
    before = set(re.findall(r"<loc>([^<]+)</loc>", xml))
    if 'xmlns:xhtml=' not in xml:
        xml = xml.replace(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
            1,
        )

    def patch_block(loc: str, links: str, must_exist: bool) -> None:
        nonlocal xml
        pattern = re.compile(rf"<url>\s*<loc>{re.escape(loc)}</loc>[\s\S]*?</url>")
        match = pattern.search(xml)
        if not match:
            if must_exist:
                raise RuntimeError(f"sitemap missing required URL {loc}")
            xml = xml.replace("</urlset>", f"<url><loc>{loc}</loc>{links}</url>\n</urlset>", 1)
            return
        block = re.sub(r'<xhtml:link\s+rel="alternate"\s+hreflang="(?:ko|en)"\s+href="[^"]+"\s*/>', "", match.group(0))
        block = block.replace("</url>", f"{links}</url>")
        xml = xml[: match.start()] + block + xml[match.end() :]

    patch_block(f"{ORIGIN}/blog/", sitemap_links(), True)
    patch_block(f"{ORIGIN}/en/blog/", sitemap_links(), False)
    for slug in slugs:
        ko, en = article_urls(slug)
        patch_block(ko, sitemap_links(slug), True)
        patch_block(en, sitemap_links(slug), False)
    after = set(re.findall(r"<loc>([^<]+)</loc>", xml))
    missing = sorted(before - after)
    if missing:
        raise RuntimeError(f"sitemap merge removed URLs: {missing}")
    path.write_text(xml, encoding="utf-8")


def rebuild_index(root: Path, payload: Path, entries: list[dict], applied: set[str]) -> None:
    template = (payload / "index-template.html").read_text(encoding="utf-8")
    marker = '<div class="blog-grid">'
    start = template.index(marker) + len(marker)
    end = template.index('</div>\n<footer class="blog-footer">', start)
    cards = []
    for entry in reversed(entries):
        if entry["id"] not in applied:
            continue
        cards.append((payload / "packages" / entry["package"] / "card.html").read_text(encoding="utf-8").strip())
    if not cards:
        raise RuntimeError("refusing to build an empty English index")
    index = template[:start] + "\n".join(cards) + template[end:]
    target = root / "en" / "blog" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(index, encoding="utf-8")


def local_asset_urls(html: str) -> set[str]:
    return set(re.findall(r'(?:src|content)="(/[^"?#]+\.(?:webp|png|jpg|jpeg|svg))"', html, flags=re.I))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--now")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    payload = args.payload.resolve()
    now = parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    entries = json.loads((payload / "manifest-en.json").read_text(encoding="utf-8"))
    state_path = root / ".scheduled-blog-state-en.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"applied": []}
    applied = set(state.get("applied", []))
    ready: list[dict] = []
    for entry in entries:
        if entry["id"] in applied or parse_utc(entry["scheduled_at"]) > now:
            continue
        slug = entry["slug"]
        package = payload / "packages" / entry["package"]
        article = package / "site" / "en" / "blog" / slug / "index.html"
        ko_page = root / "blog" / slug / "index.html"
        if not article.exists():
            raise RuntimeError(f"package article missing: {article}")
        if not ko_page.exists():
            print(f"blocked {entry['id']} {slug}: Korean counterpart is not live")
            continue
        html = article.read_text(encoding="utf-8")
        missing_assets = sorted(url for url in local_asset_urls(html) if not (root / url.lstrip("/")).exists())
        if missing_assets:
            print(f"blocked {entry['id']} {slug}: missing live assets {', '.join(missing_assets)}")
            continue
        ready.append(entry)

    if ready:
        for entry in ready:
            slug = entry["slug"]
            source = payload / "packages" / entry["package"] / "site" / "en" / "blog" / slug
            target = root / "en" / "blog" / slug
            shutil.copytree(source, target, dirs_exist_ok=True)
            applied.add(entry["id"])
            print(f"promoted {entry['id']} {slug} ({entry['scheduled_kst']})")
        ordered = [entry["id"] for entry in entries if entry["id"] in applied]
        applied_slugs = [entry["slug"] for entry in entries if entry["id"] in applied]
        rebuild_index(root, payload, entries, applied)
        patch_korean_html(root / "blog" / "index.html")
        for slug in applied_slugs:
            patch_korean_html(root / "blog" / slug / "index.html", slug)
        patch_sitemap(root, applied_slugs)
        state_path.write_text(json.dumps({"applied": ordered}, indent=2) + "\n", encoding="utf-8")

    complete = len(applied) == len(entries)
    if complete and ready:
        (root / ".github" / "workflows" / "publish-scheduled-blog-en.yml").unlink(missing_ok=True)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"changed={'true' if ready else 'false'}\n")
            handle.write(f"count={len(ready)}\n")
            handle.write(f"complete={'true' if complete else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
