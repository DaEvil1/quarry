<script setup lang="ts">
import { computed } from "vue";

import { Family, kinOf, kinText, layoutTree, SLOT, type FamilyLink } from "../world/family";
import type { GraphData } from "../world/graph";

// A family drawn in generations (docs/SPEC.md §12.2): couples side by side (a double line when married, a single one
// for two parents who aren't), children hanging from their parents, recorded siblings without parents from a "?".
// Under each name, dimmed, how they are related to the centre. Plain SVG, laid out once; a big family scrolls (or
// pans by dragging on a phone) inside its card.
const props = defineProps<{
  world: string;
  data: GraphData;
  links: FamilyLink[];
  centre: string;
  /** is this one dead as of the chosen chapter? */
  dead: (id: string) => boolean;
}>();
const emit = defineEmits<{ centre: [id: string] }>();

const fam = computed(() => new Family(props.links));
const node = computed(() => new Map(props.data.nodes.map((n) => [n.id, n])));
const tree = computed(() => (fam.value.people.has(props.centre) ? layoutTree(fam.value, props.centre, (id) => node.value.get(id)?.name ?? id) : null));
const how = computed(() => {
  const out = new Map<string, string[]>();
  for (const k of kinOf(fam.value, props.centre)) out.set(k.id, [...(out.get(k.id) ?? []), kinText(k, node.value.get(k.id)?.gender)]);
  return out;
});
const loops = computed(() => fam.value.loops().filter((l) => tree.value?.people.some((p) => p.id === l[0])));
const name = (id: string) => node.value.get(id)?.name ?? "?";
const points = (ps: [number, number][]) => ps.map(([x, y]) => `${x},${y}`).join(" ");
</script>

<template>
  <div class="family">
    <p v-for="(l, i) in loops" :key="i" class="notice warn small" data-testid="family-loop">
      {{ name(l[0]!) }} is recorded as their own ancestor: {{ l.map(name).join(" → ") }}.
    </p>
    <div v-if="tree" class="family-scroll">
      <svg
        class="family-tree"
        :width="tree.width"
        :height="tree.height"
        :viewBox="`0 0 ${tree.width} ${tree.height}`"
        data-testid="family-tree"
      >
        <g class="flines">
          <template v-for="(l, i) in tree.lines" :key="i">
            <template v-if="l.kind === 'married'">
              <polyline :points="points(l.points.map(([x, y]) => [x, y - 3]) as [number, number][])" class="fline married" :class="{ dashed: l.dashed }" />
              <polyline :points="points(l.points.map(([x, y]) => [x, y + 3]) as [number, number][])" class="fline married" :class="{ dashed: l.dashed }" />
            </template>
            <polyline v-else :points="points(l.points)" class="fline" :class="[l.kind, { dashed: l.dashed }]" :data-testid="l.kind === 'ancestor' ? 'family-lineage' : undefined" />
            <text v-if="l.label && l.kind === 'ancestor'" class="fline-label lineage" :x="l.points[1]![0] + 6" :y="(l.points[0]![1] + l.points[1]![1]) / 2" data-testid="family-lineage-label">{{ l.label }}</text>
            <text v-else-if="l.label" class="fline-label" :x="l.points[3]![0] + 4" :y="l.points[3]![1] - 6">{{ l.label }}</text>
          </template>
        </g>
        <g v-for="(u, i) in tree.unknown" :key="`u${i}`" class="funknown">
          <circle :cx="u.x" :cy="u.y" r="9" />
          <text :x="u.x" :y="u.y + 4" text-anchor="middle">?</text>
        </g>
        <g
          v-for="p in tree.people"
          :key="p.id"
          class="fperson k-character"
          :class="{ centre: p.id === props.centre }"
          :transform="`translate(${p.x} ${p.y})`"
          :data-name="name(p.id)"
          :data-gen="p.gen"
          data-testid="family-person"
        >
          <title>{{ name(p.id) }}{{ node.get(p.id)?.summary ? ` — ${node.get(p.id)!.summary}` : "" }}</title>
          <rect :x="-SLOT / 2 + 8" y="-24" :width="SLOT - 16" height="48" rx="6" @click="emit('centre', p.id)" />
          <text class="fname kname" y="-4" text-anchor="middle" @click="emit('centre', p.id)">{{ name(p.id) }}<tspan v-if="props.dead(p.id)" class="dagger"> †</tspan></text>
          <text class="fhow" y="13" text-anchor="middle" data-testid="family-how">{{ p.id === props.centre ? "" : (how.get(p.id) ?? []).join(" · ") }}</text>
          <a :href="`/w/${props.world}/bible/${p.id}`" class="fopen" :aria-label="`Open ${name(p.id)}`" @click.prevent="$router.push({ name: 'entity', params: { world: props.world, id: p.id } })">
            <text :x="SLOT / 2 - 14" y="-12" text-anchor="end">↗</text>
          </a>
        </g>
      </svg>
    </div>
    <p v-else class="empty">No recorded parents, children or marriages for them yet.</p>
    <p class="muted small">
      Click a name to centre the tree on them; ↗ opens the entry. Read from “parent of” (and any type ending in parent,
      father or mother of), “married to”, “sibling of” and “ancestor of” (a long dashed line, the generations between
      not recorded); kin is worked out, never stored.
    </p>
  </div>
</template>
