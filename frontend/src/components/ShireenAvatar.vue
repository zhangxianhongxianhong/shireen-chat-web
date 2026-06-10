<script setup>
defineProps({
  size: { type: Number, default: 36 },
})
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 80 80"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="shireen-avatar"
    aria-label="Shireen"
  >
    <circle cx="40" cy="40" r="38" fill="#FFF8F2" stroke="#F5D5BC" stroke-width="1.5"/>

    <path d="M20 30 L12 8 L34 24 Z" fill="#F0B87A"/>
    <path d="M60 30 L68 8 L46 24 Z" fill="#F0B87A"/>
    <path d="M22 28 L17 16 L30 24 Z" fill="#FFD4B0"/>
    <path d="M58 28 L63 16 L50 24 Z" fill="#FFD4B0"/>

    <ellipse cx="40" cy="46" rx="26" ry="24" fill="#FFD9A8"/>

    <ellipse cx="40" cy="56" rx="13" ry="10" fill="#FFFAF5"/>

    <ellipse cx="21" cy="50" rx="5" ry="3.5" fill="#E8A0A8" opacity="0.45"/>
    <ellipse cx="59" cy="50" rx="5" ry="3.5" fill="#E8A0A8" opacity="0.45"/>

    <ellipse cx="29" cy="42" rx="5.5" ry="6.5" fill="#4A3530"/>
    <ellipse cx="51" cy="42" rx="5.5" ry="6.5" fill="#4A3530"/>
    <circle cx="30.5" cy="40" r="2" fill="white"/>
    <circle cx="52.5" cy="40" r="2" fill="white"/>

    <path d="M40 50 L37.5 53.5 L42.5 53.5 Z" fill="#D4848A"/>

    <path
      d="M40 54 Q34 59 29 56"
      stroke="#C47B8A"
      stroke-width="1.8"
      stroke-linecap="round"
      fill="none"
    />
    <path
      d="M40 54 Q46 59 51 56"
      stroke="#C47B8A"
      stroke-width="1.8"
      stroke-linecap="round"
      fill="none"
    />

    <line x1="10" y1="48" x2="20" y2="49" stroke="#E8C4A0" stroke-width="1.2" stroke-linecap="round"/>
    <line x1="10" y1="53" x2="20" y2="53" stroke="#E8C4A0" stroke-width="1.2" stroke-linecap="round"/>
    <line x1="60" y1="49" x2="70" y2="48" stroke="#E8C4A0" stroke-width="1.2" stroke-linecap="round"/>
    <line x1="60" y1="53" x2="70" y2="53" stroke="#E8C4A0" stroke-width="1.2" stroke-linecap="round"/>
  </svg>
</template>

<style scoped>
.shireen-avatar {
  flex-shrink: 0;
  display: block;
  filter: drop-shadow(0 2px 6px rgba(180, 120, 90, 0.12));
}
</style>
