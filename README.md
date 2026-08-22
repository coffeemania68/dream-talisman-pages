# Scheduled English Dream Blog payload

This branch is an isolated publication payload. `manifest-en.json` contains all 90 verified English articles; each package contains only one rendered English article and its index card.

The first 26 entries retain their original schedule through 2026-08-30. Entries 26–49 publish three times daily from 2026-08-31 through 2026-09-07. The remaining entries publish twice daily from 2026-09-08 through 2026-09-27, with the nominal slot times advancing slightly each day.

The default-branch workflow validates the current Korean counterpart and every referenced local asset before promotion. Missing dependencies remain unapplied. It rebuilds the English index, reciprocal language links, and sitemap from the latest `main`; it never copies a site-root snapshot from a package.
