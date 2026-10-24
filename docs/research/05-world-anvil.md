# 05 — World Anvil: feature inventory (2025–2026)

Researched 2026-10-24 for comparison with Quarry. Scope: features and concepts. The UI complaints and the autolinker's
false positives are already covered in [03-writing-tools.md](03-writing-tools.md) and are not repeated here.

**Source note.** worldanvil.com refuses automated fetches (HTTP 403). Its pages were read through white-labelled
custom domains that serve the same World Anvil content (`echristopherclark.com`, also `seaofstarlight.com`), using
the same paths. URLs below are given as canonical `worldanvil.com` paths. The changelog is the most current source
(entries through 19 Oct 2026). Reviews and Reddit are thin. Kindlepreneur (updated Mar 2026) is affiliate-linked.
Reddit itself returned nothing through search. Text is paraphrased throughout.

---

## 0. What changed in 2025–2026

World Anvil spent late 2025 to late 2026 replacing its old editing interface. Third-party summaries call the overhaul
"Athena"; the changelog itself does not use that name.

| When | Change |
|---|---|
| Jan 2025 | Advanced (BBCode, "Euclid") editor available inside the new edit interface |
| May 2025 | Article edit modal reaches near parity; old editor renamed "Old Version Edit". Alt+N new-article shortcut. Variables creatable from anywhere. Chronicles join the Visual Editor mention system |
| Oct 2025 | **Folders** for maps, timelines and other entities. **Notebook overhaul**: metadata, templates, advanced search. **Articles & World Manager** (28 Oct) replaces Articles & Categories: one place for articles, categories, world settings, homepage and full-page editing |
| Nov–Dec 2025 | Manager v4.0.x: drag-and-drop reordering, list filters, full-text search in lists, optional WIP indicators, a **WIP list**, **Storyteller Notes** at the top of articles |
| Jan 2026 | **Inline article creation with @** in the Visual Editor (creates a placeholder article in the background). Clickable tags. World Search redesign. Optional **manual save mode** |
| Mar 2026 | Configurable dashboard widgets. Timeline redesign. Guild co-owners can access manuscripts |
| May 2026 | Cleaner UI with a collapsible sidebar. **Diplomacy Management** moved into the new editor. Automatic "order by" sorting in categories. To-do lists and image mass edit opened to all users |
| Jun 2026 | **Live updates**: an editing indicator and a lock that stops two people editing one article. **Family trees** in the new editor, with spouses, children and "extended relationships" in one window |
| Aug–Sep 2026 | Map markers appear in global search (Ctrl+K). Dictionary (conlang) ported. **"Referenced In" panel** (backlinks). Manuscript word counts. Private worlds default new content to private |
| Oct 2026 | **Manuscripts 1.5**: word goals with deadlines, corkboard, labels, light/dark mode. **Manuscripts Reimagined**: new reader pages, six themes, reader typography, focus mode, bookmarks, opt-in follower announcements. **World Styling menu** (themes without CSS). New user profiles at `/~username`. Redesigned world creation |

Sources: https://www.worldanvil.com/changelog (read via echristopherclark.com/changelog);
https://groupfinder.gg/library/world-anvil (third-party summary, the "Athena" naming).

**For Quarry:** two of these are basic infrastructure that Quarry already has, arriving late in WA: backlinks
("Referenced In", Sep 2026) and an edit lock to prevent overwrites (Jun 2026). Most of the rest is presentation
(themes, reader view, profiles).

---

## 1. The core model: worlds, articles, templates, categories

**What it is.** A *world* is the top container. Almost everything is an *article* built from one of about 26–28
*templates*: Character, Location (Settlement / Building / Geographic), Organization, Ethnicity, Species, Item,
Material, Document, Language, Myth, Natural Law, Condition, Profession, Title, Spell, Technology, Tradition/Ritual,
Vehicle, Military Unit, Military Conflict, Plot, Prose, Session Report, and Generic. Beside articles sit separate
entity types: maps, timelines, historical events, chronicles, calendars, family trees, diplomacy webs, whiteboards,
secrets, variables, content trees, manuscripts, notes and to-dos.

**Mechanics.**
- Each article has a free-text introduction, optional **template prompts** (guided questions opened from a Prompts
  button), and **linking fields** with type constraints (an Organization's *Leader* accepts only a Character
  article). These typed fields are WA's structured relations. They are fixed by template, with no time attached.
- Article meta (moved to a Styling menu in Sep 2026): subheading, credits, **pronunciation**, excerpt and
  **mouseover snippet** (the hover preview).
- Each article has two independent state toggles, **draft/published** and **public/private**, plus an optional WIP
  marker. A WIP list collects work-in-progress articles.
- **Categories** form the table of contents. They nest, and each article sits in exactly one category. Ordering is
  manual or automatic (alphabetical, created or updated). Categories can show as "book" covers on the world homepage.
  WA suggests at most about 30 articles per category, because the view renders only 50.
- **Tags** are free-form, clickable (Jan 2026) and used for bulk operations (tag-based diplomacy webs, adding many
  articles to a content tree at once).
- **Content trees** (Grandmaster tier) are hand-built hierarchies. Nodes point at articles or are plain titles, with
  a parent node, and each node can be private or gated to subscriber groups. They show as an interactive chart, an
  indented list or a static chart. They are separate from categories.
- **Links**: the Visual Editor's `@name` creates an article link, and since Jan 2026 it can create a placeholder
  article for a name that doesn't exist yet. Links are ID-based, so they survive renames (prior research). The
  **Referenced In** panel (Sep 2026) lists the articles that link to this one.
- **Variables** (Master tier): world-level key/value snippets in prefixed collections, embedded as `[var:prefix-key]`.
  Types are simple term (with tooltip), advanced term, rendered fragment, link and number. Editing a variable
  updates every embed. WA pitches them partly for keeping character names consistent.
- **Storyteller Notes**: private annotations at the top of an article, or on a secret or event. Only the owner sees
  them; co-authors can be allowed if they also have access.
- **Global content fields**, a world-wide "Worldbuilding Meta" (themes, conflict, inspiration), world stats.

**Who it's for.** Wiki builders and GMs. The template breadth (Spell, Session Report, Military Unit) and the many
toggles serve a published, browsable encyclopedia more than a private writing bible.

Sources: https://www.worldanvil.com/learn/article-guides/article-templates ·
https://www.worldanvil.com/learn/categories/categories-guide · https://www.worldanvil.com/learn/content-trees/content-trees ·
https://www.worldanvil.com/learn/variables/variables · https://www.worldanvil.com/learn/rpg/storyteller-notes ·
https://www.worldanvil.com/learn/interface/visual-text-editor · changelog (Jan/Sep 2026).

---

## 2. Secrets, subscriber groups and per-reader visibility

**What it is.** WA's signature feature: one world, and different readers see different things.

**Mechanics.**
- A **secret** is a separate entity with a title, content, a state (private, public, or shared with chosen subscriber
  groups), an optional **parent article** (it then shows in that article's Secrets tab), GM notes and CSS classes.
  One secret can be embedded in many articles (`/secret` in the Visual Editor). Editing it updates every embed, and
  making it public reveals it everywhere at once. Deleting it removes it everywhere, permanently.
- Nothing models which *characters* know a secret. Secrets control which *readers* can see something, not what is
  known inside the story.
- **Subscriber groups** gate whole articles, maps, timelines, chronicles, manuscripts and chapters, and also single
  map markers, marker groups, layers and timeline events. Members need a (free) WA account. Ways to join: added by
  hand, self-assigned via a join button (Grandmaster), access codes (Sage), or email import from Patreon or Ko-fi
  (Sage). Groups that share a tag are mutually exclusive.
- **Subscriber containers** (Grandmaster) hide a passage inside one article from everyone outside a group. Unlike
  secrets, they can't be reused in other articles.
- **Co-authors don't see secrets** unless the world turns on "Open Secrets". This is the one exception to editors
  seeing all private content.
- Users find the private/public model confusing and some suspect bugs: in a private world, "public" articles stay
  private (from suggestion and bug threads).

**Who it's for.** GMs (players must not see the twist), and authors publishing a world to Patreon tiers and beta
readers.

Sources: https://www.worldanvil.com/learn/secrets/secrets · https://www.worldanvil.com/learn/workflows/secrets-workflow ·
https://www.worldanvil.com/learn/access-rights/subscribers ·
https://www.worldanvil.com/community/voting/suggestion/0deac62e-240f-46f6-b314-ba65e893d11a/view

---

## 3. Timelines, historical events and eras

**What it is.** A visual history of the world.

**Mechanics (how time is modelled).**
- A **historical event** is its own entity. It needs a title and a start year. It can also have an end, detailed down
  to the minute, though only the year is required.
- Other event fields: an **alternative display date** (free text shown instead of the real date), short description,
  full content, colour, **significance** (from not significant to era-changing, shown as the pin shape), type (an
  icon), tags, **connections** (dropdowns linking characters, organisations, locations, species and session reports),
  draft/published and public/private states, subscriber groups, and Storyteller Notes.
- **An event can appear on any number of timelines** ("Also Appears In"). Editing it anywhere edits it everywhere, and
  removing it from one timeline doesn't delete it.
- A **timeline** holds events and **eras**. An era spans a start year to an end year and has a colour, a cover, an
  abbreviation (replaces BCE/CE), a count offset (restart at 0 or 1) and an "invert BCE" option. Each timeline can
  have one open-start era and one open-end ("current") era. **Global eras** are also set at world level and are used
  by character birth dates and Chronicles.
- Display modes: **Timescale** (proportional) or **List/Linear** (evenly spaced). Up to 11 lanes show parallel
  events, and a guide covers compressing large gaps. A timeline can be linked to a calendar, an article or a
  category.
- **Character ages**: entering birth and death years makes WA compute the age at death. The calculation ignores
  months and days and ignores user-defined eras; staff declined to fix this given the current system (suggestion
  threads).
- Users can't model the Gregorian leap-year exceptions.

**What's missing for a novelist.** Time is the *world's* history, measured in years. Nothing ties events to
chapters, so story order (reading order) and world chronology are never connected.

**Who it's for.** Worldbuilders and GMs presenting history: lore timelines, eras of empires.

Sources: https://www.worldanvil.com/learn/timelines/events · https://www.worldanvil.com/learn/timelines/timelines ·
https://www.worldanvil.com/learn/timelines · https://www.worldanvil.com/learn/world/global-era ·
https://www.worldanvil.com/community/voting/suggestion/53fe2017-3ba2-4d7e-817d-f64907910a0c/view ·
https://www.worldanvil.com/community/voting/suggestion/4fff8b7d-3eed-406e-81a0-721bc7b2b9c4/view

---

## 4. Calendars (custom calendars, moons)

**Mechanics.**
- A calendar has weekdays (their count sets the week length), named months with lengths, and a "preview year" plus a
  day offset that fixes which weekday year 1 starts on.
- **Celestial objects** (moons and other cycles) each have a cycle length, a phase shift, an icon, a colour and a
  description.
- **Events** on calendar dates mark holidays, leap days and recurring festivals; you add one by hovering a date.
- A calendar becomes visible only when embedded in an article (`[calendar:ID|YEAR]`). It can be exported and
  imported as WA-specific JSON.
- WA's own guide contrasts a calendar (a cycle) with a timeline (a line). A calendar is a template of recurring days,
  not a store of dated story events.
- A mid-2026 bug report says the Calendars menu still opens an old beta, and custom months don't appear in the month
  dropdown for timeline events. Linking calendar dates to timeline events looks weak.
- Available on all Guild tiers.

**Who it's for.** Worldbuilders and GMs who track festivals and moon phases for sessions.

Sources: https://www.worldanvil.com/learn/calendars/calendars · https://www.worldanvil.com/features/timelines ·
https://www.worldanvil.com/udan-tracker/2f02ec99-c61f-49d4-9581-e37f14b5d91e/view

---

## 5. Chronicles (map-linked timelines)

**Mechanics.**
- A **chronicle** is a container for maps, timelines and events. Its settings include the default time unit, the
  timeline length and a start point. It uses the world's global eras.
- Each timeline in a chronicle has four lanes. Each event has a lane, a type, significance, a cover and linked
  articles, and can point to **one map marker**.
- The link works both ways: selecting an event zooms to its marker, and selecting a marker lists every event there.
  If the event's marker is on a *different* map, that map loads. Using one map per period is how WA shows borders
  changing over time.
- There is no playback; you scroll the timeline by hand.
- Master tier and above. WA suggests chronicles for complex or multi-POV plots.

**Who it's for.** Presenting history to readers and players. Novelists are pointed to it for checking event order
and locations.

Sources: https://www.worldanvil.com/learn/chronicles/chronicles · https://www.worldanvil.com/features/chronicles ·
https://www.worldanvil.com/learn/workflows/writer-workflow

---

## 6. Interactive maps

**Mechanics.**
- Any image can be a map, including a sheet of character portraits.
- **Markers**: pins, labels, lines (roads, rivers, journeys), circles, polygons, invisible pins, draggable markers
  (readers can move them) and HTML pins. Many of these are tier-gated.
- A marker links to articles (with a pop-up showing title, description and links) or to another map, which gives
  **nested maps**. Articles can be created from the marker pop-up.
- **Layers** are images the same size as the base map, can be transparent, and can be private.
- **Marker groups** (Master) can be toggled by readers ("Roads", "Cities"), shown or hidden on load, and gated to
  subscriber groups. Each marker belongs to one group, and a layer can be tied to a group.
- Privacy can be set for the whole map, each marker, each layer and each group.
- Since Aug 2026, markers show up in global search.
- Tiers: Freeman maps are 3.5 MB with 2 layers and pins only. Guild maps are 25 MB with unlimited layers. Master adds
  labels, lines, groups and compass roses. Grandmaster adds polygons, circles, custom and draggable pins.

**Who it's for.** GMs above all (draggable party markers, layers hidden from players), and published worlds.

Sources: https://www.worldanvil.com/learn/map-making/maps · https://www.worldanvil.com/learn/map-making ·
https://www.worldanvil.com/features/maps

---

## 7. Family trees and character relationships

**Mechanics.**
- Trees are built from Character articles, with no separate genealogy store. In a character's Relationships panel you
  add parents, spouses or children (link an existing character or create one), and the tree is generated from those
  links across all characters.
- Embedding `[familytree:ID]` (the root character) shows the tree. Options set the direction and zoom.
  `[bloodline:ID&ID]` shows only ancestors and descendants of one character or a couple.
- Node marks distinguish half-siblings and non-biological relations. Portraits come from the Character template.
- **Extended relationships** (friends, rivals, teacher/student and so on) are kept in the same panel and appear on
  both characters' articles. The reverse direction appears automatically. Nothing in the docs shows dates or periods
  on relationships.
- Master tier and above. Moved into the new editor in Jun 2026.

**Who it's for.** Both groups. This is one of WA's more novelist-useful structures.

Sources: https://www.worldanvil.com/learn/family-trees/family-trees-guide ·
https://www.worldanvil.com/learn/article-guides/article-templates · changelog 29 Jun 2026.

---

## 8. Diplomacy webs

**Mechanics.**
- A diplomacy web is built from organisation-to-organisation relationships. Each relationship has **two scores from
  -100 to +100**, one per side (how A feels about B and how B feels about A), plus an optional "official diplomatic
  status" label.
- The docs mention no dates. The web is generated automatically around one organisation, or across every
  organisation with a given tag (`[diplomacy:TAG]`).
- Users have asked for the same score display for characters; it doesn't exist.
- Master tier and above. Moved into the new editor (May 2026), and onto Military Conflict articles as "Belligerents"
  (Oct 2026).

**Who it's for.** Political worldbuilding and GMs.

Sources: https://www.worldanvil.com/learn/diplomacy-webs/diplomacy-webs ·
https://www.worldanvil.com/community/voting/suggestion/2ef8d08b-93cb-4558-9932-4e68bb93b11a/view ·
changelog 28 May 2026.

---

## 9. Manuscripts (novel writing inside WA)

**Structure (data model).**
- A Manuscript has a title, cover, blurb, genres, language, fonts and privacy.
- **Chapters are folders** that hold no text. They can nest.
- **Scenes** hold the text, plus a title, **synopsis**, **label** and **notes**.
- There are also text or image pages.
- New manuscripts get a **Research** folder and a **Bin** (recoverable deletes).
- Only content under the **title folder** is published or exported. Anything outside it (research, outlines, old
  drafts) stays private.
- Manuscripts can be moved between worlds, and chapters too (Oct 2026).

**Modes.**
- **Write**: three panels (structure, editor, notes and settings), with a focus mode that hides both side panels.
- **Review**: an outline with synopsis fields, for creating chapters or scenes above or below the current one.
- **Corkboard** (Oct 2026): cards dragged to reorder, with title and synopsis edited inline.
- **Read**: no text editing, but you can add notes, which suits revision passes.
- **View**: the public reader.
- Changes autosave. WA warns against opening the same content in two tabs.

**Writing aids.**
- Word goal per manuscript or chapter, with an optional deadline.
- A **daily word count history**.
- Search and replace across the manuscript (WA suggests it for renaming characters).
- Custom labels for revision stages.

**Link to the bible.**
- A top search bar returns manuscript hits and world hits. World articles open in the right panel and can be edited
  there without leaving the manuscript.
- Quick article creation.
- The docs mention no automatic detection of which bible entries appear in which scene, and no mentions panel.
  Manuscript text and the wiki are joined only by search and by manual links. (Kindlepreneur says chapters can be
  linked to articles; the docs don't explain how.)

**Versioning.** None is built in. The official advice is to make a "Draft 2" folder, duplicate each scene by hand,
and stop editing Draft 1.

**Planning.** WA suggests plot tables or beat sheets as pages (there is a Save the Cat guide), whiteboards, and Plot
articles (§10). The docs describe a synopsis-first outline: a chapter synopsis, then scene synopses, then a "draft
zero".

**Collaboration.** The docs say plainly that Manuscripts doesn't support co-writing. Co-owners can open manuscripts
(Mar 2026).

**Publishing.**
- Chapters are published one at a time, to the public or a subscriber group, with exclusive chapters for supporters,
  Patreon and Ko-fi links, and a custom access-denied page.
- Reader comments, which can be turned off. Likes, bookmarks, author follows, and opt-in follower announcements
  (Oct 2026).
- Six reader themes, and reader typography and focus mode settings.

**Export.** **HTML only.** For PDF, print from the browser. For DOCX, paste into a word processor. For EPUB, use an
external tool (Jutoh, Vellum).

**Tier.** Master and above.

**Who it's for.** Serial-fiction and web-novel authors who publish chapters inside WA's community. As a drafting
environment for a long novel it is basic: no revision history, no automatic links between prose and bible, and
HTML-only export.

Sources: https://www.worldanvil.com/learn/manuscripts-guides/manuscripts ·
https://www.worldanvil.com/learn/manuscripts-guides/version-manuscript ·
https://www.worldanvil.com/learn/manuscripts-guides/world-bible ·
https://www.worldanvil.com/learn/manuscripts-guides/daily-word-count ·
https://www.worldanvil.com/features/novel-writing-software · changelog Oct 2026 (Manuscripts 1.5 to 1.5.6, Reimagined) ·
https://kindlepreneur.com/world-anvil/

---

## 10. Plot template, whiteboards, notebook, to-do list

- **Plot template**:
  - A free-writing "vignette" field.
  - Tabs: Generic (related characters and locations), Structure (based on Freytag's pyramid), **Components** (what
    happens, without fixing the order; WA says this tab suits discovery writers), Relations (the cast's roles) and
    Backdrops.
  - **Parent Plot** links make a plot tree: a master plot, then part-level plots below it. The tree is shown in the
    campaign manager's Plots tab and breaks if the links loop.
  - Plot articles can be searched from Manuscripts.
  - Who it's for: built for GMs, reused for novels.
- **Whiteboards** (Master tier):
  - A free canvas of shapes, text, sticky notes, freehand drawing, and embedded WA articles, maps and images.
  - Arrows are anchored to items and follow them when moved.
  - Items can link to world elements. Items can be locked.
  - Whiteboards can be embedded in articles and have privacy and subscriber groups.
  - No real-time co-editing is described.
- **Notebook** (Guild; overhauled Oct 2025):
  - Notebooks contain coloured sections, which contain notes. Notes can be starred and tagged.
  - Free key/value **metadata** carries over between notes in the same notebook and can be searched.
  - **Note templates**.
  - Private to the account: never shared with co-authors.
  - Opens over any page without a reload.
- **To-do list** (Guild; opened to all users May 2026):
  - Items have a title, a description and a five-level priority colour.
  - If a template is chosen for an item, clicking the item creates and links an article. The item's status then
    follows the article: no article, draft, published but WIP, or done.
  - Items are archived rather than deleted.
  - No due dates.
  - Earlier research says links to articles that don't exist yet land on a to-do list. The current to-do guide
    describes only manual creation.

Sources: https://www.worldanvil.com/learn/article-templates/plot · https://www.worldanvil.com/learn/whiteboards/whiteboards-guide ·
https://www.worldanvil.com/learn/notebook/notebook · https://www.worldanvil.com/learn/todo-list/todo-list

---

## 11. Collaboration and roles

- **Roles**:

  | Role | Can do |
  |---|---|
  | **Owner** | Holds the IP and is responsible for public content |
  | **Co-Owner** | Nearly everything, including configuration and CSS. Can add other authors |
  | **Editor** | Creates and edits all content and sees private content. No configuration |
  | **Advanced Writer** | Creates articles and edits only their own, even after publication. Can't change canon they didn't write |
  | **Writer** | Drafts only. Can't publish and sees only their own drafts |

- Slots per tier: 4 for Master, 9 for Grandmaster, 20 for Sage. Each slot is one person in one world. Co-authors can
  have free accounts.
- **Concurrency**: no real-time co-editing. The person editing an article shows by the title, and others are locked
  out of that article (Jun 2026).
- **No article version history.** Staff declined it, citing the database design. Deleted content can't be recovered.
- Co-authors don't see secrets unless Open Secrets is on.
- Manuscripts can't be co-written.

Sources: https://www.worldanvil.com/learn/access-rights/co-authors · https://www.worldanvil.com/pricing ·
https://www.worldanvil.com/community/voting/suggestion/74c70152-3bda-4ce0-89f5-75b3e0b35fe8/view

---

## 12. Publishing and the reader-facing world

- Every world is a public website with a homepage, category "books" and a map as the world background.
- Since Oct 2026, a **World Styling menu** offers themes without CSS. Custom CSS is still allowed, now with a live
  editor.
- Sage tier adds a custom domain, white-labelling, analytics, SEO fields and password-protected articles.
- Social features: likes, comments, followers, guestbooks, a "Discovery" stream, and new user profiles with journal
  posts.
- Monetisation: subscriber groups tied to Patreon and Ko-fi, and exclusive chapters.
- Most of WA's 2026 work went into this layer.

Sources: changelog 2026 · https://www.worldanvil.com/learn/world · https://www.worldanvil.com/learn/workflows

---

## 13. Prompts, challenges, community, Codex, Heroes

- **Template prompts**: optional guided questions on every template. A setting (Nov 2025) can expand them all at
  once.
- **Challenges**:
  - **WorldEmber** (December): 10,000 words of new worldbuilding in public, published articles. Timelines, maps,
    notes and secrets don't count.
  - **Summer Camp** (July): about 30 prompts, each at least 300 words, with gold, silver and copper badges. A 2026
    edition is running, with a "duel" format.
  - Entries are submitted from the article editor and earn a badge on every page.
- **Codex**: the WA team's own world of guides (`/w/WorldAnvilCodex`), now largely replaced by the Learn centre.
- **Heroes** (`/hero/...`): RPG player characters with a sheet, a profile and journal entries written from the
  character's point of view. Player characters can't be world articles.
- **Community**: a portal and feed (Feb 2025), discussion boards, the Discovery stream, and the WA Discord.

Who it's for: these drive engagement and social output on the platform. For a novelist they mean pressure to write
worldbuilding instead of the book.

Sources: https://www.worldanvil.com/worldember (via echristopherclark.com/worldember) ·
https://www.worldanvil.com/community/challenge/summercamp-2019/homepage · https://www.worldanvil.com/player ·
https://www.worldanvil.com/learn/player/character-manager

---

## 14. RPG campaign management (brief)

- A campaign manager with sessions, session reports, a plots tab, players and a digital "storyteller screen".
- Statblocks and character sheets for many systems: D&D 5e 2014/2024, Daggerheart, Cosmere, Call of Cthulhu, Star
  Trek Adventures, FFXIV and Nimble. Most 2025–2026 changelog entries add another one.
- Character import from D&D Beyond.
- **Foundry VTT** module: third-party, one-way, using an API token.

Who it's for: entirely GMs and players. This is WA's commercial core.

Sources: https://www.worldanvil.com/learn/rpg · https://www.worldanvil.com/learn/rpg/foundry-integration ·
https://foundryvtt.com/packages/world-anvil/

---

## 15. Integrations

- **Discord**: a server widget embed, an invite link in the footer, and **webhooks** that post a message to a
  channel after an article is created or updated. WA advises writing your own update messages.
- **Patreon and Ko-fi**: subscriber import by email (Sage).
- **API**: a user API token, used by the advanced export and the Foundry module. Building a custom importer is
  described as a job for a coding Grandmaster.
- **Other exports**: VulgarLang export from Language articles; calendar JSON.

Sources: https://www.worldanvil.com/learn/workflows/world-anvil-with-discord · https://www.worldanvil.com/learn/world/import-world

---

## 16. Export, data portability, import

- **Basic export**: a local copy of the world page, saved to PDF by printing.
- **Advanced export** (Guild): a zip of **JSON with all the metadata and contents**, plus a basic readable HTML
  version. It is started with a user API token pasted into the export page. The guide doesn't say which entity types
  are included.
- **Manuscript export**: HTML only (§9).
- **Import**: WA doesn't have an automated importer, its own JSON included. Moving in means copying by hand, or a
  custom API script.
- Article content is BBCode or editor markup, not Markdown.

**For Quarry:** WA is a lock-in benchmark. Quarry's plain-Markdown export, round-trip Restore and full revision
history are all things WA lacks.

Sources: https://www.worldanvil.com/learn/world/export · https://www.worldanvil.com/learn/world/import-world ·
https://www.worldanvil.com/learn/manuscripts-guides/export-manuscript

---

## 17. Offline and mobile

- Browser only, with an internet connection required (FAQ). There is no native app; mobile means a Chromium browser.
- 2025–2026 work improved the mobile toolbar, the character UI and the reader, but there is still no offline mode.
- Staff have said offline is hard to do reliably and may come later in some limited form via a future mobile app
  (2023–24 threads).

Sources: https://www.worldanvil.com/faq ·
https://www.worldanvil.com/community/voting/suggestion/4f99bed3-2f0f-4ff6-be64-97e94dc6b077/view ·
https://www.worldanvil.com/community/voting/suggestion/1165807e-b4bd-48a0-aa77-d2113ebfcf11/view

---

## 18. Pricing (brief)

The current pricing page lists **Freeman** (free), **Master**, **Grandmaster** and **Sage**, plus lifetime options
for Grandmaster and Sage. Prices didn't render in the fetched page. Older Journeyman-tier references appear outdated.

| Tier | Price (Kindlepreneur, Mar 2026) | Key limits and features |
|---|---|---|
| Freeman | Free | 2 worlds, very limited articles, 100 MB, ads, public content only, no Manuscripts |
| Master | About $6.50/month or $58/year | 10 worlds, unlimited articles, 2 GB, 4 co-authors, 10 subscribers. Manuscripts, family trees, chronicles, whiteboards, diplomacy |
| Grandmaster | About $12/month or $105/year | Unlimited worlds, 5 GB, 9 co-authors, 100 subscribers. Content trees, subscriber containers, advanced map markers |
| Sage | About $300/year | 15 GB, 20 co-authors, 1,000 subscribers. Custom domain, white-label, access codes, analytics |

- Prices conflict between sources; check before quoting.
- Kindlepreneur's verdict on WA for authors: powerful but a steep learning curve, with much of the platform built for
  GMs and irrelevant to authors.

Sources: https://www.worldanvil.com/pricing · https://kindlepreneur.com/world-anvil/ · https://self-publishingschool.com/world-anvil-review/

---

## 19. Who WA is really for

- **GMs and RPG players**: campaigns, statblocks, secrets per player, draggable map markers, session reports,
  Heroes. This is where most changelog entries land.
- **Public worldbuilders**: a styled encyclopedia, challenges, social feed, Patreon gating.
- **Serial-fiction authors**: Manuscripts 1.5 and the "Reimagined" reader (Oct 2026) target publishing chapters
  inside WA.
- **Private novelists drafting a long book**: poorly served.
  - Prose and wiki are joined only by search.
  - No revision history, no offline use, HTML-only manuscript export, no co-writing in Manuscripts.
  - Time is world-years only and never connected to chapter order.
  - Relationships carry no time, except family links.
  - Its strengths (secrets, publishing, reader views) solve problems a private author doesn't have.

---

## Concepts worth considering for Quarry

Tag key: **ALREADY IN QUARRY** (spec or world model covers it) · **PARTLY** · **NOT IN QUARRY**. Each note judges
the fit for one pantser who wants no friction and no AI-generated story content.

### Linking, bible and structure

1. **Backlinks panel ("Referenced In")** — ALREADY IN QUARRY. Quarry's computed mentions, grouped by project and
   chapter, go further: nothing has to be typed as a link.
2. **@-mention that creates a placeholder entry** — PARTLY. The quick-fix strip's "+ Character / Place" on a possible
   new name does this without taking the keyboard, which fits better than typing `@`.
3. **Links survive renames (ID-based)** — PARTLY. Mentions are name-based, so a renamed entity loses its old matches.
   Cheap fix that fits: on rename, offer to keep the old name as an alias (or run Replace across the world).
4. **Typed linking fields** (*Leader* accepts only a Character) — ALREADY IN QUARRY. The relation vocabulary per
   pair of kinds covers this, with time (from/until), which WA lacks.
5. **Template prompts** (guided questions per kind) — PARTLY. Quarry suggests facts per kind. Keep it at that:
   prompts invite worldbuilding instead of writing.
6. **Mouseover snippet / excerpt** — ALREADY IN QUARRY (the one-liner on hover cards).
7. **Pronunciation field** — NOT IN QUARRY. Trivial as a suggested fact on characters and places. Harmless, and
   optional.
8. **Variables** (define a name once, embed it everywhere) — NOT IN QUARRY. Poor fit: it puts markup in the prose.
   Quarry's name check and aliases solve consistency while the prose stays plain.
9. **Content trees / category hierarchy** (one category per article, manual trees) — PARTLY. Kinds, tags and the
   place tree (inside/contains) cover it. A separate hand-built tree would be extra upkeep.
10. **WIP list and article states** (draft/published, WIP marker) — PARTLY. The Archivist lists entries with no
    one-liner or never mentioned. A "stub" filter (entries that are just a name) is cheap, if wanted.
11. **Dictionary / Language template** (a conlang word list, VulgarLang export) — NOT IN QUARRY. Only fits if the book
    uses a constructed language. Terms with aliases already cover invented words.
12. **To-do items linked to articles, status following the article** — PARTLY. Items of kind task already link to
    entities; that is enough.

### Relationships and family

13. **Family tree generated from parent, spouse and child links, with a bloodline view** — PARTLY. Parent/child and
    married types exist. A read-only tree view derived from them (as of a chapter) is cheap and fits: no extra data
    entry.
14. **Extended relationships shown on both entries** — ALREADY IN QUARRY (relationships with reverse labels).
15. **Diplomacy scores**: a one-sided -100 to +100 score per party — NOT IN QUARRY. Weak fit as numbers. The idea that
    a relationship can feel different from each side is already partly captured by direction ("knows about", one
    way). A note per side would be the friction-free version.
16. **Secrets controlled per reader** — NOT IN QUARRY. No fit for a private single author.
17. **Who-knows-what inside the story** — ALREADY IN QUARRY, and better than WA: WA has no knows-of-secret mechanism,
    while Quarry has *knows* and *knows about* relationships bounded in time.
18. **Storyteller / GM notes**: a private layer inside public content — PARTLY. `%%` margin notes and entry notes play
    this role. It only matters for co-writing, when one author keeps notes private.

### Time, calendars and maps

19. **Events as their own entries, shown on several timelines** — PARTLY. The Event kind and "chapter as clock" exist.
    WA's "one event on many timelines" maps onto Quarry's later chapter-by-thread grid. Fits when threads arrive.
20. **Eras, display dates and significance** — PARTLY. The in-world date (free text plus a sortable value) is planned
    and matches WA's "alternative display date". Era and significance could be ordinary facts on an Event; no new
    machinery.
21. **Custom calendars with moons and festivals** — NOT IN QUARRY. Fit only if dates and moon phases drive the plot.
    Worth noting for the in-world-dates phase: WA's calendars barely connect to its timelines, a warning not to build
    a calendar engine on its own.
22. **Computed character age from birth and death** — NOT IN QUARRY. Becomes possible once in-world dates exist (age
    as of a chapter). WA's version ignores months and eras. Low priority.
23. **Chronicles**: an event pinned to a map marker; a marker on another map switches the map — NOT IN QUARRY.
    Quarry's later "own map with pins, who is where as of chapter" is the novelist's version, driven by chapters and
    presence. Keep that framing.
24. **Map layers, marker groups, nested maps** — NOT IN QUARRY (maps are "later"). If maps arrive, nested maps
    (a place pin opens a city map) and one toggleable group per kind are the parts worth taking. Drop the rest.

### Manuscript and writing

25. **Scenes inside chapters; scene synopsis** — PARTLY. Scenes below chapters are on Quarry's later list. A one-line
    synopsis per chapter would fit as the chapter's one-liner. It must stay optional for a pantser.
26. **Corkboard** (cards with title and synopsis, drag to reorder) — PARTLY. The Manuscript view reorders chapters;
    a corkboard is on the later list. Fits only as a view over existing chapters, never as required input.
27. **Labels for revision stages** — NOT IN QUARRY. Quarry has states (current, experiment, retired), and named
    revision passes are on the later list. A free label per chapter ("rough", "revised once") is cheap, but adds a
    ritual; optional at most.
28. **Daily word count history** — NOT IN QUARRY. Strong fit: it can be derived from revisions with no input, and it
    directly supports the standing rule ("two weeks without new story words → pause building").
29. **Word goal with a deadline** — NOT IN QUARRY. Weak fit for a pantser: deadlines add pressure. If added, keep it
    silent unless opened.
30. **Read mode with notes** (read the book without editing, annotate for a revision pass) — PARTLY. Margin notes
    exist. A read-only "read the compiled book" view with `%%` notes would fit, and pairs well with the phone.
31. **Research folder outside the title folder** — ALREADY IN QUARRY. Journal, items, experiments and salvage stay out
    of the compiled `manuscript.md`.
32. **Bin (recoverable deletes)** — ALREADY IN QUARRY (soft delete, Salvage).
33. **Manual versioning by copying scenes into Draft folders** — ALREADY IN QUARRY, and far better: automatic
    revisions, word diffs, experiments and harvest notes.
34. **Search and replace across the manuscript** — PARTLY. The name check replaces names everywhere. A general find
    and replace across a project is not specified; useful, and no friction.
35. **Open a bible entry from the editor, edit it, and return** — PARTLY. Hover cards plus the side panel. Editing an
    entry in the side panel without leaving the chapter fits well.
36. **Plot template with a parent-plot tree; Components tab for discovery writers** — NOT IN QUARRY. Low fit for a
    pantser. Items (questions) and the journal already carry plot thinking.
37. **Whiteboards** with anchored arrows and embedded entries — NOT IN QUARRY. Low to medium fit. The relationship
    graph covers the "web of people" use; a free canvas invites fiddling.

### Collaboration, publishing and platform

38. **Role ladder** (Owner, Co-Owner, Editor, Advanced Writer, Writer) — PARTLY. `world_members.role` exists, with
    owner only. The useful idea for later co-writing: "may edit what they wrote, may not change canon others wrote".
39. **Edit lock and "who is editing" indicator** — PARTLY. Quarry uses optimistic concurrency with conflict copies.
    A presence indicator only matters once there is a co-writer.
40. **Publishing, reader themes, subscriber gating for beta readers** — NOT IN QUARRY. Out of scope. If beta readers
    are ever wanted, sharing a read-only compiled manuscript is enough.
41. **Challenges, badges, prompts, community feed** — NOT IN QUARRY. No fit: they reward writing worldbuilding instead
    of the book.
42. **Random generators** — NOT IN QUARRY. No fit, even when table-based: they generate story content.
43. **Discord webhooks / Foundry VTT** — NOT IN QUARRY. No fit.
44. **Export of JSON and HTML with no re-import; no article history; no offline use** — Quarry is ALREADY ahead on all
    three (Markdown export with Restore, a complete revision history, an offline PWA). Keep them as differentiators.
