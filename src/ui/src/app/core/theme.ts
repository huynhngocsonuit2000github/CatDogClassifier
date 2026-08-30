import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'catdog-theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly theme = signal<'light' | 'dark'>('light');

  constructor() {
    const saved = localStorage.getItem(STORAGE_KEY);
    const initial: 'light' | 'dark' = saved === 'dark' ? 'dark' : 'light';
    this.theme.set(initial);
    this.apply(initial);
  }

  toggle(): void {
    const next = this.theme() === 'dark' ? 'light' : 'dark';
    this.theme.set(next);
    this.apply(next);
  }

  private apply(theme: 'light' | 'dark'): void {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }
}