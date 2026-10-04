<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const lofts = ref([])
const tokens = ref([])
const error = ref('')
const formError = ref('')
const busy = ref(false)
const scope = ref('active') // active: 有效覆盖此刻；valid: 未作废；all: 含已作废

const stateLabel = {
  active: '有效',
  pending: '未生效',
  expired: '已过期',
  revoked: '已作废',
}

const form = reactive({
  loftId: null,
  passphrase: '',
  validFrom: '',
  validUntil: '',
})

function localInputValue(d) {
  const x = new Date(d)
  x.setMinutes(x.getMinutes() - x.getTimezoneOffset())
  return x.toISOString().slice(0, 16)
}

function resetValidity() {
  const from = new Date()
  const until = new Date(from.getTime() + 12 * 3600 * 1000)
  form.validFrom = localInputValue(from)
  form.validUntil = localInputValue(until)
}

async function load() {
  error.value = ''
  try {
    const suffix =
      scope.value === 'active'
        ? '?state=active'
        : scope.value === 'valid'
          ? '?state=valid'
          : ''
    const [l, t] = await Promise.all([
      api.get('/lofts/'),
      api.get(`/pass-tokens/${suffix}`),
    ])
    lofts.value = l.data.results || l.data
    tokens.value = t.data.results || t.data
    if (!form.loftId && lofts.value.length) form.loftId = lofts.value[0].id
  } catch {
    error.value = '口令牌加载失败'
  }
}

async function issue() {
  formError.value = ''
  if (!form.passphrase.trim()) {
    formError.value = '请填写口令明文'
    return
  }
  if (new Date(form.validUntil) <= new Date(form.validFrom)) {
    formError.value = '失效时刻必须晚于生效时刻'
    return
  }
  busy.value = true
  try {
    await api.post('/pass-tokens/', {
      loftId: form.loftId,
      passphrase: form.passphrase.trim(),
      validFrom: new Date(form.validFrom).toISOString(),
      validUntil: new Date(form.validUntil).toISOString(),
    })
    form.passphrase = ''
    resetValidity()
    await load()
  } catch (e) {
    const data = e.response?.data
    formError.value =
      data?.validFrom?.[0] ||
      data?.validUntil?.[0] ||
      data?.passphrase?.[0] ||
      data?.detail ||
      '签发失败'
  } finally {
    busy.value = false
  }
}

async function revoke(row) {
  formError.value = ''
  busy.value = true
  try {
    await api.post(`/pass-tokens/${row.id}/revoke/`)
    await load()
  } catch (e) {
    formError.value = e.response?.data?.detail || '作废失败'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  resetValidity()
  await load()
})
</script>

<template>
  <div>
    <h1>口令牌</h1>
    <p class="sub">
      布卷改为「浸渍中」前，所属帆布间须有一张覆盖当前时刻、未作废的口令牌；口令不参与「已固化」判定（仍只认固化时长 ≥ 12 小时）。仅管理员可签发与作废。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="formError" class="error">{{ formError }}</p>

    <form v-if="isAdmin" class="panel token-form" @submit.prevent="issue">
      <h2 class="feed-title">签发口令牌</h2>
      <div class="row">
        <label>帆布间
          <select v-model.number="form.loftId" required>
            <option v-for="l in lofts" :key="l.id" :value="l.id">{{ l.name }}</option>
          </select>
        </label>
        <label>口令明文
          <input v-model="form.passphrase" maxlength="120" placeholder="如 北岸-1004-夜班" required />
        </label>
        <label>生效时刻
          <input v-model="form.validFrom" type="datetime-local" required />
        </label>
        <label>失效时刻
          <input v-model="form.validUntil" type="datetime-local" required />
        </label>
        <button class="btn" type="submit" :disabled="busy">签发</button>
      </div>
    </form>
    <p v-else class="panel hint" style="margin-bottom:18px">
      当前为操作工账号：仅可查看口令牌，签发与作废请联系管理员。
    </p>

    <section class="panel">
      <div class="list-toolbar">
        <h2 class="feed-title" style="margin:0">口令牌列表</h2>
        <div class="scope-switch" role="group">
          <label>
            <input type="radio" value="active" v-model="scope" @change="load" />
            有效
          </label>
          <label>
            <input type="radio" value="valid" v-model="scope" @change="load" />
            未作废
          </label>
          <label>
            <input type="radio" value="all" v-model="scope" @change="load" />
            全部
          </label>
        </div>
      </div>
      <table v-if="tokens.length">
        <thead>
          <tr>
            <th>帆布间</th>
            <th>口令明文</th>
            <th>生效时刻</th>
            <th>失效时刻</th>
            <th>签发人</th>
            <th>状态</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in tokens" :key="row.id" :class="{ 'row-revoked': row.state === 'revoked' }">
            <td>{{ row.loftName }}</td>
            <td>{{ row.passphrase }}</td>
            <td>{{ new Date(row.validFrom).toLocaleString() }}</td>
            <td>{{ new Date(row.validUntil).toLocaleString() }}</td>
            <td>{{ row.issuedByName }}</td>
            <td>
              <span class="badge" :class="'token-state-' + row.state">
                {{ stateLabel[row.state] || row.state }}
              </span>
            </td>
            <td>
              <button
                v-if="isAdmin && row.state !== 'revoked'"
                class="btn secondary"
                type="button"
                :disabled="busy"
                @click="revoke(row)"
              >
                作废
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint" style="margin:0">列表为空</p>
    </section>
  </div>
</template>
