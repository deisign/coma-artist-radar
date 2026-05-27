# Stage26A — Issue Hero Cleanup

Project:
coma.fm Radar

Task:
Remove raw machine/payload feeling from issue hero section.

Current problem:
The issue hero currently exposes raw item structures / payload-like content.
This destroys the transmission atmosphere.

Goal:
Transform issue hero into an editorial transmission block.

Requirements:

1. REMOVE
- raw item arrays
- raw JSON-like structures
- payload dumps
- debug-looking content

2. ADD
A short editorial transmission summary block:
- 2–4 lines max
- atmospheric
- concise
- field-report tone
- no fake poetry
- no AI language

3. PRESERVE
- TX metadata
- band
- node
- signal count
- issue date
- transmission identity

4. LAYOUT
Hero must feel like:
- transmission bulletin
- engineering sheet
- radio field report
- modernist editorial cover

5. VISUAL TONE
Keep:
- pearl/beige engineering paper
- Swiss structure
- signal instrumentation
- relay aesthetics
- quiet metadata hierarchy

6. DO NOT
- redesign entire site
- break existing visual system
- remove transmission infrastructure
- add gradients/glassmorphism/shadows/SaaS aesthetics

7. AFTER IMPLEMENTATION RUN

python scripts/build_css.py

python scripts/build_daily_draft.py \
  --date 2026-05-26 \
  --fetch-limit 5 \
  --issue-limit 10 \
  --base-url https://deisign.github.io/coma-artist-radar \
  --base-path /coma-artist-radar \
  --telegram-dry-run

python -m pytest -q tests

8. PROVIDE
- git diff summary
- test results
- exact files changed

