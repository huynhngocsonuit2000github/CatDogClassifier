export type DatasetStatus = 'validated' | 'validating' | 'failed' | 'invalid';
export type RunStatus = 'running' | 'finished' | 'failed';
export type ModelStage = 'Pending' | 'Staging' | 'Production' | 'Archived' | 'Rejected';
export type Arch = 'mobilenetv2' | 'resnet50' | 'efficientnetb0';

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