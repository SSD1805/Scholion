import { invokeNativeProtocol } from "./nativeProtocol";

export type UpdatePersistentState =
  | "off"
  | "never_checked"
  | "up_to_date"
  | "trusted_update_available"
  | "staged";

export interface UpdateStatus {
  enabled: boolean;
  state: UpdatePersistentState;
  current_version: string;
  available_version?: string | null;
  release_notes_url?: string;
  download_size_bytes?: number;
  message: string;
}

export interface UpdateClient {
  status(): Promise<UpdateStatus>;
  check(): Promise<UpdateStatus>;
  stage(): Promise<UpdateStatus>;
}

const UPDATE_PROTOCOL_MESSAGES = {
  invalid: "Scholion update service returned an invalid response",
  incompatible: "Scholion update service returned an incompatible response",
  failure: "Scholion could not complete the trusted update request",
} as const;

class TauriUpdateClient implements UpdateClient {
  private request(method: "updates.status" | "updates.check" | "updates.stage") {
    return invokeNativeProtocol<UpdateStatus>(
      "update_request",
      method,
      {},
      UPDATE_PROTOCOL_MESSAGES,
    );
  }

  status(): Promise<UpdateStatus> {
    return this.request("updates.status");
  }

  check(): Promise<UpdateStatus> {
    return this.request("updates.check");
  }

  stage(): Promise<UpdateStatus> {
    return this.request("updates.stage");
  }
}

function mockStatus(
  state: UpdatePersistentState,
  overrides: Partial<UpdateStatus> = {},
): UpdateStatus {
  const messages: Record<UpdatePersistentState, string> = {
    off: "This build does not contain a production update trust key. Local and offline work is unaffected.",
    never_checked: "Scholion has not checked for updates on this computer.",
    up_to_date: "This Scholion version is up to date.",
    trusted_update_available: "A trusted Scholion update is available: 0.2.0.",
    staged: "Scholion verified and staged update 0.2.0 for installation.",
  };
  return {
    enabled: state !== "off",
    state,
    current_version: "0.1.0",
    available_version:
      state === "trusted_update_available" || state === "staged" ? "0.2.0" : null,
    message: messages[state],
    ...overrides,
  };
}

class MockUpdateClient implements UpdateClient {
  private state: UpdateStatus;
  private readonly mode: string | null;

  constructor() {
    this.mode = new URLSearchParams(window.location.search).get("update-mode");
    this.state = mockStatus(this.mode === "off" ? "off" : "never_checked");
  }

  async status(): Promise<UpdateStatus> {
    return { ...this.state };
  }

  async check(): Promise<UpdateStatus> {
    await new Promise((resolve) => window.setTimeout(resolve, 60));
    if (this.mode === "failure") {
      throw new Error("Scholion could not complete the trusted update request");
    }
    this.state =
      this.mode === "available"
        ? mockStatus("trusted_update_available", {
            release_notes_url:
              "https://github.com/SSD1805/Scholion/releases/tag/v0.2.0",
            download_size_bytes: 48_234_496,
          })
        : mockStatus("up_to_date");
    return { ...this.state };
  }

  async stage(): Promise<UpdateStatus> {
    await new Promise((resolve) => window.setTimeout(resolve, 60));
    if (this.state.state !== "trusted_update_available") {
      throw new Error("Check for a trusted update before downloading it");
    }
    this.state = mockStatus("staged", { download_size_bytes: 48_234_496 });
    return { ...this.state };
  }
}

export function createUpdateClient(): UpdateClient {
  const params = new URLSearchParams(window.location.search);
  return params.get("e2e") === "1" ? new MockUpdateClient() : new TauriUpdateClient();
}
