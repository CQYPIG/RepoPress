import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/Login.vue'),
      meta: { guest: true },
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
      redirect: '/editor',
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
      return next('/view')
    }
    if (to.meta.admin && !authStore.isAdmin) {
      return next(authStore.isEditor ? '/editor' : '/view')
    }
  }

  if (to.meta.guest && authStore.token) {
    return next((authStore.isEditor || authStore.isAdmin) ? '/editor' : '/view')
  }

  next()
})

export default router
