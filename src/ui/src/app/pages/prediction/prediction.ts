import { Component, computed, inject, signal } from '@angular/core';
import { AppStore } from '../../core/store';
import { Icon } from '../../core/icon';
import { Prediction } from '../../core/models';
import { formatLong } from '../../core/format';

@Component({
  selector: 'app-prediction',
  imports: [Icon],
  templateUrl: './prediction.html',
})
export class PredictionPage {
  protected readonly store = inject(AppStore);

  protected readonly fileName = signal<string | null>(null);
  protected readonly previewUrl = signal<string | null>(null);
  protected readonly result = signal<Prediction | null>(null);
  protected readonly dragging = signal(false);

  protected readonly serving = computed(() => {
    const p = this.store.production();
    return p ? `${p.name} ${p.version} (${p.stage})` : '—';
  });

  protected formatLong = formatLong;

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
    const file = e.dataTransfer?.files?.[0];
    if (file) this.loadFile(file);
  }

  protected onFileInput(e: Event): void {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.loadFile(file);
  }

  protected predict(): void {
    const name = this.fileName();
    if (!name) return;
    this.result.set(this.store.predict(name));
  }

  private loadFile(file: File): void {
    this.fileName.set(file.name);
    this.result.set(null);
    if (this.previewUrl()) {
      URL.revokeObjectURL(this.previewUrl() as string);
    }
    this.previewUrl.set(URL.createObjectURL(file));
  }
}