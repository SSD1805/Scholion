# OS signing and notarization

This document explains the platform-trust boundary that follows Scholion's production trust-input work.

Scholion has two different kinds of release trust, and they solve different problems:

1. **Scholion project trust** verifies Scholion's own signed update metadata and exact staged artifact bytes using the project's Ed25519 release key.
2. **Operating-system distribution trust** lets Windows and macOS verify that the application package was signed by the expected registered publisher/developer and, on macOS, that the submitted build passed Apple's notarization service.

Neither mechanism replaces the other.

## macOS: direct distribution, not the Mac App Store

Scholion's planned macOS release is a directly distributed application, for example a versioned DMG published through GitHub Releases. That does **not** require publishing Scholion in the Mac App Store.

For normal direct distribution on modern macOS, the release path should use Apple's **Developer ID** signing identity and Apple's **notarization** service.

Conceptually:

1. the release owner participates in Apple's developer program/account system and obtains the appropriate Developer ID signing identity;
2. the final Scholion application bundle and relevant nested native code are signed with that identity;
3. the signed build is submitted to Apple's notarization service;
4. after Apple reports successful notarization, the notarization result is associated with the distributed artifact and stapled where appropriate; and
5. representative macOS qualification verifies that Gatekeeper accepts the exact artifact users will receive.

This is Apple's direct-download trust path. It is separate from App Store submission, App Store review, App Store commerce, sandboxing requirements specific to App Store distribution, and App Store publication.

The exact current Apple enrollment terms, certificate workflow, command-line tooling, notarization requirements, and account rules are external platform policy and must be reverified against Apple's current documentation when #173 is executed. Scholion documentation should not hard-code a fee or credential procedure that can change independently of this repository.

## What notarization means

Notarization is not a source-code review and is not an endorsement of Scholion's product claims. It is an Apple-operated automated security/distribution check over a signed submission.

For Scholion, the important release invariant is narrower:

> the exact macOS artifact published to users must be the same signed/notarized candidate that passed release qualification and whose public identity is recorded in release evidence.

Notarization therefore belongs after the production payload is finalized and before the release is represented as production-ready.

## Windows: code signing

Windows has an analogous publisher-trust problem, although the platform mechanics differ.

The Windows production release should use an appropriate production code-signing credential/certificate custody path, sign the final application/installer artifacts required by the distribution flow, verify those signatures on the exact bytes users will receive, and bind the signed artifact identity into Scholion's release evidence.

As with the macOS path, private signing credentials must not be committed to Git, embedded in the application, copied into ordinary CI logs/artifacts, or confused with Scholion's public Ed25519 update-verification key.

## Relationship to Scholion's Ed25519 update key

The three relevant trust objects are intentionally separate:

| Object | Purpose | Private material location |
|---|---|---|
| Scholion Ed25519 release key | signs Scholion update metadata | external controlled custody; never in the shipped app |
| Windows signing credential | lets Windows identify/trust the publisher of the distributed Windows artifact | external platform-signing custody |
| Apple Developer ID signing identity | lets macOS identify the developer of a directly distributed app; prerequisite for notarization | Apple/platform-signing custody |

The installed Scholion application contains only the public verification material it needs. It never needs the private Ed25519 release key, Windows private signing credential, or Apple private signing identity.

## Release sequence

The Windows/macOS release path is now tracked explicitly:

1. **#177** create and safeguard the real Scholion Ed25519 release key and produce the reviewed public verification catalog;
2. **#178** review and pin the first-release `tiny`, `small`, and `medium` faster-whisper snapshots;
3. **#168** bind those exact public trust inputs into a production-shaped candidate and qualify them end to end;
4. **#173** sign the Windows candidate and sign/notarize the macOS candidate;
5. **#174** activate only already-trusted staged updates through the narrow native host;
6. **#114** record representative native device qualification; and
7. **#175** publish the final checksums, provenance, SBOM, signatures, signed update metadata, and supported Windows/macOS MVP artifacts.

`release_ready` remains false until the applicable release gates are complete.

## Boundaries

- no Mac App Store distribution is required by this plan;
- no Apple or Windows platform signing credential belongs in repository fixtures or source control;
- platform signing does not replace Scholion's Ed25519 update-manifest verification;
- Scholion's Ed25519 signature does not replace platform signing/notarization;
- hosted CI preview packages are not production releases merely because they build and run;
- official Linux binary distribution remains separately blocked by #135.

Related: #168, #173, #174, #175, #177, #178, #114, #135, `production-trust-inputs.md`, `update-model-trust.md`.