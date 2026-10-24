# 06 — Worldbuilding and lore-keeping tools (other than World Anvil): features, data models, concepts

Survey date: October 2026. Focus: **mechanics and data models**, not user praise or complaints (those are in
[03-writing-tools.md](03-writing-tools.md)). The comparison point is Quarry as designed in [SPEC.md](../SPEC.md)
(phases 1–5) and [WORLD-MODEL.md](../WORLD-MODEL.md) (phases 6–9).

**Method.** Product pages, documentation, changelogs and a few third-party reviews and directory listings, read
between 24 Oct 2026 and the same day. Everything is paraphrased. Where a claim comes only from a directory listing
(AlternativeTo), a vendor's own comparison page, or my prior knowledge of a product that I could not re-verify
(marked **unverified**), I say so. AI-generation tools are noted only as a trend (§19).

**Name collision, worth knowing first.** The Story Shack (thestoryshack.com) now sells its writing and worldbuilding
app under the name **"Quarry"**, with the page title "Quarry: Worldbuilding Software, Map Maker & Writing App" (§15).
The two products serve the same audience.

---

## 1. Kanka (web; open source, self-hostable; freemium with premium campaigns)

The most structured of the hosted tools. It is built for TTRPG campaigns but is used by writers too. Version 3.9
(March 2026) renamed most concepts. The new names are used below, with the old names in brackets.

- **Entry types ("categories", formerly modules/entity types).** There are about 20 fixed categories: character,
  location, family, organisation, item, quest, journal, calendar, event, timeline, ability, creature, race, note, map,
  and others. Each can be switched off per campaign, but you can't add your own; a free-text *type* field
  sub-classifies within a category. Every entry has a name, aliases (managed in the name field since 3.9), an image,
  tags, a parent, a private flag, a description, **articles** (formerly posts: extra text sections, each with its own
  visibility), **properties** (formerly attributes), relations, inventory, abilities and reminders.
- **Properties and property kits (formerly attribute templates).** Properties are free label/value pairs. They can be
  calculated from other properties (HP = level × constitution), and premium campaigns can render them as a character
  sheet. *Property kits* are reusable sets of properties; *archetypes* (formerly entity templates) are whole
  pre-filled entries.
- **Relations (formerly connections).** These are explicit, labelled and two-sided. The label is free text (Kanka's
  guide says it should read as a verb phrase, such as "Trained by", and that "connected to" is not a valid label). A
  relation can be **mirrored** so it appears on both entries. From my prior knowledge (**unverified** in current
  docs), a relation also carries an *attitude* score, a colour, a pinned flag and a visibility. A separate **Related**
  list shows entries that point at this one through fields; **@mentions are kept out of that list** and shown on their
  own "mentioned in" subpage. The premium **Connection Map** draws the graph.
- **Two layers of linking.** Kanka's "living web" guide splits links into **relations** (deliberate, labelled, the
  bones) and **@mentions** (emergent, unlabelled, where an entry came up). Its diagram draws the first as solid lines
  and the second as dotted ones. Archived entries keep both as history.
- **Calendars.** You can have any number of calendars, with custom months, week length, seasons and moons with
  phases. Years run from −2 billion to +2 billion, with year 0 or year 1 as the start, and a date format made of
  tokens. A **child calendar** inherits its parent's setup and shows the parent's reminders. Eras are made by creating
  one calendar per era with a different *suffix*. A **current date** can be set by hand or advanced automatically each
  night. **Reminders** link an entry to a date and show for at most two months, so a long war needs several of them.
  A character's age can be computed from the calendar.
- **Timelines.** These are separate entries made of eras, and each era holds elements that link to entries. They
  have no shared numeric time axis with calendars.
- **Maps.** Version 3.14 (July 2026) rebuilt maps with editing on the map itself. Markers can be icons, areas
  (showing their surface area), circles, or paths (showing their length when the map has a distance unit). There are
  colour-coded groups, a searchable legend, live multiplayer cursors, and auto-tiling for large images. A marker links
  to an entry, and entries mentioned in marker descriptions count as mentions. Layers still need the old interface.
- **Family trees** (premium) are drawn on Family entries as their own structure. Each node has a visibility, which
  its descendants inherit. Family trees are **not included in exports**.
- **Organisations** have member lists with roles. **Inventory** is available on any entry (a character's
  possessions, a shop's stock), links to Item entries, and doesn't require an Item to exist. **Abilities** are
  available on any entry and track charges.
- **Secrets and permissions.** This is Kanka's most developed area. You can make a whole entry private (admin only),
  hide a single article, or set the visibility of a relation, inventory line, reminder or timeline element. Options
  are everyone, admins, self, self plus admins, and members. **Permission chaining** means a link is visible only to
  someone who can see both ends of it. Roles get per-category and per-entry permissions, and you can preview the
  campaign as any member sees it.
- **Editor.** A new Tiptap editor (alpha, 3.9) adds slash commands and bubble menus, and the redesigned @ menu can
  also find the current entry's properties and articles.
- **Whiteboards.** Version 3.5 (Nov 2025) added shapes, drawings, text and entry/image cards. Version 3.8 (Feb 2026)
  made them collaborative, and the new architecture reset existing boards.
- **Export and portability.** Admins can export once a day. The JSON export, with images, can be re-imported, though
  importing the same export twice creates duplicates. The Markdown export cannot be re-imported. Family trees,
  permissions and dashboards are lost in both. There is a public REST API and webhooks.
- **Offline and mobile:** responsive web only, with no offline mode.
- **Distinctive:** the clearest separation of *relations* from *mentions*, the strongest secrets model, and calendars
  that compute ages. The fixed categories and per-category fields make it one of the most rigid tools here.

Sources: https://kanka.io/features · https://blog.kanka.io/2026/03/10/version-3-9-a-new-language/ ·
https://docs.kanka.io/en/latest/_sources/features/connections.md.txt · https://kanka.io/learn/living-web ·
https://docs.kanka.io/en/latest/_sources/entries/calendars.md.txt · https://blog.kanka.io/2026/07/30/version-3-14-maps-v4/ ·
https://docs.kanka.io/en/latest/guides/secrets.html · https://docs.kanka.io/en/latest/advanced/visibility.html ·
https://docs.kanka.io/en/latest/features/campaigns/export.html · https://docs.kanka.io/en/latest/features/campaigns/import.html ·
https://app.kanka.io/api-docs/1.0/families · https://blog.kanka.io/2025/11/13/version-3-5-whiteboards-and-higher-limits/ ·
https://blog.kanka.io/2026/02/05/version-3-8-collabroative-whiteboards-referrals/ · https://blog.kanka.io/category/news

---

## 2. LegendKeeper (web with offline mode; subscription)

A lean wiki in which **maps are the main way into the world**. Its 2025–2026 changelog is very active.

- **Pages.** Pages nest freely to any depth, and there are **no entity types**. Structure comes from the page tree,
  templates (pages kept in a templates folder) and tags. Fast ways to create pages include @-mentions,
  **Cut-to-New-Page** (move a selection into a new page) and a one-action **auto-link** pass that links text matching
  existing page names.
- **Structured facts, added late.** Version 0.19.1 (Aug 2026) added an **Infobox block** (a Wikipedia-style container)
  and a **Properties block** (label/value facts whose values can @-mention pages). Before that, every fact was free
  text. Version 0.17.2 (Dec 2025) added a **Meter block** for progress bars, gauges and ratings.
- **Secrets.** Typing `/secret` creates a block inside a page that only admins see. Whole pages can also be hidden
  from everyone except chosen people. Pins can be hidden from players.
- **Atlas.** Maps up to about 14k px and 100 MB, **nested like pages** (world → region → town → dungeon). Pins link
  to pages, and a new page can be created from a map. Version 0.18 (Jan 2026) added **regions, paths, labels,
  measuring, "fantasy navigation" and multiplayer cursors**, and calibrated maps can be measured in read-only mode.
- **Time.** LegendKeeper's design post says it **solved calendar arithmetic first**, so that dates in any calendar
  can be compared and the real gaps between events shown. It describes a calendar as a timeline with word-wrap
  turned on. **Time systems** set hours per day, days per week, months and days per year, renamed units, eras and
  leap days per month. Moons with phase length and offset arrived in Nov 2025. Presets include Gregorian, Harptos and
  Exandria. A project can have several time systems.
  - **Timelines** have three views: List (chronicle), Gantt (spans from minutes to billions of years), and Calendar
    (one month at a time).
  - Each event has a start, an optional end, an icon and a colour, belongs to a **group** that can be filtered and
    coloured, and links to one page. Syncing a linked event copies the page's name and icon. Hovering an @-mention in
    a timeline shows a preview.
  - Separate timelines don't share events. The docs suggest groups for comparing versions of the story.
- **Boards.** A collaborative whiteboard with page cards and board cards.
- **Collaboration.** Real-time co-editing with cursors, and granular permissions.
- **Offline.** Edits go to browser storage and merge on reconnect. It doesn't work in private windows, and clearing
  site data loses unsynced work. Mobile is still a roadmap item.
- **Export, import and API.** Full-wiki export as HTML or JSON, with a warning that not every block is supported. The
  World Anvil zip import (Nov 2025) rebuilds hierarchy and @-mentions. Version 0.20 (Oct 2026) added a public **API
  and SDK** for pages, blocks, maps, timelines, calendars, tags, templates and images.
- **Distinctive:** nested maps, a serious time engine on a common axis, and secret blocks at paragraph level. It has
  structure only where the writer adds it (no types, optional properties).

Sources: https://www.legendkeeper.com/features/ · https://www.legendkeeper.com/changelog/ ·
https://legendkeeper.com/tackling-time · https://legendkeeper.com/how-to-use-legendkeepers-timeline-feature ·
https://www.legendkeeper.com/changelog/legendkeeper-0-17-0-0/ · https://legendkeeper.com/changelog/legendkeeper-0-7-4-full-wiki-export ·
https://www.legendkeeper.com/app/cmcz5hslj12el0ilhhzcecrjd (help page on secrets)

---

## 3. Campfire Writing (web, desktop, iOS/Android; pay per module or lifetime)

A **modular** suite of about 18 modules, which can be bought one by one and include a manuscript editor.

- **Modules.** Characters, Relationships, Locations, Maps, Timeline, Calendar, Encyclopedia, Magic, Species,
  Cultures, Items, Systems (governments, laws, cults), Languages (conlang), Religions, Philosophies, Research, Arcs,
  and Manuscript.
- **Character sheets.** These are built from movable, resizable **panels** of seven types, with 15+ templates and
  100+ suggested attributes, plus aliases.
- **Relationships.** A separate module of **relationship webs**: a friendship web colour-coded by attitude, generic
  webs, and family trees (one reviewer says these come out as flowcharts rather than true trees).
- **Timeline.** Customisable **rows**: one per character, act or period. Events are cards with notes and labelled
  attributes, which can be dragged and connected like a flowchart. There is a Gantt view for long spans and a
  mind-map canvas for arranging cards before structuring them. Events link to the Arcs module.
- **Calendar.** Custom months, weeks, leap days and intercalary months, any number of colour-coded moons with phases,
  and eras that count forward or backward. **Observance filters** place recurring events on given weekdays or moon
  phases. Calendar settings carry over to the Timeline, and timeline events appear on their dates in the calendar.
- **Arcs.** Charts how a character or story arc changes across the book: Campfire's way of modelling change over
  time.
- **Maps** can be **nested** (a city inside a region inside a country), with landmarks and routes.
- **Manuscript.** Known elements are highlighted in the prose, with a hover pop-up and a click that opens the sidebar
  (see the prior research). It also has revision history, goals (Update 37, Jan 2025) and faster element creation
  (Update 43).
- **Collaboration.** Unlimited invited collaborators with view, comment or edit access. Projects are private by
  default.
- **Offline:** only in the desktop app (Mac/Windows), with daily backups. The web and mobile apps need a connection.
- **Distinctive:** a separate module per domain (religions, philosophies, languages), timeline rows per character,
  and calendar–timeline sync. It invites filling in templates.

Sources: https://www.campfirewriting.com/ · https://campfirewriting.com/calendar-creator ·
https://campfirewriting.com/timeline-maker · https://campfirewriting.com/character-builder ·
https://selfpublishing.com/campfire-writing-review/ · https://mythicscribes.com/reviews/campfire-pro/ ·
https://www.campfirewriting.com/pricing · https://www.campfirewriting.com/apps · https://www.campfirewriting.com/learn

---

## 4. Notebook.ai (web; freemium; open source on GitHub)

- The **Universe** is the container. The free tier has five universes with characters, locations and items; premium
  unlocks **29 page types** (creatures, deities, governments, languages, magic, religions, towns, foods, conditions and
  more).
- Each type is a **template of categories and fields**. You can customise it per type, and changes apply to every
  page of that type; you can't vary the fields on a single page (a reviewer's complaint).
- Pages link with **@-mentions**. Notebooks are public or private.
- **Unverified** (from earlier docs; the site returned 403): timelines whose events link to pages, a documents area
  for prose, premium "document analysis", and export to several formats.
- The README's ideas for later include a knowledge graph and machine-learning name and default suggestions. Activity
  is uncertain.
- **Distinctive:** the broadest list of guided page types. It is the purest "fill in the form" model.

Sources: https://faerieboo.substack.com/p/notebook-ai (review, Aug 2023) · https://github.com/indentlabs/notebook ·
https://dunia.gg/blog/world-building-apps (competitor's roundup)

---

## 5. Fantasia Archive (desktop, offline, free, GPL-3)

- The stable release (v0.1.x, last listed around 2024) is a **strictly offline** desktop database with "dozens of
  templates" (document types), complex tags, linking between documents, and project-wide search. From my prior
  knowledge (**unverified**): fields include single and multi relationship fields, and flags such as dead/gone,
  finished and minor.
- **A rewrite is under way in the repo.** Each project is stored as a single **SQLite file** (`.faproject`) with a
  versioned schema, built with Electron, Vue 3 and Quasar. The repo has design docs for template custom fields, a
  workspace tree, floating windows and keybinds. Maps and timelines are on the roadmap.
- **Distinctive:** one portable local file per project, and no account at all.

Sources: https://github.com/Elvanos/fantasia-archive · https://fantasiaarchive.com/ ·
https://www.patreon.com/vishiri/about · https://alternativeto.net/software/fantasia-archive/

---

## 6. Obsidian as a worldbuilding tool (local Markdown files plus plugins)

The data model is **Markdown files with YAML properties (frontmatter)**. Plugins add views over those files, so any
plugin can be removed and the files stay usable.

- **Bases** (a core plugin since v1.9, May 2025). Database views over note properties: table, list, cards,
  **map** (files as pins) and kanban (grouped by a property), with filters, sorting, grouping and **formulas**. The
  view definition lives in a `.base` file or a code block, and the data stays in the notes. It is the official answer
  to "entity tables per kind" and overlaps with Dataview.
- **Dataview.** Queries over frontmatter and **inline fields** typed into the text (`Key:: value`, or
  `[key:: value]` inside a sentence). Implicit fields such as outgoing links, tags and dates are indexed
  automatically.
- **Typed links.**
  - **Breadcrumbs** declares typed edges (up/down/next/prev or your own) through frontmatter, tags, lists, folders,
    naming schemes or Dataview queries. It **implies reverse edges** automatically and supports custom transitive
    rules. Its views are a trail of ancestors, a tree, a matrix of relations by type, prev/next buttons, Mermaid
    diagrams and export to Canvas.
  - **ExcaliBrain** infers parent, child, friend and sibling from plain links (a forward link means child, a backlink
    means parent, linking both ways means friends, a parent's other children are siblings) or from explicit Dataview
    fields, and draws a mind-map.
- **Maps: Leaflet.** Image maps (with bounds, coordinates as percentages, and stacked image layers). Markers are
  added by right-click, link to notes, and have types assigned by tag. **Markers can be generated from notes**: a
  `location:` property in a note's frontmatter becomes a pin, and markers can be selected by folder, tag or links.
  Circular overlays (for example a radius of influence) and distance measuring with a custom scale and unit. The
  plugin is now in **maintenance mode**, with no new features.
- **Calendars.**
  - **Calendarium** (successor to the Fantasy Calendar plugin) defines fantasy calendars (months, leap days, moons,
    eras) and reads **events from note properties** (`fc-date` in the calendar's date format; from my prior knowledge,
    **unverified**: `fc-end`, `fc-category`, and import from Fantasy-Calendar.com).
  - **Evra Timelines** (newer) offers custom calendars per timeline with festival days, leap rules and unit names,
    and imports from Calendarium or Fantasy-Calendar. **Nested eras** are drawn as background bands. **Story threads**
    are spans (wars, reigns) that leave the main line and rejoin it, can have an unknown start or be ongoing, and can
    be linked to a person's **lifespan to show their age** on related cards. Notes are dragged on as cards that
    follow renames. Each timeline is stored as readable JSON (`.evra`), and the plugin can optionally write dates back
    into note properties. It exports to a Markdown table.
  - **Chronos** renders timelines from Markdown inside a note.
- **All-in-one plugins.**
  - **Storyteller Suite** has many entity types, each stored as Markdown with frontmatter. Relationships sync both
    ways. Its timeline has Gantt, tracks per character, location or group, dependency arrows, eras, and **forks for
    alternate continuities**, and it flags overlapping or contradictory events. Leaflet maps can be nested with portal
    navigation, and there is compile.
  - **World Builder** and **Universe Builder** are smaller sidebar wikis.
- **Canvas and JSON Canvas.** Obsidian's whiteboard is stored in an **open format** (`.canvas`, MIT licence, created
  for Obsidian). It has text, file, link and group nodes, and edges with optional labels, arrowheads and colours. The
  **Excalidraw** plugin is used for hand-drawn maps and family trees that embed and link notes.
- **Manuscript.** **Longform** handles scenes as notes, ordering, word counts and compile (see the prior research).
- **Distinctive:** everything is a file, and structure is opt-in per plugin. Typed relations and calendars exist only
  through plugins of varying upkeep (Leaflet frozen; Bases still growing).

Sources: https://obsidian.md/help/bases · https://obsidian.md/changelog/2025-05-21-desktop-v1.9.0 ·
https://blacksmithgu.github.io/obsidian-dataview/annotation/add-metadata/ · https://github.com/SkepticMystic/breadcrumbs ·
https://github.com/zsviczian/excalibrain · https://github.com/javalent/obsidian-leaflet · https://github.com/javalent/calendarium ·
https://forum.obsidian.md/t/calendarium-how-to-create-events/106945 · https://community.obsidian.md/plugins/evra ·
https://community.obsidian.md/plugins/chronos · https://community.obsidian.md/plugins/storyteller-suite ·
https://community.obsidian.md/plugins/world-builder · https://jsoncanvas.org/ · https://community.obsidian.md/plugins/longform

---

## 7. Aeon Timeline 3 (Mac, Windows, iOS; licence or subscription)

The deepest **time and relationship model** among the novelist-facing tools.

- **Item types and properties.** Item types are configurable per project; the worldbuilding template has characters,
  character groups, locations (which nest into sub-locations) and events (which nest into sub-events). Each type has
  its own properties and tags.
- **Relationships with roles.** Events connect to people and places through role-typed relationships, such as
  Participant versus Observer, set in the project's relationship settings. The **Relationship view** is a matrix of
  events against people and places, and shows **character ages at each event** when a birth date (and death date) is
  set. Ages also show in the inspector.
- **Chronology versus narrative.** **Chronological order** (when things happened) and **narrative order** (when the
  reader learns of them) are kept separately, with Narrative and Outline views for the telling order. This is how it
  handles flashbacks and story planning.
- **Uncertain dates.** Undated ("dateless") events can be dated later. Dates can be **uncertain** (earliest and
  latest bounds) or **ongoing** ("2001 – present", resolved against a settable current day). Events can be locked in
  place.
- **Dependencies and constraints.** A dependency means an event can't start before another ends. Constraints pin an
  exact relation (no earlier than, no later than, same as) and are kept automatically when things move.
- **Views.** Timeline, **Subway** (each track is a character or arc; tracks meet at shared events), Narrative,
  Outline, Spreadsheet, Relationship, and Mindmap, with split views.
- **Calendars.** Custom or fantasy calendars with renamable days, months and eras. Calendars can't be fully
  reshaped once events are dated (the advice is a new timeline plus CSV import).
- **Sync and platforms.** Sync with Scrivener and Ulysses (the narrative syncs with the manuscript, and other items
  with folders). One licence covers Mac, Windows and iOS.
- **Distinctive:** typed participation roles, narrative order separate from chronology, uncertain or ongoing dates,
  and ages computed at an event. It is a timeline, not a wiki.

Sources: https://aeontimeline.com/whats-new/introducing-aeon-timeline-3 · https://www.aeontimeline.com/guides/worldbuilding ·
https://www.aeontimeline.com/3-4-guides/getting-started · https://forum.aeontimeline.com/t/always-show-ages/3575 ·
https://forum.aeontimeline.com/t/any-way-to-have-character-of-a-track-added-to-new-event-as-participant-instead-of-observer/2710 ·
https://www.aeontimeline.com/

---

## 8. Chronicler (desktop, Windows/macOS/Linux; source-available, free core)

A newer (2025–26) **local Markdown wiki** that opens Obsidian vaults directly. It is built with Rust, Tauri 2 and
Svelte 5.

- `[[Wikilinks]]` with autocomplete, a backlinks panel, and links updated on rename. **Vault diagnostics** find
  broken links. Tags can be hierarchical.
- Templates use YAML frontmatter (`type: character`, `status: draft`) plus `{{placeholder}}` fields, and render as
  **Wikipedia-style infoboxes**. **Page inserts** embed one page in another (navboxes, stat blocks).
- `||spoiler||` syntax, borrowed from Discord, marks hidden text.
- Importers for .docx and Google Docs, **MediaWiki/Fandom XML dumps** (infobox templates are converted), and Obsidian
  vaults.
- Maps with pins linked to location pages, timelines with non-Gregorian calendars, and family trees are **planned**
  for a paid "Pro" (one-time purchase), with no date given. Mobile is on the roadmap.
- **Distinctive:** wiki conventions (infobox, navbox, spoilers) on plain files, and a MediaWiki importer.

Sources: https://github.com/mak-kirkland/chronicler ·
https://www.blog.brightcoding.dev/2026/07/20/chronicler-the-offline-worldbuilding-tool-writers-are-ditching-notion-for ·
https://alternativeto.net/software/chronicler-pro/about

---

## 9. Talmaara (web, with a desktop editor; beta, 2026) — the closest to Quarry's continuity ideas

- A lore database (13 entry types, including characters, locations, factions, gods, creatures and flora), a
  **calendar per world** (custom months, eras, day lengths), and a manuscript editor.
- Scenes, characters and events are all **dated**. A shared **universal time unit** lines up events from different
  calendars on one axis.
- **Scene Lens** shows who is alive and what has already happened as of a scene's date.
- A **continuity audit** checks scene dates against lore dates. It flags appearances after death, impossible ages,
  out-of-order events, **a character in two places at once**, and events referenced before they happen. The vendor
  calls it "pure date math" and says no model reads the manuscript.
- Lore is **dragged into the prose as live links**. **Family trees are drawn from the characters already in the lore**
  rather than redrawn by hand. Maps have pins, and there is a pin board.
- DOCX/PDF export. An AlternativeTo listing mentions an offline desktop editor that syncs on reconnect; the site
  doesn't.
- **Distinctive:** the same rule-based "no AI" continuity checking Quarry plans, but keyed on **in-world dates**
  rather than chapters, and with linking done by hand (drag-in) rather than computed mentions.

Sources: https://talmaara.com/ · https://alternativeto.net/software/talmaara/about/

---

## 10. Arcweave (and articy:draft) — game-narrative tools with useful data ideas

- **Arcweave.** Story flow lives on boards: elements, connections, jumpers, notes and branches. Lore lives in
  **components** (characters, locations, items) with a cover image and **typed attributes**: string, boolean,
  integer and float (usable as variables, e.g. `hero.health`), rich text, **component list** (typed references to
  other components) and asset list.
  - Components attach to story elements, can be @-mentioned in rich text, and have a **References** view showing
    everywhere they are used.
  - Other features: real-time collaboration, structured JSON export, a REST API, and Unity/Unreal/Godot plugins.
- **articy:draft X.** Templates are made of **features**: reusable sets of properties (for example "basic item"
  plus "armour"), each with validation rules (mandatory, maximum length). Violations show up in a conflict search.
  This is the same idea as Kanka's property kits.
- **Distinctive:** typed references as attribute values, and validation of templates. Both are aimed at games, not
  prose.

Sources: https://arcweave.com/ · https://docs.arcweave.com/project-items/components · https://docs.arcweave.com/ ·
https://www.articy.com/help/adx/Templates_Features.html

---

## 11. Map makers (brief)

- **Inkarnate** (browser, freemium). Stamp and texture map making with 23k+ assets, export up to 8K, and a
  commercial licence on the Studio tier. Maps are images with **no pins and no links to notes**.
- **Wonderdraft** (desktop, one-time $29.99, Windows/Ubuntu). Brushed landmasses with smoothed coasts, rivers and
  roads, symbols, styled labels and themes. Maps run from 512 to 8192 px. It is offline, with no linking.
- **Worldographer** (desktop; a 2025 Kickstarter edition). Hex maps at linked scales (world, continent, kingdom; child
  maps with a chosen number of hexes per parent hex), **notes on any hex**, and a gazetteer of cultures, nations and
  religions inside the map file.
- **Pattern.** Writers draw in Inkarnate or Wonderdraft and **upload the image** to Kanka, LegendKeeper or Obsidian
  Leaflet to pin it. The pin layer, not the drawing, is what lore tools own.

Sources: https://inkarnate.com/ · http://wonderdraft.net/ · https://inkwellideas.com/2018/06/hexographer-vs-worldographer/ ·
https://www.backerkit.com/c/projects/inkwell-ideas/worldographer-2

---

## 12. Fantasy-Calendar.com (web calendar engine; brief)

- Months of any number, leap months and leap days on custom intervals, intercalary days, weeks that vary by month,
  custom hours and minutes, moons, seasons and eras.
- **Recurring events with conditions**, for example a festival on the first full moon after a season starts.
- A climate-based weather generator.
- Embeds and a Discord integration, linked calendars, and export (import from Donjon).
- It is the reference implementation that Obsidian's Calendarium and Evra import from.

Source: https://fantasy-calendar.com/

---

## 13. Notion, OneNote and template packs

- **Notion templates** (Story Wiki with 40+ templates, World Building Bible with 7 linked databases, Worldbuilder's
  Compass with 9, Story Studio with 6) are all built from **databases joined by relation properties**.
  - A relation is one-way by default and **two-way** with a toggle, and can be limited to one page or no limit. A
    database can relate to itself; with two-way on, this gives separate properties such as Next and Previous.
  - **Rollups** compute over related pages: counts, earliest and latest dates, sums. Timeline and board views come
    for free.
  - Notion now bundles AI, which matters to writers avoiding it.
- **OneNote** (general knowledge): notebooks, sections and pages with free placement on the page. It has no typed
  data, only links and tags. It is used as a scrapbook rather than a database.
- **Distinctive:** two-way relations and rollups are the generic version of "typed links plus derived values". The
  user maintains every link by hand.

Sources: https://www.notion.com/help/relations-and-rollups · https://bluemoondragon.gumroad.com/l/story-wiki-notion-template ·
https://www.notioneverything.com/templates/world-building-bible · https://whyaweeye.gumroad.com/l/theworldbuilderscompassnotiontemplate ·
https://www.guideflow.com/blog/worldbuilding-software

---

## 14. Scapple (and freeform canvases)

- Scapple (Mac/Windows, from Literature & Latte) is a blank sheet: double-click to add a note, drag one note onto
  another to connect them with a line or arrow.
  - It deliberately has **no hierarchy**.
  - Notes can be stacked, and grouped with background shapes.
  - Notes drag into Scrivener.
- The same "canvas" idea appears as LegendKeeper boards, Kanka whiteboards, Obsidian Canvas, the Campfire timeline's
  mind-map, Aeon's Mindmap and the World Canvas in Story Shack's Quarry.
- Nototo, a startup that made notes live on a 2D "map" of regions, is listed as **closed**.

Sources: https://www.literatureandlatte.com/scapple/overview · https://app.dealroom.co/companies/nototo

---

## 15. Other 2024–2026 entrants (brief)

- **The Story Shack "Quarry"** (formerly "Writer"; web, with a Premium "Local Vault" folder on the device).
  Worldbuilding entries (characters, factions, cultures, species, religions, magic), internal links and backlinks, a
  **World Canvas** for connecting ideas, an Outliner (beats, chapters, scenes), and illustrated world, region and
  encounter **maps whose elements link to entries**. Manuscript export to Word, PDF, Markdown and HTML. The same site
  hosts many random generators. **Same name as this project.**
- **Asermu** (browser, **offline-first, data on the device**). Manuscript editor plus characters with a relationship
  graph, locations, a cross-linked encyclopedia, a timeline and a plot grid. Free tier, then about $10/month or a
  lifetime licence.
- **Lore Forge** (desktop and web; free plus a $6/month subscription): character database, places, plot tracking,
  file tagging, offline use.
- **Aevon** (AGPL, very early stage): pitched as an all-in-one author workspace, with minimal activity.
- **Chronica, World Scribe, Quill&Steel OS, vvd.world:** campaign planners or all-in-one wikis. vvd stresses visual
  connections and live collaboration. Little detail is available beyond directory blurbs.

Sources: https://thestoryshack.com/writer/ · https://asermu.com/blog/best-worldbuilding-software ·
https://alternativeto.net/software/lore-forge/about · https://alternativeto.net/software/aevon/about ·
https://alternativeto.net/software/chronica/ · https://vvd.world/worldbuilding-tools · https://www.quillandsteel.com/blogs/writing-tips/best-world-building-apps

---

## 16. Fandom / MediaWiki conventions (how fan wikis structure lore)

- **Infobox templates.** Each article starts with a structured box of named fields. On Fandom this is
  PortableInfobox: data fields with a source parameter, labels, defaults, groups and headers, and media. The fields
  are filled per page and rendered the same everywhere. Many wikis also add pages to **categories automatically from
  infobox fields**.
- **Common character fields:** name, aliases, status, affiliation, family, first and latest appearance (or "debut"
  per medium). Empty fields are simply not shown.
- **A status policy** (Wiki 24) allows only three status values (alive, deceased, unknown). The status reflects the
  **latest point in the canon**, so status is implicitly "as of" the newest episode. Extra states such as "arrested"
  go in the article text, not the field.
- **Affiliation** lists every group the character is or **has been** in, which shows the need for time-bounded
  membership.
- **Sourcing.** Each in-universe statement is cited to the story it comes from (for example a story-title citation),
  and the prose is written from an in-universe point of view. Out-of-universe material is kept separate.
- **Other wiki mechanics** (general MediaWiki knowledge): **redirects** for alternate names, **disambiguation pages**
  for names shared by several entities, **navboxes** linking a family or faction, "Appearances" lists, and spoiler
  templates. Policies on how long spoiler warnings last vary by wiki.
- **Why it matters.** Fan wikis are the large-scale proof of "facts with sources, status as of a point, aliases as
  redirects, appearances computed per work". The Chronicler and LegendKeeper importers show these conventions moving
  into the tools.

Sources: https://www.mediawiki.org/wiki/Extension:PortableInfobox · https://24.fandom.com/wiki/Wiki_24:Status_policy ·
https://switchedatbirth.fandom.com/wiki/Character_Guideline · https://jojowiki.com/Template:Character_Infobox ·
https://starwars.archivum.wiki/charter · https://tardis.wiki/wiki/User:Tangerineduel/Test_page · https://starfinderwiki.com/wiki/StarfinderWiki:Canon_policy

---

## 17. Novelcrafter "progressions" (cross-reference; the codex was covered in the prior research)

- A codex entry (of any type) can carry **progressions**: details that apply from a given scene onward. Each is set
  to *add to* or *replace* the base detail. Examples are a marriage or a new scar.
- The purpose is AI context, but the data model (a fact with a start point in story order) is what Quarry calls a
  fact *from chapter X*.

Sources: https://docs.novelcrafter.com/en/articles/8675593-progression-additions · https://www.novelcrafter.com/help/docs/codex/codex-types

---

## 18. Cross-tool feature table

Legend: **Y** = has it; **P** = partly, by plugin, or limited; **–** = no; **?** = unverified; **pl** = planned.
The Quarry column is the **design**: phases 1–5 in the spec and 6–9 in WORLD-MODEL. "later" means the world model's
§10 later list.

| Feature | Kanka | LegendKeeper | Campfire | Notebook.ai | Fantasia Archive | Obsidian + plugins | Aeon Timeline 3 | Chronicler | Talmaara | Arcweave | **Quarry (design)** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fixed entity types | Y (~20, can disable) | – (free pages) | Y (18 modules) | Y (29) | Y (templates) | P (folders/props) | Y (configurable) | P (template `type`) | Y (13) | P (components) | Y (8 kinds + Other) |
| Per-type fields/templates | Y (property kits, archetypes) | Y (templates, properties block 2026) | Y (panels, 100+ attrs) | Y (per-type template) | Y | Y (templates, Bases) | Y | Y (infobox templates) | ? | Y (typed attributes) | P (suggested facts only) |
| Computed fields | Y (formulas) | – | – | – | – | Y (Bases formulas, Dataview) | Y (ages) | – | Y (ages) | P (variables) | – |
| Typed relations | Y (free label) | P (properties with @) | Y (webs, colour types) | P (link fields) | P/? | P (Breadcrumbs, Dataview) | Y (roles) | – | P (cross-links) | P (component lists) | Y (vocabulary per kind pair) |
| Reverse/mirrored relation | Y (mirror) | – | ? | ? | ? | P (Breadcrumbs implied) | Y | – | ? | – | Y (reverse label) |
| Implied/derived relations | – | – | – | – | – | Y (Breadcrumbs, ExcaliBrain siblings) | – | – | Y (family tree from lore) | – | – |
| Facts/relations true for a span of story | – | – | P (Arcs) | – | – | P (Storyteller) | P (event ranges) | – | Y (dated lore) | – | Y (from/until chapter) |
| Evidence/source per fact | – | – | – | – | – | – | – | – | – | – | Y (passage) |
| Custom calendar engine | Y | Y (moons 2025) | Y | ? | – | Y (Calendarium, Evra) | Y | pl | Y | – | – (by choice) |
| Timeline views | Y (eras) | Y (list/Gantt/calendar) | Y (rows, Gantt, mindmap) | ? | pl | Y (Evra, Chronos, Storyteller) | Y (7 views) | pl | Y | – | P (where-everyone grid) |
| Narrative vs chronological order | – | – | – | – | – | – | Y | – | P (scene dates) | – | P (chapters; dates later) |
| Continuity checks | – | – | – | – | – | P (Storyteller overlaps) | P (constraints) | P (broken links) | Y (date audit) | – | Y (Checks, five editors) |
| Image maps with pins → pages | Y | Y | Y | ? | pl | Y (Leaflet, Bases map) | – | pl | Y | – | later |
| Nested maps | P (map links) | Y | Y | – | – | P (Storyteller) | – | – | ? | – | – |
| Regions/paths/measuring | Y (v4, 2026) | Y (0.18, 2026) | P (routes) | – | – | P (Leaflet circles, distance) | – | – | ? | – | – |
| Family tree view | Y (curated, not exported) | – | Y | – | – | P (Excalidraw by hand) | – | pl | Y (derived) | – | – |
| Secrets/visibility per part | Y (entry, article, relation, chaining) | Y (/secret blocks, hidden pages) | P (roles) | P (public/private) | – | – | – | P (spoiler syntax) | ? | – | – (standing: planned/rumour is about truth, not audience) |
| @mentions / explicit links | Y | Y | Y (tagging) | Y | Y | Y (wikilinks) | – | Y | Y (drag-in) | Y | Y (plus clicks on names) |
| Unmarked name detection in prose | – | P (one-shot auto-link) | P (highlighting) | – | – | P (unlinked-mentions search) | – | – | – | – | Y (computed, aliases, near misses) |
| Backlinks / "mentioned in" | Y (kept apart from relations) | ? | P | ? | ? | Y | – | Y | ? | Y (References) | Y (by project/chapter) |
| Inventory | Y | – | P (Items module) | P (Item pages) | – | – | – | – | – | P | P (owns/carries relations) |
| Tags | Y | Y | Y | ? | Y | Y | Y | Y (hierarchical) | ? | – | P (items) |
| Whiteboard/canvas | Y (2025–26) | Y (boards) | P (mindmap) | – | – | Y (Canvas, Excalidraw) | Y (mindmap) | – | Y (pin board) | Y (boards) | – (corkboard later) |
| Real-time collaboration | P (whiteboards, maps) | Y | P (invites) | P | – | – (Sync only) | – | – | ? | Y | – (data model ready) |
| Offline | – | Y (browser store) | P (desktop app) | – | Y | Y | Y | Y | P? | – | P (chapters, captures) |
| Phone | P (web) | – (pl) | Y (apps) | P (web) | – | Y | Y (iOS) | – (pl) | ? | – | Y (PWA) |
| Open export | Y (JSON re-importable; MD not) | Y (HTML/JSON) | P | ? | Y (SQLite file) | Y (it is files) | P (CSV, sync) | Y (files) | P (DOCX/PDF manuscript) | Y (JSON) | Y (Markdown + frontmatter, Restore) |
| Manuscript editor built in | – | – | Y | P | – | P (Longform) | P (sync) | – | Y | – | Y |
| Public API | Y | Y (0.20, Oct 2026) | – | ? | – | Y (plugin API) | – | – | – | Y | P (own REST API, private) |
| AI in the product | – (removed or optional) | – | – | P (analysis) | – | P (some plugins) | – | – | – (states none) | – | – (principle) |

---

## 19. Cross-cutting observations

1. **Four models of time.**
   - **Calendar engines on one numeric axis.** LegendKeeper, Talmaara's universal time unit, Fantasy-Calendar,
     Calendarium and Evra. Arithmetic and real gaps between dates come first, and months, moons and eras are labels
     on top.
   - **Era containers without arithmetic.** Kanka's timelines are lists of eras with elements, and its calendars are
     a separate system.
   - **Ordered tracks.** Campfire rows, LegendKeeper groups, Aeon's subway view and Storyteller's tracks: one line
     per character or thread.
   - **Story order.** Novelcrafter progressions (from a scene on) and Quarry's chapter clock.
   - Only Aeon keeps **narrative order and chronology** as two separate orders, and only Talmaara checks prose
     placement against in-world dates. None of the wiki tools links "true from chapter N" to an entry.
2. **Relations are typed in three ways.**
   - Free-text labels: Kanka; Talmaara, as far as the listings show.
   - A fixed set of role kinds: Aeon's participant/observer.
   - Graph rules: Breadcrumbs' up/down/next/prev with implied reverses; ExcaliBrain's inferred parent, child, friend
     and sibling.
   - Quarry's vocabulary per pair of kinds, with reverse labels, sits between the first two. Only Breadcrumbs and
     ExcaliBrain **derive** relations (reverse, sibling, transitive).
3. **Relations and mentions are kept apart deliberately.** Kanka keeps "Related" (structured) and "Mentioned in"
   (text) as separate lists and calls them bones and muscle. Quarry has the same split (relationships versus computed
   mentions and co-occurrence evidence), which confirms the design.
4. **Structured facts keep returning to free-form tools.** LegendKeeper added infobox and properties blocks in 2026,
   Chronicler renders infoboxes from frontmatter, and Obsidian added Bases. Even tools that started as plain wikis end
   up needing label/value facts, but none of them **time-bounds** those facts.
5. **Secrets are a TTRPG concern.** Every visibility system (Kanka's chaining, LegendKeeper's /secret, Chronicler's
   spoilers) exists to hide things from players. For a novelist the parallel is *what the reader knows by chapter N*
   and *canon versus planned*, which Quarry models as *standing* and *knows* relations, not access control.
6. **Maps converge on pins plus regions plus paths on an uploaded image**, with nesting (LegendKeeper, Campfire,
   Storyteller, Worldographer) and measuring (Kanka v4, LegendKeeper 0.18, Leaflet). Leaflet and Bases can **generate
   pins from entity data** (a location property on the note), so the map becomes a view of the bible rather than a
   separate store.
7. **Family trees are either curated or derived.**
   - Kanka's trees are curated, a separate structure, and **not exported**.
   - Talmaara's are **derived from existing character relations**.
   - Derived trees avoid two sources of truth.
8. **Export quality varies widely.**
   - Re-importable: Kanka's JSON (but not its Markdown, family trees or permissions).
   - Lossless by construction: Obsidian and Chronicler (the files are the data), Fantasia's single SQLite file, and
     open JSON formats (`.evra`, JSON Canvas).
   - Quarry's Markdown plus frontmatter plus Restore is in the top group, *provided relationships and facts are
     exported too*.
9. **The AI trend (2024–26) runs through new entrants.**
   - **Lorevia** drafts wiki pages from pasted session notes.
   - **Talesmyth** (public beta Feb 2026) has optional AI starting points and summaries, but its users most praise
     **auto-linking**.
   - **Inkbound** auto-extracts characters from the manuscript with AI.
   - **Dunia** generates settings and timelines from prompts.
   - **Notion** and **Google Docs** bundle AI.
   - In the other direction, **Talmaara** markets the absence of any model reading the manuscript as a feature, a niche Quarry
     shares.

   Sources: https://alternativeto.net/software/lorevia/about/ · https://alternativeto.net/software/talesmyth/about ·
   https://www.producthunt.com/products/talesmyth · https://alternativeto.net/software/inkbound-write/about/ ·
   https://dunia.gg/blog/world-building-apps

---

## 20. Concepts worth considering for Quarry

Tags:
- **ALREADY IN QUARRY**: built, or designed in SPEC/WORLD-MODEL.
- **PARTLY**: covered in part.
- **NOT IN QUARRY**: in neither document.

Each concept ends with a one-line fit note for **a single pantser novelist who wants no friction and no
AI-generated story content**.

### Structure of entries

1. **Fixed small set of kinds plus "Other"** (Kanka, Notebook.ai, Talmaara). **ALREADY IN QUARRY.** Fit: good.
   Eight kinds is far below Notebook.ai's 29, which is right for a pantser.
2. **Infobox / properties block: label–value facts at the top of a page** (Fandom, LegendKeeper 0.19.1, Chronicler).
   **ALREADY IN QUARRY** (facts). Fit: show the 3–5 facts as an infobox-style header so the page reads like a wiki,
   and keep notes free.
3. **Reusable field kits per kind** (Kanka property kits, articy features, Campfire panels). **PARTLY** (suggested
   facts per kind). Fit: keep it to suggested labels; kits and validation are form-filling.
4. **Computed fields and formulas** (Kanka, Bases). **NOT IN QUARRY.** Fit: skip, except an *age* derived from a
   birth fact once in-world dates exist.
5. **Status vocabulary as of the latest point, with a fixed small set** (Wiki 24's alive/deceased/unknown). **ALREADY
   IN QUARRY** (status fact with from/until). Fit: keep the suggested *status* values short so the Continuity checks
   can rely on them.
6. **Retire or archive an entity but keep its links as history** (Kanka archiving). **PARTLY** (soft delete only).
   Fit: a *retired* state for characters cut from the book, shown in Salvage like retired chapters, matches Thomas's
   process.
7. **Disambiguation for names shared by several entities** (MediaWiki). **PARTLY** (a first name matches only if no
   other entry claims it). Fit: when two entries share a name or alias, show both on the card and let one click pick;
   no new page type needed.

### Relations

8. **Typed relations with reverse labels** (Kanka mirrored relations, Notion two-way relations). **ALREADY IN QUARRY.**
   Fit: confirmed by every tool.
9. **Implied or derived relations: siblings from a shared parent, grandparents, membership through a sub-faction**
   (Breadcrumbs, ExcaliBrain). **NOT IN QUARRY.** Fit: high value at zero entry cost. Show them read-only and dimmed
   ("sibling, via Varren") and never store them.
10. **Participation roles on events: participant versus observer versus mentioned** (Aeon). **PARTLY** (the Event
    kind with "took part in" and "involved"). Fit: worth adding *witnessed* as a type, since it feeds "who knows
    what".
11. **Attitude or strength score on a relation** (Kanka attitude, Campfire colour-coded webs). **NOT IN QUARRY.** Fit:
    low. The type (friends, rivals, enemies) already carries it, and a number invites fiddling.
12. **Separate "related" (structured) and "mentioned in" (text) lists** (Kanka). **ALREADY IN QUARRY.** Fit: keep
    them visually distinct on the entry page, as Kanka's bones and muscle.
13. **Membership with a role** (Kanka organisation members). **PARTLY** (member of or leads, plus a note). Fit:
    the relation note is enough; maybe show the note inline in the faction's member list.
14. **Inventory: who owns or carries what** (Kanka). **PARTLY** (owns, carries and lost relations, time-bounded).
    Fit: covered. Possibly an "objects carried as of chapter N" line on the character card.

### Time

15. **Facts true from a point in the story** (Novelcrafter progressions, with add or replace). **ALREADY IN QUARRY**
    (from/until chapter). Fit: copy the *add versus replace* distinction. A new scar *adds*; eye colour changing
    *replaces*.
16. **Scene lens: who is alive and what has happened at this point** (Talmaara). **ALREADY IN QUARRY** (as-of-chapter
    view, cast panel). Fit: confirmed by an independent tool.
17. **Date-math continuity audit: dead but appearing, impossible ages, two places at once, referenced before it
    happens** (Talmaara). **ALREADY IN QUARRY** (Checks), apart from *impossible ages*, which needs in-world dates.
    Fit: confirmed. Keep the "nothing guessed from prose" rule.
18. **One sortable numeric time axis under any calendar labels** (LegendKeeper, Talmaara's universal time unit).
    **PARTLY** (planned in-world date with a sortable value). Fit: the right minimal design. Store a number and show
    free text; no calendar engine.
19. **Narrative order versus chronological order as two views** (Aeon). **PARTLY** (chapters give narrative order;
    there is no chronology view yet). Fit: once chapters have in-world dates, a "told order versus happened order"
    strip shows flashbacks for free.
20. **Uncertain dates ("between X and Y") and ongoing spans** (Aeon). **NOT IN QUARRY.** Fit: a cheap *approx* flag
    on the in-world date suits a pantser who doesn't know exact dates yet.
21. **Age shown on cards from birth and death dates** (Aeon relationship view, Evra lifespans, Kanka). **NOT IN
    QUARRY** (deferred). Fit: only after in-world dates. Then show the age as of this chapter on the hover card, which
    is useful and costs nothing to keep up.
22. **Full fantasy calendar engine with moons, leap rules and recurring events** (Fantasy-Calendar, Campfire,
    Calendarium, Kanka). **NOT IN QUARRY** (deliberately). Fit: keep out; a *Term* entry can describe the calendar in
    prose.
23. **Tracks per character, a subway view where tracks meet at shared scenes** (Aeon subway, Campfire rows,
    LegendKeeper groups). **PARTLY** (the where-everyone grid; a chapter-by-thread grid later). Fit: a read-only
    subway built from presence and co-occurrence is a nice later view, with no data entry.
24. **Eras as background bands** (Evra, Kanka, LegendKeeper). **NOT IN QUARRY.** Fit: low for one novel. If needed,
    an Event entry with a span is enough.
25. **Alternate continuities, forks and story versions** (Storyteller forks, LegendKeeper groups). **PARTLY**
    (experiments for chapters; entity experiments are an open question). Fit: if entity experiments come, model them
    as *planned* standing plus an experiment link, not as a forked world.

### Mentions and linking

26. **Mentions computed from unmarked prose, including aliases and near misses** (no surveyed tool does it
    continuously; LegendKeeper and World Anvil do a one-shot pass, Campfire highlights). **ALREADY IN QUARRY.** Fit:
    Quarry's strongest point against this field.
27. **Cut selection to a new entry** (LegendKeeper's Cut-to-New-Page). **PARTLY** (select, then *+ Character*).
    Fit: let *+ Character* from a selection optionally copy the surrounding sentence into the entry's notes as
    evidence, which is one click and loses nothing.
28. **Mentions inside map pins and timeline descriptions count** (Kanka v4). **PARTLY** (mentions run over every text
    body). Fit: when map pins arrive, run mention matching on pin notes too.
29. **Link diagnostics** (Chronicler vault diagnostics). **ALREADY IN QUARRY** (the Archivist: entries never
    mentioned, possible new names). Fit: confirmed.
30. **Inline typed fields in prose (`key:: value`)** (Dataview). **NOT IN QUARRY.** Fit: no. It breaks "prose stays
    pure"; Quarry's select-a-passage-to-record-a-fact covers the need.

### Maps and visuals

31. **Image map with pins linked to entries, regions and paths** (Kanka v4, LegendKeeper 0.18, Leaflet). **PARTLY**
    (later: map image plus pins). Fit: pins only at first; regions and paths only if Thomas actually needs them.
32. **Pins generated from entity data** (Leaflet's `location:`, Bases map view). **NOT IN QUARRY.** Fit: store the
    pin position *on the place entry*, so the map is a view of the bible, a pin is never orphaned, and export carries
    it.
33. **Nested maps** (LegendKeeper, Campfire, Storyteller, Worldographer). **NOT IN QUARRY.** Fit: low. If ever, nest
    through the existing place tree (*inside*) rather than a separate map hierarchy.
34. **Family tree derived from parent and married relations** (Talmaara; contrast Kanka's curated, un-exported
    trees). **NOT IN QUARRY.** Fit: good. It is a read-only view over relationships already recorded; avoid a separate
    tree structure.
35. **Freeform canvas with entity and chapter cards** (LegendKeeper boards, Kanka whiteboards, Obsidian Canvas,
    Scapple). **NOT IN QUARRY** (corkboard later). Fit: medium. If built, store it as **JSON Canvas** so it exports
    openly. It tempts fiddling, so keep it optional.

### Secrets, collaboration, portability

36. **Per-part visibility and permission chaining** (Kanka, LegendKeeper `/secret`). **NOT IN QUARRY.** Fit: not
    needed solo. For co-writers or beta readers later, Kanka's chaining rule (a link is visible only if both ends are)
    is the one to copy.
37. **Inline spoiler or private-note syntax** (Chronicler `||spoiler||`). **PARTLY** (`%%` margin notes in chapters).
    Fit: allow `%%` notes in bible entries too, for "author only, not canon yet".
38. **Live multiplayer cursors and co-editing** (LegendKeeper, Kanka maps and whiteboards). **NOT IN QUARRY** (out of
    scope). Fit: not needed. Per-document optimistic locking suits occasional co-writing.
39. **Re-importable open export that includes relations, trees and permissions** (Kanka's gaps are the warning).
    **ALREADY IN QUARRY** (Markdown plus frontmatter, Restore). Fit: make sure phases 6–9 add facts, relationships,
    presence and resolutions to the frontmatter or a `relations.yaml`, and test the round trip.
40. **Importers from other tools** (LegendKeeper from World Anvil, Chronicler from MediaWiki and Obsidian). **NOT IN
    QUARRY** (by decision). Fit: keep it that way; the one-time migration is done by hand.
41. **Public API or SDK** (LegendKeeper 0.20, Kanka, Arcweave). **PARTLY** (Quarry's own REST API, private). Fit: no
    need to publish one.
42. **Offline bible** (LegendKeeper's browser store, local-file tools). **PARTLY** (chapters and captures offline; the
    bible is online, and names are kept on the device for highlighting). Fit: a read-only offline copy of entries
    (one-liners and facts) would make phone look-ups work on a plane. It is medium value and fits phase 5's pattern.
