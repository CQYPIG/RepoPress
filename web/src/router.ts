import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/Login.vue'),
    },
    {
      path: '/editor/:repoId([a-zA-Z0-9-]+)?',
      name: 'editor',
      component: () => import('./views/Editor.vue'),
      meta: { auth: true, editor: true },
    },
    {
      path: '/editor/:repoId([a-zA-Z0-9-]+)/:path(.*)',
      name: 'editor-file',
      component: () => import('./views/Editor.vue'),
      meta: { auth: true, editor: true },
    },
    {
      path: '/view/:repoId([a-zA-Z0-9-]+)?',
      name: 'view',
      component: () => import('./views/View.vue'),
      meta: { auth: true },
    },
    {
      path: '/view/:repoId([a-zA-Z0-9-]+)/:path(.*)',
      name: 'view-file',
      component: () => import('./views/View.vue'),
      meta: { auth: true },
    },
    {
      path: '/user',
      name: 'user',
      component: () => import('./views/UserView.vue'),
      meta: { auth: true, admin: true },
    },
    {
      path: '/setting',
      name: 'setting',
      component: () => import('./views/SettingView.vue'),
      meta: { auth: true, admin: true },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/login',
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.auth) {
    if (!authStore.token) {
      return next('/login')
    }
    if (!authStore.user) {
      try {
        await authStore.fetchUser()
      } catch {
        authStore.logout()
        return next('/login')
      }
    }
    if (to.meta.editor && !(authStore.isEditor || authStore.isAdmin)) {
      window.location.replace('/view')
      return next(false)
    }
    if (to.meta.admin && !authStore.isAdmin) {
      window.location.replace(authStore.isEditor ? '/editor' : '/view')
      return next(false)
    }
  }

  next()
})

export default router
