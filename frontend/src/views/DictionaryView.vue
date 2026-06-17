<script setup lang="ts">
const words = [
  { word: 'accurate', translation: 'correct and exact', status: 'Learning' },
  { word: 'observe', translation: 'to watch carefully', status: 'New' },
  { word: 'reduce', translation: 'to make smaller', status: 'Review' },
];
</script>

<template>
  <section class="screen">
    <header class="screen-header">
      <p class="eyebrow">Vocabulary</p>
      <h1>Word list</h1>
    </header>

    <div class="list">
      <article v-for="item in words" :key="item.word" class="list-row">
        <div>
          <strong>{{ item.word }}</strong>
          <span>{{ item.translation }}</span>
        </div>
        <small>{{ item.status }}</small>
      </article>
    </div>
  </section>
</template>
