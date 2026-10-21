<script setup lang="ts">
const props = withDefaults(defineProps<{ what?: string }>(), { what: "page" });
</script>

<template>
  <div class="page-head">
    <div>
      <h1>No such {{ props.what }}</h1>
      <p class="muted">It may have been renamed, or the link is wrong.</p>
      <RouterLink to="/">Go to your worlds</RouterLink>
    </div>
  </div>
</template>
