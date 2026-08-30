import { Routes } from '@angular/router';
import { DashboardPage } from './pages/dashboard/dashboard';
import { DataPage } from './pages/data/data';
import { TrainingPage } from './pages/training/training';
import { RegistryPage } from './pages/registry/registry';
import { PredictionPage } from './pages/prediction/prediction';
import { NotFoundPage } from './pages/not-found/not-found';

export const routes: Routes = [
  { path: '', component: DashboardPage, data: { title: 'Dashboard' } },
  { path: 'data', component: DataPage, data: { title: 'Data Management' } },
  { path: 'training', component: TrainingPage, data: { title: 'Training' } },
  { path: 'registry', component: RegistryPage, data: { title: 'Model Registry' } },
  { path: 'prediction', component: PredictionPage, data: { title: 'Prediction' } },
  { path: '**', component: NotFoundPage, data: { title: 'Not found' } },
];