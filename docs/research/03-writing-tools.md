# 03 — What writers love and hate in writing software

Research for **Quarry**: a web/PWA novel-writing app with a CodeMirror prose editor (dark, VS Code-like), a series bible (characters, places, factions, objects, events, cultures), live mention highlighting coloured by entity kind, hover cards, typed relationships, and a rule-based side panel. No AI generation or suggestion of story content. The author is a pantser and wants no autocomplete dropdowns that steal focus while typing.

## Intro and method

Sources: vendor docs/help centres, independent reviews (Kindlepreneur, Reedsy, Macworld, Self-Publishing School, Lulu, Capterra/Trustpilot/AlternativeTo aggregates), the Literature & Latte, Obsidian and Mythic Scribes forums, feature-request boards (Dabble, Novelcrafter, World Anvil), and writer blogs. Reddit itself could not be fetched directly (blocked); Reddit content below comes via search snippets and mirror links, and is flagged as such. Several "review" sites are affiliate or vendor-owned (Kindlepreneur owns Atticus; LegendKeeper's World Anvil comparison is marketing) and are weighted accordingly.

All text is paraphrased; at most one short quote per source.

Coverage: Scrivener, Ulysses, iA Writer, Obsidian (+Longform and writing plugins), World Anvil, Campfire, LegendKeeper, Plottr, Novelcrafter (codex only), Dabble, Bibisco, yWriter, Manuskript, novelWriter, LivingWriter, Google Docs, Microsoft Word, Atticus, Vellum.

---

## Scrivener (Literature & Latte; Mac/Win/iOS, one-time licence)

**Praise**
- "Everything in one binder": chapters, research, character sheets and front matter in one project; corkboard, outliner, collections (including saved-search "smart" collections), keywords and custom metadata. Writers call it the best tool for the actual drafting side.
- Snapshots per section before a revision, with a Compare view; labelled versions of submission materials.
- Project, per-document and **session** word/character targets, plus a writing-history log of daily output.
- Split editor (up to four documents in one window on Mac/Win), Quick Reference panes, inline comments/annotations and highlights.
- Composition mode (full-screen, themeable backdrop; control bar appears only when the mouse goes to the bottom edge). Typewriter scrolling and (Mac) dimming Focus by line/sentence/paragraph.
- One-time purchase rather than a subscription is repeatedly cited as a reason to stay.

**Complaints**
- Steep learning curve and feature overload: a Capterra reviewer found the sheer number of features intimidating; a Storyist forum user said Scrivener consumed creative attention that should have gone to the story; L&L's own forum worries that adding power-user features scares off newcomers.
- **Sync** is the headline pain: Dropbox-only sync between iOS and desktop, manual sync on iOS, no background sync, and "sync painful" threads on r/scrivener (May 2025, via mirror). Users report needing to wait for Dropbox before switching devices.
- iOS app lags behind desktop features and updates slowly.
- Format lock-in: the `.scriv` package; Markdown export loses formatting unless you go through Compile; Compile itself is a learning project.
- Typewriter scrolling surprises people: a forum user thought composition mode was "jumping" when clicking near the top/bottom; it was typewriter scrolling recentring the line. It is configured separately for main editor, Quick Reference and composition mode.
- Virtual corkboard less satisfying than physical cards for some.

**Entity/codex mechanics**: no automatic mention detection. Character/place sheets are just documents; linking is manual (document links, keywords). Side-by-side reference is via split editor or Quick Reference panes.

Sources:
- https://www.literatureandlatte.com/scrivener/features
- https://www.literatureandlatte.com/blog/distraction-free-writing-with-scrivener
- https://forum.literatureandlatte.com/t/screen-jumps-in-composition-mode/33917
- https://redlib.hackliberty.org/r/scrivener/comments/1kheog0/finding_sync_painful (r/scrivener mirror; via search snippet)
- https://forum.literatureandlatte.com/t/scrivener-for-ios-yea-or-nay/94452
- https://www.capterra.com/p/180597/Scrivener/reviews/
- https://forums.storyist.com/profile/14466-wmh99338/
- https://www.goodreads.com/author_blog_posts/23497898-scrivener-the-software-that-divides-writers ("3-ring binder, but on your computer")
- https://forum.literatureandlatte.com/t/exporting-a-document-to-markdown/152512

---

## Ulysses (Mac/iOS, subscription)

**Praise**
- Minimal, distraction-free Markdown-ish editor; interface chrome disappears until only text remains. Editors' Choice from PCMag; Macworld calls it a minimalist editor with good iCloud sync.
- Unified library of "sheets" with groups, keywords and full-library search; organisation stays simple.
- Writing goals as a filling circle, later with **deadlines** that compute a daily target. Typewriter mode.
- Draft on Mac, edit on iPhone/iPad.

**Complaints**
- Subscription only; costs more than Scrivener over a few years; library goes read-only if the subscription lapses (export still possible).
- Apple-only.
- Far weaker organisation than Scrivener; limited formatting; no track changes.
- Occasional sync hiccups (Macworld).

**Entity mechanics**: none. Notes and attachments live on sheets; no bible, no mentions.

Sources:
- https://www.macworld.com/article/231436/ulysses-13-review-for-mac-and-ios.html ("not an organizational powerhouse")
- https://www.saashub.com/ulysses-app-reviews
- https://scribecount.com/author-resource/writing-tools-for-authors/ulysses
- https://write.as/narshada/insert-placeholder-here-pc97 (writer's tool stack; uses Ulysses, dislikes subscription)

---

## iA Writer (Mac/Win/iOS/Android, one-time per platform)

**Praise**
- Focus mode dims everything except the current sentence or paragraph; reviewers say they have not seen it done as well elsewhere.
- Typewriter scrolling keeps the caret line vertically centred and is independent of focus mode.
- "Syntax highlight" colours parts of speech (adjectives, adverbs, verbs...) to spot weak verbs and repetition — but as an **opt-in** review lens, not live nagging.
- Plain-text files you own; works offline; sync through your chosen cloud. One-time price.

**Complaints**
- No Linux; platform gaps; proprietary.
- Very little long-form structure (no binder/bible); you bring your own organisation.
- iA's own docs advise turning focus mode off when editing, and acknowledge screen jumping because the caret is kept centred.

**Entity mechanics**: none.

Sources:
- https://ia.net/writer/support/editor/focus-mode/focus-mode-windows
- https://moonwriting.bearblog.dev/ia-writer-review-focus-on-writing/
- https://www.macworld.com/article/2985482/ia-writer-3-0-1-review-mac-app-gets-back-to-basics-for-focused-writing.html

---

## Obsidian (+ Longform and writing plugins)

**Praise**
- Plain Markdown files, local-first, free; wikilinks with backlinks and graph view. A novelist on the L&L forum says Obsidian has almost no friction when inventing a new story element: typing a link to a non-existent note creates it.
- Link aliases let prose show a nickname while pointing at the canonical note; links survive renames.
- Wikilink autocomplete is praised by that writer for recalling half-remembered names (note: this is autocomplete **on an explicit `[[` trigger**, not while typing plain prose).
- Page preview: hover a link (optionally only with Ctrl/Cmd held) to see the target note in a popover.
- Longform plugin (~157k downloads): scene ordering by drag and drop, word counts and session goals, compile scenes into one manuscript. Other plugins: Typewriter Scroll, Word Sprint, StoryLine (codex entries attached to scenes), Dataview tables of characters.
- Split panes: manuscript beside character/plot notes.

**Complaints**
- Not built for fiction: you assemble the app yourself from plugins; writers explicitly describe the tool search and plugin tinkering as procrastination.
- Plugin quality varies (forum: some writing plugins "still a little glitchy"); Typewriter Scroll does not work on mobile.
- Mentions are only links you type; unlinked names are invisible unless you use "unlinked mentions" search or auto-link plugins.
- Hover preview is divisive: Obsidian added a Ctrl-hover requirement because unsolicited popovers in search/backlink panels felt intrusive; users file requests both to remove and to extend that requirement.
- Some plugins (Live Anchoring) turn matching words into links when you pause typing — modifies prose behind your back.

Sources:
- https://forum.literatureandlatte.com/t/scrivener-obsidian-and-aeon-timeline-oh-my/147060/7 ("almost no friction when inventing a story element")
- https://community.obsidian.md/plugins/longform
- https://www.eleanorkonik.com/writing-long-form-content/
- https://meredithbond.com/finally-found-my-writing-software/
- https://forum.obsidian.md/t/general-inquiry-on-long-form-academic-book-writing/37474
- https://obsidian.md/help/plugins/page-preview
- https://forum.obsidian.md/t/standardize-mouse-hover-ctrl-for-hover-preview/12994/
- https://forum.obsidian.md/t/some-community-plugins-will-automatically-show-a-preview-regardless-of-the-page-preview-settings/86096
- https://storyletter.substack.com/p/to-build-a-note-is-note-taking-productive
- https://curtismchale.ca/2022/01/10/9-obsidian-writing-plugins
- https://community.obsidian.md/plugins/live-anchoring
- https://github.com/PixeroJan/obsidian-storyline

---

## World Anvil (web, freemium subscription)

**Praise**
- Huge template library per entity type, guided prompts, community challenges, publishing worlds publicly. Linking system praised; links to unwritten articles land on an automatic to-do list.
- Mention links are ID-based, so they survive title changes.
- Autolinker (slash command) scans an article and proposes links to existing articles in one pass.

**Complaints**
- Interface: opinions split sharply; one AlternativeTo user called it maybe the worst UI they had seen, with confusing save buttons that lost work. Formatting and BBCode/CSS customisation are a rabbit hole.
- An initially overwhelming number of options; competitors market themselves explicitly against this clutter.
- Online-only; clunky at the game table unless everyone is on a device.
- Autolinker on large worlds returns hundreds of candidate links for a modest article; users asked for per-article ignore lists. (False-positive overload is a real failure mode for name detection.)
- Billing complaints: silent annual renewals, price jumps.

Sources:
- https://www.worldanvil.com/learn/article-guides/autolinker
- https://www.worldanvil.com/community/voting/suggestion/3cc1b66f-5ffa-46c0-9955-7bfe149166a9/view
- https://www.goodreads.com/author_blog_posts/21534398-world-anvil-review-my-5-favorite-features?tab=author
- https://alternativeto.net/u/stuff/ ("Maybe the worst UI I've ever seen")
- https://uk.trustpilot.com/review/worldanvil.com?page=9
- https://self-publishingschool.com/world-anvil-review/
- https://www.legendkeeper.com/world-anvil-alternative (competitor framing)

---

## Campfire (web/desktop/mobile, modular pricing)

**Praise**
- Buy only the modules you need (characters, locations, magic, relationships, timeline, manuscript...), lifetime options.
- **Manuscript highlighting of tracked entries**: a writer describes Campfire highlighting known entries in prose; hovering shows a small pop-up with basic info, clicking opens the full entry in a sidebar. That writer called quick look-ups like eye colour "Priceless".
- Aliases for characters; Notes sidebar usable without leaving the manuscript; manual tagging of names to elements; reports of how often an element appears.
- Relationship webs (family trees, political structures, loyalties) and multiple timelines.
- Desktop app works offline; web/mobile need a connection.

**Complaints**
- Total cost for everything is high (hundreds of USD lifetime); free tier caps (e.g. 25k manuscript words, limited elements).
- Interface felt dated and not very intuitive in older reviews (Mythic Scribes); layout unwieldy with many articles.
- Projects suited to one series, not shared universes.
- Character module invites over-detailing: the same writer warned readers to remember to actually write the book.
- No iPad app (per that writer); a mobile user could see only element titles.

Sources:
- https://write.as/narshada/insert-placeholder-here-pc97 ("Priceless")
- https://kindlepreneur.com/campfire-review/
- https://selfpublishing.com/campfire-writing-review/
- https://www.campfirewriting.com/pricing
- https://campfirewriting.com/character-builder
- https://mythicscribes.com/reviews/campfire-pro/
- https://justuseapp.com/en/app/1626123915/campfire-write-your-book/reviews

---

## LegendKeeper (web, offline-capable, subscription)

**Praise**
- Positioned as the lean alternative to World Anvil: fewer, sturdier features, no ads, no BBCode/CSS rabbit hole.
- Keyboard-driven editing: slash commands and @-mentions; one-click auto-linking between existing pages.
- Atlas: nested maps with pins linked to wiki pages; timelines (chronicle, Gantt, calendar, custom calendars) linked to pages; whiteboards.
- **Offline mode** in the browser: edits stored locally and merged on reconnect (does not work in private windows; clearing site data before sync loses work).
- Link previews when clicking a link.

**Complaints**
- Mixed reviews: some report a clunky interface and crashes during sessions; others say it lacks World Anvil's breadth.
- Preview pop-ups render text differently from the full page (Reddit).
- No mobile app (planned).

Sources:
- https://www.legendkeeper.com/features/
- https://www.legendkeeper.com/world-anvil-alternative
- https://sugggest.com/software/legendkeeper/reviews/
- https://lr.sudovanilla.org/r/legendkeeper (r/legendkeeper mirror)
- https://alternativeto.net/software/legendkeeper

---

## Plottr (desktop/web/mobile, planning tool)

**Praise**
- Visual timeline grid of plotlines × scenes/chapters; colour-coded subplots; per-character arcs; series view for many-book universes. A Capterra reviewer plans a 30-book series in it.
- Characters, places and notes shared across all books in a series; notes taggable to characters/places; 30+ structure templates; export to Scrivener.

**Complaints**
- Learning curve; some elements not intuitive; one user accidentally deleted work.
- Series bible is shallow: users want wiki-style linking and family trees; per-book character attributes.
- Search finds documents but does not show where the term occurs.
- Bugs/cloud file visibility issues and slow support in some reviews; iPhone performance on big files.
- Not a drafting tool; writers pair it with Scrivener/Ulysses.

Sources:
- https://www.capterra.com/reviews/264561/Plottr
- https://blog.reedsy.com/plottr-review
- https://blog.lulu.com/plottr-review/
- https://plottr.com/?p=57295

---

## Novelcrafter (web; non-AI codex features only)

The codex is the most direct prior art for Quarry's mention system. The $4/month tier is usable without any AI.

**Mechanics**
- **Tracking**: each entry has a "Track this entry by name/alias" toggle (on by default). Matches of name and aliases are **underlined** in manuscript, plan and snippets; counted in a mentions tracker; shown in an appearance heatmap across the book.
- Matching is **case-insensitive by default**, with a per-entry case-sensitive switch for names that are also common words. English plurals auto-match ("Goblin" → "Goblins"); irregular plurals must be added as aliases. Per-entry **exclusions** list words/phrases that should not count.
- **Click** an underlined mention to open a small preview card of the entry; one click to the full entry. Hover behaviour is not documented.
- Each entry has a Tracking tab listing every mention across the project.
- References/relations between entries (family, faction, location); tags and custom categories; **progressions** — entry details that change from a given scene onward so the bible reflects the current point in the story.
- Story timeline strip down the editor side with a marker per scene. Focus mode hides scene summaries and menus. Revision history.

**Praise**: reviewers call the codex the most powerful part of the product, a wiki on steroids; recognition of aliases/nicknames as you type with no explicit markup.

**Complaints**
- Not intuitive; "more Photoshop than Canva"; can overwhelm.
- **No offline mode**, and opening the project in two tabs/devices can overwrite changes — the most common cause of "disappearing" chapters per their own help. Intermittent "sync failed" reports.
- Much of the codex design is shaped by feeding AI context, which some writers do not want.

Sources:
- https://www.novelcrafter.com/features/codex
- https://www.novelcrafter.com/help/docs/codex/codex-tracking
- https://www.novelcrafter.com/docs/codex/additions/
- https://novelcrafter.com/help/docs/write/the-write-interface
- https://kindlepreneur.com/novelcrafter-review/ ("more of an Adobe Photoshop than a Canva")
- https://www.novelcrafter.com/help/faq/general/can-i-use-nc-in-ofline-mode
- https://www.novelcrafter.com/help/faq/general/multiple-windows
- https://feedback.novelcrafter.com/feedback/p/ability-to-use-editor-while-offline

---

## Dabble (web + native apps, subscription)

**Praise**
- Clean, distraction-free drafting; drag-and-drop scenes; Plot Grid for colour-coded arcs, which a reviewer found easier than Scrivener's corkboard; Story Notes beside the manuscript.
- Project and daily goals that adapt.
- Local-first save: every change saves to the device first then syncs in the background; clear sync status icons (yellow = offline, red = server not answering).
- Comments and co-authoring (premium); responsive support.

**Complaints**
- Older users: sync errors requiring refresh; no offline/no iPad app (since fixed via native apps). Web version still shows a persistent warning that browser storage could be evicted; reliable offline needs the native app; private browsing is a risk.
- Sparse, dated UI with options that only appear on hover.
- No templates; collaboration locked into Dabble; premium is expensive over time.

Sources:
- https://reedsy.com/studio/resources/dabble-writing-review ("more structured and easier to manage")
- https://www.dabblewriter.com/docs/apps-sync-offline/how-sync-works
- https://www.dabblewriter.com/docs/apps-sync-offline/sync-status-icons
- https://dabble.featureupvote.com/suggestions/225240/comment/380424

---

## Bibisco (desktop, open-source core + paid edition)

**Praise**: relations board linking characters, places and objects; character interview questions; analysis showing which characters appear in which strands; one-time price.

**Complaints**: unattractive interface; takes a while to get into its workflow; distraction-free mode, timelines and goals only in the paid edition; buggy behaviour and limited support; locations tab thin.

Sources:
- https://self-publishingschool.com/bibisco-review/
- https://kindlepreneur.com/bibisco-review
- https://www.linux-magazine.com/index.php/Online/Blogs/Off-the-Beat-Bruce-Byfield-s-Blog/Wanna-be-Software-for-Wanna-be-Novelists
- https://alternativeto.net/software/bibisco/reviews/

---

## yWriter, Manuskript, novelWriter (free desktop tools)

**yWriter**: scene-based; each scene linked to characters, locations and items; reliable and free; compiles to RTF. Proprietary, Windows-centric, dated.

**Manuskript**: open source; outliner, distraction-free editor, character/plot tools, Snowflake method; "fiction" vs "simple" modes. Users call it rough and not lightweight.

**novelWriter**: plain-text, Markdown-like; scenes reference bible notes via explicit tags (`@pov`, `@char`, `@location`...) that feed an outline view; follow-tag from the editor; autocomplete appears only on lines starting with `@`; right-click an undefined tag to create its note. A good model of keeping metadata out of prose lines.

Sources:
- https://alternativeto.net/software/ywriter/
- https://kindlepreneur.com/ywriter/
- https://alternativeto.net/software/manuskript/
- https://community.linuxmint.com/software/view/manuskript
- https://newreleases.io/project/github/vkbo/novelWriter/release/v2.2b1
- https://gigazine.net/gsc_news/en/20210131-novelwriter

---

## LivingWriter (brief)

A writer who tried it liked that typing a character or place name autosuggested a link to its note, but felt the rest of the app fell flat. Shows that name-linking alone does not carry an app.

Source: https://write.as/narshada/insert-placeholder-here-pc97

---

## Google Docs and Microsoft Word as writing tools

**Google Docs — praise**: free, autosave, version history, any device, best-in-class comments/suggestions for beta readers; heading-based outline for navigation. A TechRadar writer finished a novel there and felt it had everything they needed.
**Complaints**: files beyond ~100 pages get sluggish; no planning or character database; chapter organisation by manual headings; offline must be enabled in advance; poor for publishing formatting; editors still want Word.

**Word — praise**: familiar; Navigation Pane over Heading styles lets a novelist (Claire Fuller, five novels) jump around a 90k-word manuscript, using descriptive chapter titles as a running summary; Focus mode. **Complaints**: Navigation Pane only sees real Heading styles; slowness on very large files; no bible.

Sources:
- https://scribecount.com/author-resource/writing-tools-for-authors/google-docs
- https://kindlepreneur.com/write-in-google-docs/
- https://www.goodreads.com/author_blog_posts/16112295-the-pros-and-cons-of-writing-a-novel-google-docs?tab=book
- https://www.techradar.com/computing/software/forget-all-the-fancy-writing-apps-i-wrote-a-novel-in-google-docs-and-it-had-everything-i-needed
- https://clairefuller.co.uk/2022/03/01/how-to-organise-your-manuscript-using-word/
- https://techcommunity.microsoft.com/discussions/word/problems-with-navigation-pane-on-word-2021---constantly-slowness-and-freezing/3984286

---

## Atticus and Vellum (formatting-first; brief)

**Atticus**: cross-platform formatter with a writing mode, daily goals and habit tracking, offline when installed with cloud sync on reconnect. Limited fonts/themes; some features need a connection. (Reviewer is the vendor.)
**Vellum**: Mac-only, fully offline, gold standard for ebook/print layout; no writing goals or collaboration; editor is weak (undo reportedly per letter). Writers draft elsewhere and import.

Sources:
- https://kindlepreneur.com/atticus-vs-vellum/
- https://thewritelife.com/?p=10948

---

## Cross-cutting evidence: spell-check and live nagging

Many writers turn off red squiggles while drafting because they trigger an urge to stop and fix, and because spell-checkers flag correctly spelled proper nouns — exactly the invented names a fantasy bible is full of. The common pattern is: off while drafting, on for revision.

Sources:
- https://www.goodreads.com/author_blog_posts/14161266-pantsing-101-3-secrets-that-make-pantsing-easier
- https://katemessner.com/turn-off-the-spell-check/
- https://timstevens.substack.com/p/writers-stop-your-spell-checks

---

## Patterns: what reduces friction vs what adds it

### Reduces friction
1. **Zero-markup recognition of names in plain prose** (Novelcrafter, Campfire). Writers praise being able to type normally and have names recognised; Obsidian users praise the low cost of creating a new entity from the text.
2. **Look-up without leaving the page**: Campfire hover pop-up + click-to-sidebar; Novelcrafter click → preview card; Scrivener Quick Reference and split view; Obsidian side-by-side panes. The value is answering "what colour were her eyes?" in under a second.
3. **Local-first saving with visible sync state** (Dabble's cloud icons, LegendKeeper offline merge, Obsidian/iA plain files). Trust in "my words are safe" is a precondition for flow.
4. **Opt-in lenses rather than always-on nagging**: iA's parts-of-speech highlight, focus dimming, typewriter scrolling — each a toggle, each independent.
5. **Session targets and history** (Scrivener session targets, Ulysses deadline goals, Dabble adaptive goals, Longform session goals) give motivation without interrupting.
6. **Simple, discoverable core** with power behind it (Ulysses, LegendKeeper's pitch versus World Anvil).
7. **One-time or fair pricing and open/portable formats** reduce anxiety about lock-in (iA, Obsidian, Scrivener's licence; Ulysses read-only lapse is resented).
8. **Stable identity for links** (World Anvil ID-based mentions survive renames; Obsidian links update on rename).

### Adds friction
1. **Feature overload and setup tax**: Scrivener's learning curve, World Anvil's options, Novelcrafter's Photoshop-like UI, Obsidian plugin tinkering. Writers report the tool consuming attention meant for the story.
2. **Worldbuilding as procrastination**: deep entity templates (Campfire, World Anvil) invite filling fields instead of writing.
3. **Sync fragility**: Scrivener/Dropbox, Novelcrafter's multi-tab overwrite and no offline mode, Dabble web eviction, Ulysses hiccups. Lost-work stories are the most emotionally charged complaints.
4. **Unsolicited popovers and interruptions**: Obsidian had to add Ctrl-gating for hover previews; spell-check squiggles on invented names; options that appear only on hover (Dabble) hurt discoverability.
5. **Screen jumps**: typewriter scrolling/focus recentring surprises users when clicking or editing (Scrivener forum, iA docs).
6. **False positives in name detection**: World Anvil's autolinker returning hundreds of candidates; Novelcrafter needs case-sensitivity, exclusions, and manual irregular plurals to keep underlines meaningful.
7. **Silent prose mutation**: plugins that convert words into links when you pause typing change the manuscript text itself.
8. **Platform gaps**: Apple-only (Ulysses, Vellum), weak or missing mobile/iPad apps (Scrivener iOS lag, Campfire, LegendKeeper).
9. **Paywalled basics**: distraction-free mode only in paid Bibisco; Campfire word caps.

---

## Implications for Quarry's editor

### Live name highlighting
- **Do** detect names/aliases in plain prose with no markup required, like Novelcrafter/Campfire. The text stays pure prose; the bible link lives in a decoration layer, never in the document text.
- **Do** colour by entity kind, but keep it quiet: a thin underline or low-contrast tint in the kind's colour rather than bold backgrounds. In a dark VS Code-like theme, muted underlines read as "semantic tokens", not as errors. Provide a one-key toggle to hide all highlights (draft mode) and a per-kind toggle.
- **Do** copy Novelcrafter's per-entry controls: aliases, case-sensitive switch for names that are common words ("Rose", "Hope", "Mark"), an exclusion list, and plural/possessive handling ("Aric's", "Goblins") with manual aliases for irregulars.
- **Do** make suppression one gesture from the prose: from the hover card, "not this one" (ignore this occurrence) and "never in this sense" (add exclusion). World Anvil's false-positive overload is the cautionary tale.
- **Do** keep detection incremental and viewport-scoped (CodeMirror decorations over the visible range, recompute on change of the edited lines only) so typing latency never depends on bible size. Google Docs/Word slowdowns on long files are a top complaint.
- **Do** feed bible names into the spell-check dictionary so invented names never get red squiggles; ideally let the user disable spell-check while drafting.
- **Don't** ever rewrite the manuscript text to insert links (no auto-converting words to `[[links]]` on pause).
- **Don't** colour-flash or animate a name as it becomes recognised mid-word; apply the decoration once the word boundary is reached to avoid flicker while typing.

### Hover cards
- **Do** show a compact card on hover after a short delay (~300–500 ms) with: kind, canonical name, aliases, 2–4 key facts the author pinned, and relationships most relevant to this scene. That matches Campfire's praised "eye colour" look-up.
- **Do** also offer a keyboard path: a shortcut on the caret's mention opens the same card; Esc closes it; another shortcut pins it to the side panel (Campfire's click-to-sidebar, Novelcrafter's click-to-preview).
- **Do** make hover cards non-focus-stealing: they must not take keyboard focus, must not move the caret, and must dismiss on any keystroke. Typing should always go to the prose.
- **Do** provide a setting to require a modifier (Ctrl/Alt) for hover cards, as Obsidian learned some users find unsolicited popovers intrusive. Default can be plain hover with delay; but never while the user is actively typing (suppress hover for a second or two after the last keystroke, and hide the mouse cursor while typing).
- **Don't** render the card differently from the full entry (LegendKeeper users complained about preview/page mismatch); reuse the same components.
- **Do** show "as of this scene" values if Quarry supports progressions (Novelcrafter's progressions show that writers want the bible to reflect the current point in the story).

### Side-panel suggestions (rule-based)
- **Do** keep the side panel passive and glanceable: "in this scene" entities (from detection), relationship reminders, continuity flags (e.g. a character marked dead appears later, an unknown capitalised word that looks like a new name). Updates should be debounced and never pull focus.
- **Do** present "possible new entity" candidates (capitalised words not in the bible) as a quiet list in the panel, not inline prompts; one click or keystroke to create the entry with the word prefilled — Obsidian-style near-zero cost of inventing an entity, without interrupting the sentence.
- **Don't** pop toasts, modals or inline widgets while drafting; no red/yellow badges inside the prose for rule findings during a drafting session. Offer a "review" mode where findings become inline diagnostics (iA-style opt-in lens).
- **Don't** suggest or generate any story content (consistent with the no-AI rule); suggestions are strictly about the author's own bible facts and text.
- **Do** avoid "fill these 40 fields" templates; entries should start as a name and grow. Campfire/World Anvil users warn about worldbuilding replacing writing.

### Keyboard flow
- **Do** make every action reachable without the mouse: command palette (VS Code style), quick-open for scenes and entries, toggle panels, jump to next/previous mention of the entity under the caret, open entry under caret, create entry from word under caret.
- **Do** keep autocomplete strictly opt-in and trigger-based if it exists at all (novelWriter only offers it on `@` lines; Obsidian only on `[[`). Plain prose typing never opens a dropdown.
- **Do** implement typewriter scrolling and focus dimming (sentence/paragraph) as separate toggles; recentre only on typing, not on mouse clicks, to avoid the "screen jumps" complaint.
- **Do** provide a distraction-free mode that hides panels and highlights, with chrome reachable by moving to an edge or a shortcut (Scrivener's control bar), and include it in the free core.
- **Do** support split view (scene + scene, or scene + entry) — a staple of Scrivener, Obsidian and Quick Reference workflows.

### Trust, sync and versioning
- **Do** save locally first (IndexedDB/OPFS) with an always-visible, unambiguous sync indicator (Dabble's model) and real offline support for the PWA; warn clearly about private windows.
- **Do** handle multiple tabs/devices safely (lock or merge) — Novelcrafter's multi-tab overwrite is a top data-loss cause.
- **Do** offer per-scene snapshots with compare, plus automatic history; and session/project word targets with a daily history.
- **Do** keep export to plain Markdown/text trivially available to counter lock-in fears.
- **Do** allow margin comments/notes anchored to ranges that do not live in the prose text.
