/**
 * Default (local dev) environment.
 *
 * These are the ports the four API services are exposed on when you run them
 * directly with uvicorn (see notes/app/run-app-local.md). `ng serve` picks this
 * file up, so local dev keeps talking to the local services without any change.
 */
export const environment = {
  production: false,
  dataManagementUrl: 'http://127.0.0.1:8000',
  trainingUrl: 'http://127.0.0.1:8001',
  registryUrl: 'http://127.0.0.1:8002',
  predictionUrl: 'http://127.0.0.1:8003',
};