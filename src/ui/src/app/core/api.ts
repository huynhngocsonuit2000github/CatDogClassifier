import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import {
  Arch,
  DatasetStatus,
  DatasetVersion,
  ModelStage,
  ModelVersion,
  Prediction,
  RunStatus,
  TrainingConfig,
  TrainingRun,
} from './models';
import { environment } from '../../environments/environment';

/**
 * Base URL of the Data Management service (Step 1). The backend sets
 * `Access-Control-Allow-Origin: *`, so the browser can call it directly
 * without a dev-server proxy. The URL comes from the build environment:
 * local dev targets 127.0.0.1:8000; the docker build targets 127.0.0.1:8100
 * (see src/environments/ and src/docker-compose.yml).
 */
const BASE_URL = environment.dataManagementUrl;

/** Wire shape returned by the FastAPI backend (snake_case). */
interface DatasetDto {
  version: string;
  name: string;
  images: number;
  cats: number;
  dogs: number;
  cat_pct: number;
  status: string;
  object_key: string;
  dvc_file: string;
  warnings: string[];
  created_at: string;
}

function normalizeStatus(status: string): DatasetStatus {
  switch (status) {
    case 'validated':
      return 'validated';
    case 'invalid':
      return 'invalid';
    case 'validating':
    case 'uploading':
      return 'validating';
    case 'failed':
    default:
      return 'failed';
  }
}

function toDataset(dto: DatasetDto): DatasetVersion {
  return {
    version: dto.version,
    name: dto.name,
    images: dto.images,
    cats: dto.cats,
    dogs: dto.dogs,
    status: normalizeStatus(dto.status),
    createdAt: new Date(dto.created_at),
    warnings: dto.warnings,
    dvcFile: dto.dvc_file,
  };
}

@Injectable({ providedIn: 'root' })
export class DataApi {
  private readonly http = inject(HttpClient);

  list(): Observable<DatasetVersion[]> {
    return this.http
      .get<{ datasets: DatasetDto[] }>(`${BASE_URL}/datasets`)
      .pipe(map((res) => res.datasets.map(toDataset)));
  }

  upload(file: File, name: string): Observable<DatasetVersion> {
    const form = new FormData();
    form.append('file', file);
    const trimmed = name?.trim();
    if (trimmed) {
      form.append('name', trimmed);
    }
    return this.http
      .post<DatasetDto>(`${BASE_URL}/datasets`, form)
      .pipe(map(toDataset));
  }
}

/* ------------------------------------------------------------------ */
/* Training service (Step 2)                                           */
/* ------------------------------------------------------------------ */

/** Base URL of the Training service (Step 2). See TrainingApi docs. */
const TRAINING_BASE_URL = environment.trainingUrl;

/** Wire shape of one run from `GET /runs` (snake_case, MLflow Enum names). */
interface RunDto {
  run_id: string;
  status: string;
  run_name: string | null;
  start_time: string | null;
  end_time: string | null;
  params: Record<string, string>;
  metrics: Record<string, number>;
}

/** Wire shape returned by `POST /train` (HTTP 202). */
interface TrainStartDto {
  job_id: string;
  status: string;
  dataset_version: string;
  epochs: number;
  batch_size: number;
  learning_rate: number;
  image_size: number;
}

/** Wire shape of one entry from `GET /jobs/{job_id}`. */
interface JobDto {
  job_id: string;
  status: string;
  dataset_version: string;
  run_id: string | null;
  metrics: Record<string, number> | null;
  error: string | null;
  created_at: string;
}

export type TrainingJobStatus =
  | 'starting'
  | 'pulling'
  | 'training'
  | 'finished'
  | 'failed';

export interface TrainingJob {
  jobId: string;
  status: TrainingJobStatus;
  runId: string | null;
  error: string | null;
  metrics: Record<string, number> | null;
}

/** The backend only ever trains MobileNetV2 — pin the arch regardless of input. */
function toArch(_value: unknown): Arch {
  return 'mobilenetv2';
}

function toNumber(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function durationSeconds(start: string | null, end: string | null): number | null {
  if (!start || !end) return null;
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  if (!Number.isFinite(s) || !Number.isFinite(e) || e < s) return null;
  return Math.round((e - s) / 1000);
}

function normalizeRunStatus(status: string): RunStatus {
  switch (status) {
    case 'FINISHED':
      return 'finished';
    case 'RUNNING':
      return 'running';
    case 'FAILED':
    default:
      return 'failed';
  }
}

function toRun(dto: RunDto): TrainingRun {
  // `params`/`metrics` are index signatures (Record<…>), so read them with
  // bracket access (dot access fails TS4111).
  const params = dto.params ?? {};
  const metrics = dto.metrics ?? {};
  const accuracy = metrics['accuracy'];
  const loss = metrics['loss'];
  return {
    id: dto.run_id,
    name: dto.run_name ?? dto.run_id.slice(0, 8),
    arch: toArch(params['model_name']),
    datasetVersion: params['dataset_version'] ?? '',
    epochs: toNumber(params['epochs'], 0),
    batchSize: toNumber(params['batch_size'], 0),
    learningRate: toNumber(params['learning_rate'], 0),
    accuracy: accuracy != null ? Math.round(accuracy * 1000) / 10 : null,
    loss: loss != null ? Math.round(loss * 1000) / 1000 : null,
    status: normalizeRunStatus(dto.status),
    createdAt: dto.start_time ? new Date(dto.start_time) : new Date(),
    params,
    durationSeconds: durationSeconds(dto.start_time, dto.end_time),
  };
}

@Injectable({ providedIn: 'root' })
export class TrainingApi {
  private readonly http = inject(HttpClient);

  /** `GET /runs` — every run recorded in MLflow, newest first. */
  listRuns(): Observable<TrainingRun[]> {
    return this.http
      .get<{ runs: RunDto[] }>(`${TRAINING_BASE_URL}/runs`)
      .pipe(map((res) => (res.runs ?? []).map(toRun)));
  }

  /** `POST /train` — start a background training job, returns its `job_id`. */
  startTraining(cfg: TrainingConfig): Observable<{ jobId: string }> {
    return this.http
      .post<TrainStartDto>(`${TRAINING_BASE_URL}/train`, {
        dataset_version: cfg.datasetVersion,
        epochs: cfg.epochs,
        batch_size: cfg.batchSize,
        learning_rate: cfg.learningRate,
        image_size: cfg.imageSize,
        optimizer: cfg.optimizer,
        validation_split: cfg.validationSplit,
        weight_decay: cfg.weightDecay,
        lr_scheduler: cfg.lrScheduler,
        early_stopping: cfg.earlyStopping,
        pretrained: cfg.pretrained,
        seed: cfg.seed,
        augment_flip: cfg.flip,
        augment_rotation: cfg.rotation,
        augment_color_jitter: cfg.colorJitter,
        augment_crop: cfg.randomCrop,
      })
      .pipe(map((dto) => ({ jobId: dto.job_id })));
  }

  /** `GET /jobs/{job_id}` — status of one background training job. */
  getJob(jobId: string): Observable<TrainingJob> {
    return this.http.get<JobDto>(`${TRAINING_BASE_URL}/jobs/${jobId}`).pipe(
      map((dto) => ({
        jobId: dto.job_id,
        status: dto.status as TrainingJobStatus,
        runId: dto.run_id ?? null,
        error: dto.error ?? null,
        metrics: dto.metrics ?? null,
      })),
    );
  }
}

/* ------------------------------------------------------------------ */
/* Model Registry service (Step 3)                                     */
/* ------------------------------------------------------------------ */

/** Base URL of the Model Registry service (Step 3). See RegistryApi docs. */
const REGISTRY_BASE_URL = environment.registryUrl;

/** Wire shape of one model version from `GET /models` (snake_case). */
interface ModelDto {
  name: string;
  version: string;
  stage: string;
  run_id: string;
  dataset_version: string;
  size_mb: number;
  accuracy: number;
  loss: number;
}

const MODEL_STAGES: ModelStage[] = ['Pending', 'Staging', 'Production', 'Archived', 'Rejected'];

function normalizeModelStage(stage: string): ModelStage {
  return MODEL_STAGES.includes(stage as ModelStage) ? (stage as ModelStage) : 'Pending';
}

function toModel(dto: ModelDto): ModelVersion {
  return {
    name: dto.name,
    version: dto.version,
    stage: normalizeModelStage(dto.stage),
    runId: dto.run_id,
    datasetVersion: dto.dataset_version,
    sizeMb: dto.size_mb,
    accuracy: dto.accuracy,
    loss: dto.loss,
  };
}

@Injectable({ providedIn: 'root' })
export class RegistryApi {
  private readonly http = inject(HttpClient);

  /** `GET /models` — every registered version, enriched from its source run. */
  listModels(): Observable<ModelVersion[]> {
    return this.http
      .get<{ models: ModelDto[] }>(`${REGISTRY_BASE_URL}/models`)
      .pipe(map((res) => (res.models ?? []).map(toModel)));
  }

  /** `POST /models/{name}/{version}/stage` — move a version's stage. */
  setStage(name: string, version: string, stage: ModelStage): Observable<ModelVersion[]> {
    return this.http
      .post<{ models: ModelDto[] }>(
        `${REGISTRY_BASE_URL}/models/${encodeURIComponent(name)}/${encodeURIComponent(version)}/stage`,
        { stage },
      )
      .pipe(map((res) => (res.models ?? []).map(toModel)));
  }

  /** `POST /models/{name}/register` — backfill a finished run as a new version. */
  register(name: string, runId: string): Observable<ModelVersion[]> {
    return this.http
      .post<{ models: ModelDto[] }>(
        `${REGISTRY_BASE_URL}/models/${encodeURIComponent(name)}/register`,
        { run_id: runId },
      )
      .pipe(map((res) => (res.models ?? []).map(toModel)));
  }
}

/* ------------------------------------------------------------------ */
/* Prediction service (Step 4)                                         */
/* ------------------------------------------------------------------ */

/** Base URL of the Prediction service (Step 4). Serves the Production model. */
const PREDICTION_BASE_URL = environment.predictionUrl;

/** Wire shape of one prediction record (snake_case) — `POST /predict` and `GET /predictions`. */
interface PredictionDto {
  id: number;
  image_name: string;
  prediction: string;
  confidence: number;
  model_name: string;
  model_version: string;
  created_at: string;
}

function toPrediction(dto: PredictionDto): Prediction {
  return {
    id: String(dto.id),
    imageName: dto.image_name,
    result: dto.prediction === 'dog' ? ('dog' as const) : ('cat' as const),
    confidence: dto.confidence,
    modelVersion: `${dto.model_name} ${dto.model_version}`,
    createdAt: new Date(dto.created_at),
  };
}

@Injectable({ providedIn: 'root' })
export class PredictionApi {
  private readonly http = inject(HttpClient);

  /** `POST /predict` — upload an image; returns the stored Prediction (with DB id/createdAt). */
  predict(file: File): Observable<Prediction> {
    const form = new FormData();
    form.append('file', file);
    return this.http
      .post<PredictionDto>(`${PREDICTION_BASE_URL}/predict`, form)
      .pipe(map(toPrediction));
  }

  /** `GET /predictions` — prediction history, newest first. */
  listPredictions(): Observable<Prediction[]> {
    return this.http
      .get<{ predictions: PredictionDto[] }>(`${PREDICTION_BASE_URL}/predictions`)
      .pipe(map((res) => (res.predictions ?? []).map(toPrediction)));
  }

  /** `DELETE /predictions` — clear the history. */
  clearHistory(): Observable<void> {
    return this.http.delete(`${PREDICTION_BASE_URL}/predictions`).pipe(map(() => undefined));
  }
}