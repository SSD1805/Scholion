# Getting started with Scholion 💃

This is the **use-the-thing** guide.

Scholion is a private, local-first workspace for recorded evidence. You do not need to understand CUDA, DuckDB, SQLite, model revisions, signatures, or desktop IPC to use it. Python owns application/evidence decisions so the desktop can speak in recordings, transcripts, speakers, searches, notes, playback, storage, updates, and evidence.

Scholion is still pre-production. There is no polished signed installer yet, so the supported path remains a source/developer checkout while issue #145 finishes pre-packaging readiness and packaging waits for the next milestone.

## Pick the smallest setup

| Goal | First command after cloning | You do not need yet |
|---|---|---|
| inspect/click the frontend with fake local data | `cd frontend && npm ci && npm run dev:mock` | Python backend, Rust, FFmpeg, model |
| run the native desktop window | bootstrap repository Python, follow desktop prerequisites, run `npm run tauri dev` | transcription model until processing media |
| use the Python CLI / process recordings | `python3.12 scripts/bootstrap_python.py` | frontend tooling unless you want the GUI |

The repository bootstrap installs Scholion's pinned `uv` into `.tools/uv` and uses it to create/synchronize `.venv`. A system-wide `uv` installation is not required. See **[Project-local developer toolchain](development/project-local-toolchain.md)** and **[Desktop source-build troubleshooting](development/troubleshooting.md)**.

## Frontend-only mock path

```bash
git clone https://github.com/SSD1805/Scholion.git
cd Scholion/frontend
npm ci
npm run doctor:desktop -- --mode=mock
npm run dev:mock
```

`dev:mock` intentionally uses fake local data. Plain `npm run dev` in a browser shows a development-mode explanation rather than pretending the browser has Tauri/Python filesystem authority.

## Native desktop path

Read **[Desktop development prerequisites](development/desktop-development.md)** before the first native build. On a prepared Linux/macOS machine:

```bash
cd Scholion
python3.12 scripts/bootstrap_python.py
cd frontend
npm ci
npm run doctor:desktop
npm run tauri dev
```

On Windows, use `py -3.12 scripts\bootstrap_python.py`; the project-local toolchain guide includes the PowerShell variants.

The debug Tauri host prefers the repository `.venv` for local backend calls. Normally you should not set `SCHOLION_PYTHON` yourself. If you do need an override, preserve the `.venv` launcher path.

## Help is built into the desktop

The sidebar offers **How this screen works** for the active workspace and **How Scholion works** for the overall evidence model. Evidence, Playback, Transcript tools, multi-track preflight, Storage, and Updates add local explanation where their semantics become unusual.

Those explanations are presentation only. They do not recreate backend policy in React. See **[In-app guidance](in-app-guidance.md)**.

## 1. Add or remember recordings

Use **Add evidence** to select recordings, existing transcript JSON, or folders you want Scholion to remember. Remembered locations are explicit permissions, not media custody.

Recording discovery does not itself hash, probe, copy, or transcribe candidates. Manual processing remains the default unless you explicitly choose a different processing policy.

## 2. Process a recording

Choose **Processing**. The current control loop includes:

- machine/resource readiness;
- managed model state;
- outcome-oriented processing profile;
- backend preflight before execution;
- explicit embedded-audio-track confirmation when a source contains more than one audio stream;
- optional deterministic enhancement;
- optional anonymous diarization;
- derived publication intent;
- supervised local start/cancel;
- durable job progress/state;
- checkpoint resume versus fresh retry; and
- private execution-state discard that does not delete source media, canonical transcript evidence, or research.

Transcription models download only when you choose. After installation they stay on this computer in Scholion's private app storage, so transcription can run offline.

Scholion now has two distinct model-trust layers. Provider/local custody records the immutable revision received and revalidates the managed snapshot. Project policy trust, when a reviewed catalog is bundled, requires the exact approved revision plus complete file-set/size/SHA-256 verification before new-job admission. The machinery is implemented; the repository deliberately does **not** contain guessed production faster-whisper entries. Real revisions/licenses/regression behavior must be reviewed under **[Production trust inputs](security/production-trust-inputs.md)** before packaging bundles them.

For a normal single-track recording, there is no track choice to make. If preflight finds several embedded audio tracks, Processing Center shows bounded source-declared metadata and keeps **Start local transcription** disabled until you choose one. Scholion then sends that exact index back to Python and re-runs preflight before enabling Start.

Those source labels are clues, not Scholion recommendations. See **[Processing Center](architecture/processing-center.md)** and **[Audio tracks](audio-tracks.md)**.

## 3. Process from the CLI when useful

```bash
python3.12 scripts/bootstrap_python.py
source .venv/bin/activate
scholion init
scholion doctor
scholion models recommend
scholion models install small
scholion transcribe interview.m4a --dry-run
scholion transcribe interview.m4a
```

For a file with several embedded audio tracks, bind an exact FFmpeg stream index:

```bash
scholion transcribe meeting.mkv --audio-stream 3 --dry-run
scholion transcribe meeting.mkv --audio-stream 3
```

An unavailable or non-audio index fails instead of silently falling back. The selected stream is preserved in canonical source provenance and restored on checkpoint resume.

Publication views can be requested with:

```bash
scholion transcribe interview.m4a --export txt --export srt --export vtt
```

Resume a validated interrupted job with:

```bash
scholion transcribe interview.m4a --resume JOB_ID
```

Resume rechecks source identity and current resource admission rather than silently changing the original execution contract.

## 4. Search the Library

```bash
scholion library rebuild
scholion library refresh
scholion library search "housing insecurity"
scholion library find "housing affordability" --context-segments 1
```

In the desktop **Library**, search transcripts, notes, tags, and collections. A transcript result can open either **Open transcript passage** for exact verified context/playback or **Transcript tools** for transcript/speaker management on that exact canonical generation.

## 5. Play the verified source

Open a transcript passage and choose **Prepare playback**.

Scholion does not hand the recording path to React. The request carries only the exact transcript generation and current source-relative cursor. Python re-verifies canonical bytes, original source fingerprint, duration bounds, and selected audio stream. Rust opens only that approved file and gives the webview an opaque local media session.

Playback is refused when the source is missing/changed, the transcript view is stale, the coordinate is invalid, or a multi-track source cannot yet be proven to render the same embedded stream that produced the transcript. This restriction does not prevent multi-track transcription.

See **[Verified native playback](native-playback.md)**.

## 6. Use transcript and speaker tools

From a transcript result, choose **Transcript tools**. Scholion verifies `(document_id, canonical_sha256)` before returning details or accepting mutations.

The panel can show generation identity, duration/language/segment/speaker summary, source availability, selected-stream/provenance details, anonymous speaker refs with optional human display names, overlap-aware speaker transcript, and post-hoc TXT/SRT/WebVTT publication.

Speaker names never replace anonymous evidence refs. Stale generations are refused rather than silently mutated. See **[Transcript and speaker tools](transcript-tools.md)** and **[Give the anonymous speakers names](speaker-names.md)**.

## 7. Keep durable research

Notes, tags, collections, anchors, and saved searches are authoritative local user state.

```bash
scholion library notes add JOB_ID segment-000042 \
  --body "Compare this with the 2024 survey." \
  --tag methodology \
  --collection "Chapter 3"
```

Saved searches persist question intent rather than frozen result snapshots. Research can reopen the exact older canonical generation cited by a durable note. See **[Research search](research-search.md)** and **[Research notes](research-notes.md)**.

## 8. Review storage and retention deliberately

Choose **Storage** to inspect backend-planned custody changes before anything destructive occurs. The desktop previews requested/effective scopes, concrete actions, preserved-note/affected-saved-search counts, and plan-bound confirmation. Source recording deletion requires its own scope and second acknowledgment.

Retention is narrower: it previews old private processing workspaces, excludes running jobs, and marks failed/interrupted candidates whose resume capability would be lost. It does not age-delete canonical transcripts, source recordings, published transcripts, human research, or lightweight lifecycle manifests.

See **[Storage and lifecycle controls](storage-lifecycle.md)**.

## 9. Check application update state

Choose **Updates**.

Current repository code supports:

- **Update checking is off** for a source/development build with no production verifier;
- **Never checked** before a manual request;
- explicit **Checking**, **Up to date**, and **Trusted update available** states;
- **Download and verify** staging only after trusted signed metadata authorizes the platform artifact; and
- bounded failure that does not block local evidence work.

The first-release update endpoint is fixed by application policy. React cannot submit a URL, path, header, executable command, or installer argument. Metadata must pass signature, publication/expiry, stable-channel, platform, anti-rollback, and same-sequence equivocation checks. Staged bytes must match the signed size/SHA-256 exactly.

A staged package is **not installed**. Production verifier/public-key bundling, native activation, and Windows/macOS signing/notarization belong to the later packaging milestone.

A manual update check is network activity. GitHub/CDN can observe ordinary connection metadata such as IP address and request time. Scholion sends no installation ID, recordings/transcripts/research content, hardware/model inventory, or behavioral telemetry.

See **[Signed update and model trust channel](security/update-model-trust.md)** and **[Production trust inputs](security/production-trust-inputs.md)**.

## 10. Change the appearance

The header has one **Theme** dropdown with Archive, Midnight, Paper, Moss, Plum, Ember, Pride, and Monochrome. The choice is local presentation preference only. All eight skins use one semantic text/control/focus contract and one registry-driven contrast/a11y matrix.

See **[Desktop themes and accessibility](development/desktop-accessibility.md)**.

## 11. Know the trust boundary

The desktop WebView does not receive arbitrary SQL, shell, subprocess, database, raw canonical/source filesystem, update-network, or installer authority.

Ordinary bounded desktop calls share one fixed-command protocol helper and one capability-blind Python host transport. Transcript tools, lifecycle, and Updates retain separate fixed capability commands because their authority differs. Playback is narrower still: path-bearing authorization stays private to Rust, which opens the file and returns only an opaque session to React.

Long-running Processing tasks remain separate from bounded request/response IPC. Tauri owns supervised child-process lifetime/task identity/status/cancellation; Python remains job/checkpoint/transcription authority.

See **[frontend/SECURITY.md](../frontend/SECURITY.md)**, **[Architecture and redundancy audit](architecture/redundancy-audit.md)**, and **[Pre-release security hardening](security/release-hardening.md)**.

## 12. Optional semantic/hybrid search

Lexical search is the dependency-light default. Semantic search helps when you remember the idea but not the wording; hybrid retrieval combines lexical/semantic ranking using reciprocal rank fusion.

The current optional semantic source path is sufficient for MVP use. Fully packaged immutable embedding dependency/model custody is a **post-MVP** productization tranche, not a reason to block the first packaged Scholion release.

See **[Semantic search](semantic-search.md)**.

## What comes next?

The current milestone is issue #145: finish the post-update redundancy/trust-input/documentation cleanup and replace the placeholder product icon.

After #145, the sequence is:

1. package Windows/macOS with managed runtime/native dependencies, real public update keys, reviewed model catalog, OS signing/notarization, update activation, first-run/repair/uninstall semantics; official Linux binary packaging remains blocked by #135;
2. qualify real packages across representative machines, including #114's remaining CPU-only/accelerator task-transport evidence; and
3. release the MVP.

Backup/restore + research portability, packaged semantic custody, and broader research-native features are **post-MVP** work. For the detailed sequence, see **[ROADMAP.md](../ROADMAP.md)**.
