import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AppStore } from './core/store';
import { ThemeService } from './core/theme';
import { Icon } from './core/icon';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly store = inject(AppStore);
  protected readonly theme = inject(ThemeService);
  private readonly router = inject(Router);

  protected readonly sidebarOpen = signal(true);
  protected readonly pageTitle = signal('Dashboard');

  protected readonly nav = [
    { path: '/', icon: 'dashboard', label: 'Dashboard' },
    { path: '/data', icon: 'database', label: 'Data Management' },
    { path: '/training', icon: 'flask', label: 'Training' },
    { path: '/registry', icon: 'package', label: 'Model Registry' },
    { path: '/prediction', icon: 'image', label: 'Prediction' },
  ];

  constructor() {
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => {
      let route = this.router.routerState.root;
      while (route.firstChild) {
        route = route.firstChild;
      }
      this.pageTitle.set(route.snapshot.data?.['title'] ?? 'Dashboard');
    });
  }

  protected toggleTheme(): void {
    this.theme.toggle();
  }

  protected toggleSidebar(): void {
    this.sidebarOpen.update((v) => !v);
  }
}