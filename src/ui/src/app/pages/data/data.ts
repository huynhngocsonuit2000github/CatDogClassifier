import { Component, inject, signal } from '@angular/core';
import { AppStore } from '../../core/store';
import { Icon } from '../../core/icon';
import { DatasetVersion } from '../../core/models';
import { formatShort } from '../../core/format';

@Component({
  selector: 'app-data',
  imports: [Icon],
  templateUrl: './data.html',
})
export class DataPage {
  protected readonly store = inject(AppStore);

  protected readonly note = signal('');
  protected readonly imageCount = signal(5000);

  protected formatShort = formatShort;

  protected catPercent(d: DatasetVersion): number {
    return Math.round((d.cats / d.images) * 100);
  }

  protected upload(): void {
    const count = this.imageCount();
    this.store.uploadDataset(this.note(), count > 0 ? count : 5000);
    this.note.set('');
  }

  protected onNoteInput(e: Event): void {
    this.note.set((e.target as HTMLInputElement).value);
  }

  protected onCountInput(e: Event): void {
    const v = Number((e.target as HTMLInputElement).value);
    this.imageCount.set(Number.isFinite(v) && v > 0 ? Math.round(v) : 0);
  }
}