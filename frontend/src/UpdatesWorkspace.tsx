import { useCallback, useEffect, useState } from "react";

import type { UpdateClient, UpdateStatus } from "./api/updates";
import { type Theme, WorkspaceHeader } from "./components/WorkspaceHeader";

interface UpdatesWorkspaceProps {
  updates: UpdateClient;
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
}

type TransientState = "idle" | "checking" | "staging" | "failure";

function formatBytes(value: number | undefined): string | null {
  if (value === undefined) return null;
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function stateTitle(status: UpdateStatus | null, transient: TransientState): string {
  if (transient === "checking") return "Checking for updates";
  if (transient === "staging") return "Verifying update package";
  if (transient === "failure") return "Update check could not finish";
  if (!status) return "Loading update state";
  switch (status.state) {
    case "off":
      return "Update checking is off";
    case "never_checked":
      return "Never checked";
    case "up_to_date":
      return "Up to date";
    case "trusted_update_available":
      return "Trusted update available";
    case "staged":
      return "Trusted update staged";
  }
}

export function UpdatesWorkspace({
  updates,
  theme,
  onThemeChange,
}: UpdatesWorkspaceProps) {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [transient, setTransient] = useState<TransientState>("idle");
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await updates.status());
    } catch {
      setError("Scholion could not read the local update state.");
      setTransient("failure");
    }
  }, [updates]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  async function checkForUpdates() {
    setTransient("checking");
    setError(null);
    try {
      setStatus(await updates.check());
      setTransient("idle");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Scholion could not complete the trusted update request",
      );
      setTransient("failure");
    }
  }

  async function stageUpdate() {
    setTransient("staging");
    setError(null);
    try {
      setStatus(await updates.stage());
      setTransient("idle");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Scholion could not verify the update package",
      );
      setTransient("failure");
    }
  }

  const busy = transient === "checking" || transient === "staging";
  const size = formatBytes(status?.download_size_bytes);

  return (
    <section className="updates-workspace">
      <WorkspaceHeader
        eyebrow="Application updates"
        title="Keep Scholion trustworthy."
        theme={theme}
        onThemeChange={onThemeChange}
      />

      <div className="updates-grid">
        <article className="updates-card" aria-labelledby="update-state-heading">
          <p className="eyebrow">Update state</p>
          <h2 id="update-state-heading">{stateTitle(status, transient)}</h2>
          <p role="status" aria-live="polite">
            {busy
              ? transient === "checking"
                ? "Fetching a small signed release manifest and verifying it on this computer."
                : "Downloading the signed release package and checking its exact size and SHA-256 before staging it."
              : error ?? status?.message ?? "Reading local update state…"}
          </p>

          {status && (
            <dl className="updates-facts">
              <div>
                <dt>This version</dt>
                <dd>{status.current_version}</dd>
              </div>
              {status.available_version && (
                <div>
                  <dt>Trusted release</dt>
                  <dd>{status.available_version}</dd>
                </div>
              )}
              {size && (
                <div>
                  <dt>Package size</dt>
                  <dd>{size}</dd>
                </div>
              )}
            </dl>
          )}

          <div className="updates-actions">
            <button
              type="button"
              onClick={() => void checkForUpdates()}
              disabled={!status?.enabled || busy}
            >
              {transient === "checking" ? "Checking…" : "Check for updates"}
            </button>
            {status?.state === "trusted_update_available" && (
              <button
                type="button"
                className="secondary-button"
                onClick={() => void stageUpdate()}
                disabled={busy}
              >
                {transient === "staging" ? "Verifying…" : "Download and verify"}
              </button>
            )}
          </div>
        </article>

        <aside className="updates-card updates-privacy" aria-labelledby="update-privacy-heading">
          <p className="eyebrow">Privacy and trust</p>
          <h2 id="update-privacy-heading">A version check is network activity, not telemetry.</h2>
          <p>
            Scholion asks one fixed GitHub-hosted location for signed release metadata only when
            you choose <strong>Check for updates</strong>. It does not send an installation ID,
            recording or transcript information, research state, hardware inventory, model
            inventory, or product-behavior data.
          </p>
          <p>
            GitHub and its delivery network can still see ordinary connection metadata such as
            your IP address and request time. Existing local work remains available when update
            checking is off, unavailable, or offline.
          </p>
          <p>
            Release metadata must pass Scholion&apos;s signature, expiry, and rollback checks before
            it can authorize a package. A downloaded package is staged only after its signed size
            and SHA-256 match exactly.
          </p>
        </aside>
      </div>

      {status?.state === "staged" && transient === "idle" && (
        <div className="updates-boundary-note" role="note">
          <strong>Installation is deliberately separate.</strong> This build has verified and
          staged the package, but Scholion will not activate it until the native installer and
          operating-system signing boundary is configured for a production release.
        </div>
      )}
    </section>
  );
}
