# RAINYMINE 2026 native desktop design

User reference: Mongolian RAINYMINE brand board supplied in this conversation. Implemented layout: light mineral-white surfaces, midnight-navy outline icons, teal selection accents, copper/steel/teal faceted M mark. Native Windows title bar and scientific geometry vary with OS, screen size and project data; the reference's photorealistic pit is not used as a fake 3D background.

## Assets and UI

- `assets/splash.jpg`: generated startup artwork, bundled for offline use; shown before heavy VTK imports. JPEG delivery copy preserves the generated composition. Progress is indeterminate; stage text reflects actual startup steps, with no artificial delay or fabricated percentage.
- `assets/rainymine.ico`, `assets/brandmark.png`: vector M rendered for native application, installer and shortcut icons.
- `rainymine/icons.py`: editable native SVG icon system, no remote icon/font dependencies.
- `rainymine/theme.py`: shared native style tokens.
- `rainymine/presentation.py`: grouped layers, table paging, command search, guide/local AI tabs, focus and ribbon collapse.
- Prior local-model support (Qwen3/llama.cpp), advanced geology and planning features merged on main are preserved. The guide's manual steps launch real tools. The local AI tab uses the existing restricted reviewed-help engine.

## Artwork generation

Built-in imagegen edit mode was used with the supplied brand board as the reference. Final prompt:

> Edit the supplied RAINYMINE brand board. Produce ONLY the startup splash panel shown in the bottom left, as a standalone full-bleed landscape image, approximately 2.25:1 aspect ratio, high resolution. Preserve its exact visual identity: deep midnight navy, fine teal topographic contour lines, fractured dark geological rock along the left and right edges with restrained teal and copper glowing seams, the central faceted three dimensional M emblem formed from navy/teal/steel silver/copper geological pieces, the exact white RAINYMINE wordmark and small widely spaced teal 2026 directly below it. Reproduce these faithfully, crisp and professional. Remove the progress bar, the 68% percentage, and the Mongolian loading caption; leave quiet dark negative space in the bottom fifth for the application's real progress/status overlay. No board headings, no workspace screenshot, no colour swatches, no surrounding white margins, no extra text. Only the standalone dark startup artwork with the central logo, RAINYMINE, and 2026.

The visual is decorative branding, not a geological model or measured deposit.

## Integrated 0.8.0

The default application uses `rainymine/workspace.py` with the six ribbon categories and lazy block grid. Command search, focus/ribbon controls, labeling and branded startup are preserved from main. `rainymine/presentation.py` remains as the separately tested compatibility presentation. See [Монгол брэндбүүк](docs/BRANDBOOK.mn.md) for the current palette, logo, startup and distribution notes.

## 0.9 startup correction

The dark startup background is generated decorative geology artwork (`assets/splash-background.jpg`): midnight navy negative space, fractured geological strata, restrained copper seams and teal wireframe ore blocks. It contains no baked-in logo, text or progress bar. `StartupScreen` overlays the same canonical `rainymine-brand.svg`, with its navy upper stratum rendered white for dark-background contrast, plus native wordmark/year and the real busy indicator. The logo geometry is shared with the application icon. `splash-new.png` is a runtime preview, not the compositing source.
