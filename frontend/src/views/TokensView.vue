<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const lofts = ref([])
const tokens = ref([])
const activeTokens = ref([])
const error = ref('')
const formError = ref('')
const busyId = ref(null)
const submitting = ref(false)

const form = reactive({
  loftId: null,
  plaintext: '',
  validFrom: '',
  validUntil: '',
})

function localInput(d) {
  const x = new Date(d)
  x.setMinutes(x.getMinutes() - x.getTimezoneOffset())
  return x.toISOString().slice(0, 16)
}

const activeRows = computed(() => activeTokens.value)

function tokenState(t) {
  if (t.revokedAt) return { key: 'revoked', label: '已作废' }
  const now = Date.now()
  const from = new Date(t.validFrom).getTime()
  const until = new Date(t.validUntil).getTime()
  if (now < from) return { key: 'future', label: '未生效' }
  if (now >= until) return { key: 'expired', label: '已过期' }
  return { key: 'active', label: '生效中' }
}

async function load() {
  error.value = ''
  try {
    const [l, all, act] = await Promise.all([
      api.get('/lofts/'),
      api.get('/tokens/'),
      api.get('/tokens/?active=1'),
    ])
    lofts.value = l.data.results || l.data
    tokens.value = all.data.results || all.data
    activeTokens.value = act.data.results || act.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
  } catch {
    error.value = '口令牌加载失败'
  }
}

function resetForm() {
  form.plaintext = ''
  const now = new Date()
  form.validFrom = localInput(now)
  const until = new Date(now.getTime() + 12 * 60 * 60 * 1000)
  form.validUntil = localInput(until)
}

function fieldError(data, key) {
  const v = data?.[key]
  return Array.isArray(v) ? v[0] : v
}

async function issue() {
  formError.value = ''
  submitting.value = true
  try {
    await api.post('/tokens/', {
      loftId: form.loftId,
      plaintext: form.plaintext,
      validFrom: new Date(form.validFrom).toISOString(),
      validUntil: new Date(form.validUntil).toISOString(),
    })
    resetForm()
    await load()
  } catch (e) {
    const data = e.response?.data
    formError.value =
      fieldError(data, 'non_field_errors') ||
      fieldError(data, 'validUntil') ||
      fieldError(data, 'plaintext') ||
      fieldError(data, 'loftId') ||
      data?.detail ||
      '签发失败'
  } finally {
    submitting.value = false
  }
}

async function revoke(t) {
  formError.value = ''
  busyId.value = t.id
  try {
    await api.post(`/tokens/${t.id}/revoke/`, {})
    await load()
  } catch (e) {
    formError.value = e.response?.data?.detail || '作废失败'
  } finally {
    busyId.value = false
  }
}

onMounted(async () => {
  resetForm()
  await load()
})
</script>

<template>
  <div class="tokens-page">
    <h1>帆布间口令牌</h1>
    <p class="sub">
      布卷改标「浸渍中」前，所属帆布间必须有一张<strong>覆盖当前时刻、未作废</strong>的口令牌；
      口令不参与固化判定（固化仍只认最近浸渍时长 ≥ 12 小时）。仅管理员可签发与作废。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>

    <section class="panel">
      <h2 class="feed-title">当前有效口令（覆盖此刻、未作废）</h2>
      <table v-if="activeRows.length">
        <thead>
          <tr>
            <th>帆布间</th>
            <th>口令明文</th>
            <th>生效时刻</th>
            <th>失效时刻</th>
            <th>签发人</th>
            <th v-if="isAdmin"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in activeRows" :key="t.id">
            <td>{{ t.loftName }}</td>
            <td><code>{{ t.plaintext }}</code></td>
            <td>{{ new Date(t.validFrom).toLocaleString() }}</td>
            <td>{{ new Date(t.validUntil).toLocaleString() }}</td>
            <td>{{ t.issuedByName }}</td>
            <td v-if="isAdmin">
              <button
                class="btn secondary"
                type="button"
                :disabled="busyId === t.id"
                @click="revoke(t)"
              >
                作废
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint" style="margin:0">此刻没有任何帆布间持有有效口令——此期间无法把布卷标为浸渍中。</p>
    </section>

    <section v-if="isAdmin" class="panel">
      <h2 class="feed-title">签发口令牌</h2>
      <form class="row" style="margin-top:12px" @submit.prevent="issue">
        <label>帆布间
          <select v-model.number="form.loftId" required>
            <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
          </select>
        </label>
        <label>口令明文
          <input v-model="form.plaintext" required maxlength="120" placeholder="本班口令" />
        </label>
        <label>生效时刻
          <input v-model="form.validFrom" type="datetime-local" required />
        </label>
        <label>失效时刻
          <input v-model="form.validUntil" type="datetime-local" required />
        </label>
        <button class="btn" type="submit" :disabled="submitting">签发</button>
      </form>
      <p class="hint" style="margin:10px 0 0">失效时刻必须晚于生效时刻；同一帆布间未作废且时段重叠的口令只允许一张。</p>
    </section>

    <section class="panel">
      <h2 class="feed-title">全部口令牌</h2>
      <table>
        <thead>
          <tr>
            <th>帆布间</th>
            <th>口令明文</th>
            <th>生效时刻</th>
            <th>失效时刻</th>
            <th>签发人</th>
            <th>状态</th>
            <th>作废时刻</th>
            <th v-if="isAdmin"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tokens" :key="t.id">
            <td>{{ t.loftName }}</td>
            <td><code>{{ t.plaintext }}</code></td>
            <td>{{ new Date(t.validFrom).toLocaleString() }}</td>
            <td>{{ new Date(t.validUntil).toLocaleString() }}</td>
            <td>{{ t.issuedByName }}</td>
            <td>
              <span class="badge" :class="'tok-' + tokenState(t).key">{{ tokenState(t).label }}</span>
            </td>
            <td>{{ t.revokedAt ? new Date(t.revokedAt).toLocaleString() : '—' }}</td>
            <td v-if="isAdmin">
              <button
                v-if="!t.revokedAt"
                class="btn secondary"
                type="button"
                :disabled="busyId === t.id"
                @click="revoke(t)"
              >
                作废
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!tokens.length" class="hint" style="margin:0">尚未签发任何口令牌。</p>
    </section>
  </div>
</template>
