# Native desktop icons

`scholion-master.svg` is the reviewed Scholion product-icon master. It is the visual authority for future native icon generation and should remain platform-neutral.

`icon.png` is still the checked-in native build placeholder consumed by Tauri's generated application context. It is not a browser-only decoration and must remain available until the packaging milestone generates and wires the native icon family from `scholion-master.svg`.

The visual contract lives in **[Scholion application icon](../../../docs/product-icon.md)**: source/evidence plus marginal annotation, with only a restrained recorded-time cue and no generic microphone/AI branding.

The subsequent packaging milestone will generate the native derivative family from the one reviewed master, including Windows `.ico`, macOS `.icns`, and required PNG sizes. Do not create different platform-specific visual revisions or regenerate from a compressed screenshot/chat preview.
