# e-Himaya design system (phase UI)

**Standing rule (Yamen, 2026-10-24):** every surface of the project, the citizen app, the institutions portal
and the central and regional dashboards, follows one visual language: vivid colours, coloured icon tiles,
rounded white cards, pill badges and bold Arabic type, as in Yamen's reference mockups for additions 11 and 12.
New screens are designed in this language from the start, and older screens are moved to it when they are touched.
The language is our own: no logo, icon set or layout is copied from another app. The only logo used is the
Office's own.

Every change still follows review → redesign → develop.

A visual reference with every colour code, icon, shape, font and framework, with sources and download links, is in
[`design-reference.html`](design-reference.html).

## 1. Review: what exists today

| Area | Today | Gap with the reference |
|---|---|---|
| Mobile colours | Material 3 `ColorScheme.fromSeed` from the logo blue; tonal, low-saturation surfaces | Reference uses saturated fills (navy, red, orange, green, purple, teal, amber) and a cool grey page with white cards |
| Mobile font | Platform default (Roboto / SF, Arabic fallback) | Reference uses one bold Arabic sans for every weight |
| Mobile components | Plain `ListTile`s, outlined cards, icon without a tile | Coloured icon tiles, card rows with a chevron, pastel pills, segmented tabs, fixed bottom action bar |
| Web colours | One token set copied in `dashboard` and `portal` `global.css`, red primary `#b71c1c` | Navy primary, red kept for emergencies only, the same category colours as the app |
| Web font | `"Noto Sans Arabic"` named but never loaded, so the system font shows | Bundled font, same as the app |
| Web icons | A few inline SVGs, navigation is text only | Coloured icon tiles in the navigation, the KPI cards and the lists |

## 2. Redesign: tokens

All values below are checked for WCAG 2.2 AA: text ≥ 4.5:1 (≥ 3:1 for bold text of 18.66 px and above), icons and
borders that carry meaning ≥ 3:1 against what they sit on.

### 2.0 Brand colours: white base, royal blue or royal red frame (Yamen, 2026-11-08)

White is the base colour of every surface: the page, the cards, the forms and the tables stay white (in the dark
mode, the dark page). The user picks one of two royal colours, **royal blue** (default) or **royal red**, and the
choice changes three things only, so the face of the system stays the same:

1. **The frame:** a band of the royal colour around the screen, with a gold hairline on its inner edge and rounded
   inner corners, like the sign-in page. It fills the side spaces and never covers content: 10 px on screens of
   721 px and more, 5 px on narrow screens; 4 dp in the app.
2. **The primary colour:** primary buttons, links, the selected menu entry, the selected segment and language, the
   focus ring of the frame's own controls.
3. **The primary tint:** pills and soft tiles that show "selected" or "primary" use the tint of the royal colour.

Nothing else changes: the category colours (§2.3), the status colours, the priority bands, the [SIM] amber and the
emergency red stay the same in both choices, so an icon keeps its colour wherever it appears. The emergency red
(`#D7141A`) is brighter than royal red and is only used for 198, SOS, alerts and destructive actions, each with its
word and icon, never colour alone.

| Token | Royal blue | Royal red | Use | Contrast |
|---|---|---|---|---|
| `brand` | `#1F3FA0` | `#9B1B2C` | Frame, primary buttons, links, selected states | white 9.2:1 / 8.1:1 |
| `brand-deep` | `#152D78` | `#761420` | Hover and pressed, frame gradient | white 11:1 |
| `brand-night` | `#0B1A3F` | `#3A0910` | Frame in the dark mode, sign-in background | gold 7.1:1 |
| `brand-tint` | `#E8EDFA` | `#FBE9EC` | Selected pills and soft tiles | |
| `brand-ink` | `#1F3FA0` | `#8E1426` | Text on the tint | 7.9:1 on the tint |
| `brand` (dark mode) | `#8FA8FF` | `#FF8A95` | Primary on dark cards, with `#0E1426` text | 8.0:1 / 8.1:1 |
| `gold` | `#C9A24A` | `#C9A24A` | Hairline inside the frame, the switch coins (decorative) | |

**The switch:** on the web, a 32 px coin of the *other* colour, ringed in gold, sits with the tools of the top bar of
the dashboard and the portal, and under the language coin on the sign-in page; one press changes the colour, and it
is named for screen readers («اللون الأحمر الملكي» / «اللون الأزرق الملكي»). In the app, Settings › Colours offers the
two choices («أزرق ملكي» / «أحمر ملكي»), each with its gold-ringed coin. The choice is kept on the device
(`localStorage` key `ehimaya.brand` on the web, the app settings on the phone), applied before the first paint,
and never sent to the server.

### 2.1 Colours (light)

| Token | Value | Use | Contrast |
|---|---|---|---|
| `ink` | `#182038` | Titles and body text | 16.1:1 on white |
| `muted` | `#5B6478` | Subtitles, captions | 5.9:1 on white |
| `page` | `#FFFFFF` | Page background: white is the base colour (§2.0); cards keep their `line` border | |
| `card` | `#FFFFFF` | Cards, sheets, app bar | |
| `line` | `#E3E7EF` | Card borders, dividers | decorative |
| `navy` | `#1F3FA0` | Category colour; the primary colour is `brand` (§2.0) | white 9.2:1 |
| `red` (emergency) | `#D7141A` | 198, SOS, alert headers, destructive | white 5.2:1 |
| `orange` (accent) | `#F08C00` | Step bars, selection borders, highlights; never text, never the only sign (2.5:1 on white) | ink 6.5:1 |
| `orangeStrong` | `#C25E00` | Orange buttons and orange text | white 4.3:1 (bold large only) |
| `green` | `#188038` | Call buttons, "OK" states, progress rings | white 5.0:1 |
| `purple` | `#7838A0` | Information requests, knowledge | white 7.3:1 |
| `teal` | `#00806A` | Partnerships, places, water | white 4.9:1 |
| `amber` | `#F5B400` | Ideas, warnings (fill only, glyph in ink) | ink 8.6:1 |
| `pink` | `#C2185B` | Culture and sport, rewards | white 5.9:1 |
| `slate` | `#5B6478` | Bugs, neutral items | white 5.9:1 |
| `sky` | `#1976D2` | Weather, information | white 4.6:1 |

Each colour has a **tint** (≈ 10 % on white) used for pills and soft tiles, with text in a darker shade of the same
colour (≥ 4.5:1 on the tint):

| Pill | Background | Text |
|---|---|---|
| green | `#E6F4EA` | `#166B2E` |
| navy | `#E8EDFA` | `#1F3FA0` |
| red | `#FDE8E8` | `#B3121A` |
| amber | `#FFF3D6` | `#7A4B00` |
| purple | `#F2EAF8` | `#5E2A80` |
| teal | `#E0F3EF` | `#00695A` |
| slate | `#EEF0F4` | `#3E4657` |

### 2.2 Colours (dark)

Page `#0E1426`, card `#161E35`, line `#26304D`, ink `#E8ECF5`, muted `#A6AFC4`. Fills keep their hue and are lifted
for contrast: navy `#8FA8FF` (text on it `#0E1426`), red `#FF6B6B`, orange `#FFA733`, green `#4CC772`, purple
`#C49BE6`, teal `#4DD0B8`, amber `#FFC933`, pink `#F06292`, sky `#64B5F6`. Pills use the colour at 18 % on the card
with the light text value. The critical-alert lock screen keeps its own deep navy gradient in both modes.

### 2.3 Category colours

One map, the same in the three apps, so an item has the same colour everywhere:

| Category | Colour | Example |
|---|---|---|
| Emergency, report, alert, SOS, live | red | Report a problem, 198 |
| Follow-up, tracking, institution, account | navy | Track a request, my institution |
| Information, knowledge, doctors | purple | Access to information |
| Question, safety, health, OK | green | Ask a question, tips |
| Idea, warning, maintenance | amber | Suggestion |
| Partnership, places, maps, water | teal | Association partnership |
| Bug, settings, neutral | slate | Report an app bug |
| Rewards, culture | pink | Rewards |
| Weather, notifications | sky | Weather |

### 2.4 Type

**IBM Plex Sans Arabic** (SIL Open Font License 1.1), bundled in the app and self-hosted on the web, Arabic and Latin
in one family. Weights 400, 500, 600, 700.

| Style | Size / weight |
|---|---|
| Screen title | 22 / 700 |
| Section title | 17 / 700 |
| Card title | 16 / 700 |
| Body | 15 / 400 |
| Caption | 13 / 500, `muted` |
| Button | 16 / 700 |

### 2.5 Shape and depth

Cards radius 16, buttons 14, icon tiles 12, pills and segmented tracks fully rounded. Cards: white, 1 px `line`
border, shadow `0 1px 3px rgb(24 32 56 / 6%)`. Buttons 52–56 high. Spacing scale 4, 8, 12, 16, 20, 24.

## 3. Redesign: components

| Component | Look | Where |
|---|---|---|
| `IconTile` | 44 px rounded square, solid category colour, white glyph (amber: ink glyph); `soft` variant: tint background, coloured glyph | Every list row, grids, KPI cards |
| `NavCard` | White card row: icon tile, bold title, muted subtitle, chevron at the end (mirrored in RTL) | Contact us, settings, menus |
| `ChoiceTile` | Square card, soft icon tile, title and caption centred; selected = orange 2 px border, orange tint and a check mark | Choices (institution type), shortcuts |
| `Pill` | Fully rounded tint badge with the darker text | Status, visibility (public / institution / on incident) |
| `SegmentedTabs` | Grey track, white raised pill on the selected segment, navy text | Citizen / association / institution, tabs |
| `LanguagePill` | Grey track; the current language in a navy circle | Every app bar |
| `BottomActionBar` | Two large rounded buttons on a white bar with a top border: emergency red first | Home, contact, institution |
| `HeroHeader` | Full-width red (or navy) band, white icon, title and one meta line | Alert screens |
| `StepBar` | Segments, done = orange, to do = line grey | Multi-step forms |
| `ProgressRing` | Green ring with the percentage in the centre | Readiness, completion |
| `PageTitle` (UI-2) | Page heading: the section's icon tile (same icon and colour as its navigation entry) next to the bold title | Every dashboard and portal page |
| `EnvironmentStrip` (UI-2, G3) | Full-width amber band with the [SIM] tag naming the environment (development, pilot, training); absent in production | Top of the dashboard, the portal and the app |
| Draft notice (UI-2, G4) | Warning alert «the record changed while you typed; your text is kept» with an acknowledge button | Dashboard forms with a draft |
| `Stepper` (R4a) | − value + in one rounded box: 48 px buttons in `surface-2`, the value bold and centred, still typeable; a step per field (1 for counts, 5 for minutes, 500 for litres, 0.1 for a factor); a long press repeats, then moves ten steps; arrow keys step; buttons named for screen readers («زيادة السعة») and disabled at the bounds | Every number field of the dashboard, the portal and the app |
| Icons | Material Symbols Rounded (Apache 2.0), filled inside tiles | All apps |

**Less typing (R4, Yamen 2026-10-28):** never ask the user to type what they can pick. A number is a `Stepper`, a short
list is segmented buttons or chips, a long list a searchable select, a yes or no a switch, a reason a set of ready reasons
with «other» opening the text; free text only where nothing else fits (notes, the description of a report).

Rules kept from phase A: language bar on every screen, red asterisk on required fields, 48 dp targets, no meaning by
colour alone (every pill has its word, every tile its label), text scaling to 200 %.

## 4. Develop: where it lives

* **Mobile** `apps/mobile/lib/core/ui/`: `tokens.dart` (colours, category map, radii), `theme.dart` (Material theme
  built from the tokens: font, cards, buttons, inputs, chips, segmented buttons, app bar, navigation),
  `components.dart` (the components above). Font files in `assets/fonts/`.
* **Web** `apps/dashboard/src/styles/global.css` and `apps/portal/src/styles/global.css`: the same tokens as CSS
  custom properties, component classes (`.icon-tile`, `.nav-card`, `.pill`, `.segmented`, …), and an `Icon`
  component with the Material Symbols paths in use. Font self-hosted from `@fontsource/ibm-plex-sans-arabic`.
* The colour palettes of phase A (office, red, blue, green) are replaced by the two brand colours of §2.0. A stored
  `red` becomes royal red; `office`, `blue` and `green` become royal blue. The category colours never change.
* Brand frame: `apps/dashboard/src/lib/brand.ts` and `apps/portal/src/lib/brand.ts` (choice and switch), the
  "Brand frame" block at the end of each `global.css`; `apps/mobile/lib/core/ui/theme.dart` (`AppPalette.blue`,
  `AppPalette.red`) and `BrandFrame` in `components.dart`; the sign-in page in
  `infra/keycloak/themes/ehimaya/login/resources/css/ehimaya.css` (`html.ehimaya-red`).
