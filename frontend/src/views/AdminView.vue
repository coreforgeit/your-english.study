<script setup lang="ts">
import Button from 'primevue/button';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';

const rows = [
  { word: 'accurate', level: 'A2', reviews: 8 },
  { word: 'observe', level: 'B1', reviews: 3 },
  { word: 'reduce', level: 'A2', reviews: 6 },
];
</script>

<template>
  <section class="screen admin-screen">
    <header class="screen-header admin-header">
      <div>
        <p class="eyebrow">Admin</p>
        <h1>Vocabulary manager</h1>
      </div>
      <Button size="small">Add word</Button>
    </header>

    <DataTable :value="rows" size="small" stripedRows>
      <Column field="word" header="Word" />
      <Column field="level" header="Level" />
      <Column field="reviews" header="Reviews" />
    </DataTable>
  </section>
</template>
