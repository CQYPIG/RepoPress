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

async function ensureRepo(repoId?: string) {
  if (repo.repos.length === 0) await repo.fetchRepos()
  if (repoId && repo.repos.some(r => r.id === repoId)) {
    repo.setCurrentRepo(repoId)
  } else if (!repo.currentRepoId && repo.repos.length > 0) {
    repo.setCurrentRepo(repo.repos[0].id)
  }
  if (repo.currentRepoId) {
    await repo.fetchTree()
  }
}

async function openRouteFile(path?: string) {
  if (!path || !repo.currentRepoId) return
  try {
    await fetchAndOpen(path)
  } catch { /* ignore missing file */ }
}

onMounted(async () => {
  await ensureRepo(route.params.repoId as string | undefined)
  await openRouteFile(route.params.path as string | undefined)
})

// Open the file referenced by the URL whenever it changes, so arriving from
// another page (or a reused window/tab) loads the requested file.
watch(
  () => [
    route.params.repoId as string | undefined,
    route.params.path as string | undefined,
  ],
  async ([repoId, path], [prevRepoId, prevPath]) => {
    if (repoId !== prevRepoId) {
      await ensureRepo(repoId)
    }
    if (path && path !== prevPath) {
      await openRouteFile(path)
    }
  },
)

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
