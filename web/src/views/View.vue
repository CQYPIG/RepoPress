<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRepoStore } from '../stores.js'
import { useEditor, usePreview } from '../composables.js'
import AppHeader from '../components/AppHeader.vue'
import AppSidebar from '../components/AppSidebar.vue'
import PreviewPanel from '../components/PreviewPanel.vue'

const route = useRoute()
const repo = useRepoStore()
const { store: editorStore, fetchAndOpen } = useEditor()
const preview = usePreview()

onMounted(async () => {
  await repo.fetchRepos()
  const repoId = route.params.repoId as string | undefined
  if (repoId && repo.repos.length > 0) {
    repo.setCurrentRepo(repoId)
  } else if (repo.repos.length > 0) {
    repo.setCurrentRepo(repo.repos[0].id)
  }
  if (repo.currentRepoId) {
    await repo.fetchTree()
  }

  const filePath = route.params.path as string | undefined
  if (filePath && repo.currentRepoId) {
    await fetchAndOpen(filePath)
  }
})

watch(() => editorStore.content, (val) => {
  preview.render(val)
})
</script>

<template>
  <div class="app-layout">
    <AppHeader readonly />

    <div class="app-main">
      <AppSidebar readonly />
      <div class="preview-panel relative flex-1">
        <PreviewPanel :html="preview.renderedHtml" />
      </div>
    </div>
  </div>
</template>
