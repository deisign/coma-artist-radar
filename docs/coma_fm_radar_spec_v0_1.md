# coma.fm Radar — технічне та редакційне завдання

Версія: `0.1`  
Дата фіксації: `2026-05-25`  
Робоча назва: **coma.fm Radar**  
Рекомендований субдомен: **radar.coma.fm**  
Медіа-субдомен: **media.coma.fm**

---

## 1. Суть проєкту

**coma.fm Radar** — двомовний музичний радар / редакційний журнал навколо естетичного поля coma.fm.

Це не просто агрегатор новин по артистах. Система має збирати й осмислювати:

- нові релізи;
- перевидання;
- архівні записи;
- інтерв’ю;
- рецензії;
- жанрові матеріали;
- статті про сцени, лейбли й музичні ніші;
- ручні редакторські знахідки;
- авторські нотатки.

Головна ідея:

```text
tracks CSV + artist registry
+
canonical genre/tag map
+
source pool
+
human/editorial inbox
+
automated monitoring
+
Claude editorial pass
=
bilingual coma.fm Radar issue
```

Система має працювати як **музичний нооскоп coma.fm**: ловити не лише “що нового”, а й “що належить до нашого поля”.

---

## 2. Вихідні дані

Завантажений CSV Radio.co:

```text
data/s4360dbc20.csv
```

Перевірена структура на поточному файлі:

```text
Rows: 8849
Columns: Title, Artist, Album, Duration, Media Type
Unique Artist values before cleaning: 2912
```

Приклади найчастіших Artist-значень у поточному CSV:

```text
Amphibian Man
Lou Reed
The Rolling Stones
Angelo Badalamenti
The Wise Guyz
David Bowie
The Stranglers
Bohren & Der Club Of Gore
Marianne Faithfull
The Pretenders
```

Важливо: поле `Artist` не можна вважати чистим canonical artist list. Там можливі:

- `feat.`;
- `with`;
- `&`;
- `and`;
- оркестри / backing bands;
- колаборації;
- службові значення;
- різні написання одного артиста.

---

## 3. Принципова архітектура

```text
GitHub repository
    ↓
Python scripts
    ↓
SQLite editorial database
    ↓
Static site generator
    ↓
GitHub Pages: radar.coma.fm
    ↓
Cloudflare R2: media.coma.fm
    ↓
Telegram announcement
```

Claude використовується не як єдине джерело істини, а як:

1. помічник у розробці через Claude Code;
2. редакторський шар для добору й адаптації матеріалів;
3. можливий агент для scheduled routines після стабілізації пайплайна.

Скрипти, база, конфіги, шаблони й дані мають жити в репозиторії, а не лише локально на ноутбуці.

---

## 4. Публікація

Основний сайт:

```text
https://radar.coma.fm/
```

Структура:

```text
radar.coma.fm/
  en/
    index.html
    archive.html
    issues/
      2026-05-25.html
    tags/
      index.html
      surf.html
      psychobilly.html
  uk/
    index.html
    archive.html
    issues/
      2026-05-25.html
    tags/
      index.html
      surf.html
      psychobilly.html
  feed.xml
  sitemap.xml
  robots.txt
```

Медіа:

```text
https://media.coma.fm/issues/2026/05/2026-05-25/cover-og.webp
```

Платформа:

```text
GitHub Pages для HTML
Cloudflare R2 для зображень
```

---

## 5. Двомовність

Проєкт має бути двомовним:

```text
English + Ukrainian
```

Базова логіка:

```text
EN = international / source-facing / archival version
UK = Ukrainian editorial adaptation
```

Українська версія не має бути машинною калькою. Вона повинна пояснювати контекст, але не додавати неперевірених фактів.

### 5.1. Музичні теги не перекладаються

Музичні жанрові та естетичні теги залишаються стабільними в міжнародному вигляді.

Не перекладати:

```text
surf
instrumental surf
rockabilly
neo-rockabilly
psychobilly
horrorbilly
punkabilly
jazz noir
dark jazz
lounge noir
swamp blues
jump blues
honky tonk
country noir
gothic country
ghost americana
exotica
space age pop
garage surf
garage blues
cowpunk
deathrock
```

Перекладається / адаптується:

- навігація;
- описи тегів;
- редакційні тексти;
- вступи;
- пояснення;
- Telegram-анонси.

Приклад:

```yaml
- id: instrumental_surf
  slug: instrumental-surf
  type: subgenre
  label: Instrumental surf
  description_en: "Instrumental surf, surf guitar, twang and reverb-heavy guitar music."
  description_uk: "Instrumental surf, surf guitar, twang і гітарна музика з густим ревербом."
```

---

## 6. Жанрове ядро

Початкові core genres coma.fm:

```text
jazz
blues
country
rockabilly
psychobilly
surf
```

Але система має працювати не на плоскому списку, а на карті жанрів, сабжанрів і естетичних тегів.

Файл:

```text
data/genre_radar.yaml
```

Для кожного жанру:

```text
core_tags
adjacent_tags
negative_tags
search_phrases
aesthetic_tags
```

Приклад:

```yaml
psychobilly:
  core_tags:
    - psychobilly
    - horrorbilly
    - punkabilly
    - gothabilly
  adjacent_tags:
    - horror punk
    - deathrock
    - garage punk
    - surf punk
  negative_tags:
    - psychology
    - billy idol gossip
  search_phrases:
    - '"psychobilly" "new album"'
    - '"psychobilly" "review"'
    - '"horrorbilly" "bandcamp"'
  aesthetic_tags:
    - lacquer_and_graves
    - graveyard_party
```

### 6.1. Psychobilly style note

У psychobilly не “бриолін”, а **лак**.

Правильно:

```text
hairspray / lacquered quiffs / mohawks / psychobilly wedge
```

Не використовувати psychobilly-опис через greaser-помаду.

Приклад опису:

```yaml
- id: psychobilly
  slug: psychobilly
  type: genre
  label: Psychobilly
  parent: rockabilly
  aliases:
    - psycho-billy
    - horrorbilly
    - punkabilly
  related_tags:
    - horrorbilly
    - punkabilly
    - rockabilly
    - horror_punk
    - deathrock
  description_en: "A fast, punk-infected rockabilly strain with horror imagery, upright bass, lacquered quiffs and graveyard humor."
  description_uk: "Швидка, панкова гілка rockabilly з horror-образністю, контрабасом, лакованими зачісками й цвинтарним гумором."
```

Окремий aesthetic tag:

```yaml
- id: lacquer_and_graves
  slug: lacquer-and-graves
  type: aesthetic
  label: Lacquer & Graves
  related_tags:
    - psychobilly
    - horrorbilly
    - punkabilly
    - horror_punk
  description_en: "Psychobilly aesthetics: hairspray, upright bass, graveyard jokes, horror pulp and punk speed."
  description_uk: "Естетика psychobilly: лак, контрабас, цвинтарний гумор, horror-pulp і панкова швидкість."
```

---

## 7. Система тегів

Теги — центральний словник проєкту.

Основний файл:

```text
data/tags.yaml
```

Правила автоматичного мапінгу:

```text
data/tag_rules.yaml
data/tag_mapping.yaml
```

Типи тегів:

```text
genre
subgenre
aesthetic
content_type
source_type
editorial
negative
```

### 7.1. Приклади тегів

Genre:

```text
jazz
blues
country
rockabilly
psychobilly
surf
```

Subgenre:

```text
jazz_noir
dark_jazz
lounge_jazz
swamp_blues
jump_blues
honky_tonk
country_noir
gothic_country
neo_rockabilly
horrorbilly
instrumental_surf
surf_revival
garage_surf
```

Aesthetic:

```text
lynchy
ghost_americana
grease_and_reverb
lacquer_and_graves
retro_future
lounge_noir
midnight_drive
dusty_vinyl
bad_radio_signal
graveyard_party
```

Content type:

```text
new_release
single
album
ep
reissue
compilation
archive_release
live_recording
interview
review
essay
obituary
festival
tour
video
podcast
label_profile
scene_report
editor_note
```

Editorial:

```text
must_use
high_priority
needs_check
good_for_telegram
evergreen
time_sensitive
duplicate_risk
weak_source
```

Negative:

```text
seo_listicle
celebrity_gossip
sports_surfing
mainstream_pop_country
generic_blues_rock
press_release_only
country_as_nation
ai_generated_spam
```

### 7.2. Tag confidence

Кожен автоматичний тег повинен мати джерело й confidence.

Приклад:

```json
{
  "tag": "instrumental_surf",
  "source": "keyword_match",
  "confidence": 0.92
}
```

Пріоритет джерел тегів:

```text
manual > program_rule > artist_rule > source_registry > external_api > keyword_match > claude_editorial
```

Ручні теги завжди сильніші за автоматичні.

---

## 8. Клік по тегу / tag pages

Теги мають бути клікабельними.

Механізм:

```text
published issue JSON files
    ↓
build tag index
    ↓
generate tag pages
```

Для кожного canonical tag створюється сторінка:

```text
/en/tags/surf.html
/uk/tags/surf.html
```

Загальна карта тегів:

```text
/en/tags/index.html
/uk/tags/index.html
```

Сторінка тега має показувати:

- tag label;
- English/Ukrainian description;
- related tags;
- список матеріалів із датою;
- посилання на випуск;
- excerpt;
- matched artists, якщо є.

Музичний label у EN і UK однаковий:

```text
Psychobilly
```

А опис — мовою сторінки.

---

## 9. Artist registry

Файл:

```text
data/artists_registry.csv
```

Поля:

```text
artist_raw
artist_canonical
track_count
monitor_priority
ignore
notes
```

Приорітети:

```text
high    >= 20 tracks
medium  5–19 tracks
low     1–4 tracks
```

Окремо потрібен authority file для aliases:

```text
data/artist_aliases.yaml
```

Приклад:

```yaml
- canonical: Nick Cave & The Bad Seeds
  aliases:
    - Nick Cave and The Bad Seeds
    - Nick Cave & Bad Seeds
  related:
    - Nick Cave
    - Grinderman
    - Warren Ellis
  priority: high
```

Artist registry потрібен для:

- моніторингу новин по артистах;
- track catalog enrichment;
- перетину статей із артистами coma.fm;
- побудови сторінок артистів у майбутньому.

---

## 10. Source registry

Файл:

```text
data/sources_music.yaml
```

Це має бути не список “музичних журналів взагалі”, а джерела, чутливі до поля coma.fm.

Типи джерел:

```text
magazine
blog
label
bandcamp_editorial
festival
archive
youtube_channel
podcast
newsletter
radio
official_artist_site
```

Поля:

```text
name
site_url
feed_url
source_type
language
region
genre_tags
priority
active
paywall
notes
```

Джерела мають оцінюватися за:

```text
genre_match_count
artist_match_count
rss_available
freshness
editorial_depth
seo_garbage penalty
press_release_duplicate penalty
paywall penalty
```

---

## 11. Labels layer

Для музики coma.fm лейбли можуть бути важливіші за великі журнали.

Файл:

```text
data/labels.yaml
```

Поля:

```text
name
site_url
bandcamp_url
feed_url
genre_tags
priority
notes
```

Лейбли моніторяться для:

- перевидань;
- архівних релізів;
- збірок;
- vinyl reissues;
- rare recordings;
- scene/label profiles.

---

## 12. Human / Editorial Intake

Система має приймати матеріали “від людини”.

Це не допоміжний канал, а рівноправний редакційний вхід.

Файли:

```text
inbox/manual.md
data/editorial_inbox.yaml
```

Або таблиця SQLite:

```text
human_submissions
```

Поля:

```text
id
submitted_at
submitted_by
source_type
url
title
notes
suggested_genres
suggested_artists
priority
status
used_in_issue
issue_date
created_by
```

Priority:

```text
low
normal
high
must_use
```

Status:

```text
new
reviewed
accepted
rejected
used
archived
```

### 12.1. Типи ручних матеріалів

- URL на статтю;
- Bandcamp release;
- YouTube video;
- label page;
- festival page;
- interview;
- archive item;
- власна редакторська нотатка без URL.

Приклад editor note:

```yaml
- type: editor_note
  title: "Surf without the sea"
  genres: [surf, noir]
  priority: must_use
  note: >
    Instrumental surf давно відірвався від пляжу. В coma.fm він звучить радше як музика дороги,
    мотелю й лампи над порожньою барною стійкою.
```

Правило:

```text
human priority high/must_use має більшу вагу, ніж автоматичний score
```

Claude не має переписувати авторські нотатки до невпізнаваності. Він може лише акуратно редагувати стиль, якщо це дозволено.

---

## 13. Автоматичний моніторинг

Daily monitor:

```text
RSS / Atom feeds
label pages
Bandcamp/editorial sources
MusicBrainz/Spotify/Discogs/Last.fm enrichment later
manual inbox
```

Weekly discovery:

```text
genre search phrases
new sources
new labels
new artists
new scenes
```

Daily monitor відповідає:

```text
що нового у відомих джерелах?
```

Weekly discovery відповідає:

```text
які нові джерела / сцени / артисти схожі на coma.fm?
```

---

## 14. База даних

Файл:

```text
data/coma_radar.sqlite
```

Основні таблиці:

```text
artists
sources
labels
items
human_submissions
issues
seen_urls
```

`items`:

```text
id
title
url
canonical_url
source
source_type
published_at
first_seen_at
last_seen_at
matched_artists
matched_tags
matched_genres
score
included_in_issue
```

Потрібно зберігати:

```text
url_hash
title_hash
canonical_url
first_seen_at
last_seen_at
included_in_issue
```

Ціль — не повторювати одні й ті ж матеріали.

---

## 15. Scoring

Item score має враховувати:

```text
+ matched artist from artist registry
+ matched core genre tag
+ matched adjacent tag
+ source priority
+ content type: reissue / archive / interview / review / new album
+ human priority
- negative tags
- SEO garbage
- duplicate risk
- weak source
```

Приклад candidate JSON:

```json
{
  "title": "New instrumental surf compilation...",
  "url": "https://example.com/item",
  "source": "Example Label",
  "published_at": "2026-05-25",
  "matched_artists": [],
  "matched_tags": ["surf", "instrumental_surf", "grease_and_reverb"],
  "source_score": 70,
  "item_score": 82,
  "why_candidate": "matched instrumental surf + reissue + high-priority label"
}
```

---

## 16. Claude editorial pass

Claude отримує не “погугли все”, а структурований JSON кандидатів.

Вхід:

```json
[
  {
    "title": "...",
    "url": "...",
    "source": "...",
    "published_at": "...",
    "matched_tags": ["surf"],
    "matched_artists": ["..."],
    "score": 84,
    "excerpt": "...",
    "why_candidate": "..."
  }
]
```

Завдання Claude:

- вибрати 5–10 найкращих матеріалів;
- пояснити, чому вони важливі для coma.fm;
- не додавати фактів поза evidence;
- не вигадувати посилань;
- створити EN version;
- створити UK adaptation;
- зберегти стабільні music tags;
- залишити авторські нотатки впізнаваними.

---

## 17. Формат випуску

Базова структура:

```text
1. Signal of the day
2. From the coma.fm rotation field
3. Genre catch
4. Archive noise
5. Label / scene / reissue signal
6. Editor note
```

Не обов’язково всі блоки в кожному випуску.

Правило для публікації:

```text
якщо менше 3 сильних матеріалів — не публікувати повний випуск автоматично
```

---

## 18. Telegram

Telegram — це вітрина, не повний журнал.

Пост:

```text
📡 coma.fm Radar — 25.05

Сьогодні в полі:
— ...
— ...
— ...

Повний випуск:
https://radar.coma.fm/uk/issues/2026-05-25.html
```

Для Telegram краще використовувати український анонс.

Telegram має отримувати:

- короткий текст;
- посилання на повний випуск;
- одну generated cover/card.

---

## 19. Зображення

Не перезаливати автоматично чужі картинки зі статей.

Основна схема:

```text
generated cover/card → Cloudflare R2 → media.coma.fm
```

Файли для одного випуску:

```text
cover-og.webp          1200x630
cover-telegram.webp    1080x1080 або 1200x630
cover-header.webp      для hero-блоку сайту
```

Структура R2:

```text
coma-radar-media/
  issues/
    2026/
      05/
        2026-05-25/
          cover-og.webp
          cover-telegram.webp
          cover-header.webp
  genres/
    surf.webp
    psychobilly.webp
    jazz-noir.webp
```

Файли проєкту:

```text
scripts/generate_issue_cover.py
scripts/upload_media_r2.py
templates/cover.svg.j2
data/visual_themes.yaml
```

Візуальна тема обирається за main_genre / main aesthetic tag.

---

## 20. Пошук та індексація

Потрібні три рівні пошуку.

### 20.1. External indexing

Для Google/Bing:

```text
robots.txt
sitemap.xml
feed.xml
hreflang
canonical
OpenGraph
```

Закрити від індексації:

```text
/reports/
/drafts/
/data/
/admin/
/internal/
```

Не публікувати повні тексти чужих статей.

### 20.2. Public site search

Статичний пошук через Pagefind або аналогічний static search.

Індексувати тільки опубліковані випуски:

```html
<main data-pagefind-body>
```

Мови:

```html
<html lang="en">
<html lang="uk">
```

### 20.3. Editorial search

SQLite FTS для внутрішнього пошуку по:

- кандидатах;
- відхилених матеріалах;
- ручних submissions;
- джерелах;
- артистах;
- випусках;
- нотатках.

Команда майбутнього пошуку:

```bash
python scripts/search_archive.py "surf guitar reissue"
python scripts/search_archive.py "Badalamenti jazz noir"
python scripts/search_archive.py "psychobilly"
```

---

## 21. Enrichment музичної бази coma.fm

Після побудови карти субжанрів і canonical tag dictionary потрібно використати ті самі теги для музичної бази coma.fm.

Один словник тегів має використовуватися в:

```text
coma.fm Radar
track catalog / track passport
program pages
filters
search
Telegram
```

Центральні файли:

```text
data/tags.yaml
data/tag_mapping.yaml
data/artist_tag_rules.yaml
data/program_tag_rules.yaml
```

Скрипт:

```text
scripts/enrich_tracks_tags.py
```

Вхід:

```text
data/s4360dbc20.csv
```

Вихід:

```text
data/tracks_enriched.csv
data/tracks_enriched.json
```

Поля enriched track:

```text
artist
title
album
canonical_artist
canonical_title
canonical_tags
aesthetic_tags
program_tags
tag_sources
confidence
```

Логіка пріоритету:

```text
manual tags
program rules
artist rules
external tags
keyword rules
```

Приклад:

```json
{
  "artist": "The Meteors",
  "title": "Graveyard Stomp",
  "canonical_tags": [
    "psychobilly",
    "horrorbilly",
    "rockabilly",
    "punkabilly"
  ],
  "aesthetic_tags": [
    "lacquer_and_graves",
    "graveyard_party"
  ],
  "program_tags": [
    "psycho_barbara"
  ],
  "confidence": 0.91
}
```

---

## 22. Рекомендована структура репозиторію

```text
coma-artist-radar/
  data/
    s4360dbc20.csv
    artists_registry.csv
    artist_aliases.yaml
    genre_radar.yaml
    tags.yaml
    tag_rules.yaml
    tag_mapping.yaml
    artist_tag_rules.yaml
    program_tag_rules.yaml
    sources_music.yaml
    labels.yaml
    visual_themes.yaml
    coma_radar.sqlite

  inbox/
    manual.md

  content/
    issues/
      2026-05-25.en.json
      2026-05-25.uk.json

  scripts/
    import_artists.py
    match_genres.py
    tag_item.py
    validate_sources.py
    import_human_submissions.py
    fetch_sources.py
    score_items.py
    build_issue.py
    build_bilingual_issue.py
    build_tag_pages.py
    build_sitemap.py
    build_feed.py
    generate_issue_cover.py
    upload_media_r2.py
    send_telegram.py
    enrich_tracks_tags.py
    search_archive.py

  templates/
    issue.html.j2
    tag_page.html.j2
    tags_index.html.j2
    index.html.j2
    archive.html.j2
    cover.svg.j2
    robots.txt.j2
    sitemap.xml.j2
    feed.xml.j2

  reports/
    sources_report.csv
    source_candidates.csv
    unknown_tags.csv
    duplicate_report.csv

  dist/
    en/
    uk/
    pagefind/
    sitemap.xml
    robots.txt
    feed.xml

  tests/
    test_import_artists.py
    test_match_genres.py
    test_tag_item.py
    test_sources_registry.py
    test_human_submissions.py
    test_build_issue.py
    test_build_tag_pages.py
    test_enrich_tracks_tags.py

  docs/
    EDITORIAL_STYLE_EN.md
    EDITORIAL_STYLE_UK.md
    PIPELINE.md
    TAGGING.md
    SOURCES.md

  README.md
```

---

## 23. Етапність задач

### Етап 0. Concept lock

Зафіксувати:

```text
name: coma.fm Radar
domain: radar.coma.fm
media domain: media.coma.fm
languages: English + Ukrainian
platform: GitHub Pages + Cloudflare R2
mode: semi-auto first, auto later
```

### Етап 1. Repository skeleton

Створити структуру:

```text
data/
scripts/
tests/
templates/
content/
dist/
docs/
reports/
inbox/
```

### Етап 2. Import artists from CSV

Скрипт:

```text
scripts/import_artists.py
```

Результат:

```text
data/artists_raw.csv
data/artists_registry.csv
```

Тести обов’язкові.

### Етап 3. Genre radar

Створити:

```text
data/genre_radar.yaml
scripts/match_genres.py
```

Перевірити core/adjacent/negative tags.

### Етап 4. Canonical tag taxonomy

Створити:

```text
data/tags.yaml
data/tag_rules.yaml
scripts/tag_item.py
```

Теги мають бути канонічні, стабільні, не перекладатися як labels.

### Етап 5. Editorial inbox

Створити:

```text
inbox/manual.md
scripts/import_human_submissions.py
```

Підтримати:

```text
manual link
editor_note
priority
status
must_use
```

### Етап 6. Source registry

Створити:

```text
data/sources_music.yaml
scripts/validate_sources.py
```

Перевірка RSS/Atom, HTTP status, active/inactive.

### Етап 7. SQLite seen-items

Створити базу:

```text
data/coma_radar.sqlite
```

Таблиці:

```text
items
seen_urls
issues
human_submissions
sources
artists
```

### Етап 8. Fetch sources

Створити:

```text
scripts/fetch_sources.py
```

Збирати RSS/Atom, складати нові candidates.

### Етап 9. Score items

Створити:

```text
scripts/score_items.py
```

Враховувати tags, artists, source score, human priority, negative tags.

### Етап 10. First static issue without Claude

Створити:

```text
scripts/build_issue.py
templates/issue.html.j2
```

Згенерувати перший EN/UK draft з мінімальним текстом.

### Етап 11. Claude editorial pass

Підключити Claude як редактора structured candidates.

Вихід:

```text
content/issues/YYYY-MM-DD.en.json
content/issues/YYYY-MM-DD.uk.json
```

### Етап 12. GitHub Pages

Опублікувати сайт:

```text
radar.coma.fm
```

Додати:

```text
robots.txt
sitemap.xml
feed.xml
hreflang
canonical
OpenGraph
```

### Етап 13. Tag pages

Створити:

```text
scripts/build_tag_pages.py
templates/tag_page.html.j2
templates/tags_index.html.j2
```

Вихід:

```text
/en/tags/
/uk/tags/
```

### Етап 14. Telegram dry-run

Створити:

```text
scripts/send_telegram.py
```

Спочатку:

```text
--dry-run
```

Потім ручна публікація.

### Етап 15. Media pipeline

Створити:

```text
scripts/generate_issue_cover.py
scripts/upload_media_r2.py
templates/cover.svg.j2
data/visual_themes.yaml
```

Зберігати generated covers у Cloudflare R2.

### Етап 16. Semi-auto period

2–3 тижні:

```text
fetch → score → Claude draft → human review → publish
```

### Етап 17. Automation

Після стабілізації:

```text
GitHub Actions або Claude Code Routine
```

Правило:

```text
якщо менше 3 сильних матеріалів — не autopublish
```

### Етап 18. Weekly discovery

Створити weekly discovery:

```text
genre search phrases
new domains
new labels
new sources
source_candidates.csv
```

Не додавати джерела автоматично без review.

### Етап 19. Track catalog enrichment

Після стабілізації tag taxonomy:

```text
scripts/enrich_tracks_tags.py
```

Застосувати canonical tags до всієї музичної бази coma.fm.

### Етап 20. Advanced public archive

Пізніше:

```text
artist pages
program pages
label pages
source pages
tag graph
track/tag cross-links
```

---

## 24. Мінімальний MVP

MVP вважається готовим, якщо є:

```text
1. artists_registry.csv з CSV Radio.co
2. tags.yaml з canonical music tags
3. genre/tag matcher з тестами
4. editorial inbox
5. sources_music.yaml
6. fetch + score candidates
7. static EN/UK issue
8. tag pages
9. sitemap/robots/feed
10. generated cover
11. Telegram dry-run
```

Autopublish не входить у MVP. Спочатку потрібен semi-auto режим.

---

## 25. Перший prompt для Claude Code

```text
Создай минимальный репозиторий coma-artist-radar.

Контекст:
У нас есть CSV Radio.co с треками coma.fm: data/s4360dbc20.csv.
Колонки: Title, Artist, Album, Duration, Media Type.

Задача:
1. Создай структуру проекта:
   data/
   scripts/
   tests/
   reports/
   docs/
   inbox/
   templates/
   content/
2. Напиши scripts/import_artists.py.
3. Скрипт должен:
   - читать data/s4360dbc20.csv;
   - извлекать Artist;
   - чистить пробелы;
   - считать количество треков на каждого артиста;
   - сохранять data/artists_raw.csv;
   - сохранять data/artists_registry.csv.
4. artists_registry.csv должен иметь колонки:
   artist_raw, artist_canonical, track_count, monitor_priority, ignore, notes.
5. monitor_priority:
   - high для >=20 треков;
   - medium для 5–19;
   - low для 1–4.
6. ignore=true для пустых значений и artist_raw == "coma.fm".
7. Добавь pytest-тесты.
8. Добавь README с командами запуска.
9. Никаких TODO, заглушек и псевдокода.
10. После выполнения запусти:
    python scripts/import_artists.py
    pytest -q
    head -20 data/artists_registry.csv
```

---

## 26. Принципы якості

- Усі скрипти мають мати тести.
- Ніяких фейкових даних у production pipeline.
- Ніяких повних копій чужих статей у public output.
- Ніяких автоматичних публікацій без достатнього score на старті.
- Ручний editorial input має найвищий пріоритет.
- Music tags не перекладати.
- Авторські нотатки не перетворювати на AI-style prose.
- Claude не вигадує факти, а редагує structured evidence.
- Canonical tags мають бути єдиними для Radar і music catalog enrichment.
- Система має пам’ятати seen/used materials і не повторювати старе.
- Якщо система не впевнена — створити draft, а не публікувати.

---

## 27. Коротка формула

```text
artists = хто звучить на coma.fm
tags = як coma.fm розуміє музику
sources = де шукати сигнали
human inbox = редакторська інтуїція
Claude = редактор structured evidence
GitHub Pages = журнал
R2 = власна графіка
Telegram = вітрина
SQLite = пам’ять
```

**coma.fm Radar** має стати не RSS-агрегатором, а живим двомовним архівом і радаром музичного поля coma.fm.
