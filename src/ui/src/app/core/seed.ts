import {
  Arch,
  ChartPoint,
  DatasetVersion,
  ModelVersion,
  Prediction,
  RunStatus,
  TrainingRun,
} from './models';

function dt(date: string): Date {
  return new Date(`${date}T14:00:00`);
}

export const SEED_DATASETS: DatasetVersion[] = [
  { version: 'v1', name: 'Initial Kaggle subset', images: 4000, cats: 2000, dogs: 2000, sizeMb: 412, status: 'validated', createdAt: dt('2026-04-30') },
  { version: 'v2', name: 'Added web-scraped images', images: 8000, cats: 4000, dogs: 4000, sizeMb: 830, status: 'validated', createdAt: dt('2026-05-24') },
  { version: 'v3', name: 'De-duplicated + relabeled', images: 12500, cats: 6250, dogs: 6250, sizeMb: 1290, status: 'validated', createdAt: dt('2026-06-19') },
  { version: 'v4', name: 'Augmentation pipeline v2', images: 20000, cats: 10000, dogs: 10000, sizeMb: 2140, status: 'validated', createdAt: dt('2026-07-14') },
  { version: 'v5', name: 'Hard-negative mining', images: 34000, cats: 17000, dogs: 17000, sizeMb: 3560, status: 'validated', createdAt: dt('2026-08-07') },
  { version: 'v6', name: 'Community contributions batch', images: 47500, cats: 23750, dogs: 23750, sizeMb: 4980, status: 'validating', createdAt: dt('2026-08-22') },
];

type RunSpec = [string, number, number, RunStatus, string];

const RUN_SPECS: RunSpec[] = [
  ['v5', 96.5, 0.211, 'finished', '2026-08-28'],
  ['v5', 96.3, 0.222, 'finished', '2026-08-25'],
  ['v5', 96.0, 0.233, 'failed', '2026-08-22'],
  ['v5', 96.1, 0.244, 'finished', '2026-08-19'],
  ['v4', 95.5, 0.255, 'finished', '2026-08-16'],
  ['v4', 94.7, 0.266, 'finished', '2026-08-13'],
  ['v4', 95.0, 0.277, 'finished', '2026-08-10'],
  ['v4', 95.1, 0.288, 'failed', '2026-08-07'],
  ['v4', 94.5, 0.299, 'finished', '2026-08-04'],
  ['v3', 94.2, 0.31, 'finished', '2026-08-01'],
  ['v3', 93.9, 0.321, 'finished', '2026-07-29'],
  ['v3', 94.0, 0.332, 'finished', '2026-07-26'],
  ['v3', 92.9, 0.343, 'finished', '2026-07-23'],
  ['v3', 93.2, 0.354, 'finished', '2026-07-20'],
  ['v2', 92.9, 0.365, 'finished', '2026-07-17'],
  ['v2', 93.0, 0.376, 'failed', '2026-07-14'],
  ['v2', 92.4, 0.387, 'finished', '2026-07-11'],
  ['v2', 92.1, 0.398, 'finished', '2026-07-08'],
  ['v2', 91.9, 0.409, 'finished', '2026-07-05'],
  ['v2', 91.4, 0.42, 'finished', '2026-07-02'],
];

const ARCHES: Arch[] = ['efficientnetb0', 'resnet50', 'mobilenetv2'];

function archOf(n: number): Arch {
  return ARCHES[((n % 3) + 3) % 3];
}

export const SEED_RUNS: TrainingRun[] = RUN_SPECS.map((spec, i) => {
  const n = 20 - i;
  const [datasetVersion, accuracy, loss, status, date] = spec;
  const arch = archOf(n);
  return {
    id: `run-${String(n).padStart(3, '0')}`,
    name: `catdog-${arch}-${n}`,
    arch,
    datasetVersion,
    epochs: 15,
    batchSize: 32,
    learningRate: 0.0005,
    accuracy,
    loss,
    status,
    createdAt: dt(date),
  };
});

export const SEED_MODELS: ModelVersion[] = [
  { name: 'CatDogClassifier', version: 'v1', stage: 'Archived', runId: 'run-003', datasetVersion: 'v2', sizeMb: 98, accuracy: 92.1, loss: 0.401 },
  { name: 'CatDogClassifier', version: 'v2', stage: 'Archived', runId: 'run-009', datasetVersion: 'v3', sizeMb: 98, accuracy: 94.0, loss: 0.288 },
  { name: 'CatDogClassifier', version: 'v3', stage: 'Production', runId: 'run-018', datasetVersion: 'v6', sizeMb: 102, accuracy: 96.4, loss: 0.182 },
  { name: 'CatDogClassifier', version: 'v4', stage: 'Staging', runId: 'run-019', datasetVersion: 'v5', sizeMb: 41, accuracy: 96.6, loss: 0.176 },
  { name: 'CatDogClassifier', version: 'v5', stage: 'Pending', runId: 'run-020', datasetVersion: 'v5', sizeMb: 102, accuracy: 96.5, loss: 0.179 },
  { name: 'CatDogClassifier-lite', version: 'v1', stage: 'Pending', runId: 'run-016', datasetVersion: 'v5', sizeMb: 22, accuracy: 94.8, loss: 0.244 },
];

export const SEED_PREDICTIONS: Prediction[] = [
  { id: 'pred-1', imageName: 'cat_4239.jpg', result: 'cat', confidence: 0.96, modelVersion: 'CatDogClassifier v3', createdAt: dt('2026-08-29') },
  { id: 'pred-2', imageName: 'dog_1187.jpg', result: 'dog', confidence: 0.97, modelVersion: 'CatDogClassifier v3', createdAt: dt('2026-08-29') },
  { id: 'pred-3', imageName: 'dog_0042.jpg', result: 'dog', confidence: 0.99, modelVersion: 'CatDogClassifier v3', createdAt: dt('2026-08-28') },
  { id: 'pred-4', imageName: 'cat_7701.jpg', result: 'cat', confidence: 0.93, modelVersion: 'CatDogClassifier v3', createdAt: dt('2026-08-28') },
];

export const SEED_CHART: ChartPoint[] = [
  90.1, 91.4, 91.9, 92.4, 92.9, 93.2, 93.9, 94.0, 94.2, 94.5, 94.7, 95.0, 95.1, 95.5, 96.0, 96.3, 96.5,
].map((accuracy, i) => ({ seq: i + 1, accuracy }));