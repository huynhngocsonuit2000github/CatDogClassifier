import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { DatasetStatus, DatasetVersion } from './models';

/**
 * Base URL of the Data Management service (Step 1). The backend sets
 * `Access-Control-Allow-Origin: *`, so the browser can call it directly
 * without a dev-server proxy. Point this at the host/port where uvicorn
 * (local) or the `data-management` container (docker) is exposed.
 */
const BASE_URL = 'http://127.0.0.1:8000';

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