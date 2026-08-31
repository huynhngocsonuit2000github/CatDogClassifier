import { Injectable, computed, inject, signal } from '@angular/core';
import { EMPTY, Observable, catchError, map, of, tap } from 'rxjs';
import {
  DatasetVersion,
  ModelStage,
  ModelVersion,
  Prediction,
  TrainingConfig,
  TrainingRun,
} from './models';
import {
  SEED_CHART,
  SEED_DATASETS,
  SEED_MODELS,
  SEED_PREDICTIONS,
  SEED_RUNS,
} from './seed';
import { DataApi, PredictionApi, RegistryApi, TrainingApi } from './api';
import { USE_MOCK } from './env';

/** localStorage key for prediction history — survives page reloads. */
const PREDICTIONS_KEY = 'catdog.predictions';

@Injectable({ providedIn: 'root' })
export class AppStore {
  private readonly dataApi = inject(DataApi);
  private readonly trainingApi = inject(TrainingApi);
  private readonly registryApi = inject(RegistryApi);
  private readonly predictionApi = inject(PredictionApi);

  readonly datasets = signal<DatasetVersion[]>(USE_MOCK ? SEED_DATASETS : []);
  readonly runs = signal<TrainingRun[]>(USE_MOCK ? SEED_RUNS : []);
  readonly models = signal<ModelVersion[]>(USE_MOCK ? SEED_MODELS : []);
  readonly predictions = signal<Prediction[]>(USE_MOCK ? SEED_PREDICTIONS : []);
  readonly chart = signal(SEED_CHART);

  /** True while a `POST /train` is in flight. */
  readonly starting = signal(false);
  /** Non-empty when the last runs fetch/launch failed (shown on the page). */
  readonly runsError = signal('');
  readonly runsLoading = signal(false);
  /** Non-empty when the last models fetch/stage change failed (Registry page). */
  readonly modelsError = signal('');
  /** Non-empty when the last `POST /predict` failed (Predict page). */
  readonly predictionError = signal('');
  /** True while a `POST /predict` is in flight. */
  readonly predicting = signal(false);

  constructor() {
    if (!USE_MOCK) {
      this.predictions.set(this.loadPredictions());
      this.loadDatasets();
      this.loadRuns();
      this.loadModels();
    }
  }

  readonly production = computed(() => this.models().find((m) => m.stage === 'Production'));
  readonly totalImages = computed(() => this.datasets().reduce((sum, d) => sum + d.images, 0));

  loadDatasets(): void {
    if (USE_MOCK) {
      this.datasets.set(SEED_DATASETS);
      return;
    }
    this.dataApi.list().subscribe({
      next: (list) => this.datasets.set(list),
      error: () => {
        // Keep whatever we have; the Data page surfaces its own error.
      },
    });
  }

  loadRuns(): void {
    if (USE_MOCK) {
      this.runs.set(SEED_RUNS);
      return;
    }
    this.runsLoading.set(true);
    this.trainingApi.listRuns().subscribe({
      next: (list) => {
        this.runs.set(list);
        this.runsLoading.set(false);
        this.runsError.set('');
      },
      error: (err) => {
        this.runsError.set(this.detailOf(err));
        this.runsLoading.set(false);
      },
    });
  }

  startTraining(cfg: TrainingConfig): void {
    if (USE_MOCK) {
      this.startTrainingMock(cfg);
      return;
    }
    this.runsError.set('');
    this.starting.set(true);
    this.trainingApi.startTraining(cfg).subscribe({
      next: ({ jobId }) => {
        this.starting.set(false);
        const pending: TrainingRun = {
          id: `job-${jobId}`,
          name: `${cfg.datasetVersion}-${cfg.arch}`,
          arch: cfg.arch,
          datasetVersion: cfg.datasetVersion,
          epochs: cfg.epochs,
          batchSize: cfg.batchSize,
          learningRate: cfg.learningRate,
          accuracy: null,
          loss: null,
          status: 'running',
          createdAt: new Date(),
        };
        this.runs.update((list) => [pending, ...list]);
        this.trackJob(jobId, pending.id);
      },
      error: (err) => {
        this.starting.set(false);
        this.runsError.set(this.detailOf(err));
      },
    });
  }

  /** Poll the job until it settles, then reflect the result in `runs`. */
  private trackJob(jobId: string, pendingId: string): void {
    const timer = setInterval(() => {
      this.trainingApi.getJob(jobId).subscribe({
        next: (job) => {
          if (job.status !== 'finished' && job.status !== 'failed') {
            return;
          }
          clearInterval(timer);
          if (job.status === 'finished') {
            // The MLflow run is recorded by now; reload the authoritative list.
            this.loadRuns();
          } else {
            this.runs.update((list) =>
              list.map((r) =>
                r.id === pendingId ? { ...r, status: 'failed' as const } : r,
              ),
            );
            this.runsError.set(job.error ?? 'Training failed');
          }
        },
        error: () => {
          // Transient poll failure — keep polling.
        },
      });
    }, 3000);
  }

  private startTrainingMock(cfg: TrainingConfig): void {
    const n = this.runs().length + 1;
    const id = `run-${String(n).padStart(3, '0')}`;

    const run: TrainingRun = {
      id,
      name: `catdog-${cfg.arch}-${n}`,
      arch: cfg.arch,
      datasetVersion: cfg.datasetVersion,
      epochs: cfg.epochs,
      batchSize: cfg.batchSize,
      learningRate: cfg.learningRate,
      accuracy: null,
      loss: null,
      status: 'running',
      createdAt: new Date(),
    };

    this.runs.update((list) => [run, ...list]);

    setTimeout(() => {
      const accuracy = Math.round((96.0 + Math.random() * 0.9) * 10) / 10;
      const loss = Math.round((0.18 + Math.random() * 0.06) * 1000) / 1000;
      this.runs.update((list) =>
        list.map((r) =>
          r.id === id ? { ...r, accuracy, loss, status: 'finished' as const } : r,
        ),
      );
    }, 2400);
  }

  /** Promote a version to Production — it auto-archives the current winner. */
  promote(name: string, version: string): void {
    this.setStage(name, version, 'Production');
  }

  /** Load registered models from the Registry service (Step 3). */
  loadModels(): void {
    if (USE_MOCK) {
      this.models.set(SEED_MODELS);
      return;
    }
    this.modelsError.set('');
    this.registryApi.listModels().subscribe({
      next: (list) => {
        this.models.set(list);
        this.modelsError.set('');
      },
      error: (err) => this.modelsError.set(this.detailOf(err)),
    });
  }

  /** Move a version via the Registry API (or the local mock, offline). */
  private setStage(name: string, version: string, stage: ModelStage): void {
    if (USE_MOCK) {
      this.setStageMock(name, version, stage);
      return;
    }
    this.modelsError.set('');
    this.registryApi.setStage(name, version, stage).subscribe({
      next: (list) => {
        this.models.set(list);
        this.modelsError.set('');
      },
      error: (err) => this.modelsError.set(this.detailOf(err)),
    });
  }

  /** Local (mock) stage transition; mirrors the Registry service's rules. */
  private setStageMock(name: string, version: string, stage: ModelStage): void {
    if (stage === 'Production') {
      this.models.update((list) =>
        list.map((m) =>
          m.stage === 'Production' ? { ...m, stage: 'Archived' as const } : m,
        ),
      );
    }
    this.updateStage(name, version, stage);
  }

  private updateStage(name: string, version: string, stage: ModelStage): void {
    this.models.update((list) =>
      list.map((m) => (m.name === name && m.version === version ? { ...m, stage } : m)),
    );
  }

  /** Prepend a prediction to the history and persist it across page reloads. */
  private recordPrediction(prediction: Prediction): void {
    this.predictions.update((list) => [prediction, ...list]);
    this.persistPredictions();
  }

  private loadPredictions(): Prediction[] {
    try {
      const raw = localStorage.getItem(PREDICTIONS_KEY);
      if (!raw) return [];
      const parsed: unknown = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.map((p) => ({ ...p, createdAt: new Date(p.createdAt) }));
    } catch {
      return [];
    }
  }

  private persistPredictions(): void {
    try {
      localStorage.setItem(PREDICTIONS_KEY, JSON.stringify(this.predictions()));
    } catch {
      // Storage unavailable (e.g. private mode) — history just won't persist.
    }
  }

  predict(file: File): Observable<Prediction> {
    if (USE_MOCK) {
      const prediction = this.predictMock(file.name);
      this.recordPrediction(prediction);
      return of(prediction);
    }
    this.predictionError.set('');
    this.predicting.set(true);
    const imageName = file.name;
    return this.predictionApi.predict(file).pipe(
      map(
        ({ result, confidence, modelVersion }) =>
          ({
            id: `pred-${Date.now()}`,
            imageName,
            result,
            confidence,
            modelVersion,
            createdAt: new Date(),
          }) satisfies Prediction,
      ),
      tap({
        next: (prediction) => {
          this.predicting.set(false);
          this.recordPrediction(prediction);
        },
        error: () => this.predicting.set(false),
      }),
      catchError((err) => {
        this.predictionError.set(this.detailOf(err));
        return EMPTY;
      }),
    );
  }

  /** Local (mock) prediction; hashes the filename — mirrors the real cat/dog split. */
  private predictMock(imageName: string): Prediction {
    const prod = this.production();
    const modelVersion = prod ? `${prod.name} ${prod.version}` : 'CatDogClassifier v3';

    let h = 0;
    for (let i = 0; i < imageName.length; i++) {
      h = (h * 31 + imageName.charCodeAt(i)) >>> 0;
    }
    const result = h % 2 === 0 ? 'cat' : 'dog';
    const confidence = (88 + (h % 11)) / 100;

    return {
      id: `pred-${Date.now()}`,
      imageName,
      result,
      confidence,
      modelVersion,
      createdAt: new Date(),
    };
  }

  /** Extract FastAPI's `{detail: ...}` or fall back to a generic message. */
  private detailOf(err: unknown): string {
    const e = err as { error?: { detail?: string }; message?: string };
    return e?.error?.detail ?? e?.message ?? 'Request failed';
  }
}