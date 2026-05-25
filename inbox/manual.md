# Editorial inbox — coma.fm Radar
#
# Кожен запис — YAML-блок між роздільниками `---`.
# Типи:
#   type: link        — посилання на статтю, реліз або сторінку
#   type: editor_note — редакторська нотатка без зовнішнього URL
#
# Поля:
#   title             (обов'язково)
#   url               (обов'язково для link, не потрібно для editor_note)
#   notes             вільний текст
#   suggested_genres  один рядок або YAML-список
#   suggested_artists один рядок або YAML-список
#   priority          low | normal | high | must_use  (default: normal)
#   status            new | reviewed | accepted | rejected | used | archived  (default: new)

---
type: link
title: "New instrumental surf compilation — Reverb Caravan Vol.3"
url: https://reverbcaravan.bandcamp.com/album/vol-3
notes: Excellent reverb-heavy twang, very coma.fm. Potential signal of the week.
suggested_genres: surf, instrumental_surf
suggested_artists: The Shadowers, Los Ventiladores
priority: high
status: new

---
type: link
title: "The Meteors — 40 years of psychobilly: in conversation"
url: https://example-zine.com/meteors-40-years
notes: Long-form retrospective. Worth an essay treatment for the next issue.
suggested_genres: psychobilly, horrorbilly
suggested_artists: The Meteors
priority: normal
status: new

---
type: editor_note
title: Surf without the sea
notes: >
  Instrumental surf давно відірвався від пляжу. В coma.fm він звучить радше як музика
  дороги, мотелю й лампи над порожньою барною стійкою. Це не про океан — це про швидкість
  і порожнечу.
suggested_genres: surf, jazz_noir
priority: must_use
status: new
