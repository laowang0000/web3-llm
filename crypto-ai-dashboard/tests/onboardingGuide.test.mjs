import assert from "node:assert/strict";
import {
  ONBOARDING_STORAGE_KEY,
  getInitialGuideOpen,
  onboardingSteps,
  rememberGuideDismissed,
} from "../src/onboardingGuide.js";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
  };
}

assert.equal(getInitialGuideOpen(createStorage()), true, "guide opens for first-time users");
assert.equal(
  getInitialGuideOpen(createStorage({ [ONBOARDING_STORAGE_KEY]: "true" })),
  false,
  "guide stays closed after dismissal",
);

const storage = createStorage();
rememberGuideDismissed(storage);
assert.equal(storage.getItem(ONBOARDING_STORAGE_KEY), "true", "dismissal is persisted");
assert.equal(onboardingSteps.length >= 5, true, "guide covers the main workflow");
assert.deepEqual(
  onboardingSteps.map((step) => step.targetEngine),
  ["insight", "models", "insight", "prediction", "insight"],
  "steps point users to the main interactive areas",
);
