# 07 — Novel-writing, planning and revision tools: features and concepts (2025–2026)

A feature survey for comparing with **Quarry**. The earlier file [03-writing-tools.md](03-writing-tools.md) covered
what writers praise and hate. This one covers **mechanics**: what each tool models, how, and which concepts Quarry does
not have yet. The reader in mind is one pantser writing long fantasy in a shared world, chapter by chapter, salvaging
old chapters, possibly co-writing later (already co-writes a screenplay in WriterDuet).

**Method.** Vendor docs, help centres, changelogs and app-store listings first, then reviews. Checked October 2026.
Text is paraphrased, with at most one short quote per source. AI features are noted only as a trend. Where a detail
comes from general knowledge of the product and was not re-checked this time, it says *(not re-verified)*. Vendor
comparison pages (Dabble vs NovelPad, Storyflow's "best alternatives", Kindlepreneur on Atticus) are weighted as
marketing.

---

## 1. Long-form writing environments

### Scrivener 3 (Literature & Latte)

**News.** The latest release found is **3.1.6 (September 2025)**: 64-bit refinements and fixes, with compile
file-naming suggestions and hierarchical MultiMarkdown indexes. No Scrivener 4. L&L is building a **separate, simpler
app** for Mac, iOS and Windows, described on its forum (November 2025) as reducing Scrivener's complexity rather than
cutting it down. It was delayed to 2026 (Windows work plus a Liquid Glass UI rewrite), and as of August 2026 users were
still waiting.

**Concepts.**
- **Binder of arbitrary documents.** Scenes, chapters and parts are just folders and texts. *Scrivenings* edits
  several as one continuous text.
- **Corkboard** of synopsis cards (free-form or along coloured label lines). Moving cards reorders the manuscript.
  The **Outliner** shows synopses, word counts and any metadata as columns.
- **Metadata:** a coloured **label** (one per document), a **status** (To Do, First Draft …), free **keywords**, and
  **custom metadata** fields. **Collections**, including smart collections from saved searches ("everything still
  First Draft").
- **Snapshots** per document (optionally titled) and **Compare**, which shows deletions struck through in red and
  additions underlined in blue.
- **Revision mode:** five revision colours. New text is typed in the current colour. Deletions are *not* tracked, and
  the colours are removed one document at a time. Users snapshot the coloured state before stripping it.
- **Targets:** project, document and session word targets. The project target can carry a **deadline and chosen
  writing days**, and the session target is derived from the words left. Missed days are recalculated. Users ask for
  the reverse ("at this pace, when do I finish?"), which it does not do. A **Writing History** logs words per day.
- **Compile:** one manuscript to DOCX, RTF, PDF, EPUB/Kindle, Final Draft and more, with formats that map document
  types to layouts *(section types and layouts not re-verified)*.
- Split editor (up to four), Quick Reference panes, inline comments and footnotes, templates for new documents.
- **Aeon Timeline sync** (below) is how Scrivener users get chronological time.

Sources:
- https://releasebot.io/updates/literature-and-latte/scrivener
- https://forum.literatureandlatte.com/t/l-l-new-product/152462
- https://www.literatureandlatte.com/scrivener/features
- https://scrivener.tenderapp.com/help/kb/general/revising-in-scrivener
- https://forum.literatureandlatte.com/t/revision-mode-not-showing-deletions/125697
- https://forum.literatureandlatte.com/t/revision-mode-questions/127438
- https://well-storied.com/blog/setting-easy-writing-goals-deadlines-with-scrivener-targets
- https://forum.literatureandlatte.com/t/project-target-calculate-days-left-based-on-session-target/149140
- https://www.goodreads.com/author_blog_posts/19043495-four-nanowrimo-scrivener-tips?tab=book

### Novelcrafter (codex, plan and matrix only; AI skipped)

- **Structure:** acts → chapters → scenes. Scenes carry a summary, a POV and **labels**. Two label presets ship
  (*Status*: draft/outline/final, and *Temporal setting*: past/present/future), and you can add your own with names and
  colours. Labels show on Grid cards and can organise the Matrix.
- **Plan views:** **Grid** (cards), **Matrix** and **Outline**.
- **Matrix:** a spreadsheet of chapters/scenes × tracked things. By default it marks where each codex entry appears,
  either **automatically** (found in a scene's summary or text) or **manually** (assigned to the scene). The *Show*
  menu switches to POV (change a scene's POV with one click in the cell), Labels, a codex **category** (is the
  rebellion present here?), subplots side by side, or a **custom** set of entries (do the hero and villain ever
  meet?). One documented trick: an "edits" codex entry whose progressions are revision notes, reviewed per chapter in
  the Matrix.
- **Codex entries:** name, aliases, tracking toggle, case sensitivity and exclusions (see file 03), **categories**, a
  **Mentions** tab, and **details**. Details are custom fields of type *text*, *line*, *dropdown* (options with colours
  and an order, which can show beside the entry name in the sidebar) or *codex reference*. Each detail is scoped to
  the book or the series and to chosen codex types.
- **Relations** are untyped and directional (one entry nested under another). The docs stress that a relation is not
  a family link like father/daughter: it exists mainly to pull the related entry into AI context.
- **Progressions** are inserted from the editor at a point in the manuscript (via `/`). They are linked to an entry
  and optionally to one text detail, and are either an **addition** or a **replacement**. They are meant for major
  changes (a new scar, a marriage), while plot belongs in scene summaries. They show on the entry and in the Matrix.
  They don't work on line, dropdown or codex-reference details.
- **Series codex vs book codex:** series entries are shared by every book in the series. An entry can be moved
  between them ("move to series / move to book"), and the codex panel has *all / series / book* tabs.

Sources:
- https://www.novelcrafter.com/help/docs/plan/the-plan-interface
- https://www.novelcrafter.com/help/docs/plan/planning-with-the-matrix
- https://www.novelcrafter.com/help/docs/organization/labeling-scenes
- https://www.novelcrafter.com/help/categories/codex
- https://www.novelcrafter.com/help/docs/codex/codex-details
- https://www.novelcrafter.com/help/docs/codex/codex-relations
- https://www.novelcrafter.com/help/docs/codex/progressions-codex-details
- https://www.novelcrafter.com/help/docs/codex/series-codex
- https://docs.novelcrafter.com/en/articles/8675593-progression-additions

### Dabble

- **Manuscript:** a binder of parts, chapters and scenes. **Scene cards** and **sticky notes** pin notes to scenes,
  and a **Story Notebook** holds world notes beside the text.
- **Plot Grid:** **plot lines are columns** and **plot points are cards**. A grid **linked to a book** gets a
  *Scenes* column on the left, so each row is a scene. **Spacer rows** hold plot points that belong to no scene and
  can be turned into a scene. When a scene moves in the binder, Dabble asks whether its plot points move with it (the
  answer can be remembered). Dragging a row on the grid moves both. **Standalone grids** explore ideas with no
  book attached. While writing, a **Plots tab** in the sidebar shows the plot points of the current scene, grouped by
  grid, and new ones can be added there.
- **Goals:** a deadline goal (words + date) becomes a daily target, with **days off** as recurring weekdays plus
  one-off calendar dates. The goal card shows today's target, progress, a pacing graph, words left and a countdown.
  An account-wide daily goal counts words across projects. Stats and streaks reset at local midnight.
- **Revision:** margin comments, track changes, per-scene version history, read-aloud, grammar and style checks.
- **Beta readers ("branch invitation"):** the reader accepts an invitation and gets an **isolated review copy** of the
  whole book or chosen parts, in a reading view with no writing tools. Readers comment in the margin, see only their
  own and the author's comments, tick **Finished reading** (the author sees a count), and lose access when the author
  closes the read. The author pulls the feedback into the manuscript. A free account is required.
- Co-authoring live (premium), local-first save with background sync, and multiple books per project (series).

Sources:
- https://www.dabblewriter.com/features
- https://www.dabblewriter.com/docs/planning-story-notes/plot-grid-overview
- https://www.dabblewriter.com/docs/planning-story-notes/using-the-plot-grid
- https://www.dabblewriter.com/docs/goals-progress/set-a-word-count-goal
- https://help.dabblewriter.com/en/articles/9584974-writing-goals-with-deadlines
- https://www.dabblewriter.com/docs/goals-progress/stats-and-streaks
- https://www.dabblewriter.com/docs/collaboration-sharing/beta-reader-guide
- https://dabblewriter.com/articles/dabble-vs-novelpad (vendor comparison)

### novelWriter (free, open source, plain-text)

- **Chapters vs scenes are heading levels inside documents:** `#` partition, `##` chapter, `###` scene, `####`
  section. `##!` is an unnumbered chapter (prologue), and `###!` is an alternative scene heading for **hard vs soft
  scene breaks**, which the build can format differently.
- **Tags and references:** a note heading defines `@tag: Name | Display name`. Scene headings reference tags by
  keyword: `@pov`, `@focus`, `@char`, `@plot`, `@time`, `@location`, `@object`, `@entity`, `@custom`, `@mention`
  (mentioned but not present) and `@story`. Each keyword must point into the right root folder type. Valid tags are
  coloured. **Undefined tags get a wavy underline**, and right-click offers *Create Note for Tag*. Autocomplete appears
  only on lines starting with `@`. The index feeds an **Outline view** and a **Reference panel**.
- **Comments as data:** `%` comments, `%Synopsis`, and since 2.7 **`%Story.term:`** structure comments
  (`%Story.incite: …`) and **`%Note.term:`** notes. Each term becomes a **column** when the outline is exported to CSV,
  and each can be included in or left out of the built manuscript. 2.8 (2025) allows several per heading.
- **Writing statistics:** a session log (open/close time, **idle time**, novel and notes word totals). A session counts
  only if it lasted over 5 minutes or changed the count. Filters and JSON/CSV export.
- **Manuscript build:** reusable build definitions, filters per root folder and per document, and output to
  ODT/DOCX/PDF/HTML/**EPUB**/Markdown/JSON. Dialogue highlighting, Vim mode, status and importance labels with colours.

Sources:
- https://novelwriter.io/docs/usage/tags_and_references.html
- https://novelwriter.io/docs/usage/chapters_and_scenes.html
- https://novelwriter.io/docs/features/story_comments.html
- https://novelwriter.io/docs/user_interface/statistics.html
- https://novelwriter.io/docs/user_interface/manuscript.html
- https://newreleases.io/project/github/vkbo/novelWriter/release/v2.7rc1
- https://newreleases.io/project/github/vkbo/novelWriter/release/v2.8b1

### Bibisco

Chapters and scenes with **scene revisions** (several versions of a scene, one active). Premise, **fabula** and
**narrative strands**. Settings split into geographic, temporal and social context. A **timeline** links events to
scenes, characters, locations, objects or real-world events. **Analysis** shows chapter lengths, use of points of view,
and where characters, locations and strands fall across chapters. Groups of characters, locations and objects, and
**mind maps** of their relations. Goals with deadline, daily target, monthly averages and trends. Export to
PDF/DOCX/TXT/EPUB. "bibisco Everywhere" syncs desktop and mobile.

Sources:
- https://bibisco.com/writer-software-bibisco-features/
- https://bibisco.gumroad.com/l/bibisco-ce-5
- https://www.linuxlinks.com/bibisco/

### Manuskript

Open source. **0.17.0 (June 2025)** was a bug-fix release. Snowflake-method assistant, outliner and index cards,
characters, plots linked to characters, world, item tracking, a **story line view**, a **frequency analyzer**, a
distraction-free mode that can require a word or time goal before you leave it, plain-text storage, and HTML/EPUB/ODT/DOCX
export. Its outline also shows POV, label, status and per-item goals *(not re-verified)*.

Sources:
- https://www.theologeek.ch/manuskript/
- https://github.com/olivierkes/manuskript

### Ulysses (2025–2026 changes)

- v37 (Mar 2025): **incoming links (backlinks)** in the Dashboard. v35 (2024): internal links to headings and sheets.
- v39 (Nov 2025): Liquid Glass and project sharing as zip archives. v40 (May 2026): new Statistics views for projects,
  groups and filters. v41 (Sep 2026): **project templates**.
- v36 (Oct 2024): Apple Intelligence writing tools (an AI trend). Ulysses 20 (earlier) merged goals, statistics and
  annotations into one Dashboard, and added "Revision", a LanguageTool-based grammar check, not revision colours.
- Goals with deadlines (daily target computed), keywords, filters, and export to DOCX/EPUB/PDF.

Sources:
- https://ulysses.app/releases/
- https://www.macstories.net/reviews/ulysses-20-review-new-dashboard-featuring-advanced-grammar-and-style-check-outline-and-much-more/

### Storyist 4

Mac/iOS, one-time price. Manuscript plus customisable **story sheets** (plot, character, setting), an outliner, a
corkboard of colour-coded **index cards that can sit beside the manuscript** while you draft, and EPUB/DOCX export
*(export not re-verified)*. Little news since 2019.

Source: https://apps.apple.com/us/app/storyist-4/id1445242832

### Atticus

Writing plus formatting: daily goals, a **sprint timer** with planned breaks, themes, export to EPUB/PDF/DOCX
*(DOCX not re-verified)*, offline when installed, **box sets** (several books in one collection), and sharing with
another Atticus user to see their changes and comments. One-time price (~USD 147). No dated 2025 changelog found.
Atticus is owned by Kindlepreneur, so their reviews are vendor material.

Sources:
- https://meredithbond.com/update-atticus-reviewed/
- https://writem.substack.com/p/atticus-the-ultimate-all-in-one-tool
- https://speakwiseapp.com/blog/scrivener-alternatives

### LivingWriter

Chapters and sub-chapters, a **Story Board** of outline elements, outline templates (Hero's Journey, Save the Cat,
Plot Dot), simple story elements (characters, locations, events) that the prose links to as you type (file 03), project
goals without streaks, auto-saved versions, and desktop apps with limited offline. It now markets itself as an "AI
writing app".

Sources:
- https://kindlepreneur.com/living-writer-review (updated Dec 2025)
- https://www.capterra.com/p/266259/LivingWriter/

### Reedsy Studio (formerly Reedsy Book Editor)

Sections → chapters → scenes in a sidebar, plus front and back matter. **Free typesetting to EPUB and PDF**, with the
final style visible while you write. One manuscript goal free. Custom goals, daily check-ins and reminders in the paid
*Craft* add-on. A **timeline** of past versions that you can compare, restore and **star**. Real-time collaboration with
comments and tracked changes, and **online previews of the whole book or one chapter** for beta readers. Planning
boards (card view free). Browser only, no offline. States it will never train AI on your work.

Source: https://reedsy.com/write-a-book

### Campfire (Manuscript module)

Tagging of characters and locations in the manuscript (highlighted, hover info, click opens a sidebar; see file 03).
A Notes sidebar, chapters in an **index-card view** (several moved at once), **DOCX/EPUB import split automatically
into chapters**, manuscript and **chapter goals** with stats, version history, comments that tag collaborators, roles
for **editors, commenters and viewers**, EPUB/PDF export, and offline only in the desktop app. Other modules (timeline,
relationships, maps …) are sold separately. No AI.

Sources:
- https://campfirewriting.com/word-processor
- https://kindlepreneur.com/campfire-write-review/

### Shaxpir, Wavemaker, NovelPad, The Novel Factory (brief)

- **Shaxpir:** cloud word processor for long narratives, with "concepts" (characters, places, themes) cross-referenced
  from the text, an **Emotional Story Arc** chart from positive and negative word counts, and a spell-check dictionary
  extended from ProseCraft's corpus. No 2025 news found.
- **Wavemaker:** draggable **index-card storyboards** in columns (chapters, acts, beats), a Snowflake tool, a
  chronological **timeline**, a hierarchy, and Word export. Now a web app (v3, wavemaker.cards), with the Chrome OS app
  retired.
- **NovelPad:** scene cards on plot and chapter boards. **Character and location views fill themselves with the scenes
  where each appears**, and you can **read one plot thread, or one character's scenes, in isolation**. *Create
  Revision* duplicates a scene to rewrite while keeping the original, and *Rewind* returns the whole project to an
  earlier state. Goals can be in **minutes or words**, plus custom coloured scene tags and a free *Editor* role for
  commenting collaborators.
- **The Novel Factory:** Plot Manager (corkboard with genre templates), **Subplot Manager**, character and location
  profiles, a step-by-step roadmap, statistics with weekly averages, *Turn Back Time* versions, sequel projects, and
  Word export. Its pitch is that it "contains no AI of any kind".

Sources:
- https://alternativeto.net/software/shaxpir/about/
- https://mac.softpedia.com/progChangelog/Shaxpir-Changelog-142151.html
- https://chromewebstore.google.com/detail/hklbpjbehnbccpfcomcnbjalbgpkamlo
- https://alternativeto.net/software/wavemaker-novel-writing-andplanning-software/about
- https://selfpublishing.com/novelpad-review
- https://dabblewriter.com/articles/dabble-vs-novelpad (vendor comparison)
- https://www.novel-software.com/ and https://www.novel-software.com/features/

---

## 2. Planning and timeline tools

### Plottr

- **Timeline grid:** plotlines (main plot, subplots, character arcs) against chapters/beats. **Scene cards** carry
  characters, places, tags and custom **scene attributes** (POV, goal, conflict). **Scene stacks** group several scenes
  in one cell. Flip, zoom and filter by character, place or time. The outline is generated from the timeline.
- **Series:** unlimited books, a **Series View** timeline plus one per book, and characters, places and notes shared
  across the series. Users still ask for per-book character attributes (file 03).
- **2025 shipments:** **Family Tree** (Aug), pin/unpin **preview panels**, linked-items lists and selectable notes on
  cards (Sep), **Bookmarks** to key notes and outline items (Oct), an **Idea Board** (Oct), and **Idea Threads**, a
  separate phone app for capturing ideas, integrated in Dec. Also Offline Beta v2. **Storysnap** (book bibles and
  "virtual beta readers" built from a manuscript) is a separate service and appears AI-based.
- **2026:** no new features, refinement only. The team states "AI is NOT coming to Plottr."
- Export of outlines and bible to Word and Scrivener. Pro adds the web app, live collaboration and offline sync.
  Comments are "coming".

Sources:
- https://plottr.com/features/
- https://plottr.com/plottr-in-2026/
- https://www.plottr.com/changelog

### Aeon Timeline 3

- **Two independent orders.** The timeline holds **events in chronological order**, and the optional **Narrative**
  ("Track independent narrative") holds **folders (books, acts, chapters) and events in reading order**. Moving an item
  in one order doesn't move it in the other, while shared fields (title, characters) stay in sync. *Remove from
  Narrative* hides an event from the story but keeps it on the timeline. Section labels ("Chapter 2") follow folder
  depth and can be overridden ("Prologue"). An event from book 1's time can sit in book 5's narrative.
- **Entities** (people, places, arcs …) link to events through **roles** (participant, witness …) defined in a
  template. **Ages** are calculated for anyone with a birth date who is related to an event. A **Relationship view**
  is a matrix that shows each link and the time between items' start dates (several ages at a glance).
- **Views:** Timeline, Spreadsheet, **Subway** (one track per person or arc in strict chronology, with shared events
  as junctions), Relationship, Narrative (cards), Outline (table), Mindmap.
- **Dependencies and constraints:** an event can be no earlier or later than another, or match it exactly. Connecting
  lines are **green when a rule holds and red when it is violated**, and a sidebar lists all of them. This is a
  rule-based consistency check over the writer's own data.
- **Scrivener/Ulysses sync:** the Manuscript folder mirrors the Narrative, optionally syncing titles, synopses,
  colours and keywords both ways. One writing project per timeline in v3. A scene containing several events maps
  awkwardly. A collaborative web version has been "planned" for years. No 2025–26 release found beyond 3.x.

Sources:
- https://www.aeontimeline.com/3-4-guides/narrative
- https://help.aeontimeline.com/article/20-key-concepts
- https://www.aeontimeline.com/guides/story/work-out-dates-ages-and-story-math
- https://www.aeontimeline.com/guides/measure-time-between-events
- https://www.aeontimeline.com/guides/manage-dependencies-and-event-order
- https://aeontimeline.com/whats-new/introducing-aeon-timeline-3
- https://forum.aeontimeline.com/t/how-to-sync-the-narrative-and-a-timeline-from-scrivener-to-aeon-timeline/1983
- https://forum.aeontimeline.com/t/web-version-update/2143?page=2

### Granthika (a niche reference point)

Vikram Chandra's knowledge-aware editor. You select a phrase in the text and link it to a character, place, event or
object. Events land on a timeline, and age arithmetic would be flagged ("turned 21 sixteen years later"). The sources
are 2017–2019 and describe plans, so treat it as a concept, not a current product.

Sources:
- https://alumni.berkeley.edu/california-magazine/fall-2017-bugged/debugging-novel
- https://wheelercolumn.berkeley.edu/2019/06/07/writing-in-the-digital-age/

---

## 3. Analysis and revision reports (non-AI parts)

### Fictionary (StoryTeller)

- **38 story elements** per scene, in Character, Plot and Setting groups. Examples: POV character, POV goal, what
  happens if the goal fails (stakes), the five-point story arc, conflict vs tension, entry and exit hooks, weather,
  emotional impact of the location, and the five senses. The rest are not listed publicly in what I could reach.
- On import it builds a **cast** and links characters to scenes, setting the POV per scene. **Insights** (about 15
  charts) include characters per scene, scenes per character, words per scene, scenes per chapter, and the
  **story arc** (your arc against a recommended one). A **Story Map** flags empty stages and confusing timelines.
- Per scene: a "finished" checkbox, a red dot when data changed, and a **word cloud** of the scene's most-used words.
- A reviewer found the manual entry tedious and noted there is no subplot tracking, but caught several continuity
  errors by tracking a single element. AI now names scenes and guesses plot points (trend).

Sources:
- https://fictionary.co/journal/story-elements
- https://fictionary.co/support/help-doc/evaluate/
- https://thebleedingtypewriter.substack.com/p/writing-software-review-fictionary
- https://fictionary.co/storyteller-creative-editing-software-for-fiction-writers/

### ProWritingAid and AutoCrit

- **ProWritingAid** non-AI reports: overused words, **repeats** (words and phrases), **consistency** (spelling
  variants, capitalisation, hyphenation, punctuation), pacing (slow passages, with a bar graph), sticky sentences,
  sentence length variety, dialogue (tags, patterns), readability, clichés, sensory language, style (passive, adverbs).
  The **Combo Report** runs a chosen set of about 27 reports together. AI layer (trend): Sparks/Rephrase, chapter
  critique, "Virtual Beta Reader".
- **AutoCrit:** pacing and momentum (sentence, paragraph and chapter variation, slow paragraphs highlighted), dialogue
  tags and adverbs in dialogue, **repeated uncommon words**, **repeated phrases (within about 100 words)**, word
  frequency, a **Personal Words and Phrases** list (your own crutch words, flagged everywhere), **analysis by chapter**
  (needs headings starting "Chapter"), and **genre comparison** (benchmarks change with the chosen genre).

Sources:
- https://prowritingaid.com/features
- https://help.prowritingaid.com/article/32-how-to-use-the-combo-report
- https://thewritelife.com/autocrit-review/
- https://www.techradar.com/news/i-let-a-machine-critique-my-novel
- https://www.autocrit.com/editing/support/the-new-summary-report/

---

## 4. Collaboration-first and screenwriting tools

### WriterDuet (Thomas already co-writes here)

- **Real-time co-writing** with in-app chat. Roles are **Admin, Editor and Read-only** (read-only can comment). Only
  one co-writer needs a paid plan. A **static collaborator** (auto-update off) sees your changes only when you push
  them from the Share menu.
- **Revisions:** *Production* revisions (standard page colours: Blue, Pink, Goldenrod …, tracking on for everyone),
  *Writer* revisions (one writer's changes tracked, visible to all in that colour) and *Custom* revisions (several
  writers, **one session, or one day**). Each has a text colour and a paper colour, shown as a **banner on the page
  edge**, plus margin **asterisks** on changed lines. Per-user Track/View/Ignore. Optional deleted text in red
  strikethrough. Recent collaborator edits show **red until the owner has seen them, then fade to black**.
- **Lock Pages** (Pro), **infinite history** (roll back to any earlier point), a **Tagger** that colours lines or
  passages by tag and **filters the script to tagged lines** (plotlines, jokes to revise, props), and a Cards view
  where reordering cards reorders the script.
- **ReadThrough:** a read-only, comment-friendly link to the current draft, created by Admins.

Sources:
- https://www.writerduet.com/article/109-view-and-track-revisions-edits
- https://writerduet.helpscoutdocs.com/article/115-display-settings
- https://writerduet.helpscoutdocs.com/article/149-invite-collaborators-to-a-project
- https://writerduet.helpscoutdocs.com/article/253-readthrough
- https://writerduet.helpscoutdocs.com/article/4-writerduet-faq
- https://www.writerduet.com/blog/tricks-you-didnt-know-writerduet-could-do/

### Final Draft 13

- **Track Changes** (each writer's insertions and deletions in their colour, accepted or rejected one by one) is for
  drafting. **Revision Mode + Lock Pages** is for production. Locking protects **pagination**: overflow goes to
  A-pages instead of shifting later pages. Revision sets follow the WGA colour cycle (White, Blue, Pink, Yellow …), with
  colours in the margin, renamable sets and "Next Revision".
- **Beat Board** (free-form beats) and **structure lines** that colour outlines, acts, sequences and scenes. Real-time
  collaboration on both script and Beat Board. A new Navigator. Revision mode and locking are not in the cheaper
  *Final Draft Writer*.

Sources:
- https://kb.finaldraft.com/hc/en-us/articles/27817054455828-How-do-I-lock-or-unlock-script-pages-and-use-the-locking-tools
- https://kb.finaldraft.com/hc/en-us/articles/27813588722708-How-do-I-use-Revision-Mode
- https://www.finaldraft.com/blog/tech-tips-track-changes-vs.-revision-mode
- https://kb.finaldraft.com/hc/en-us/articles/15573791756180-Can-Final-Draft-track-changes-when-more-than-one-person-works-on-a-script
- https://www.videomaker.com/news/final-draft-13-gets-major-update/

### Highland Pro (Quote-Unquote Apps)

Screenplays **and novels** (Novel and Manuscript templates), plain Fountain/Markdown text. **The Shelf** holds
snippets, cut lines and ideas (pinned items and Quick Notes added Dec 2025 – Jul 2026). The **Navigator** shows what is
written and what is left. **Revision Mode** marks changes in colour with margin stars. **Sprints** are timed sessions.
**Gender Analysis** counts lines and words spoken per character, grouped by gender. **Grammar Highlight** colours parts
of speech. **Highland Fling** (Mar 2026) makes a **private web version for readers to comment on**, and the comments
come back into a Comments view. DOCX export arrived in May 2026.

Sources:
- https://apps.apple.com/us/app/highland-pro/id6612007609
- https://nofilmschool.com/Highland-screenwriting-software
- https://thesweetsetup.com/highland-2-is-a-screenwriting-app-that-can-handle-all-kinds-of-text/

### Arc Studio Pro

- **Branch Copies:** a private workspace that doesn't touch the main draft. Write offline privately, then share. A
  branch of one section can be shared for review without giving access to the project. A **Drafts** sidebar shows who
  filed each draft.
- Live co-writing with **a colour per collaborator** for cursor and text, avatars and a "live" light, and a video-call
  button. **Changes by writer** colours added text by author. Comments in the margin or a sidebar, @mentions, comments
  on beats. Roles are *Can edit*, *Admin* and *Read only*, and **guests** can join without an account.
- **Plot Board:** beats in acts or sequences, tagged with plots and characters for colour coding. **Stash:** cut a line
  or scene to a titled sidebar item, edit it there, and drag it back later.

Sources:
- https://help.arcstudiopro.com/guides/collaboration-feedback
- https://www.arcstudiopro.com/blog/my-favorite-arc-studio-features-as-a-pro-screenwriter
- https://www.thewritercoach.com/blog/2025/4/7/arc-studio-pro-professional-scriptwriting-in-the-cloud

### Ellipsus

Collaborative prose editor (beta). **Drafts** are standalone copies linked to the main document. **Compare** shows a
draft against the main text (green added, red removed or changed). **Merge** is all-or-nothing: the draft replaces the
main text and becomes read-only, and comments carry over (the draft's comment wins on a clash). You can't compare two
drafts with each other. Roles: **Owner, Document editor, Draft editor, Commenter, Viewer**, plus **a separate chat per
draft**. Comments can come loose when their text is heavily edited.

Sources:
- https://ellipsus.com/features
- https://help.ellipsus.com/article/create-and-merge-drafts
- https://help.ellipsus.com/support/solutions/articles/205000067239
- https://help.ellipsus.com/article/add-comments

### Beta-reader platforms (for comparison)

**BetaBooks** shows each reader's progress through the book, comments per chapter that can be sorted by chapter or by
reader, and author triage of feedback into **To Do / Consider / Ignore**. In 2026 a reviewer called it alive but
slow-moving.

Sources:
- https://janefriedman.com/beta-management-services-compete-for-authors/
- https://aifictionlab.substack.com/p/i-looked-at-every-beta-reader-platform

---

## 5. Other reference points and trends

- **Obsidian** writers now keep scene metadata in YAML frontmatter (characters, setting, timeline day, draft number)
  and view it as tables with **Bases** (core, 2025) or Dataview. Longform compiles and keeps session goals. New plugins
  include Draft Bench (works with Bases) and Novelr.
  Sources: https://obsidian.rocks/getting-started-with-obsidian-bases/ , https://vanessaglau.substack.com/p/how-i-plan-and-write-fiction-in-obsidian , https://community.obsidian.md/plugins/draft-bench
- **iA Writer Authorship:** text can be marked by author (you, a co-author, an AI). Pasted AI text shows greyed out,
  later edits are attributed, and the metadata is stripped on export.
  Source: https://ia.net/writer/how-to/track-authors-and-ai
- **AI as the default (trend, out of scope for Quarry):** Novelcrafter, Sudowrite, Storyflow (AI reads the whole
  planning canvas), Novlr, Chapter, LivingWriter ("AI writing app"), ProWritingAid's Virtual Beta Reader, Plottr's
  Storysnap, Fictionary's scene naming, and Ulysses with Apple Intelligence.
  Source: https://storyflow.so/blog/best-scrivener-alternatives-2026 (vendor)
- **"No AI" as a selling point (counter-trend):** Plottr ("AI is NOT coming"), The Novel Factory, Quillen,
  Campfire, Reedsy (no training on your work) and Scrivener.
  Sources: https://plottr.com/plottr-in-2026/ , https://www.novel-software.com/ , https://www.quillandsteel.com/blogs/writing-tips/scrivener-alternatives
- **Branch-and-merge collaboration is spreading** (Ellipsus drafts, Arc Studio branch copies, Dabble's branch
  invitations for beta readers) as an alternative to everyone typing in one live document.
- **Shareable read-only links with comments** are now standard for feedback: Highland Fling, WriterDuet ReadThrough,
  Reedsy previews, Dabble review copies.
- **Offline and local-first keep improving** (Plottr Offline Beta v2, Dabble true offline), while Reedsy and
  Novelcrafter remain online-only.

---

## 6. Cross-tool table

Y = has it, ~ = partial or indirect, – = not found, ? = not verified. Quarry column: what the spec (phases 1–5) has;
`p` = designed in WORLD-MODEL (phases 6–9) or listed "for later", not built.

| Concept | Scriv | NovCr | Dabble | nvW | Bibisco | Ulysses | Plottr | Aeon | Fictionary | Campfire | Reedsy | NovelPad | WriterDuet | FinalDraft | Highland | Arc | Ellipsus | **Quarry** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Scenes below chapters | Y | Y | Y | Y (headings) | Y | ~ | Y | ~ | Y | – | Y | Y | Y | Y | ~ | Y | – | p |
| Scene/chapter metadata (POV, status, custom) | Y | Y | ~ | Y (@tags) | Y | ~ | Y | Y | Y (38) | – | – | ~ | ~ | ~ | – | ~ | – | ~ (POV) |
| Status / labels with colours | Y | Y | ~ | Y | ? | ~ | ~ | Y | ~ | – | – | Y | ~ | Y | – | Y | – | – |
| Thread / plot grid | ~ | Y (matrix) | Y | ~ | ~ | – | Y | Y (subway) | – | ? | – | ~ | ~ (tagger) | ~ | – | Y | – | p |
| Matrix of entities × chapters (auto from text) | – | Y | – | ~ | ~ | – | – | ~ | ~ | – | – | Y | – | – | – | – | – | p (where-is grid) |
| Corkboard / cards | Y | Y | Y | – | – | – | Y | Y | – | Y | ~ | Y | Y | Y | – | Y | – | p |
| Revision colours / passes | Y (5) | ~ (labels) | ~ | ~ | – | – | – | – | ~ | – | – | – | Y | Y | Y | Y (by writer) | – | p (named passes) |
| Snapshots + compare | Y | ? | Y | – | Y (scene rev.) | ? | – | – | – | Y | Y | Y | Y | ? | – | Y | Y | **Y** |
| Alternate drafts / branches | ~ | ? | ~ (review copy) | – | Y | – | – | – | – | – | – | Y | – | – | – | Y | Y | **Y** (experiments) |
| Cuts bin / shelf | – | ? | – | – | – | – | ~ (idea board) | – | – | – | – | – | – | – | Y | Y | – | ~ (chapter salvage; p) |
| Word goals with deadline / days off | Y | ? | Y | – | Y | Y | – | – | – | Y | Y (paid) | Y (words or minutes) | – | – | ~ (sprints) | – | – | – |
| Session stats / writing history | Y | ? | Y | Y (session log) | Y | Y | – | – | – | Y | Y (paid) | ? | – | – | ~ | – | – | – (word count only) |
| Compile to DOCX / EPUB | Y | ? | ~ (DOCX) | Y | Y | Y | ~ (outline) | – | – | Y (EPUB/PDF) | Y | ? | Y (script) | Y | Y | Y | ? | ~ (Markdown) |
| Inline comments / annotations | Y | ? | Y | Y (% lines) | – | Y | ~ | – | – | Y | Y | Y | Y | Y | Y | Y | Y | p (%% margin notes) |
| Beta-reader sharing with feedback | – | – | Y | – | – | – | ~ (AI) | – | – | ~ (viewer role) | Y | ~ | Y (ReadThrough) | – | Y (Fling) | ~ | Y | – |
| Real-time co-writing / presence | – | ? | Y | – | – | – | Y (Pro) | – | – | Y | Y | ? | Y | Y | – | Y | Y | – (model ready) |
| Roles (editor / commenter / viewer) | – | ? | ~ | – | – | – | ? | – | – | Y | Y | Y | Y | ~ | – | Y | Y | – |
| Locks (pages / sections) | – | – | – | – | – | – | – | – | – | – | – | – | Y | Y | – | – | ~ (read-only after merge) | – |
| Series-level bible | – | Y | Y | ~ | – | – | Y | Y | – | ~ | – | – | – | – | – | – | – | **Y** (world) |
| Facts that change over the story (progressions) | – | Y | – | – | – | – | – | ~ (ages) | – | – | – | – | – | – | – | – | – | p |
| Story time vs reading order | ~ (via Aeon) | ~ | – | ~ (@time) | Y | – | ~ | **Y** | ~ | ~ (module) | – | ~ | – | – | – | – | – | p (in-world dates) |
| Automatic name tracking in prose | – | Y | – | – (explicit tags) | – | – | – | – | ~ (cast) | Y | – | Y | – | – | ~ (char. highlight) | – | – | **Y** |
| Rule-based consistency checks | – | – | – | ~ (undefined tags) | – | – | – | Y (constraints) | – | – | – | – | – | – | – | – | – | ~ (near-miss names; p) |
| Repetition / overused / consistency reports | – | – | ~ (grammar) | – | – | ~ (LanguageTool) | – | – | ~ (word cloud) | – | – | – | – | – | ~ | – | – | p (Proofreader) |
| Presence / POV analysis charts | – | ~ (matrix) | – | – | Y | – | – | Y | Y | ~ (counts) | – | ~ | – | – | Y (dialogue share) | – | – | ~ (POV tally) |

---

## 7. Concepts worth considering for Quarry

Tags: **ALREADY IN QUARRY** = in the spec (phases 1–5). **PARTLY** = part of it exists, or it is designed in
WORLD-MODEL (phases 6–9). **NOT IN QUARRY** = neither (noted when the research README already lists it "for later").
The fit note is for one pantser novelist who wants no friction and no AI story content.

### Structure and metadata
1. **Scenes derived from scene breaks** (novelWriter's heading levels and hard/soft breaks, Dabble/Novelcrafter
   scenes). **PARTLY** (`***` is already a "natural break" in Drafting; scenes are listed for later). *Fit:* treat the
   `***`-separated stretches of a chapter as implicit scenes that can carry optional metadata, rather than adding a
   binder level the pantser must manage.
2. **Chapter one-liner / synopsis** (Scrivener synopsis, Novelcrafter summary, Fictionary's scene blurb).
   **NOT IN QUARRY.** *Fit:* high and cheap. It mirrors the entity one-liner, feeds the corkboard and the manuscript
   list, and can stay empty forever.
3. **Status label per chapter with colours** (Scrivener status, Novelcrafter labels, novelWriter status/importance).
   **NOT IN QUARRY.** *Fit:* one pill per chapter (raw, rewritten, polished), set from the manuscript list. It also
   answers "how many passes has this had?", which Novelcrafter users fake with labels.
4. **Structured margin notes as data** (novelWriter `%Story.term:` / `%Note.term:` → outline columns and CSV).
   **PARTLY** (`%%` margin notes designed). *Fit:* let `%%pov: …`, `%%when: …` or `%%thread: …` lines fill chapter
   metadata with no form to open. Prose stays pure and it is keyboard-only.
5. **Custom fields per entity kind** (Novelcrafter details: text, line, dropdown, reference, scoped to book or series).
   **PARTLY** (facts with labels are designed, deliberately with no rigid schema). *Fit:* keep facts free-form, but a
   dropdown fact type (status: alive/dead/missing) helps the checks.

### Grids, boards and views
6. **Entity × chapter matrix, auto-filled from mentions plus manual marks** (Novelcrafter Matrix, NovelPad
   auto-populated character views). **PARTLY** (the Where-everyone-is grid covers characters × chapters). *Fit:*
   generalise the planned grid to any kind or category (factions, objects, a custom set: "do these two ever meet?")
   and show POV per column. It costs nothing to keep because it is computed.
7. **Thread grid with plot points bound to chapters** (Dabble Plot Grid: columns are threads, rows are scenes; spacer
   rows; points move with their scene, with a prompt). **NOT IN QUARRY** (chapter-by-thread grid listed for later).
   *Fit:* for a pantser, fill it *after* writing: threads could be an entity kind or a tag on items. Dabble's
   "move cards with the chapter?" rule is worth copying.
8. **Filtered reading** (NovelPad: read only one thread or one character's scenes; WriterDuet Tagger filter).
   **NOT IN QUARRY.** *Fit:* high. Read the book as only the chapters (or paragraphs) where Isolde appears, computed
   from mentions. Very useful for continuity passes on a long fantasy.
9. **Corkboard of chapter cards** (Scrivener, Plottr, Wavemaker, Arc Plot Board, Final Draft Beat Board).
   **NOT IN QUARRY** (listed for later). *Fit:* medium. The drag-reorder manuscript list plus one-liners (item 2)
   covers most of it. Free-form placement suits planning, which a pantser does little of.
10. **Appearance strip / heatmap per entity** (Novelcrafter tracking heatmap). **PARTLY** (mentions grouped by
    chapter, first appearance). *Fit:* a sparkline of mentions across chapters on each bible page, which quickly shows
    a character who vanishes for twelve chapters.
11. **Presence and balance charts** (Fictionary scenes per character and words per scene, bibisco POV and location
    analysis, Highland dialogue share). **PARTLY** (POV tally). *Fit:* chapter length and POV rotation over the book
    are rule-based and cheap. Dialogue share needs speaker attribution, so skip it.
12. **Family tree layout** (Plottr, Aug 2025). **PARTLY** (relationship graph designed). *Fit:* a parent/child layout
    of the graph is the view writers ask for most in dynastic fantasy.

### Time
13. **Narrative order vs chronological order** (Aeon's independent Narrative: moving in one never moves the other).
    **PARTLY** (the chapter is the clock; an in-world date per chapter is "later"). *Fit:* the sortable in-world date
    gives the second order for free. Show a "chronological view" of chapters only when dates exist.
14. **Computed ages and time between events** (Aeon Relationship view, Granthika). **NOT IN QUARRY** (listed for later
    and research marked calendars "not building"). *Fit:* only with a simple year count per chapter. No calendars.
15. **Constraints with green/red status** (Aeon dependencies and constraints, all violations in a sidebar).
    **PARTLY** (the Checks page is designed). *Fit:* confirms the design. Show resolved vs violated, as Aeon colours its
    lines.
16. **Progressions: changes from a point in the story, as addition or replacement** (Novelcrafter). **PARTLY** (facts
    with from/until, *as of chapter*). *Fit:* already better modelled. The addition/replacement distinction maps to
    "a second value" vs "the value changes".

### Revision
17. **Snapshots with labels and compare.** **ALREADY IN QUARRY** (checkpoint with label, word diff, restore). *Fit:*
    Reedsy's **star a version** is a cheap extra.
18. **Alternate drafts compared and merged** (Ellipsus compare/merge, NovelPad Create Revision, Arc branch copies,
    bibisco scene revisions). **ALREADY IN QUARRY** (experiments, accept swaps in, salvage). *Fit:* add a side-by-side
    or word-diff compare of experiment vs current chapter before accepting, if it isn't there.
19. **Changes since a point, shown inline** (WriterDuet custom revisions "since this session or day", Scrivener
    revision colours, red-until-seen edits). **PARTLY** (diff exists in the History panel only). *Fit:* in Revising
    mode, an optional overlay tinting text changed since a chosen checkpoint. It is derived from revisions, so there
    is no colour bookkeeping and no deletion blind spot like Scrivener's.
20. **Named revision passes** (Scrivener colour levels, Final Draft revision sets). **NOT IN QUARRY** (listed for
    later). *Fit:* make a pass a labelled checkpoint across all chapters ("after structural pass"), which item 19 can
    then diff against.
21. **Cuts bin / shelf** (Highland Shelf, Arc Stash: cut a passage to a titled sidebar item and drag it back).
    **PARTLY** (Salvage works at chapter level; cuts bin listed for later). *Fit:* high for a salvager. One key sends
    the selection to the bin with its source chapter.
22. **Repetition, crutch-word and echo reports** (ProWritingAid repeats/overused, AutoCrit repeated uncommon words
    within ~100 words and a **personal crutch-word list**). **PARTLY** (Proofreader: doubled words, same word close
    together). *Fit:* add a personal crutch-word list, shown only in Revising.
23. **Consistency of ordinary spellings** (ProWritingAid consistency: grey/gray, hyphenation, capitalisation).
    **PARTLY** (near-miss names only). *Fit:* extend the name checker to variant spellings across the world
    ("Lamp-guild" vs "Lamp Guild", "grey" vs "gray"). It is rule-based and fits the Name check page.
24. **TK / placeholder tracking.** **PARTLY** (TK placeholders listed under Loose ends). *Fit:* confirmed by
    novelWriter and Fictionary users. Count them on the manuscript list.
25. **Read aloud** (Dabble). **NOT IN QUARRY.** *Fit:* medium. The browser's speech synthesis is free and works
    offline on Android, which helps for line-level revision.
26. **Dialogue highlighting / parts-of-speech lens** (novelWriter, Highland, iA). **NOT IN QUARRY.** *Fit:* low to
    medium. Possible as an opt-in Revising lens.

### Progress
27. **Deadline goal with writing days and days off** (Scrivener, Dabble, Ulysses, bibisco). **NOT IN QUARRY.** *Fit:*
    optional and passive. The research rules out streaks and guilt prompts, so show only "words this week" and a
    projected finish if a target is set.
28. **Session history** (novelWriter session log with idle time, Scrivener Writing History, Dabble stats). **NOT IN
    QUARRY** (word count only). *Fit:* high and invisible. It can be derived from revisions (new words per day), and it
    directly supports Quarry's own standing rule ("two weeks without new story words → building pauses").
29. **Sprints / timers, goals in minutes** (Highland, Atticus, NovelPad). **NOT IN QUARRY.** *Fit:* low. Skip unless
    asked.

### Output
30. **Compile to DOCX / EPUB with build options** (novelWriter build definitions: filters, unnumbered chapters,
    scene separators, notes in or out; Scrivener compile; Reedsy typesetting). **PARTLY** (compiled `manuscript.md` in
    the export). *Fit:* DOCX for beta readers and editors (e.g. via Pandoc on the server), with `%%` notes stripped
    and `***` as the separator. EPUB is a nice-to-have for reading on the phone.

### Feedback and co-writing (later)
31. **Beta-reader review copy** (Dabble's isolated copy with Finished-reading flag, Highland Fling, WriterDuet
    ReadThrough, Reedsy preview). **NOT IN QUARRY.** *Fit:* when wanted, a read-only shared link to a frozen
    revision of chosen chapters, with margin comments and a "finished" tick.
32. **Feedback into triage** (BetaBooks To Do / Consider / Ignore). **PARTLY** (Inbox and Triage exist). *Fit:*
    excellent. Each reader comment becomes an item linked to the chapter, closed with the existing accept/reject/defer
    keys. No new workflow is needed.
33. **Anchored range comments** (all collaborative tools; Ellipsus warns that comments come loose after heavy edits).
    **PARTLY** (`%%` line notes designed; comments out of scope). *Fit:* needed for co-writing. Anchor by revision and
    offset, and re-anchor with the word diff Quarry already has.
34. **Branch-and-merge co-writing** (Arc branch copies, Ellipsus drafts with roles and chat per draft, WriterDuet
    static collaborators). **PARTLY** (experiments are branches; the data model has users and members). *Fit:* the
    best match for Quarry's no-CRDT stance. A co-writer works in an experiment or branch, and the owner compares and
    accepts.
35. **Presence and soft locks** (live avatars and cursors in Arc/WriterDuet; Final Draft and WriterDuet lock pages).
    **NOT IN QUARRY.** *Fit:* for co-writing, a soft "X is editing this chapter" lock plus the existing 409 conflict
    copy is enough. Page locking is a production concept and not needed.
36. **Roles: owner / editor / commenter / viewer** (Ellipsus, Campfire, WriterDuet, Arc). **NOT IN QUARRY**
    (`world_members.role` exists with only `owner`). *Fit:* add *commenter* first (for beta readers), *editor* later.
37. **Per-author attribution of text** (Arc "changes by writer", iA Authorship). **NOT IN QUARRY** (only
    `updated_by` per document). *Fit:* only relevant once co-writing starts. It could be derived per revision diff
    instead of tracked live.

### Confirmations (things Quarry already does that the market validates)
38. **Capture anywhere, then triage** (Plottr's 2025 Idea Board and the Idea Threads phone app). **ALREADY IN
    QUARRY.** Quarry's capture/inbox/triage loop is deeper.
39. **Series bible shared across books, with book-only entries possible** (Novelcrafter series vs book codex, "move to
    series/book"). **ALREADY IN QUARRY** (world-level entities). *Fit:* Novelcrafter's move action answers spec §12's
    open question cheaply: an optional "belongs to project" tag, not a separate bible.
40. **Automatic name tracking with no markup** (Novelcrafter, Campfire, NovelPad). **ALREADY IN QUARRY**, including
    the near-miss check that no surveyed tool has.
41. **Rule-based continuity over your own data** (only Aeon's constraints come close; nothing else checks "dead but
    mentioned"). **PARTLY** (designed). This is Quarry's clearest gap in the market.

### Deliberately not recommended
Beat-sheet and structure templates (Plottr, LivingWriter, Fictionary's recommended arc), character questionnaires
(Novel Factory, bibisco), genre benchmarks (AutoCrit), the Emotional Story Arc (Shaxpir) and any AI critique or "virtual
beta reader". They are planner-oriented or judge the story rather than keep its books.
