<!--
  Data Results View - View scraped data with verification status
  Browse, filter, and verify scraped data from all sessions
-->
<template>
  <div class="data-results-view">
    <h1 class="mb-3">📊 Resultados del Scraping</h1>

    <!-- Summary cards -->
    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-icon">📦</div>
        <div class="summary-content">
          <span class="summary-value">{{ summary.total_records }}</span>
          <span class="summary-label">Registros Totales</span>
        </div>
      </div>
      <div class="summary-card verified">
        <div class="summary-icon">✅</div>
        <div class="summary-content">
          <span class="summary-value">{{ summary.verified_count }}</span>
          <span class="summary-label">Verificados</span>
        </div>
      </div>
      <div class="summary-card pending">
        <div class="summary-icon">⏳</div>
        <div class="summary-content">
          <span class="summary-value">{{ summary.pending_count }}</span>
          <span class="summary-label">Pendientes</span>
        </div>
      </div>
      <div class="summary-card">
        <div class="summary-icon">🏢</div>
        <div class="summary-content">
          <span class="summary-value">{{ summary.organizations_with_data }}</span>
          <span class="summary-label">Organizaciones con Datos</span>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card">
      <div class="filters-grid">
        <div class="form-group mb-0">
          <label class="form-label">Sesión</label>
          <select v-model="filters.session_id" class="form-control" @change="loadData">
            <option :value="null">Todas las sesiones</option>
            <option v-for="session in sessions" :key="session.id" :value="session.id">
              Sesión #{{ session.id }} - {{ formatDate(session.started_at) }}
            </option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Organización</label>
          <select v-model="filters.organization_id" class="form-control" @change="loadData">
            <option :value="null">Todas las organizaciones</option>
            <option v-for="org in organizations" :key="org.id" :value="org.id">
              {{ org.name }}
            </option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Variable</label>
          <select v-model="filters.variable_id" class="form-control" @change="loadData">
            <option :value="null">Todas las variables</option>
            <option v-for="variable in variables" :key="variable.id" :value="variable.id">
              {{ variable.name }}
            </option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Estado</label>
          <select v-model="filters.verified" class="form-control" @change="loadData">
            <option :value="null">Todos</option>
            <option :value="true">Verificados</option>
            <option :value="false">Pendientes</option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Buscar</label>
          <input
            v-model="filters.search"
            type="text"
            class="form-control"
            placeholder="Buscar en valores..."
            @input="debouncedSearch"
          />
        </div>
      </div>
    </div>

    <!-- Data table -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">📋 Datos Scrapeados</h2>
        <div class="flex gap-2">
          <button @click="verifySelected" class="btn btn-outline" :disabled="selectedRows.length === 0">
            ✅ Verificar Seleccionados ({{ selectedRows.length }})
          </button>
          <button @click="exportData" class="btn btn-outline">
            📥 Exportar CSV
          </button>
        </div>
      </div>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
      </div>

      <div v-else-if="data.length === 0" class="text-center text-muted" style="padding: 2rem;">
        No hay datos que coincidan con los filtros seleccionados
      </div>

      <div v-else class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th style="width: 40px;">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  @change="toggleSelectAll"
                />
              </th>
              <th>Organización</th>
              <th>Variable</th>
              <th>Clave</th>
              <th>Valor</th>
              <th>Confianza</th>
              <th>Fuente</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in data" :key="row.id" :class="{ 'verified-row': row.verified }">
              <td>
                <input
                  type="checkbox"
                  :value="row.id"
                  v-model="selectedRows"
                />
              </td>
              <td>
                <strong>{{ getOrganizationName(row.organization_id) }}</strong>
              </td>
              <td>
                <span v-if="row.variable_id" class="variable-badge" :style="{ borderColor: getVariableColor(row.variable_id) }">
                  {{ getVariableName(row.variable_id) }}
                </span>
                <span v-else class="text-muted">-</span>
              </td>
              <td>
                <code>{{ row.data_key }}</code>
              </td>
              <td class="value-cell">
                <div class="value-preview" @click="showValueDetail(row)">
                  {{ formatValue(row.data_value) }}
                </div>
              </td>
              <td>
                <div class="confidence-bar">
                  <div
                    class="confidence-fill"
                    :style="{ width: (row.confidence_score || 0) * 100 + '%' }"
                    :class="getConfidenceClass(row.confidence_score)"
                  ></div>
                </div>
                <span class="confidence-text">{{ Math.round((row.confidence_score || 0) * 100) }}%</span>
              </td>
              <td>
                <a v-if="row.source_url" :href="row.source_url" target="_blank" rel="noopener" class="source-link">
                  🔗
                </a>
                <span v-else>-</span>
              </td>
              <td>
                <span :class="['status-badge', row.verified ? 'verified' : 'pending']">
                  {{ row.verified ? '✅' : '⏳' }}
                </span>
              </td>
              <td>
                <div class="action-buttons">
                  <button
                    @click="toggleVerify(row)"
                    :class="['btn-icon', { active: row.verified }]"
                    :title="row.verified ? 'Marcar como pendiente' : 'Verificar'"
                  >
                    {{ row.verified ? '✓' : '○' }}
                  </button>
                  <button @click="showValueDetail(row)" class="btn-icon" title="Ver detalle">
                    👁️
                  </button>
                  <button @click="editRow(row)" class="btn-icon" title="Editar">
                    ✏️
                  </button>
                  <button @click="deleteRow(row)" class="btn-icon delete" title="Eliminar">
                    🗑️
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination">
        <div class="pagination-info">
          Mostrando {{ (pagination.page - 1) * pagination.limit + 1 }} - 
          {{ Math.min(pagination.page * pagination.limit, pagination.total) }} 
          de {{ pagination.total }}
        </div>
        <div class="pagination-controls">
          <button
            @click="changePage(pagination.page - 1)"
            :disabled="pagination.page <= 1"
            class="btn btn-outline"
          >
            ← Anterior
          </button>
          <span class="page-indicator">{{ pagination.page }} / {{ totalPages }}</span>
          <button
            @click="changePage(pagination.page + 1)"
            :disabled="pagination.page >= totalPages"
            class="btn btn-outline"
          >
            Siguiente →
          </button>
        </div>
      </div>
    </div>

    <!-- Value detail modal -->
    <div v-if="detailRow" class="modal-overlay" @click="detailRow = null">
      <div class="modal modal-lg" @click.stop>
        <div class="modal-header">
          <h3>📝 Detalle del Registro</h3>
          <button @click="detailRow = null" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
          <div class="detail-grid">
            <div class="detail-item">
              <label>Organización:</label>
              <span>{{ getOrganizationName(detailRow.organization_id) }}</span>
            </div>
            <div class="detail-item">
              <label>Variable:</label>
              <span>{{ getVariableName(detailRow.variable_id) || '-' }}</span>
            </div>
            <div class="detail-item">
              <label>Clave:</label>
              <code>{{ detailRow.data_key }}</code>
            </div>
            <div class="detail-item">
              <label>Confianza:</label>
              <span>{{ Math.round((detailRow.confidence_score || 0) * 100) }}%</span>
            </div>
            <div class="detail-item">
              <label>Fuente:</label>
              <a v-if="detailRow.source_url" :href="detailRow.source_url" target="_blank">
                {{ detailRow.source_url }}
              </a>
              <span v-else>-</span>
            </div>
            <div class="detail-item">
              <label>Fecha Scraping:</label>
              <span>{{ formatDate(detailRow.scraped_at) }}</span>
            </div>
            <div class="detail-item">
              <label>Estado:</label>
              <span :class="detailRow.verified ? 'text-success' : 'text-warning'">
                {{ detailRow.verified ? 'Verificado' : 'Pendiente de verificación' }}
              </span>
            </div>
            <div v-if="detailRow.verified_at" class="detail-item">
              <label>Fecha Verificación:</label>
              <span>{{ formatDate(detailRow.verified_at) }}</span>
            </div>
          </div>
          <div class="detail-value">
            <label>Valor:</label>
            <pre>{{ JSON.stringify(detailRow.data_value, null, 2) }}</pre>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="toggleVerify(detailRow); detailRow = null" class="btn btn-primary">
            {{ detailRow.verified ? '⏳ Marcar Pendiente' : '✅ Verificar' }}
          </button>
          <button @click="detailRow = null" class="btn btn-outline">Cerrar</button>
        </div>
      </div>
    </div>

    <!-- Edit modal -->
    <div v-if="editingRow" class="modal-overlay" @click="editingRow = null">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>✏️ Editar Registro</h3>
          <button @click="editingRow = null" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Clave</label>
            <input v-model="editForm.data_key" type="text" class="form-control" />
          </div>
          <div class="form-group">
            <label class="form-label">Valor (JSON)</label>
            <textarea
              v-model="editForm.data_value_str"
              class="form-control"
              rows="5"
              style="font-family: monospace;"
            ></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">Puntuación de Confianza</label>
            <input
              v-model.number="editForm.confidence_score"
              type="number"
              min="0"
              max="1"
              step="0.01"
              class="form-control"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="saveEdit" class="btn btn-primary">💾 Guardar</button>
          <button @click="editingRow = null" class="btn btn-outline">Cancelar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import {
  getScrapedData,
  getScrapedDataSummary,
  verifyScrapedData,
  updateScrapedData,
  deleteScrapedData,
  getScrapingSessions,
  getOrganizationsWithLinks,
  getVennVariables
} from '../api'

// State
const loading = ref(false)
const data = ref([])
const sessions = ref([])
const organizations = ref([])
const variables = ref([])
const selectedRows = ref([])
const detailRow = ref(null)
const editingRow = ref(null)

// Summary
const summary = ref({
  total_records: 0,
  verified_count: 0,
  pending_count: 0,
  organizations_with_data: 0
})

// Filters
const filters = ref({
  session_id: null,
  organization_id: null,
  variable_id: null,
  verified: null,
  search: ''
})

// Pagination
const pagination = ref({
  page: 1,
  limit: 25,
  total: 0
})

// Edit form
const editForm = ref({
  data_key: '',
  data_value_str: '',
  confidence_score: 0
})

// Computed
const totalPages = computed(() => {
  return Math.ceil(pagination.value.total / pagination.value.limit) || 1
})

const allSelected = computed(() => {
  return data.value.length > 0 && selectedRows.value.length === data.value.length
})

// Methods
async function loadInitialData() {
  try {
    const [sess, orgs, vars] = await Promise.all([
      getScrapingSessions(),
      getOrganizationsWithLinks(),
      getVennVariables()
    ])
    sessions.value = sess
    organizations.value = orgs
    variables.value = vars
  } catch (error) {
    console.error('Error loading initial data:', error)
  }
}

async function loadData() {
  loading.value = true
  selectedRows.value = []
  try {
    const params = {
      skip: (pagination.value.page - 1) * pagination.value.limit,
      limit: pagination.value.limit
    }
    
    if (filters.value.session_id) params.session_id = filters.value.session_id
    if (filters.value.organization_id) params.organization_id = filters.value.organization_id
    if (filters.value.variable_id) params.variable_id = filters.value.variable_id
    if (filters.value.verified !== null) params.verified = filters.value.verified
    if (filters.value.search) params.search = filters.value.search

    const result = await getScrapedData(params)
    data.value = result.data
    pagination.value.total = result.total

    // Load summary
    await loadSummary()
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    summary.value = await getScrapedDataSummary()
  } catch (error) {
    console.error('Error loading summary:', error)
  }
}

function debouncedSearch() {
  clearTimeout(window.searchTimeout)
  window.searchTimeout = setTimeout(() => {
    pagination.value.page = 1
    loadData()
  }, 300)
}

function changePage(page) {
  if (page < 1 || page > totalPages.value) return
  pagination.value.page = page
  loadData()
}

function toggleSelectAll(event) {
  if (event.target.checked) {
    selectedRows.value = data.value.map(d => d.id)
  } else {
    selectedRows.value = []
  }
}

async function verifySelected() {
  if (selectedRows.value.length === 0) return
  try {
    await Promise.all(selectedRows.value.map(id => verifyScrapedData(id, true)))
    await loadData()
  } catch (error) {
    console.error('Error verifying data:', error)
    alert('Error al verificar los datos')
  }
}

async function toggleVerify(row) {
  try {
    await verifyScrapedData(row.id, !row.verified)
    row.verified = !row.verified
    row.verified_at = row.verified ? new Date().toISOString() : null
    await loadSummary()
  } catch (error) {
    console.error('Error toggling verification:', error)
  }
}

function showValueDetail(row) {
  detailRow.value = row
}

function editRow(row) {
  editingRow.value = row
  editForm.value = {
    data_key: row.data_key,
    data_value_str: JSON.stringify(row.data_value, null, 2),
    confidence_score: row.confidence_score || 0
  }
}

async function saveEdit() {
  try {
    let data_value
    try {
      data_value = JSON.parse(editForm.value.data_value_str)
    } catch {
      data_value = editForm.value.data_value_str
    }

    await updateScrapedData(editingRow.value.id, {
      data_key: editForm.value.data_key,
      data_value,
      confidence_score: editForm.value.confidence_score
    })

    await loadData()
    editingRow.value = null
  } catch (error) {
    console.error('Error saving edit:', error)
    alert('Error al guardar los cambios')
  }
}

async function deleteRow(row) {
  if (!confirm(`¿Eliminar el registro "${row.data_key}"?`)) return
  try {
    await deleteScrapedData(row.id)
    await loadData()
  } catch (error) {
    console.error('Error deleting row:', error)
    alert('Error al eliminar el registro')
  }
}

function exportData() {
  const headers = ['ID', 'Organización', 'Variable', 'Clave', 'Valor', 'Confianza', 'Fuente', 'Verificado', 'Fecha']
  const rows = data.value.map(row => [
    row.id,
    getOrganizationName(row.organization_id),
    getVariableName(row.variable_id) || '',
    row.data_key,
    JSON.stringify(row.data_value),
    row.confidence_score,
    row.source_url || '',
    row.verified ? 'Sí' : 'No',
    row.scraped_at
  ])

  const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `scraping_data_${new Date().toISOString().split('T')[0]}.csv`
  link.click()
}

function getOrganizationName(id) {
  const org = organizations.value.find(o => o.id === id)
  return org?.name || `ID ${id}`
}

function getVariableName(id) {
  if (!id) return null
  const variable = variables.value.find(v => v.id === id)
  return variable?.name
}

function getVariableColor(id) {
  const variable = variables.value.find(v => v.id === id)
  return variable?.color || '#6c757d'
}

function formatValue(value) {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'object') {
    const str = JSON.stringify(value)
    return str.length > 60 ? str.substring(0, 60) + '...' : str
  }
  const str = String(value)
  return str.length > 60 ? str.substring(0, 60) + '...' : str
}

function formatDate(dateString) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString()
}

function getConfidenceClass(score) {
  if (score >= 0.8) return 'high'
  if (score >= 0.5) return 'medium'
  return 'low'
}

// Lifecycle
onMounted(async () => {
  await loadInitialData()
  await loadData()
})
</script>

<style scoped>
/* Premium Dark Theme - Data Results */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.25rem;
  margin-bottom: 1.5rem;
}

.summary-card {
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.25s ease;
}

.summary-card:hover {
  background: rgba(34, 34, 46, 0.8);
  transform: translateY(-2px);
  box-shadow: 0 0 40px rgba(91, 127, 255, 0.15);
}

.summary-card.verified {
  border-left: 3px solid #34D399;
}

.summary-card.pending {
  border-left: 3px solid #FBBF24;
}

.summary-icon {
  font-size: 2rem;
  filter: drop-shadow(0 0 8px rgba(91, 127, 255, 0.3));
}

.summary-content {
  display: flex;
  flex-direction: column;
}

.summary-value {
  font-size: 1.75rem;
  font-weight: 800;
  color: #FFFFFF;
  letter-spacing: -0.02em;
}

.summary-label {
  font-size: 0.8rem;
  color: #5A5A6E;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.table-container {
  overflow-x: auto;
  background: rgba(26, 26, 36, 0.5);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.table {
  min-width: 900px;
  width: 100%;
  border-collapse: collapse;
}

.table th {
  background: rgba(255, 255, 255, 0.05);
  color: #BABABD;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.table td {
  padding: 0.875rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: #FFFFFF;
}

.table tr:hover td {
  background: rgba(91, 127, 255, 0.05);
}

.verified-row {
  background: rgba(52, 211, 153, 0.05);
}

.variable-badge {
  border-left: 3px solid;
  padding-left: 0.5rem;
  font-size: 0.85rem;
  color: #BABABD;
}

.value-cell {
  max-width: 200px;
}

.value-preview {
  cursor: pointer;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.8rem;
  padding: 0.35rem 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #BABABD;
  transition: all 0.2s;
}

.value-preview:hover {
  background: rgba(91, 127, 255, 0.1);
  border-color: rgba(91, 127, 255, 0.3);
  color: #FFFFFF;
}

.confidence-bar {
  width: 60px;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
  display: inline-block;
  vertical-align: middle;
}

.confidence-fill {
  height: 100%;
}

.confidence-fill.high { background: linear-gradient(90deg, #34D399, #10B981); }
.confidence-fill.medium { background: linear-gradient(90deg, #FBBF24, #F59E0B); }
.confidence-fill.low { background: linear-gradient(90deg, #F87171, #EF4444); }

.confidence-text {
  font-size: 0.75rem;
  color: #5A5A6E;
  margin-left: 0.25rem;
}

.source-link {
  text-decoration: none;
  color: #8BA4FF;
}

.source-link:hover {
  color: #5B7FFF;
  text-decoration: underline;
}

.status-badge {
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status-badge.verified { 
  background: rgba(52, 211, 153, 0.2); 
  color: #34D399;
}
.status-badge.pending { 
  background: rgba(251, 191, 36, 0.2); 
  color: #FBBF24;
}

.action-buttons {
  display: flex;
  gap: 0.25rem;
}

.btn-icon {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  cursor: pointer;
  padding: 0.35rem 0.5rem;
  font-size: 0.85rem;
  transition: all 0.2s;
  color: #BABABD;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(91, 127, 255, 0.3);
}

.btn-icon.active {
  background: rgba(52, 211, 153, 0.2);
  border-color: #34D399;
  color: #34D399;
}

.btn-icon.delete:hover {
  background: rgba(248, 113, 113, 0.1);
  border-color: #F87171;
  color: #F87171;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.pagination-info {
  font-size: 0.9rem;
  color: #5A5A6E;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.page-indicator {
  font-size: 0.9rem;
  color: #BABABD;
}

.modal-lg {
  max-width: 700px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-item label {
  font-size: 0.75rem;
  color: #5A5A6E;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-item code {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.35rem 0.5rem;
  border-radius: 6px;
  color: #BABABD;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.85rem;
}

.detail-value {
  margin-top: 1rem;
}

.detail-value label {
  font-size: 0.75rem;
  color: #5A5A6E;
  display: block;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-value pre {
  background: rgba(10, 10, 15, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 1rem;
  border-radius: 12px;
  overflow-x: auto;
  max-height: 300px;
  font-size: 0.85rem;
  margin: 0;
  color: #E5E5E8;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
}

.text-success { color: #34D399; }
.text-warning { color: #FBBF24; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
