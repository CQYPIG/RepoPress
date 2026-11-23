<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { NButton, NTag, useMessage, useDialog } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { type User } from '../stores.js'
import { api } from '../api.js'

const message = useMessage()
const dialog = useDialog()

const users = ref<User[]>([])
const loading = ref(false)
const showModal = ref(false)
const editingUser = ref<User | null>(null)
const form = ref<{
  username: string
  email: string
  display_name: string
  password: string
  role: 'editor' | 'viewer'
}>({
  username: '',
  email: '',
  display_name: '',
  password: '',
  role: 'viewer',
})

const columns: DataTableColumns<User> = [
  { title: 'Username', key: 'username' },
  {
    title: 'Role',
    key: 'role',
    width: 100,
    render(row) {
      return h(NTag, {
        type: row.role === 'editor' ? 'error' : 'info',
        size: 'small',
      }, { default: () => row.role === 'editor' ? 'Editor' : 'Viewer' })
    },
  },
  {
    title: 'Status',
    key: 'is_active',
    width: 80,
    render(row) {
      return h(NTag, {
        type: row.is_active ? 'success' : 'default',
        size: 'small',
      }, { default: () => row.is_active ? 'Active' : 'Inactive' })
    },
  },
  {
    title: 'Actions',
    key: 'actions',
    width: 120,
    render(row) {
      return h('div', { class: 'flex gap-2' }, [
        h(NButton, { size: 'small', onClick: () => editUser(row) }, { default: () => 'Edit' }),
      ])
    },
  },
]

onMounted(fetchUsers)

async function fetchUsers() {
  loading.value = true
  try {
    users.value = await api.admin.getUsers()
  } catch (e: any) {
    message.error(e?.data?.detail || 'Failed to load users')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingUser.value = null
  form.value = { username: '', email: '', display_name: '', password: '', role: 'viewer' }
  showModal.value = true
}

function editUser(row: User) {
  editingUser.value = row
  form.value = {
    username: row.username,
    email: row.email,
    display_name: row.display_name,
    password: '',
    role: row.role,
  }
  showModal.value = true
}

async function saveUser() {
  if (!form.value.role) {
    message.warning('请选择权限')
    return
  }
  try {
    if (editingUser.value) {
      await api.admin.updateUser(editingUser.value.id, {
        ...(form.value.password ? { password: form.value.password } : {}),
        role: form.value.role,
      })
      message.success('User updated')
    } else {
      await api.admin.createUser({
        username: form.value.username,
        email: `${form.value.username}@repopress.local`,
        display_name: form.value.username,
        password: form.value.password,
        role: form.value.role,
      })
      message.success('User created')
    }
    showModal.value = false
    await fetchUsers()
  } catch (e: any) {
    message.error(e?.data?.detail || 'Failed to save user')
  }
}
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold">User Management</h1>
      <n-button type="primary" @click="openCreate">Add User</n-button>
    </div>

    <n-data-table :columns="columns" :data="users" :loading="loading" />

    <n-modal v-model:show="showModal" preset="card" :title="editingUser ? 'Edit User' : 'Add User'" class="w-120">
      <n-form>
        <n-form-item label="Username">
          <n-input v-model:value="form.username" :disabled="!!editingUser" placeholder="Username" />
        </n-form-item>
        <n-form-item label="Password">
          <n-input v-model:value="form.password" type="password" :placeholder="editingUser ? 'Leave blank to keep current' : 'Password'" />
        </n-form-item>
        <n-form-item label="权限" required>
          <n-select
            v-model:value="form.role"
            :options="[
              { label: '编辑者', value: 'editor' },
              { label: '查看者', value: 'viewer' },
            ]"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="showModal = false">Cancel</n-button>
          <n-button type="primary" @click="saveUser">Save</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>
