// One of the Guide's walkthroughs (docs/SPEC.md §15). See ../engine.ts for what a step can say and do.

import type { Step, Tour } from "../engine";
import { tid } from "./common";

/** a place on the chart, by its name (an SVG group: pointed at or rested on, never clicked) */
const place = (name: string, extra = "") => `[data-testid="chart-place"]${extra}[data-name="${name}"]`;

const steps: Step[] = [
  {
    go: "/w/{w}/chart",
    target: { css: tid("chart") },
    say: "The chart draws the places in the bible as they relate: what holds what, what borders what, the roads between. Nothing on it is drawn by hand.",
  },
  {
    target: { css: place("The Ninefold Delta") },
    say: "The Ninefold Delta's type is land, so it is a hexagon. The places recorded inside it are drawn inside it: Carrow Ferry, Greywater, Marrow Locks.",
  },
  {
    target: { css: place("The Outer Sound") },
    say: "The Outer Sound is a sea, drawn as water around the Salt Flats, an island at high tide. The delta borders it, so the two touch.",
  },
  {
    target: { css: tid("chart-shapes") },
    say: "Every shape comes from the place's type: a town or a fort is a circle, a building a square. Shapes… gives a type of the world's own a shape.",
  },
  {
    target: { css: place("Greywater", ".pinned") },
    say: "Greywater and Marrow Locks are pinned: dragged by hand to the north and south of the delta. A pin is kept inside its container, and stays put when the rest is laid out again.",
  },
  {
    target: { css: place("Carrow Ferry") },
    say: "Carrow Ferry isn't pinned, so it is laid out for you, between them, as the bible says it is north of Marrow Locks and south of Greywater. Reset layout unpins everything, with Undo.",
  },
  {
    target: { css: tid("chart-road") },
    say: "A road is a solid line: the dyke road from Greywater to Carrow Ferry.",
  },
  {
    target: { css: tid("chart-sea") },
    say: "A sea route is dashed: the ferry runs out to the Salt Flats at low tide.",
  },
  {
    target: { css: tid("chart-legend") },
    say: "A shade is who controls a place, from the bible's controls relationships. The River Wardens hold Marrow Locks; the legend gives each faction its colour.",
  },
  {
    target: { css: place("Marrow Locks") },
    act: { hover: true },
    wait: { css: tid("name-card"), text: "Marrow Locks" },
    say: "Rest on a place for its card, the same card as in the editor. A click would open its page.",
  },
  {
    target: { css: tid("chart-as-of") },
    act: { choose: "The Crossing" },
    wait: { css: `${place("Carrow Ferry")} [data-who="Tamsin Vey"]` },
    say: "As of reads the chart at a chapter or a time: who controls what, and who is where. In chapter 1 Tamsin lives at Carrow Ferry.",
  },
  {
    target: { css: tid("chart-as-of") },
    act: { choose: "What the River Kept" },
    wait: { css: `${place("Saltreach Abbey")} [data-who="Tamsin Vey"]` },
    say: "By chapter 3 her father is gone and she lives at Saltreach Abbey: her dot moves with her.",
  },
  {
    target: { css: tid("chart-as-of") },
    act: { choose: "" },
    say: "With nothing chosen, the chart is read at the end of the story.",
    read: 1500,
  },
  {
    go: "/w/{w}/timeline?from=412&to=413",
    target: { css: tid("open-chart") },
    act: { click: true },
    wait: { css: `${tid("timeline-chart")} ${tid("chart-scrubber")}` },
    say: "The Timeline has the chart beside it. With a span brushed along its axis, here year 412 to 413, the chart follows the span.",
  },
  {
    target: { css: tid("chart-page-link") },
    act: { click: true },
    wait: { css: tid("chart-follow") },
    say: "Open the chart for more room. It keeps following the span brushed on the Timeline.",
  },
  {
    target: { css: tid("chart-scrubber") },
    act: { fill: "0" },
    wait: { css: tid("chart-scrub-at"), text: "412" },
    say: "The scrubber steps through the span. Back to year 412, the year of the flood.",
  },
  {
    target: { css: `${place("Saltreach Abbey")} [data-who="Tamsin Vey"]` },
    say: "Each small dot is someone who lives there then. In 412 Tamsin Vey goes to live at Saltreach Abbey, so her dot is there as well as at home.",
  },
  {
    target: { css: tid("chart-scrubber") },
    act: { fill: "1" },
    wait: { css: tid("chart-scrub-at"), text: "413" },
    say: "Forward to 413, Ash Season: she lives at Carrow Ferry again, running the ferry alone.",
  },
  {
    target: { css: tid("chart-follow") },
    say: "Untick Follow the Timeline to go back to the chart's own As of.",
  },
];

export const chart: Tour = {
  id: "chart",
  title: "The chart",
  blurb: "Places drawn from the bible: shapes from types, pins and automatic layout, routes, as of a time, and the Timeline.",
  minutes: 2,
  covers: ["Chart", "Shapes and pins", "Routes and control", "As of", "From the Timeline"],
  steps,
};
