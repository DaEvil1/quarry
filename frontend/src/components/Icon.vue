<script setup lang="ts">
// Line icons drawn in the current text colour (unicode symbols turn into colour emoji on some systems).
const PATHS = {
  world: "M8 1.5 14.5 8 8 14.5 1.5 8Z",
  capture: "M10.5 2.5l3 3L6 13H3v-3zM9 4l3 3",
  inbox: "M2 9.5V13h12V9.5M2 9.5 4 3h8l2 6.5M2 9.5h3.5l1 1.5h3l1-1.5H14",
  triage: "M2 8h9M8 4.5 11.5 8 8 11.5M14 3v10",
  decisions: "M3 8.5l3 3 7-7",
  journal: "M3.5 2h8a1 1 0 0 1 1 1v11h-8a1 1 0 0 1-1-1zM3.5 12a1 1 0 0 1 1-1h8M6 5h4.5",
  bible: "M2 3.5c2-1 4-1 6 .5 2-1.5 4-1.5 6-.5V13c-2-1-4-1-6 .5-2-1.5-4-1.5-6-.5zM8 4v9.5",
  names: "M2 11c1-2 2 2 3 0s2 2 3 0 2 2 3 0 2 2 3 0M3 7.5 5 2.5l2 5M3.7 5.8h2.6M9 2.5h2.5a1.5 1.5 0 0 1 0 3H9zm0 3h3a1.5 1.5 0 0 1 0 3H9z",
  project: "M4 1.5h5.5L12.5 4.5V14.5h-8.5zM9.5 1.5v3h3M6 8h4.5M6 10.5h4.5",
  settings: "M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3",
} as const;

const props = defineProps<{ name: keyof typeof PATHS }>();
</script>

<template>
  <svg class="icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
    <path :d="PATHS[props.name]" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>
