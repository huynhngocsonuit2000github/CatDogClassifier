import { Component, computed, inject, signal } from '@angular/core';
import { AppStore } from '../../core/store';
import { Arch } from '../../core/models';
import { formatShort } from '../../core/format';

@Component({
  selector: 'app-training',
  templateUrl: './training.html',
})
export class TrainingPage {
  protected readonly store = inject(AppStore);

  protected readonly arches: Arch[] = ['mobilenetv2', 'resnet50', 'efficientnetb0'];

  protected readonly arch = signal<Arch>('resnet50');
  protected readonly datasetVersion = signal<string>(
    this.store.datasets()[this.store.datasets().length - 1].version,
  );
  protected readonly epochs = signal(15);
  protected readonly batchSize = signal(32);
  protected readonly learningRate = signal('0.0005');

  protected readonly selected = signal<string[]>([]);

  protected readonly selectedRuns = computed(() => {
    const ids = this.selected();
    return this.store.runs().filter((r) => ids.includes(r.id));
  });

  protected formatShort = formatShort;

  protected startTraining(): void {
    const lr = Number(this.learningRate());
    this.store.startTraining({
      arch: this.arch(),
      datasetVersion: this.datasetVersion(),
      epochs: Math.max(1, this.epochs()),
      batchSize: Math.max(1, this.batchSize()),
      learningRate: Number.isFinite(lr) && lr > 0 ? lr : 0.0005,
    });
  }

  protected toggleSelect(id: string): void {
    const cur = this.selected();
    if (cur.includes(id)) {
      this.selected.set(cur.filter((x) => x !== id));
    } else if (cur.length < 3) {
      this.selected.set([...cur, id]);
    }
  }

  protected isDisabled(id: string): boolean {
    return this.selected().length >= 3 && !this.selected().includes(id);
  }

  protected onArchInput(e: Event): void {
    this.arch.set((e.target as HTMLSelectElement).value as Arch);
  }

  protected onDatasetInput(e: Event): void {
    this.datasetVersion.set((e.target as HTMLSelectElement).value);
  }

  protected onEpochs(e: Event): void {
    this.epochs.set(Number((e.target as HTMLInputElement).value) || 0);
  }

  protected onBatch(e: Event): void {
    this.batchSize.set(Number((e.target as HTMLInputElement).value) || 0);
  }

  protected onLr(e: Event): void {
    this.learningRate.set((e.target as HTMLInputElement).value);
  }
}