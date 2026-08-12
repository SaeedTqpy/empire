# Iranian architectural design system

Iran 3D Peaks uses an Iranian visual language that is intentionally broader than a generic "Islamic" theme. The interface combines documented pre-Islamic, garden and vernacular traditions and translates them into modern UI structure rather than copying a historic monument.

## Research anchors

### Achaemenid architecture — Persepolis and Susa

Encyclopaedia Iranica documents the strong axial and ceremonial planning of Persepolis, monumental stone platforms and columns, and decorative vocabularies including lotus, palmette and rosette motifs. Surviving descriptions also record glazed architectural colors including blue, green and orange. Achaemenid glazed brick decoration from Susa includes yellow, blue, blue-green, black, brown and white.

UI translation:

- ordered horizontal rhythm in the header rather than mosque silhouettes;
- a restrained twelve-petal rosette mark;
- lapis / blue-green accents alongside earth and stone;
- thin frieze bands and strong edge hierarchy instead of dense ornamental wallpaper.

Sources:

- Encyclopaedia Iranica, **Persepolis**
- Encyclopaedia Iranica, **Achaemenid Glazed Brick Decoration**

### Sasanian construction

Sasanian architecture made extensive use of mud brick, brick, mortar masonry, vaulting and plaster/stucco. These materials are part of a long Iranian architectural continuum and should not be reduced to later tile-heavy religious architecture.

UI translation:

- plaster / adobe primary surfaces;
- brick-red actions;
- solid portal-like panel framing and asymmetric corner rhythm;
- shadows kept soft and material rather than glassy/neon.

Source:

- Encyclopaedia Iranica, **Architecture iii. Sasanian Period**

### Persian garden

UNESCO describes the Persian Garden as geometrically proportioned, often divided into four parts (Chahar Bagh), with water systems, terrain and vegetation integrated into a coherent human-made environment.

UI translation:

- a nearly invisible four-part background axis across the application shell;
- central map as the visual "courtyard";
- side panels as ordered wings around the terrain;
- water blue-green used as a secondary spatial accent rather than the dominant brand color.

Source:

- UNESCO World Heritage Centre, **The Persian Garden**

### Vernacular Yazd

UNESCO describes Yazd's earthen architecture, sunken courtyards, windcatchers, thick earthen walls, qanats and shaded urban fabric as a long-lived adaptation to the Iranian plateau. This is a crucial counterweight to the common assumption that Iranian visual identity equals mosque tilework.

UI translation:

- warm earth / plaster page field;
- recessed panels and shaded edges;
- restrained ornament with generous breathing room;
- visual hierarchy based on shade, depth and material contrast.

Source:

- UNESCO World Heritage Centre, **Historic City of Yazd**

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| Adobe paper | `#F3EADC` | page field |
| Plaster | `#FFFAF0` | cards and panels |
| Brick / terracotta | `#A6513D` | primary actions and hazards |
| Deep brick | `#78382E` | pressed / active actions |
| Lapis | `#245B72` | navigation and structural emphasis |
| Blue-green | `#347B76` | secondary Iranian glazed-color accent |
| Garden green | `#536B50` | natural / healthy status |
| Water | `#6D9FA1` | chahar-bagh axis and water semantics |
| Saffron / ochre | `#C3923F` | fine ornament and summit emphasis |
| Charcoal stone | `#2E2923` | primary text |

The palette deliberately keeps turquoise subordinate. The base identity comes from earth, plaster, brick, stone and garden/water tones; this prevents the interface from collapsing into a generic "Islamic blue tile" theme.

## Typography

Primary font: **Estedad Variable**.

- self-hosted through `@fontsource-variable/estedad`;
- variable weights 100–900;
- Arabic/Persian and Latin coverage;
- optimized for screen/web use;
- SIL Open Font License.

The site no longer depends on Google Fonts at runtime.

## Shape language

- Cards: `4px 18px 4px 18px` alternating corners, used as an abstract portal / framed-opening rhythm rather than literal arches.
- Primary buttons: brick red with a fine saffron line.
- Navigation: lapis as the architectural/wayfinding color.
- Rosette: twelve petals, used only at brand level so the UI does not become ornamental noise.
- MapLibre chrome: dark mineral/earth glass with warm borders, while the terrain remains visually dominant.

## UX rules

1. Terrain is always the hero. Ornament must never cover the mountain.
2. Iranian identity comes from composition and material hierarchy before decoration.
3. Historic motifs are abstracted, not copied as decorative wallpaper.
4. Persian labels are paired with concise English where global comprehension matters.
5. Reduced-motion preferences remain respected.
6. All runtime fonts and map tiles stay self-hosted.
