export type DatasetStatus = 'validated' | 'validating' | 'failed' | 'invalid';
export type RunStatus = 'running' | 'finished' | 'failed';
export type ModelStage = 'Pending' | 'Staging' | 'Production' | 'Archived' | 'Rejected';
/** The only architecture the backend actually trains (see services/training/app/model.py). */
export type Arch = 'mobilenetv2';
export type Optimizer = 'adam' | 'adamw' | 'sgd';
export type LRScheduler = 'none' | 'step' | 'cosine' | 'reduce_on_plateau';

export interface DatasetVersion {
  version: string; // "v1"
  name: string;
  images: number;
  cats: number;
  dogs: number;
  status: DatasetStatus;
  createdAt: Date;
  warnings?: string[];
  dvcFile?: string; // repo-relative .dvc path, e.g. "datasets/v1.dvc"
}

export interface TrainingConfig {
  datasetVersion: string;
  epochs: number;
  batchSize: number;
  learningRate: number;
  imageSize: number;
  optimizer: Optimizer;
  validationSplit: number; // fraction, 0..1 (0.2 = 20%)
  weightDecay: number;
  lrScheduler: LRScheduler;
  earlyStopping: boolean;
  pretrained: boolean;
  seed: number;
  flip: boolean;
  rotation: boolean;
  colorJitter: boolean;
  randomCrop: boolean;
}

export interface TrainingRun {
  id: string; // "run-020"
  name: string;
  arch: Arch;
  datasetVersion: string;
  epochs: number;
  batchSize: number;
  learningRate: number;
  accuracy: number | null;
  loss: number | null;
  status: RunStatus;
  createdAt: Date;
  /** Raw MLflow params (snake_case keys, string values) for the detail view. */
  params: Record<string, string>;
  /** Wall-clock duration derived from MLflow start/end time, when available. */
  durationSeconds: number | null;
}

export interface GateCheck {
  key: string; // "train_accuracy" | "val_accuracy"
  label: string; // "Training accuracy"
  value: number | null; // percent; null when the run logged no such metric
  threshold: number; // percent floor it must clear
  passed: boolean;
}

export interface GateResult {
  qualified: boolean;
  checks: GateCheck[];
}

/** Promotion-gate floors (percent), editable from the Registry page. */
export interface GateSettings {
  trainAccuracyMin: number;
  valAccuracyMin: number;
}

export interface ModelVersion {
  name: string; // "CatDogClassifier" | "CatDogClassifier-lite"
  version: string; // "v3"
  stage: ModelStage;
  runId: string;
  datasetVersion: string;
  sizeMb: number;
  accuracy: number;
  loss: number;
  valAccuracy: number | null; // percent
  gate: GateResult;
}

export interface Prediction {
  id: string;
  imageName: string;
  result: 'cat' | 'dog';
  confidence: number; // 0..1
  modelVersion: string;
  createdAt: Date;
}

export interface ChartPoint {
  seq: number;
  accuracy: number;
}