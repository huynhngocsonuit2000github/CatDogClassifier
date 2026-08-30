import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { Icon } from '../../core/icon';
import { DatasetVersion } from '../../core/models';
import { DataApi } from '../../core/api';
import { formatShort } from '../../core/format';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

@Component({
  selector: 'app-data',
  imports: [Icon],
  templateUrl: './data.html',
})
export class DataPage implements OnInit, OnDestroy {
  private readonly api = inject(DataApi);

  protected readonly datasets = signal<DatasetVersion[]>([]);
  protected readonly loading = signal(true);
  protected readonly note = signal('');
  protected readonly file = signal<File | null>(null);
  protected readonly dragging = signal(false);
  protected readonly error = signal('');

  protected formatShort = formatShort;
  protected formatBytes = formatBytes;

  private poll: ReturnType<typeof setInterval> | undefined;

  ngOnInit(): void {
    this.refresh();
    // The backend finalizes (DVC push → MinIO) in the background, so poll
    // while anything is still `validating` to pick up `validated`/`failed`.
    this.poll = setInterval(() => {
      if (this.datasets().some((d) => d.status === 'validating')) {
        this.refresh();
      }
    }, 2000);
  }

  ngOnDestroy(): void {
    if (this.poll) clearInterval(this.poll);
  }

  protected catPercent(d: DatasetVersion): number {
    return d.images > 0 ? Math.round((d.cats / d.images) * 100) : 0;
  }

  protected refresh(): void {
    this.api.list().subscribe({
      next: (list) => {
        this.datasets.set(list);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.detailOf(err));
        this.loading.set(false);
      },
    });
  }

  protected onNoteInput(e: Event): void {
    this.note.set((e.target as HTMLInputElement).value);
  }

  protected onFileInput(e: Event): void {
    const input = e.target as HTMLInputElement;
    this.setFile(input.files?.length ? input.files[0] : null);
  }

  protected onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.dragging.set(true);
  }

  protected onDragLeave(): void {
    this.dragging.set(false);
  }

  protected onDrop(e: DragEvent): void {
    e.preventDefault();
    this.dragging.set(false);
    this.setFile(e.dataTransfer?.files?.length ? e.dataTransfer.files[0] : null);
  }

  protected upload(): void {
    const f = this.file();
    if (!f) {
      this.error.set('Choose a .zip file of labelled images first.');
      return;
    }
    this.error.set('');
    this.api.upload(f, this.note()).subscribe({
      next: (created) => {
        this.datasets.update((list) => [created, ...list.filter((d) => d.version !== created.version)]);
        this.file.set(null);
        this.note.set('');
        this.refresh();
      },
      error: (err) => this.error.set(this.detailOf(err)),
    });
  }

  private setFile(f: File | null): void {
    this.error.set('');
    this.file.set(f);
  }

  /** Extract FastAPI's `{detail: ...}` or fall back to a generic message. */
  private detailOf(err: unknown): string {
    const e = err as { error?: { detail?: string }; message?: string };
    return e?.error?.detail ?? e?.message ?? 'Request failed';
  }
}