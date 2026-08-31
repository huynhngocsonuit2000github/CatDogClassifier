/**
 * Switches the store between the real HTTP services and the seeded mock data.
 *
 * When `false` (the wiring target of Step 5), the store pulls datasets from the
 * Data Management service and training runs/launches from the Training service.
 * Set to `true` to run the UI with no backend up — every page falls back to
 * `core/seed.ts`.
 */
export const USE_MOCK = false;