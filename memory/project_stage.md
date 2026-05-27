---
name: project-stage
description: Current stage, pipeline structure, key design constraints, CSS approach
metadata:
  type: project
---

Current stage: **Stage 20 — Pearl Broadcast Modernism**

**Why:** Visual redesign from warm dark modernist (Stage 19) to light pearl paper editorial system. Swiss/Bauhaus/mid-century/streamline direction.

**How to apply:** When suggesting visual or CSS changes, work within the Pearl Broadcast Modernism palette (light bg, not dark). Always preserve test coverage.

## Pipeline structure

- `scripts/build_css.py` — renders `templates/style.css.j2` → `dist/assets/style.css`
- `scripts/build_site.py` — renders index + archive per language
- `scripts/build_issue.py` — renders individual issue pages
- `scripts/build_tag_pages.py` — renders tag pages + tags index
- `scripts/build_daily_draft.py` — orchestrates a full build run

## Design system (Stage 20)

Palette: pearl paper `#F3EBDD`, warm ivory `#EFE6D6`, dusty cream `#E6D9C6`, graphite `#1F2523`, muted brown `#6A5F52`, burnt orange `#D86F32`, petrol teal `#2E8C8A`, oxide red `#A93A32`, ochre `#C6A13A`.

Key classes: `.masthead`, `.brand-grid`, `.signal-strip`, `.frequency-lines`, `.program-grid`, `.issue-layout`, `.issue-hero`, `.issue-meta-panel`, `.entry-list`, `.entry-card`, `.entry-number`, `.archive-index`, `.archive-row`, `.taxonomy-board`, `.taxonomy-module`, `.tag-dossier`, `.tag-strip`.

## Constraints

- No dark base background (`--bg` is pearl paper, not black/dark)
- No external CDN, Google Fonts, or JS
- No `border-radius` beyond 0–6px
- `dist/` is not in git
- `reports/*.txt` is not in git
- `data/coma_radar.sqlite` is not in git

## Test count

492 tests passing as of Stage 20.
