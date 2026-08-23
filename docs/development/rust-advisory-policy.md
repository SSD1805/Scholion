# Rust dependency advisory policy

Scholion audits the locked Rust graph with RustSec. Findings are not all the same kind of risk, and a transitive advisory is not automatically fixable by adding or upgrading a direct Scholion dependency.

## Current Tauri 2 Linux debt

The current stable Tauri 2 Linux runtime resolves through GTK3/WebKitGTK-era bindings. That graph includes the archived gtk-rs GTK3 family and `glib 0.18.5`.

RustSec currently reports a known family of transitive advisories tracked by Scholion issue #135:

- RUSTSEC-2024-0411 through RUSTSEC-2024-0420 for the unmaintained GTK3 binding family;
- RUSTSEC-2024-0429 for unsoundness in `glib::VariantStrIter`;
- RUSTSEC-2024-0370 for unmaintained `proc-macro-error`; and
- RUSTSEC-2025-0075, RUSTSEC-2025-0080, RUSTSEC-2025-0081, RUSTSEC-2025-0098, and RUSTSEC-2025-0100 for the unmaintained `unic-*` family.

RUSTSEC-2024-0429 is materially different from an `unmaintained` notice. RustSec marks `glib >=0.15.0,<0.20.0` as affected for the relevant iterator functions and `glib >=0.20.0` as patched. The Tauri 2 GTK3 graph cannot be made to consume that API generation by a compatible leaf-package bump.

## Temporary audit allowlist

`.github/workflows/security.yml` passes the exact known advisory IDs above to `rustsec/audit-check` through its supported `ignore` input.

That allowlist means **tracked elsewhere**, not **fixed**.

The purpose is to prevent one known upstream migration from creating a new GitHub issue for every transitive crate on every audit run while preserving the useful invariant that an unfamiliar advisory ID still fails/alerts normally.

Rules for changing the allowlist:

1. Every ignored ID must have a named open owner/gate such as #135.
2. Do not add an ID merely to make CI green. First classify whether it is vulnerable/unsound, unmaintained, yanked, or otherwise informational and trace the dependency root.
3. Prefer removal or an upstream-supported dependency update over an exception.
4. Remove an ID as soon as the effective shipped graph no longer contains the affected dependency.
5. If a crate remains only as lockfile residue, prove that it is absent from the shipped target graph before downgrading the finding to cleanup debt.
6. Never use success on one operating system to waive a target-specific dependency problem on another.

## Linux release gate

A public Linux package must not be represented as release-qualified while RUSTSEC-2024-0429 remains in the shipped Linux graph.

The intended remediation is adoption of a stable/reviewed Tauri Linux runtime using maintained GTK4/WebKitGTK 6-era dependencies, or another upstream-supported runtime that removes the affected GLib implementation. Experimental personal forks, moving git branches, or application-level GTK/GLib overrides are not an acceptable production shortcut because they replace one known dependency problem with an unowned framework fork.

Before closing #135:

- re-run RustSec with the temporary allowlist removed;
- verify the effective Linux graph no longer contains the affected GLib/GTK3 dependencies;
- prove whether `proc-macro-error` and `unic-*` are gone or non-shipped residue;
- keep cargo-deny source/license policy green;
- qualify the native app on Linux Wayland and X11; and
- keep Windows and macOS CI green.

## Dependency-update decision rule

When RustSec reports a new Rust finding, start from the dependency root rather than the leaf crate name:

```text
Scholion direct dependency
        ↓
framework/runtime dependency
        ↓
transitive crate named by RustSec
```

If Scholion owns the direct dependency choice and a compatible patched release exists, update it and regenerate the lockfile. If the affected crate is constrained by a framework runtime, follow the framework's supported migration path or explicitly track the upstream blocker. Do not force an ABI/API-incompatible crate generation underneath a framework just to make the advisory line disappear.
