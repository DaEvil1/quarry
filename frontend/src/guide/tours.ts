// The Guide's walkthroughs (docs/SPEC.md §15.6), in the order the Guide page lists them: the order a writer meets
// the features. Each is a few minutes on the sandbox copy of the demo world (backend/src/quarry/demo.py) and leans on
// the data-testids the e2e tests use, so the e2e run that plays every walkthrough (e2e/guide.spec.ts) catches one that
// has gone stale.

import type { Tour } from "./engine";
import { backIn } from "./walkthroughs/back-in";
import { bible } from "./walkthroughs/bible";
import { capture } from "./walkthroughs/capture";
import { chart } from "./walkthroughs/chart";
import { companion } from "./walkthroughs/companion";
import { experiments } from "./walkthroughs/experiments";
import { facts } from "./walkthroughs/facts";
import { journal } from "./walkthroughs/journal";
import { names } from "./walkthroughs/names";
import { revising } from "./walkthroughs/revising";
import { safe } from "./walkthroughs/safe";
import { species } from "./walkthroughs/species";
import { timeline } from "./walkthroughs/timeline";

export const TOURS: Tour[] = [
  backIn,
  capture,
  companion,
  bible,
  facts,
  species,
  timeline,
  revising,
  experiments,
  journal,
  chart,
  names,
  safe,
];
