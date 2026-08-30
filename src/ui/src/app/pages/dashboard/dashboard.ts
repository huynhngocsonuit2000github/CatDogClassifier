import { Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AppStore } from '../../core/store';
import { Icon } from '../../core/icon';
import { formatLong } from '../../core/format';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, Icon],
  templateUrl: './dashboard.html',
})
export class DashboardPage {
  protected readonly store = inject(AppStore);

  protected readonly kpis = computed(() => {
    const prod = this.store.production();
    return [
      { label: 'Models registered', value: String(this.store.models().length), hint: '+2 this month', icon: 'package' },
      { label: 'Production version', value: prod ? `${prod.version} · ${prod.accuracy}%` : '—', hint: '+2.4 pts vs v2', icon: 'rocket' },
      { label: 'Training runs', value: String(this.store.runs().length), hint: '+5 last 7 days', icon: 'flask' },
      { label: 'Datasets', value: String(this.store.datasets().length), hint: `${this.store.totalImages().toLocaleString('en-US')} images`, icon: 'database' },
    ];
  });

  protected readonly recentRuns = computed(() => this.store.runs().slice(0, 5));

  private readonly geo = { w: 640, h: 240, l: 30, r: 12, t: 12, b: 24, yMin: 88, yMax: 99 };

  protected readonly render = computed(() => {
    const pts = this.store.chart();
    const { w, h, l, r, t, b, yMin, yMax } = this.geo;
    const iw = w - l - r;
    const ih = h - t - b;
    const n = pts.length;
    const xy = pts.map((p, i) => ({
      x: l + (n === 1 ? 0 : (i * iw) / (n - 1)),
      y: t + (1 - (p.accuracy - yMin) / (yMax - yMin)) * ih,
    }));
    const line = xy.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const area = `${line} ${xy[n - 1].x.toFixed(1)},${h - b} ${xy[0].x.toFixed(1)},${h - b}`;
    const ticks = [90, 92, 94, 96, 98].map((value) => ({
      value,
      y: t + (1 - (value - yMin) / (yMax - yMin)) * ih,
    }));
    const xticks = pts
      .map((p, i) => ({ label: `#${p.seq}`, x: xy[i].x }))
      .filter((_, i) => i % 4 === 0 || i === n - 1);
    return { line, area, ticks, xticks };
  });

  protected formatLong = formatLong;

  protected badgeClass(status: string): string {
    return status === 'finished' ? 'success' : status === 'failed' ? 'danger' : 'info';
  }
}