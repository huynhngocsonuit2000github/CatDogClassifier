import { Component, effect, inject, signal } from '@angular/core';
import type { OnInit } from '@angular/core';
import { AppStore } from '../../core/store';
import { ModelVersion } from '../../core/models';

@Component({
  selector: 'app-registry',
  templateUrl: './registry.html',
})
export class RegistryPage implements OnInit {
  protected readonly store = inject(AppStore);

  protected readonly trainMinPct = signal(93);
  protected readonly valMinPct = signal(90);

  constructor() {
    // Reflect the service's current thresholds into the editable fields.
    effect(() => {
      const s = this.store.gateSettings();
      this.trainMinPct.set(s.trainAccuracyMin);
      this.valMinPct.set(s.valAccuracyMin);
    });
  }

  ngOnInit(): void {
    this.store.loadModels();
    this.store.loadGateSettings();
  }

  protected saveSettings(): void {
    this.store.saveGateSettings({
      trainAccuracyMin: this.trainMinPct(),
      valAccuracyMin: this.valMinPct(),
    });
  }

  protected onTrainMin(e: Event): void {
    const n = Number((e.target as HTMLInputElement).value);
    this.trainMinPct.set(Number.isFinite(n) ? n : 0);
  }

  protected onValMin(e: Event): void {
    const n = Number((e.target as HTMLInputElement).value);
    this.valMinPct.set(Number.isFinite(n) ? n : 0);
  }

  protected canApprove(m: ModelVersion): boolean {
    return m.stage === 'Pending' && m.gate.qualified;
  }

  protected canReject(m: ModelVersion): boolean {
    return m.stage === 'Pending' || m.stage === 'Staging';
  }

  protected canPromote(m: ModelVersion): boolean {
    // One-click promote: any qualified model (Pending / Staging / Archived /
    // Rejected) can be promoted directly; the server re-runs the hard gate.
    return m.gate.qualified && m.stage !== 'Production';
  }
}