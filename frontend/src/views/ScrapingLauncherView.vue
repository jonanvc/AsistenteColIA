<!--
  Scraping Launcher View - Configure and launch scraping with real-time progress
  Monitor scraping sessions and view progress via WebSocket
-->
<template>
  <div class="scraping-launcher-view">
    <h1 class="mb-3">🚀 Lanzador de Scraping</h1>

    <!-- Stats overview -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-content">
          <span class="stat-value">{{ organizations.length }}</span>
          <span class="stat-label">Organizaciones</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🔗</div>
        <div class="stat-content">
          <span class="stat-value">{{ totalLinks }}</span>
          <span class="stat-label">Links Configurados</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📝</div>
        <div class="stat-content">
          <span class="stat-value">{{ configs.length }}</span>
          <span class="stat-label">Configuraciones</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">⏱️</div>
        <div class="stat-content">
          <span class="stat-value">{{ activeSessions }}</span>
          <span class="stat-label">Sesiones Activas</span>
        </div>
      </div>
    </div>

    <div class="grid grid-2">
      <!-- Configuration panel -->
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">⚙️ Configuración de Scraping</h2>
          <button @click="showConfigForm = !showConfigForm" class="btn btn-outline" style="padding: 0.25rem 0.5rem;">
            {{ showConfigForm ? '✕' : '➕' }}
          </button>
        </div>

        <!-- Config form -->
        <div v-if="showConfigForm" class="config-form">
          <div class="form-group">
            <label class="form-label">Nombre de la Configuración *</label>
            <input
              v-model="configForm.name"
              type="text"
              class="form-control"
              placeholder="Ej: Scraping Básico"
              required
            />
          </div>
          <div class="grid grid-2">
            <div class="form-group">
              <label class="form-label">Timeout (segundos)</label>
              <input
                v-model.number="configForm.timeout_seconds"
                type="number"
                min="5"
                max="300"
                class="form-control"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Max Reintentos</label>
              <input
                v-model.number="configForm.max_retries"
                type="number"
                min="0"
                max="10"
                class="form-control"
              />
            </div>
          </div>
          <div class="grid grid-2">
            <div class="form-group">
              <label class="form-label">Delay entre requests (ms)</label>
              <input
                v-model.number="configForm.delay_between_requests"
                type="number"
                min="0"
                max="10000"
                class="form-control"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Requests Concurrentes</label>
              <input
                v-model.number="configForm.max_concurrent_requests"
                type="number"
                min="1"
                max="20"
                class="form-control"
              />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">User Agent</label>
            <input
              v-model="configForm.user_agent"
              type="text"
              class="form-control"
              placeholder="Mozilla/5.0..."
            />
          </div>
          <div class="form-group">
            <label class="flex items-center gap-2">
              <input v-model="configForm.headless" type="checkbox" />
              <span>Modo Headless (sin ventana del navegador)</span>
            </label>
          </div>
          <button @click="saveConfig" class="btn btn-primary" :disabled="!configForm.name">
            💾 Guardar Configuración
          </button>
        </div>

        <!-- Configs list -->
        <div class="configs-list">
          <div v-if="configs.length === 0" class="text-muted text-center" style="padding: 1rem;">
            No hay configuraciones guardadas
          </div>
          <div
            v-for="config in configs"
            :key="config.id"
            :class="['config-item', { selected: selectedConfig?.id === config.id }]"
            @click="selectConfig(config)"
          >
            <div class="config-info">
              <strong>{{ config.name }}</strong>
              <span class="config-meta">
                ⏱️ {{ config.timeout_seconds }}s |
                🔄 {{ config.max_retries }} reintentos |
                ⚡ {{ config.max_concurrent_requests }} concurrentes
              </span>
            </div>
            <button @click.stop="deleteConfig(config.id)" class="btn-icon">🗑️</button>
          </div>
        </div>
      </div>

      <!-- Launch panel -->
      <div class="card">
        <h2 class="card-title mb-2">🎯 Lanzar Scraping</h2>

        <div v-if="!selectedConfig" class="alert alert-info">
          Selecciona una configuración de la lista para continuar
        </div>

        <div v-else>
          <div class="selected-config-badge mb-2">
            Configuración: <strong>{{ selectedConfig.name }}</strong>
          </div>

          <div class="form-group">
            <label class="form-label">Organizaciones a Scrapear</label>
            <div class="organization-selector">
              <div class="selector-header">
                <label class="flex items-center gap-2">
                  <input
                    type="checkbox"
                    :checked="selectedOrganizations.length === organizations.length"
                    @change="toggleAllOrganizations"
                  />
                  <span>Seleccionar todas ({{ organizations.length }})</span>
                </label>
              </div>
              <div class="organizations-checklist">
                <label
                  v-for="org in organizations"
                  :key="org.id"
                  class="org-checkbox"
                >
                  <input
                    type="checkbox"
                    :value="org.id"
                    v-model="selectedOrganizations"
                  />
                  <span>{{ org.name }}</span>
                  <span class="links-count">{{ org.links?.length || 0 }} links</span>
                </label>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Variables a Buscar</label>
            <div class="variables-selector">
              <label v-for="variable in vennVariables" :key="variable.id" class="var-checkbox">
                <input
                  type="checkbox"
                  :value="variable.id"
                  v-model="selectedVariables"
                />
                <span :style="{ borderLeftColor: variable.color }" class="var-label">
                  {{ variable.name }} ({{ variable.proxies?.length || 0 }} proxies)
                </span>
              </label>
            </div>
          </div>

          <button
            @click="launchScraping"
            class="btn btn-primary btn-lg"
            :disabled="launching || selectedOrganizations.length === 0"
          >
            {{ launching ? '⏳ Iniciando...' : '🚀 Lanzar Scraping' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Active sessions -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">📊 Sesiones de Scraping</h2>
        <button @click="loadSessions" class="btn btn-outline" style="padding: 0.25rem 0.5rem;">
          🔄 Refrescar
        </button>
      </div>

      <div v-if="sessions.length === 0" class="text-center text-muted" style="padding: 2rem;">
        No hay sesiones de scraping registradas
      </div>

      <div v-else class="sessions-list">
        <div v-for="session in sessions" :key="session.id" class="session-card">
          <div class="session-header">
            <div class="session-info">
              <span class="session-id">#{{ session.id }}</span>
              <span :class="['session-status', 'status-' + session.status]">
                {{ getStatusLabel(session.status) }}
              </span>
              <span class="session-date">{{ formatDate(session.started_at) }}</span>
            </div>
            <div class="session-actions">
              <button
                v-if="session.status === 'running'"
                @click="cancelSession(session.id)"
                class="btn btn-outline"
                style="padding: 0.25rem 0.5rem; color: #dc3545;"
              >
                ⏹️ Cancelar
              </button>
              <button
                v-if="session.status === 'running' && !activeWebSockets[session.id]"
                @click="connectWebSocket(session.id)"
                class="btn btn-outline"
                style="padding: 0.25rem 0.5rem;"
              >
                📡 Conectar
              </button>
            </div>
          </div>

          <!-- Progress bar -->
          <div class="progress-container">
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: getProgressPercent(session) + '%' }"
                :class="'status-' + session.status"
              ></div>
            </div>
            <span class="progress-text">
              {{ session.processed_count || 0 }} / {{ session.total_count || 0 }}
              ({{ getProgressPercent(session) }}%)
            </span>
          </div>

          <!-- Real-time logs -->
          <div v-if="sessionLogs[session.id]?.length" class="session-logs">
            <div class="logs-header" @click="toggleLogs(session.id)">
              <span>📝 Logs en tiempo real</span>
              <span>{{ expandedLogs.includes(session.id) ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedLogs.includes(session.id)" class="logs-content">
              <div v-for="(log, index) in sessionLogs[session.id].slice(-20)" :key="index" class="log-entry">
                <span class="log-time">{{ log.time }}</span>
                <span :class="['log-level', 'level-' + log.level]">{{ log.level }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>

          <!-- Error message -->
          <div v-if="session.error_message" class="session-error">
            ⚠️ {{ session.error_message }}
          </div>

          <!-- Results summary -->
          <div v-if="session.status === 'completed'" class="session-results">
            <span>✅ Completado</span>
            <span v-if="session.completed_at">
              Duración: {{ getDuration(session.started_at, session.completed_at) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  getOrganizationsWithLinks,
  getVennVariables,
  getScrapingConfigs,
  createScrapingConfig,
  deleteScrapingConfig,
  getScrapingSessions,
  launchScrapingSession,
  cancelScrapingSession
} from '../api'

// State
const loading = ref(false)
const launching = ref(false)
const showConfigForm = ref(false)
const organizations = ref([])
const vennVariables = ref([])
const configs = ref([])
const sessions = ref([])
const selectedConfig = ref(null)
const selectedOrganizations = ref([])
const selectedVariables = ref([])
const sessionLogs = ref({})
const expandedLogs = ref([])
const activeWebSockets = ref({})

// Config form
const defaultConfigForm = () => ({
  name: '',
  timeout_seconds: 30,
  max_retries: 3,
  delay_between_requests: 1000,
  max_concurrent_requests: 5,
  user_agent: '',
  headless: true
})

const configForm = ref(defaultConfigForm())

// Computed
const totalLinks = computed(() => {
  return organizations.value.reduce((sum, o) => sum + (o.links?.length || 0), 0)
})

const activeSessions = computed(() => {
  return sessions.value.filter(s => s.status === 'running').length
})

// Methods
async function loadData() {
  loading.value = true
  try {
    const [orgs, vars, cfgs, sess] = await Promise.all([
      getOrganizationsWithLinks(),
      getVennVariables(),
      getScrapingConfigs(),
      getScrapingSessions()
    ])
    organizations.value = orgs
    vennVariables.value = vars
    configs.value = cfgs
    sessions.value = sess

    // Auto-connect to running sessions
    sessions.value
      .filter(s => s.status === 'running')
      .forEach(s => connectWebSocket(s.id))
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

async function loadSessions() {
  try {
    sessions.value = await getScrapingSessions()
  } catch (error) {
    console.error('Error loading sessions:', error)
  }
}

async function saveConfig() {
  try {
    await createScrapingConfig(configForm.value)
    configs.value = await getScrapingConfigs()
    showConfigForm.value = false
    configForm.value = defaultConfigForm()
  } catch (error) {
    console.error('Error saving config:', error)
    alert('Error al guardar la configuración')
  }
}

async function deleteConfig(configId) {
  if (!confirm('¿Eliminar esta configuración?')) return
  try {
    await deleteScrapingConfig(configId)
    configs.value = await getScrapingConfigs()
    if (selectedConfig.value?.id === configId) {
      selectedConfig.value = null
    }
  } catch (error) {
    console.error('Error deleting config:', error)
  }
}

function selectConfig(config) {
  selectedConfig.value = config
}

function toggleAllOrganizations(event) {
  if (event.target.checked) {
    selectedOrganizations.value = organizations.value.map(o => o.id)
  } else {
    selectedOrganizations.value = []
  }
}

async function launchScraping() {
  launching.value = true
  try {
    const result = await launchScrapingSession({
      config_id: selectedConfig.value.id,
      organization_ids: selectedOrganizations.value,
      variable_ids: selectedVariables.value
    })

    // Refresh sessions and connect to new one
    await loadSessions()
    connectWebSocket(result.session_id)

    selectedOrganizations.value = []
    selectedVariables.value = []
  } catch (error) {
    console.error('Error launching scraping:', error)
    alert('Error al lanzar el scraping')
  } finally {
    launching.value = false
  }
}

async function cancelSession(sessionId) {
  try {
    await cancelScrapingSession(sessionId)
    await loadSessions()
  } catch (error) {
    console.error('Error cancelling session:', error)
  }
}

function connectWebSocket(sessionId) {
  if (activeWebSockets.value[sessionId]) return

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/scraping/ws/progress/${sessionId}`
  const ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    console.log(`WebSocket connected for session ${sessionId}`)
    activeWebSockets.value[sessionId] = ws
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    handleWebSocketMessage(sessionId, data)
  }

  ws.onclose = () => {
    console.log(`WebSocket closed for session ${sessionId}`)
    delete activeWebSockets.value[sessionId]
  }

  ws.onerror = (error) => {
    console.error(`WebSocket error for session ${sessionId}:`, error)
  }
}

function handleWebSocketMessage(sessionId, data) {
  // Update session data
  const sessionIndex = sessions.value.findIndex(s => s.id === sessionId)
  if (sessionIndex >= 0) {
    if (data.status) sessions.value[sessionIndex].status = data.status
    if (data.processed_count !== undefined) sessions.value[sessionIndex].processed_count = data.processed_count
    if (data.total_count !== undefined) sessions.value[sessionIndex].total_count = data.total_count
    if (data.error_message) sessions.value[sessionIndex].error_message = data.error_message
  }

  // Add log entry
  if (data.message) {
    if (!sessionLogs.value[sessionId]) {
      sessionLogs.value[sessionId] = []
    }
    sessionLogs.value[sessionId].push({
      time: new Date().toLocaleTimeString(),
      level: data.level || 'info',
      message: data.message
    })
  }
}

function toggleLogs(sessionId) {
  const index = expandedLogs.value.indexOf(sessionId)
  if (index >= 0) {
    expandedLogs.value.splice(index, 1)
  } else {
    expandedLogs.value.push(sessionId)
  }
}

function getStatusLabel(status) {
  const labels = {
    pending: '⏳ Pendiente',
    running: '🔄 En Progreso',
    completed: '✅ Completado',
    failed: '❌ Fallido',
    cancelled: '⏹️ Cancelado'
  }
  return labels[status] || status
}

function getProgressPercent(session) {
  if (!session.total_count) return 0
  return Math.round((session.processed_count / session.total_count) * 100)
}

function formatDate(dateString) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString()
}

function getDuration(start, end) {
  if (!start || !end) return '-'
  const diff = new Date(end) - new Date(start)
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  }
  return `${seconds}s`
}

// Lifecycle
onMounted(() => {
  loadData()
})

onUnmounted(() => {
  // Close all WebSocket connections
  Object.values(activeWebSockets.value).forEach(ws => ws.close())
})
</script>

<style scoped>
/* Premium Dark Theme Styles */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  transition: all 0.25s ease;
}

.stat-card:hover {
  background: rgba(34, 34, 46, 0.8);
  transform: translateY(-2px);
  box-shadow: 0 0 40px rgba(91, 127, 255, 0.15);
}

.stat-icon {
  font-size: 2rem;
  filter: drop-shadow(0 0 8px rgba(91, 127, 255, 0.3));
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 800;
  color: #FFFFFF;
  letter-spacing: -0.02em;
}

.stat-label {
  font-size: 0.8rem;
  color: #8A8A9E;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.config-form {
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  margin-bottom: 1rem;
}

.configs-list {
  max-height: 300px;
  overflow-y: auto;
}

.config-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: all 0.25s ease;
  background: transparent;
}

.config-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.config-item.selected {
  background: rgba(91, 127, 255, 0.1);
  border-left: 3px solid #5B7FFF;
}

.config-meta {
  font-size: 0.8rem;
  color: #8A8A9E;
  display: block;
  margin-top: 0.25rem;
}

.config-info strong {
  color: #FFFFFF;
}

.selected-config-badge {
  background: rgba(91, 127, 255, 0.15);
  border: 1px solid rgba(91, 127, 255, 0.3);
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  color: #FFFFFF;
}

.organization-selector {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.03);
}

.selector-header {
  background: rgba(255, 255, 255, 0.06);
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: #BABABD;
  font-weight: 500;
}

.organizations-checklist {
  max-height: 200px;
  overflow-y: auto;
  padding: 0.75rem;
}

.org-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  cursor: pointer;
  color: #FFFFFF;
  transition: color 0.2s;
}

.org-checkbox:hover {
  color: #5B7FFF;
}

.links-count {
  margin-left: auto;
  font-size: 0.75rem;
  color: #5A5A6E;
}

.variables-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.var-checkbox {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  color: #BABABD;
}

.var-label {
  border-left: 3px solid;
  padding-left: 0.5rem;
  font-size: 0.85rem;
}

.btn-lg {
  width: 100%;
  padding: 0.75rem;
  font-size: 1.1rem;
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.session-card {
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 1.25rem;
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.session-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.session-id {
  font-weight: 600;
  color: #FFFFFF;
}

.session-status {
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status-pending { background: rgba(251, 191, 36, 0.2); color: #FBBF24; }
.status-running { background: rgba(91, 127, 255, 0.2); color: #8BA4FF; }
.status-completed { background: rgba(52, 211, 153, 0.2); color: #34D399; }
.status-failed { background: rgba(248, 113, 113, 0.2); color: #F87171; }
.status-cancelled { background: rgba(138, 138, 158, 0.2); color: #8A8A9E; }

.session-date {
  font-size: 0.8rem;
  color: #5A5A6E;
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.progress-fill.status-running { background: linear-gradient(90deg, #5B7FFF, #8B5CF6); }
.progress-fill.status-completed { background: linear-gradient(90deg, #34D399, #10B981); }
.progress-fill.status-failed { background: linear-gradient(90deg, #F87171, #EF4444); }

.progress-text {
  font-size: 0.85rem;
  color: #BABABD;
  min-width: 100px;
  text-align: right;
}

.session-logs {
  margin-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.75rem;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  cursor: pointer;
  font-size: 0.9rem;
  color: #BABABD;
}

.logs-content {
  max-height: 200px;
  overflow-y: auto;
  margin-top: 0.5rem;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.75rem;
  background: rgba(10, 10, 15, 0.8);
  color: #E5E5E8;
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.log-entry {
  display: flex;
  gap: 0.5rem;
  padding: 0.15rem 0;
}

.log-time {
  color: #5A5A6E;
}

.log-level {
  min-width: 50px;
}

.level-info { color: #22D3EE; }
.level-success { color: #34D399; }
.level-warning { color: #FBBF24; }
.level-error { color: #F87171; }

.log-message {
  flex: 1;
  word-break: break-word;
}

.session-error {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: #F87171;
  border-radius: 8px;
  font-size: 0.85rem;
}

.session-results {
  margin-top: 0.5rem;
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: #34D399;
}

.btn-icon {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.35rem;
  font-size: 1rem;
  opacity: 0.6;
  transition: all 0.2s;
  border-radius: 6px;
}

.btn-icon:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

@media (max-width: 768px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
