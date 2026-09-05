import { Component, computed, effect, inject, signal } from '@angular/core';
import type { OnInit } from '@angular/core';
import { AppStore } from '../../core/store';
import { Icon } from '../../core/icon';
import { LRScheduler, Optimizer, TrainingRun } from '../../core/models';
import { formatDuration, formatLong, formatShort } from '../../core/format';

interface DetailRow {
  label: string;
  value: string;
}

interface DetailGroup {
  title: string;
  rows: DetailRow[];
}

type BooleanKey =
  | 'pretrained'
  | 'earlyStopping'
  | 'flip'
  | 'rotation'
  | 'colorJitter'
  | 'randomCrop';

@Component({
  selector: 'app-training',
  imports: [Icon],
  templateUrl: './training.html',
})
export class TrainingPage implements OnInit {
  protected readonly store = inject(AppStore);

  protected readonly optimizers: Optimizer[] = ['adam', 'adamw', 'sgd'];
  protected readonly schedulers: LRScheduler[] = ['none', 'step', 'cosine', 'reduce_on_plateau'];

  // Model
  protected readonly pretrained = signal(true);
  protected readonly imageSize = signal(160);

  // Training
  protected readonly datasetVersion = signal('');
  protected readonly epochs = signal(15);
  protected readonly batchSize = signal(32);
  protected readonly learningRate = signal('0.0005');
  protected readonly optimizer = signal<Optimizer>('adam');
  protected readonly valSplitPct = signal(20);

  // Advanced
  protected readonly weightDecay = signal('0.0001');
  protected readonly lrScheduler = signal<LRScheduler>('cosine');
  protected readonly earlyStopping = signal(true);
  protected readonly seed = signal(42);

  // Data augmentation
  protected readonly flip = signal(true);
  protected readonly rotation = signal(true);
  protected readonly colorJitter = signal(true);
  protected readonly randomCrop = signal(true);

  protected readonly selected = signal<string[]>([]);
  protected readonly expandedRunId = signal<string | null>(null);

  /** Only validated versions have data pulled into the shared repo. */
  protected readonly trainableDatasets = computed(() =>
    this.store.datasets().filter((d) => d.status === 'validated'),
  );

  constructor() {
    // Keep the picker on a real, trainable version once the catalogue loads.
    effect(() => {
      const options = this.trainableDatasets();
      const current = this.datasetVersion();
      if (options.length === 0) return;
      if (!options.some((d) => d.version === current)) {
        this.datasetVersion.set(options[options.length - 1].version);
      }
    });
  }

  ngOnInit(): void {
    this.store.loadDatasets();
    this.store.loadRuns();
  }

  protected readonly selectedRuns = computed(() => {
    const ids = this.selected();
    return this.store.runs().filter((r) => ids.includes(r.id));
  });

  protected formatShort = formatShort;
  protected formatLong = formatLong;
  protected formatDuration = formatDuration;

  protected startTraining(): void {
    const lr = Number(this.learningRate());
    const wd = Number(this.weightDecay());
    const pct = Math.min(50, Math.max(5, Number(this.valSplitPct()) || 20));
    this.store.startTraining({
      datasetVersion: this.datasetVersion(),
      epochs: Math.max(1, this.epochs()),
      batchSize: Math.max(1, this.batchSize()),
      learningRate: Number.isFinite(lr) && lr > 0 ? lr : 0.0005,
      imageSize: Math.max(32, Math.min(512, this.imageSize())),
      optimizer: this.optimizer(),
      validationSplit: pct / 100,
      weightDecay: Number.isFinite(wd) && wd >= 0 ? wd : 0.0001,
      lrScheduler: this.lrScheduler(),
      earlyStopping: this.earlyStopping(),
      pretrained: this.pretrained(),
      seed: Math.max(0, this.seed()),
      flip: this.flip(),
      rotation: this.rotation(),
      colorJitter: this.colorJitter(),
      randomCrop: this.randomCrop(),
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

  protected toggleRun(id: string): void {
    this.expandedRunId.set(this.expandedRunId() === id ? null : id);
  }

  protected isExpanded(id: string): boolean {
    return this.expandedRunId() === id;
  }

  /** Grouped configuration for a run's expandable detail panel. */
  protected detailGroups(run: TrainingRun): DetailGroup[] {
    const p = run.params ?? {};
    const val = (key: string) => {
      const raw = p[key];
      return raw == null || raw === '' ? '—' : this.prettyParam(key, raw);
    };
    return [
      {
        title: 'Model',
        rows: [
          { label: 'Architecture', value: run.arch },
          { label: 'Pretrained', value: val('pretrained') },
          { label: 'Image size', value: val('image_size') },
        ],
      },
      {
        title: 'Training',
        rows: [
          { label: 'Dataset version', value: val('dataset_version') },
          { label: 'Epochs', value: val('epochs') },
          { label: 'Batch size', value: val('batch_size') },
          { label: 'Learning rate', value: val('learning_rate') },
          { label: 'Optimizer', value: val('optimizer') },
          { label: 'Loss function', value: val('loss_function') },
          { label: 'Validation split', value: val('validation_split') },
        ],
      },
      {
        title: 'Advanced',
        rows: [
          { label: 'Weight decay', value: val('weight_decay') },
          { label: 'LR scheduler', value: val('lr_scheduler') },
          { label: 'Early stopping', value: val('early_stopping') },
          { label: 'Random seed', value: val('seed') },
        ],
      },
      {
        title: 'Data augmentation',
        rows: [
          { label: 'Horizontal flip', value: val('augment_flip') },
          { label: 'Rotation', value: val('augment_rotation') },
          { label: 'Color jitter', value: val('augment_color_jitter') },
          { label: 'Random crop', value: val('augment_crop') },
        ],
      },
    ];
  }

  private prettyParam(key: string, value: string): string {
    const boolKeys = [
      'early_stopping',
      'pretrained',
      'augment_flip',
      'augment_rotation',
      'augment_color_jitter',
      'augment_crop',
    ];
    if (boolKeys.includes(key)) {
      const t = value.toLowerCase();
      if (t === 'true') return 'Enabled';
      if (t === 'false') return 'Disabled';
    }
    if (key === 'validation_split') {
      const n = Number(value);
      if (Number.isFinite(n)) return `${Math.round(n * 100)}%`;
    }
    return value;
  }

  protected onToggle(key: BooleanKey, e: Event): void {
    const checked = (e.target as HTMLInputElement).checked;
    const map = {
      pretrained: this.pretrained,
      earlyStopping: this.earlyStopping,
      flip: this.flip,
      rotation: this.rotation,
      colorJitter: this.colorJitter,
      randomCrop: this.randomCrop,
    };
    map[key].set(checked);
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

  protected onImageSize(e: Event): void {
    this.imageSize.set(Number((e.target as HTMLInputElement).value) || 0);
  }

  protected onOptimizer(e: Event): void {
    this.optimizer.set((e.target as HTMLSelectElement).value as Optimizer);
  }

  protected onValSplit(e: Event): void {
    this.valSplitPct.set(Number((e.target as HTMLInputElement).value) || 0);
  }

  protected onWeightDecay(e: Event): void {
    this.weightDecay.set((e.target as HTMLInputElement).value);
  }

  protected onScheduler(e: Event): void {
    this.lrScheduler.set((e.target as HTMLSelectElement).value as LRScheduler);
  }

  protected onSeed(e: Event): void {
    this.seed.set(Number((e.target as HTMLInputElement).value) || 0);
  }
}