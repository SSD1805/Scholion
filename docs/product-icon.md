# Scholion application icon

Scholion's application icon should represent the product it became: a private workspace for **recorded evidence and annotation**, not a generic transcription utility.

## Product metaphor

The mark combines three ideas without trying to draw all of them literally:

1. **evidence page / source**: a stable rectangular or page-like field;
2. **marginal annotation**: a bracket, marginal stroke, or note mark attached to that source rather than replacing it; and
3. **recorded time**: a restrained waveform/timeline gesture that reads as a secondary clue, not a microphone logo.

A successful mark should still make sense if the viewer never knows the word *scholion*. It should communicate “source + annotation / evidence work” before “audio recorder.”

## Visual constraints

The master should be:

- square and centered with generous optical padding;
- legible at 16×16 and 32×32 without relying on tiny text/details;
- recognizable as a silhouette at normal taskbar/dock sizes;
- free of the word `Scholion` or any text that becomes illegible at small sizes;
- free of literal microphones, headphones, play buttons, cloud/network motifs, or AI sparkle clichés;
- built from a small number of strong shapes with clear negative space;
- usable against both light and dark system chrome;
- safe under macOS rounded-square masking and Windows icon presentation; and
- visually compatible with every Scholion theme without belonging to one theme skin.

The icon is product identity, not evidence/research state. Theme switching must never recolor the installed application icon dynamically.

## Preferred direction

The first final candidate should use a compact **page/evidence tile with a marginal bracket and one restrained waveform/timeline cut**. The bracket should feel attached to or embracing the source. The waveform should be abstract enough that the icon does not collapse into “audio editor.”

The overall tone should be scholarly without becoming faux-antique: modern geometric construction, slightly human edges if useful, no quills, scrolls, wax seals, columns, books-with-tiny-pages, or illuminated-manuscript micro-detail.

Color should be quiet and durable. A warm paper/ivory field with very dark ink and one restrained plum/indigo accent is a good starting direction, but contrast and silhouette matter more than a fixed palette. The final packaging asset set should include enough opaque background/edge treatment that the mark does not disappear on either light or dark desktops.

## Asset custody

`frontend/src-tauri/icons/icon.png` is currently the checked-in placeholder required by the native build. Do not delete it until a reviewed master is committed and the generated native icon family is present.

The final icon source/master should be retained in the repository in a reproducible high-resolution/vector-friendly form. Packaging then generates the platform derivatives required by Tauri, including Windows `.ico`, macOS `.icns`, and the required PNG sizes. Generated derivatives are build assets; the reviewed master is the visual authority.

Do not regenerate platform assets from a screenshot, compressed chat preview, or different visual revision on each operating system.

## Acceptance checks

Before packaging freezes the icon:

- inspect at 16, 20, 24, 32, 48, 64, 128, 256, 512, and 1024 px;
- inspect on light, dark, and mid-tone neutral backgrounds;
- inspect under a rounded-square mask and with no mask;
- verify the smallest sizes still show one source shape and one annotation gesture;
- verify no tiny stroke turns into visual noise;
- verify there is no accidental resemblance to a microphone, chat bubble, document-upload icon, or generic AI sparkle mark; and
- keep the same approved master across Windows/macOS/Linux derivatives even while official Linux binary packaging remains blocked by issue #135.

Issue #145 owns the final pre-packaging icon decision. Platform derivative generation belongs with the subsequent packaging milestone once the final master is approved.
