import { invokeNativeProtocol } from "./nativeProtocol";

export type ProcessingProfile = "screening" | "balanced" | "accuracy";
export type ExportFormat = "txt" | "srt" | "vtt";

export interface ProcessingHealthCheck {
  check_id: string;
  status: "pass" | "warn" | "fail";
  summary: string;
  required: boolean;
  error_code: string | null;
}

export interface ProcessingAccelerator {
  accelerator_id: string;
  backend: string;
  device_index: number;
  name: string;
  memory_topology: string;
  memory_total_bytes: number | null;
  memory_available_bytes: number | null;
}

export interface ProcessingStrategy {
  strategy_id: string;
  model: string;
  device: string;
  compute_type: string;
  estimated_peak_memory_bytes: number;
  estimated_peak_device_memory_bytes: number;
  model_cache_bytes: number;
  feasible: boolean;
  rejection_reasons: string[];
  recommended: boolean;
}

export interface ProcessingModel {
  model_id: string;
  engine: string;
  estimated_cache_bytes: number;
  quality_rank: number;
  installed: boolean;
  resolved_revision: string | null;
  installed_size_bytes: number | null;
  verification: string | null;
}

export interface ProcessingCapability {
  available: boolean;
  reason_code: string | null;
  message: string | null;
}

export interface ProcessingReadiness {
  health: {
    status: "healthy" | "degraded" | "unhealthy";
    checks: ProcessingHealthCheck[];
  };
  capabilities: {
    speaker_labeling: ProcessingCapability;
  };
  resources: {
    platform: string;
    machine: string;
    processor_name: string | null;
    effective_cpus: number;
    memory_total_bytes: number;
    memory_available_bytes: number;
    effective_memory_available_bytes: number;
    constraints: string[];
    accelerators: ProcessingAccelerator[];
  };
  policy: {
    profile: ProcessingProfile;
    provisional: boolean;
    cpu_threads: number;
    memory_budget_bytes: number;
    constraints: string[];
  };
  strategies: ProcessingStrategy[];
  models: ProcessingModel[];
  model_policy_enforced: boolean;
  model_policy_trust: Record<string, boolean>;
  recommended_model: string | null;
  recommended_model_installed: boolean;
  recommended_model_ready: boolean;
}

export interface ProcessingJob {
  job_id: string;
  recording_name: string;
  status: "running" | "interrupted" | "failed" | "completed";
  started_at: string;
  updated_at: string;
  total_segments: number | null;
  completed_segments: number;
  progress_fraction: number | null;
  resumable: boolean;
  artifact_published: boolean;
  error_code: string | null;
  failure_message: string | null;
}

export interface ProcessingAudioStream {
  index: number;
  codec: string;
  duration_seconds: number | null;
  sample_rate_hz: number | null;
  channels: number | null;
  title: string | null;
  language: string | null;
  is_default: boolean;
}

export interface ProcessingPreflight {
  job_id: string;
  recording_name: string;
  source_sha256: string;
  container_format: string;
  duration_seconds: number;
  audio_streams: ProcessingAudioStream[];
  selected_audio_stream_index: number;
  audio_stream_selection_required: boolean;
  profile: ProcessingProfile;
  provisional: boolean;
  strategy_id: string;
  engine: string;
  model: string;
  model_revision: string;
  device: string;
  compute_type: string;
  cpu_threads: number;
  decode_strategy: string;
  enhancement_enabled: boolean;
  estimated_disk_bytes: number;
  estimated_peak_memory_bytes: number;
  memory_budget_bytes: number;
  fits_memory_budget: boolean;
  warnings: string[];
}

export interface ProcessingTaskStatus {
  task_id: string;
  state: "running" | "completed" | "failed" | "cancelled";
  exit_code: number | null;
  error_code: string | null;
  error_message: string | null;
}

export interface PreflightOptions {
  profile: ProcessingProfile;
  strategyId?: string | null;
  audioStreamIndex?: number | null;
  enhance?: boolean;
}

export interface ExecutionOptions {
  diarize: boolean;
  allowDiarizationModelDownload: boolean;
  speakers: number | null;
  minSpeakers: number | null;
  maxSpeakers: number | null;
  exportFormats: ExportFormat[];
}

export interface ProcessingClient {
  readiness(profile: ProcessingProfile): Promise<ProcessingReadiness>;
  jobs(): Promise<ProcessingJob[]>;
  preflight(inputPath: string, options: PreflightOptions): Promise<ProcessingPreflight>;
  retryPreflight(sourceJobId: string, options: PreflightOptions): Promise<ProcessingPreflight>;
  discardJob(job: ProcessingJob): Promise<void>;
  verifyModel(modelId: string): Promise<{ model_id: string; installed: boolean; resolved_revision: string | null }>;
  startTranscription(
    inputPath: string,
    plan: ProcessingPreflight,
    options: PreflightOptions,
    execution: ExecutionOptions,
  ): Promise<ProcessingTaskStatus>;
  retryTranscription(
    sourceJobId: string,
    plan: ProcessingPreflight,
    options: PreflightOptions,
    execution: ExecutionOptions,
  ): Promise<ProcessingTaskStatus>;
  resumeTranscription(
    job: ProcessingJob,
    execution: ExecutionOptions,
  ): Promise<ProcessingTaskStatus>;
  installModel(modelId: string, revision?: string | null): Promise<ProcessingTaskStatus>;
  removeModel(model: ProcessingModel): Promise<ProcessingTaskStatus>;
  taskStatus(taskId: string): Promise<ProcessingTaskStatus>;
  cancelTask(taskId: string): Promise<ProcessingTaskStatus>;
}

const PROCESSING_PROTOCOL_MESSAGES = {
  invalid: "Scholion Processing Center returned an invalid response",
  incompatible: "Scholion Processing Center returned an incompatible response",
  failure: "Scholion could not complete that request",
} as const;

function taskId(): string {
  return crypto.randomUUID();
}

function taskPayload(
  plan: ProcessingPreflight,
  options: PreflightOptions,
  execution: ExecutionOptions,
): Record<string, unknown> {
  return {
    job_id: plan.job_id,
    profile: options.profile,
    strategy_id: options.strategyId ?? null,
    audio_stream_index: options.audioStreamIndex ?? null,
    enhance: options.enhance ?? false,
    diarize: execution.diarize,
    allow_diarization_model_download: execution.allowDiarizationModelDownload,
    speakers: execution.speakers,
    min_speakers: execution.minSpeakers,
    max_speakers: execution.maxSpeakers,
    export_formats: execution.exportFormats,
  };
}

class TauriProcessingClient implements ProcessingClient {
  private request<T>(method: string, params: Record<string, unknown>): Promise<T> {
    return invokeNativeProtocol<T>(
      "desktop_request",
      method,
      params,
      PROCESSING_PROTOCOL_MESSAGES,
    );
  }

  private async startTask(task: Record<string, unknown>): Promise<ProcessingTaskStatus> {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<ProcessingTaskStatus>("processing_start_task", { task });
  }

  readiness(profile: ProcessingProfile): Promise<ProcessingReadiness> {
    return this.request("processing.readiness", { profile });
  }

  jobs(): Promise<ProcessingJob[]> {
    return this.request("processing.jobs.list", {});
  }

  preflight(inputPath: string, options: PreflightOptions): Promise<ProcessingPreflight> {
    return this.request("processing.preflight", {
      input_path: inputPath,
      profile: options.profile,
      strategy_id: options.strategyId ?? null,
      audio_stream_index: options.audioStreamIndex ?? null,
      enhance: options.enhance ?? false,
    });
  }

  retryPreflight(sourceJobId: string, options: PreflightOptions): Promise<ProcessingPreflight> {
    return this.request("processing.retry.preflight", {
      source_job_id: sourceJobId,
      profile: options.profile,
      strategy_id: options.strategyId ?? null,
      audio_stream_index: options.audioStreamIndex ?? null,
      enhance: options.enhance ?? false,
    });
  }

  async discardJob(job: ProcessingJob): Promise<void> {
    await this.request("processing.job.discard", {
      job_id: job.job_id,
      expected_updated_at: job.updated_at,
    });
  }

  verifyModel(modelId: string): Promise<{ model_id: string; installed: boolean; resolved_revision: string | null }> {
    return this.request("processing.model.verify", { model_id: modelId });
  }

  startTranscription(
    inputPath: string,
    plan: ProcessingPreflight,
    options: PreflightOptions,
    execution: ExecutionOptions,
  ): Promise<ProcessingTaskStatus> {
    return this.startTask({
      task_id: taskId(),
      kind: "transcribe",
      input_path: inputPath,
      ...taskPayload(plan, options, execution),
    });
  }

  retryTranscription(
    sourceJobId: string,
    plan: ProcessingPreflight,
    options: PreflightOptions,
    execution: ExecutionOptions,
  ): Promise<ProcessingTaskStatus> {
    return this.startTask({
      task_id: taskId(),
      kind: "retry",
      source_job_id: sourceJobId,
      ...taskPayload(plan, options, execution),
    });
  }

  resumeTranscription(
    job: ProcessingJob,
    execution: ExecutionOptions,
  ): Promise<ProcessingTaskStatus> {
    return this.startTask({
      task_id: taskId(),
      kind: "resume",
      job_id: job.job_id,
      diarize: execution.diarize,
      allow_diarization_model_download: execution.allowDiarizationModelDownload,
      speakers: execution.speakers,
      min_speakers: execution.minSpeakers,
      max_speakers: execution.maxSpeakers,
      export_formats: execution.exportFormats,
    });
  }

  installModel(modelId: string, revision?: string | null): Promise<ProcessingTaskStatus> {
    return this.startTask({
      task_id: taskId(),
      kind: "model-install",
      model_id: modelId,
      revision: revision ?? null,
    });
  }

  removeModel(model: ProcessingModel): Promise<ProcessingTaskStatus> {
    return this.startTask({
      task_id: taskId(),
      kind: "model-remove",
      model_id: model.model_id,
      expected_revision: model.resolved_revision,
    });
  }

  async taskStatus(taskIdValue: string): Promise<ProcessingTaskStatus> {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<ProcessingTaskStatus>("processing_task_status", {
      taskId: taskIdValue,
    });
  }

  async cancelTask(taskIdValue: string): Promise<ProcessingTaskStatus> {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<ProcessingTaskStatus>("processing_cancel_task", {
      taskId: taskIdValue,
    });
  }
}

export const processingClient: ProcessingClient = new TauriProcessingClient();
