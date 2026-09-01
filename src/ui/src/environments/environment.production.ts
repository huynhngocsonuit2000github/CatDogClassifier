/**
 * Container ("production") environment.
 *
 * When the whole platform runs under docker-compose, every API service is
 * published on the host at local-port + 100 so it doesn't collide with a
 * locally-running uvicorn instance (see src/docker-compose.yml):
 *
 *   data-management  8000 -> 8100
 *   training         8001 -> 8101
 *   model-registry   8002 -> 8102
 *   prediction       8003 -> 8103
 *
 * `ng build` runs with the production configuration and file-replaces
 * environment.ts with this file, so the image served from the UI container can
 * reach the containerized services from the browser.
 */
export const environment = {
  production: true,
  dataManagementUrl: 'http://127.0.0.1:8100',
  trainingUrl: 'http://127.0.0.1:8101',
  registryUrl: 'http://127.0.0.1:8102',
  predictionUrl: 'http://127.0.0.1:8103',
};