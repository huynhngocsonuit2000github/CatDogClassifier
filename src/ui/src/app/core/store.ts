import { Injectable, computed, signal } from '@angular/core';
import { Arch, DatasetVersion, ModelVersion, Prediction, TrainingRun } from './models';
import { SEED_CHART, SEED_DATASETS, SEED_MODELS, SEED_PREDICTIONS, SEED_RUNS } from './seed';

export interface TrainingConfig {
  arch: Arch;
  datasetVersion: string;
  epochs: number;
  batchSize: number;
  learningRate: number;
}

@Injectable({ providedIn: 'root' })
export class AppStore {
  readonly datasets = signal<DatasetVersion[]>(SEED_DATASETS);
  readonly runs = signal<TrainingRun[]>(SEED_RUNS);
  readonly models = signal<ModelVersion[]>(SEED_MODELS);
  readonly predictions = signal<Prediction[]>(SEED_PREDICTIONS);
  readonly chart = signal(SEED_CHART);

  readonly production = computed(() => this.models().find((m) => m.stage === 'Production'));
  readonly totalImages = computed(() => this.datasets().reduce((sum, d) => sum + d.images, 0));

  uploadDataset(note: string, imageCount: number): void {
    const version = `v${this.datasets().length + 1}`;
    const name = note.trim() || `Dataset ${version}`;
    const cats = Math.round(imageCount / 2);
    const dogs = imageCount - cats;

    const record: DatasetVersion = {
      version,
      name,
      images: imageCount,
      cats,
      dogs,
      sizeMb: Math.round(imageCount * 0.1),
      status: 'validating',
      createdAt: new Date(),
    };

    this.datasets.update((list) => [...list, record]);

    setTimeout(() => {
      this.datasets.update((list) =>
        list.map((d) => (d.version === version ? { ...d, status: 'validated' as const } : d)),
      );
    }, 1800);
  }

  startTraining(cfg: TrainingConfig): void {
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
}