import { Component, inject } from '@angular/core';
import type { OnInit } from '@angular/core';
import { AppStore } from '../../core/store';
import { ModelVersion } from '../../core/models';

@Component({
  selector: 'app-registry',
  templateUrl: './registry.html',
})
export class RegistryPage implements OnInit {
  protected readonly store = inject(AppStore);

  ngOnInit(): void {
    this.store.loadModels();
  }

  protected canApprove(m: ModelVersion): boolean {
    return m.stage === 'Pending';
  }

  protected canReject(m: ModelVersion): boolean {
    return m.stage === 'Pending' || m.stage === 'Staging';
  }

  protected canPromote(m: ModelVersion): boolean {
    return m.stage === 'Staging';
  }
}