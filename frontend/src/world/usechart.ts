// The chart's data for a world (docs/SPEC.md §13.7): the graph, the pins and settings (`GET /chart`), and how often
// each place is named; and the state of the places as of a point, read with the cards. Shared by the chart page and
// the Timeline's chart panel.

import { computed, ref, shallowRef, watch, type Ref } from "vue";

import { del, get, post, put } from "../api";
import { listEntities } from "../bible";
import { useCards } from "./cards";
import { chartState, layoutChart, pinKey, type ChartState, type Layout, type Pin } from "./chart";
import type { GraphData } from "./graph";
import { valuesAtEnd } from "./labels";
import type { At } from "./time";

export interface ChartData {
  pins: Pin[];
  settings: { shapes: Record<string, string> };
}

export function useChart(world: Ref<string>) {
  const cards = useCards();
  const graph = shallowRef<GraphData | null>(null);
  const chart = shallowRef<ChartData>({ pins: [], settings: { shapes: {} } });
  const mentions = shallowRef(new Map<string, number>());
  const error = ref("");
  const base = () => `/api/worlds/${encodeURIComponent(world.value)}`;

  async function load() {
    error.value = "";
    try {
      const [g, c, es] = await Promise.all([get<GraphData>(`${base()}/graph`), get<ChartData>(`${base()}/chart`), listEntities(world.value)]);
      graph.value = g;
      chart.value = c;
      mentions.value = new Map(es.filter((e) => e.kind === "place").map((e) => [e.id, e.mention_count]));
    } catch (e) {
      error.value = (e as Error).message;
    }
  }
  watch(world, (w) => {
    void cards.load(w, true);
    void load();
  }, { immediate: true });

  const pins = computed(() => new Map(chart.value.pins.map((p) => [pinKey(p.place_id, p.container_id), p])));
  /** the end of the story: the last place on the clock (null with no chapters) */
  const last = computed(() => {
    const places = cards.timeline.map((c) => c.clock ?? c.index).filter((x): x is number => x !== null && x !== undefined);
    return places.length ? Math.max(...places) : null;
  });

  /** The places as of a point (null: the end of the story), with "is at" from a chapter when one is chosen. */
  function stateAt(asOf: At | null, chapter: string | null, standings: Set<string>): ChartState | null {
    const g = graph.value;
    if (!g) return null;
    const at = asOf ?? last.value;
    const typeOf = (id: string) => {
      const c = cards.byId.get(id);
      if (!c) return [];
      if (asOf === null) return valuesAtEnd(c, "type", true, last.value, cards.indexOf);
      const now = cards.asOf(c, typeof asOf === "object" && "time" in asOf ? { time: asOf.time } : chapter);
      return (now?.facts ?? []).filter((f) => f.label.trim().toLowerCase() === "type").map((f) => f.value.trim()).filter(Boolean);
    };
    return chartState({ data: g, cards: cards.byId, typeOf, shapes: chart.value.settings.shapes, mentions: mentions.value, asOf: at, indexOf: cards.indexOf, chapter, standings });
  }
  const layoutOf = (state: ChartState, visible?: (id: string) => boolean): Layout => layoutChart(state, pins.value, visible);

  async function setPin(place: string, container: string | null, x: number, y: number) {
    const p = await put<Pin>(`${base()}/chart/pins/${place}`, { container_id: container, x, y });
    chart.value = { ...chart.value, pins: [...chart.value.pins.filter((q) => pinKey(q.place_id, q.container_id) !== pinKey(place, container)), p] };
  }
  /** Reset layout (all), or inside these containers; answers with what it removed, for Undo. */
  async function resetPins(containers?: string[]): Promise<Pin[]> {
    const q = containers?.length ? `?${containers.map((c) => `container=${encodeURIComponent(c)}`).join("&")}` : "";
    const { removed } = await del<{ removed: Pin[] }>(`${base()}/chart/pins${q}`);
    const gone = new Set(removed.map((p) => pinKey(p.place_id, p.container_id)));
    chart.value = { ...chart.value, pins: chart.value.pins.filter((p) => !gone.has(pinKey(p.place_id, p.container_id))) };
    return removed;
  }
  async function putBack(removed: Pin[]) {
    chart.value = await post<ChartData>(`${base()}/chart/pins`, { pins: removed });
  }
  async function saveShapes(shapes: Record<string, string>) {
    chart.value = await put<ChartData>(`${base()}/chart/settings`, { shapes });
  }
  return { graph, chart, mentions, error, load, pins, last, stateAt, layoutOf, setPin, resetPins, putBack, saveShapes };
}
