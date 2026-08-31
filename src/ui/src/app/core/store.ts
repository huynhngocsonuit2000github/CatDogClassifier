import { Injectable, computed, inject, signal } from '@angular/core';
import {
  DatasetVersion,
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
import { DataApi, TrainingApi } from './api';
import { USE_MOCK } from './env';

@Injectable({ providedIn: 'root' })
export class AppStore {
  private readonly dataApi = inject(DataApi);
  private readonly trainingApi = inject(TrainingApi);

  readonly datasets = signal<DatasetVersion[]>(USE_MOCK ? SEED_DATASETS : []);
  readonly runs = signal<TrainingRun[]>(USE_MOCK ? SEED_RUNS : []);
  readonly models = signal<ModelVersion[]>(SEED_MODELS);
  readonly predictions = signal<Prediction[]>(SEED_PREDICTIONS);
  readonly chart = signal(SEED_CHART);

  /** True while a `POST /train` is in flight. */
  readonly starting = signal(false);
  /** Non-empty when the last runs fetch/launch failed (shown on the page). */
  readonly runsError = signal('');
  readonly runsLoading = signal(false);

  constructor() {
    if (!USE_MOCK) {
      this.loadDatasets();
      this.loadRuns();
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

  approve(name: string, version: string): void {
    this.updateStage(name, version, 'Staging');
  }

  reject(name: string, version: string): void {
    this.updateStage(name, version, 'Rejected');
  }

  promote(name: string, version: string): void {
    this.models.update((list) =>
      list.map((m) =>
        m.stage === 'Production' ? { ...m, stage: 'Archived' as const } : m,
      ),
    );
    this.updateStage(name, version, 'Production');
  }

  private updateStage(name: string, version: string, stage: ModelVersion['stage']): void {
    this.models.update((list) =>
      list.map((m) => (m.name === name && m.version === version ? { ...m, stage } : m)),
    );
  }

  predict(imageName: string): Prediction {
    const prod = this.production();
    const modelVersion = prod ? `${prod.name} ${prod.version}` : 'CatDogClassifier v3';

    let h = 0;
    for (let i = 0; i < imageName.length; i++) {
      h = (h * 31 + imageName.charCodeAt(i)) >>> 0;
    }
    const result = h % 2 === 0 ? 'cat' : 'dog';
    const confidence = (88 + (h % 11)) / 100;

    const prediction: Prediction = {
      id: `pred-${Date.now()}`,
      imageName,
      result,
      confidence,
      modelVersion,
      createdAt: new Date(),
    };

    this.predictions.update((list) => [prediction, ...list]);
    return prediction;
  }

  /** Extract FastAPI's `{detail: ...}` or fall back to a generic message. */
  private detailOf(err: unknown): string {
    const e = err as { error?: { detail?: string }; message?: string };
    return e?.error?.detail ?? e?.message ?? 'Request failed';
  }
}