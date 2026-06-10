<script setup>
defineProps({
  size: { type: Number, default: 36 },
})
</script>

<template>
  <img
    src="/favicon.svg"
    :width="size"
    :height="size"
    alt="Shireen"
    class="shireen-avatar"
  />
</template>

<style scoped>
.shireen-avatar {
  flex-shrink: 0;
  display: block;
  filter: drop-shadow(0 2px 6px rgba(180, 120, 90, 0.12));
}
</style>
