<!--
  Venn Results View - View and verify Venn diagram results
  Shows all VennResults with verification status, source URLs, and matched proxies
-->
<template>
  <div class="venn-results-view">
    <h1 class="mb-3">🔍 Resultados de Variables Venn</h1>

    <!-- Summary cards -->
    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-icon">📊</div>
        <div class="summary-content">
          <span class="summary-value">{{ stats.total }}</span>
          <span class="summary-label">Resultados Totales</span>
        </div>
      </div>
      <div class="summary-card pending">
        <div class="summary-icon">⏳</div>
        <div class="summary-content">
          <span class="summary-value">{{ stats.pending }}</span>
          <span class="summary-label">Pendientes de Verificar</span>
        </div>
      </div>
      <div class="summary-card verified">
        <div class="summary-icon">✅</div>
        <div class="summary-content">
          <span class="summary-value">{{ stats.verified }}</span>
          <span class="summary-label">Verificados</span>
        </div>
      </div>
      <div class="summary-card rejected">
        <div class="summary-icon">❌</div>
        <div class="summary-content">
          <span class="summary-value">{{ stats.rejected }}</span>
          <span class="summary-label">Rechazados</span>
        </div>
      </div>
    </div>

    <!-- Verification Rate -->
    <div class="card mb-3">
      <div class="verification-progress">
        <div class="progress-header">
          <span>Progreso de Verificación</span>
          <span class="progress-percent">{{ stats.verification_rate }}%</span>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar" :style="{ width: stats.verification_rate + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-3">
      <div class="filters-grid">
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
          <label class="form-label">Variable Venn</label>
          <select v-model="filters.venn_variable_id" class="form-control" @change="loadData">
            <option :value="null">Todas las variables</option>
            <option v-for="variable in vennVariables" :key="variable.id" :value="variable.id">
              {{ variable.name }}
            </option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Estado de Verificación</label>
          <select v-model="filters.verification_status" class="form-control" @change="loadData">
            <option :value="null">Todos</option>
            <option value="pending">⏳ Pendientes</option>
            <option value="verified">✅ Verificados</option>
            <option value="rejected">❌ Rechazados</option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Origen</label>
          <select v-model="filters.source" class="form-control" @change="loadData">
            <option :value="null">Todos</option>
            <option value="automatic">🤖 Automático</option>
            <option value="manual">👤 Manual</option>
            <option value="mixed">🔀 Mixto</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Bulk Actions -->
    <div v-if="selectedRows.length > 0" class="bulk-actions card mb-3">
      <span class="selected-count">{{ selectedRows.length }} seleccionados</span>
      <div class="bulk-buttons">
        <button @click="bulkVerify('verified')" class="btn btn-success">
          ✅ Aprobar Seleccionados
        </button>
        <button @click="bulkVerify('rejected')" class="btn btn-danger">
          ❌ Rechazar Seleccionados
        </button>
      </div>
    </div>

    <!-- Results table -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">📋 Resultados</h2>
        <button @click="loadData" class="btn btn-outline">
          🔄 Actualizar
        </button>
      </div>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
      </div>

      <div v-else-if="results.length === 0" class="text-center text-muted" style="padding: 2rem;">
        No hay resultados que coincidan con los filtros seleccionados
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
              <th>Valor</th>
              <th>Origen</th>
              <th>URLs Fuente</th>
              <th>Proxies Encontrados</th>
              <th>Fecha</th>
              <th>Verificación</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in results" :key="row.id" :class="getRowClass(row)">
              <td>
                <input
                  type="checkbox"
                  :value="row.id"
                  v-model="selectedRows"
                />
              </td>
              <td>
                <strong>{{ row.organization_name || 'Organización #' + row.organization_id }}</strong>
              </td>
              <td>
                <span class="variable-badge">
                  {{ row.variable_name || 'Variable #' + row.venn_variable_id }}
                </span>
              </td>
              <td>
                <span :class="row.value ? 'badge-yes' : 'badge-no'">
                  {{ row.value ? '✓ SÍ' : '✗ NO' }}
                </span>
                <span v-if="row.original_value !== null && row.original_value !== row.value" class="original-value">
                  (original: {{ row.original_value ? 'SÍ' : 'NO' }})
                </span>
              </td>
              <td>
                <span :class="'source-badge source-' + row.source">
                  {{ getSourceLabel(row.source) }}
                </span>
                <span v-if="row.search_score" class="score-badge">
                  {{ (row.search_score * 100).toFixed(0) }}%
                </span>
              </td>
              <td>
                <div v-if="row.source_urls && row.source_urls.length > 0" class="urls-list">
                  <a 
                    v-for="(url, idx) in row.source_urls.slice(0, 3)" 
                    :key="idx" 
                    :href="url" 
                    target="_blank" 
                    class="url-link"
                    :title="url"
                  >
                    🔗 {{ truncateUrl(url) }}
                  </a>
                  <span v-if="row.source_urls.length > 3" class="more-urls">
                    +{{ row.source_urls.length - 3 }} más
                  </span>
                </div>
                <span v-else class="text-muted">-</span>
              </td>
              <td>
                <div v-if="row.matched_proxies && row.matched_proxies.length > 0" class="proxies-list">
                  <span v-for="(proxy, idx) in row.matched_proxies.slice(0, 3)" :key="idx" class="proxy-tag">
                    {{ proxy }}
                  </span>
                  <span v-if="row.matched_proxies.length > 3" class="more-proxies">
                    +{{ row.matched_proxies.length - 3 }}
                  </span>
                </div>
                <span v-else class="text-muted">-</span>
              </td>
              <td>
                <div class="date-info">
                  <span class="date-created">{{ formatDate(row.created_at) }}</span>
                </div>
              </td>
              <td>
                <div class="verification-info">
                  <span :class="'status-badge status-' + row.verification_status">
                    {{ getStatusLabel(row.verification_status) }}
                  </span>
                  <div v-if="row.verified_by" class="verified-by">
                    por {{ row.verified_by }}
                  </div>
                  <div v-if="row.verified_at" class="verified-at">
                    {{ formatDate(row.verified_at) }}
                  </div>
                </div>
              </td>
              <td>
                <div class="action-buttons">
                  <button 
                    v-if="row.verification_status === 'pending'"
                    @click="openVerifyModal(row)" 
                    class="btn btn-sm btn-primary"
                    title="Verificar"
                  >
                    ✓
                  </button>
                  <button 
                    @click="openDetailModal(row)" 
                    class="btn btn-sm btn-outline"
                    title="Ver detalle"
                  >
                    👁️
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Verify Modal -->
    <div v-if="showVerifyModal" class="modal-overlay" @click.self="closeVerifyModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Verificar Resultado</h3>
          <button @click="closeVerifyModal" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="verify-info">
            <p><strong>Organización:</strong> {{ selectedResult?.organization_name }}</p>
            <p><strong>Variable:</strong> {{ selectedResult?.variable_name }}</p>
            <p><strong>Valor detectado:</strong> {{ selectedResult?.value ? 'SÍ (1)' : 'NO (0)' }}</p>
            <p v-if="selectedResult?.search_score"><strong>Confianza:</strong> {{ (selectedResult.search_score * 100).toFixed(1) }}%</p>
          </div>
          
          <div v-if="selectedResult?.source_urls?.length > 0" class="verify-urls">
            <h4>URLs donde se encontró:</h4>
            <ul>
              <li v-for="(url, idx) in selectedResult.source_urls" :key="idx">
                <a :href="url" target="_blank">{{ url }}</a>
              </li>
            </ul>
          </div>
          
          <div v-if="selectedResult?.matched_proxies?.length > 0" class="verify-proxies">
            <h4>Proxies coincidentes:</h4>
            <div class="proxy-tags">
              <span v-for="(proxy, idx) in selectedResult.matched_proxies" :key="idx" class="proxy-tag">
                {{ proxy }}
              </span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">¿El valor es correcto?</label>
            <div class="radio-group">
              <label class="radio-option">
                <input type="radio" v-model="verifyForm.corrected_value" :value="null" />
                <span>Sí, mantener valor actual</span>
              </label>
              <label class="radio-option">
                <input type="radio" v-model="verifyForm.corrected_value" :value="!selectedResult?.value" />
                <span>No, cambiar a {{ selectedResult?.value ? 'NO (0)' : 'SÍ (1)' }}</span>
              </label>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Tu nombre</label>
            <input v-model="verifyForm.verified_by" type="text" class="form-control" placeholder="Tu nombre..." />
          </div>

          <div class="form-group">
            <label class="form-label">Notas (opcional)</label>
            <textarea v-model="verifyForm.verification_notes" class="form-control" rows="3" placeholder="Notas sobre la verificación..."></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeVerifyModal" class="btn btn-outline">Cancelar</button>
          <button @click="rejectResult" class="btn btn-danger">❌ Rechazar</button>
          <button @click="approveResult" class="btn btn-success" :disabled="!verifyForm.verified_by">✅ Aprobar</button>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="showDetailModal" class="modal-overlay" @click.self="closeDetailModal">
      <div class="modal-content modal-large">
        <div class="modal-header">
          <h3>Detalle del Resultado</h3>
          <button @click="closeDetailModal" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-grid">
            <div class="detail-section">
              <h4>📋 Información General</h4>
              <dl>
                <dt>Organización</dt>
                <dd>{{ selectedResult?.organization_name }}</dd>
                <dt>Variable Venn</dt>
                <dd>{{ selectedResult?.variable_name }}</dd>
                <dt>Valor</dt>
                <dd>
                  <span :class="selectedResult?.value ? 'badge-yes' : 'badge-no'">
                    {{ selectedResult?.value ? 'SÍ (1)' : 'NO (0)' }}
                  </span>
                </dd>
                <dt>Origen</dt>
                <dd>{{ getSourceLabel(selectedResult?.source) }}</dd>
                <dt v-if="selectedResult?.search_score">Puntuación</dt>
                <dd v-if="selectedResult?.search_score">{{ (selectedResult.search_score * 100).toFixed(1) }}%</dd>
              </dl>
            </div>

            <div class="detail-section">
              <h4>✅ Verificación</h4>
              <dl>
                <dt>Estado</dt>
                <dd>
                  <span :class="'status-badge status-' + selectedResult?.verification_status">
                    {{ getStatusLabel(selectedResult?.verification_status) }}
                  </span>
                </dd>
                <dt v-if="selectedResult?.verified_by">Verificado por</dt>
                <dd v-if="selectedResult?.verified_by">{{ selectedResult.verified_by }}</dd>
                <dt v-if="selectedResult?.verified_at">Fecha de verificación</dt>
                <dd v-if="selectedResult?.verified_at">{{ formatDateTime(selectedResult.verified_at) }}</dd>
                <dt v-if="selectedResult?.verification_notes">Notas</dt>
                <dd v-if="selectedResult?.verification_notes">{{ selectedResult.verification_notes }}</dd>
                <dt v-if="selectedResult?.original_value !== null">Valor original</dt>
                <dd v-if="selectedResult?.original_value !== null">{{ selectedResult.original_value ? 'SÍ' : 'NO' }}</dd>
              </dl>
            </div>
          </div>

          <div v-if="selectedResult?.source_urls?.length > 0" class="detail-section">
            <h4>🔗 URLs Fuente</h4>
            <ul class="url-list-detail">
              <li v-for="(url, idx) in selectedResult.source_urls" :key="idx">
                <a :href="url" target="_blank" class="url-link-detail">{{ url }}</a>
              </li>
            </ul>
          </div>

          <div v-if="selectedResult?.matched_proxies?.length > 0" class="detail-section">
            <h4>🏷️ Proxies Coincidentes</h4>
            <div class="proxy-tags-detail">
              <span v-for="(proxy, idx) in selectedResult.matched_proxies" :key="idx" class="proxy-tag-large">
                {{ proxy }}
              </span>
            </div>
          </div>

          <!-- Evidence Panel - Traceability -->
          <div class="detail-section evidence-section">
            <h4>🔎 Trazabilidad de Evidencias</h4>
            <p class="text-muted mb-2">Fragmentos de texto donde se detectaron los proxies</p>
            
            <div v-if="loadingEvidence" class="loading-evidence">
              <div class="spinner-small"></div>
              <span>Cargando evidencias...</span>
            </div>
            
            <div v-else-if="evidenceList.length === 0" class="no-evidence">
              No hay evidencias registradas para este resultado
            </div>
            
            <div v-else class="evidence-list">
              <div v-for="evidence in evidenceList" :key="evidence.id" class="evidence-card" :class="{ 'evidence-invalid': evidence.is_valid === false }">
                <div class="evidence-header">
                  <div class="evidence-source">
                    <span class="source-type-badge">{{ getSourceTypeLabel(evidence.source_type) }}</span>
                    <a :href="evidence.source_url" target="_blank" class="evidence-url" :title="evidence.source_url">
                      🔗 {{ truncateUrl(evidence.source_url) }}
                    </a>
                  </div>
                  <div class="evidence-validation" v-if="evidence.is_valid !== null">
                    <span :class="evidence.is_valid ? 'validation-valid' : 'validation-invalid'">
                      {{ evidence.is_valid ? '✅ Válida' : '❌ Inválida' }}
                    </span>
                  </div>
                </div>
                
                <div class="evidence-fragment">
                  <strong>Fragmento encontrado:</strong>
                  <div class="fragment-text">
                    "{{ evidence.text_fragment }}"
                  </div>
                  <div class="matched-highlight" v-if="evidence.matched_text">
                    Coincidencia: <mark>{{ evidence.matched_text }}</mark>
                  </div>
                </div>
                
                <div class="evidence-meta">
                  <span v-if="evidence.section_title" class="meta-item">
                    📍 Sección: {{ evidence.section_title }}
                  </span>
                  <span v-if="evidence.paragraph_number" class="meta-item">
                    📝 Párrafo #{{ evidence.paragraph_number }}
                  </span>
                  <span v-if="evidence.match_score" class="meta-item">
                    🎯 Score: {{ (evidence.match_score * 100).toFixed(0) }}%
                  </span>
                  <span class="meta-item">
                    {{ evidence.is_exact_match ? '✓ Coincidencia exacta' : '~ Aproximada' }}
                  </span>
                </div>
                
                <div v-if="evidence.xpath || evidence.css_selector" class="evidence-selector">
                  <code v-if="evidence.xpath" title="XPath">xpath: {{ evidence.xpath }}</code>
                  <code v-else-if="evidence.css_selector" title="CSS Selector">css: {{ evidence.css_selector }}</code>
                </div>
                
                <div class="evidence-actions">
                  <button 
                    v-if="evidence.is_valid === null"
                    @click="handleValidateEvidence(evidence, true)" 
                    class="btn btn-sm btn-success"
                    title="Validar como correcto"
                  >
                    ✓ Validar
                  </button>
                  <button 
                    v-if="evidence.is_valid === null"
                    @click="handleValidateEvidence(evidence, false)" 
                    class="btn btn-sm btn-danger"
                    title="Marcar como inválido"
                  >
                    ✗ Rechazar
                  </button>
                  <a 
                    :href="evidence.source_url" 
                    target="_blank" 
                    class="btn btn-sm btn-outline"
                    title="Abrir URL en nueva pestaña"
                  >
                    🔗 Abrir
                  </a>
                </div>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <h4>📅 Fechas</h4>
            <dl>
              <dt>Creado</dt>
              <dd>{{ formatDateTime(selectedResult?.created_at) }}</dd>
              <dt v-if="selectedResult?.updated_at">Actualizado</dt>
              <dd v-if="selectedResult?.updated_at">{{ formatDateTime(selectedResult.updated_at) }}</dd>
            </dl>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeDetailModal" class="btn btn-outline">Cerrar</button>
          <button 
            v-if="selectedResult?.verification_status === 'pending'" 
            @click="closeDetailModal(); openVerifyModal(selectedResult)" 
            class="btn btn-primary"
          >
            Verificar
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { 
  getVennResults, 
  getVennResultsStats, 
  verifyVennResult, 
  bulkVerifyVennResults,
  getOrganizations,
  getVennVariables,
  getEvidenceByResult,
  validateEvidence,
  bulkValidateEvidence
} from '../api'

// State
const loading = ref(false)
const results = ref([])
const organizations = ref([])
const vennVariables = ref([])
const selectedRows = ref([])
const stats = ref({
  total: 0,
  pending: 0,
  verified: 0,
  rejected: 0,
  verification_rate: 0,
  by_source: { manual: 0, automatic: 0, mixed: 0 }
})

// Filters
const filters = ref({
  organization_id: null,
  venn_variable_id: null,
  verification_status: null,
  source: null
})

// Modals
const showVerifyModal = ref(false)
const showDetailModal = ref(false)
const selectedResult = ref(null)
const verifyForm = ref({
  verification_status: 'verified',
  verified_by: localStorage.getItem('verifier_name') || '',
  verification_notes: '',
  corrected_value: null
})

// Evidence
const evidenceList = ref([])
const loadingEvidence = ref(false)

// Computed
const allSelected = computed(() => {
  return results.value.length > 0 && selectedRows.value.length === results.value.length
})

// Methods
async function loadData() {
  loading.value = true
  try {
    const params = {}
    if (filters.value.organization_id) params.organization_id = filters.value.organization_id
    if (filters.value.venn_variable_id) params.venn_variable_id = filters.value.venn_variable_id
    
    let data = await getVennResults(params)
    
    // Client-side filtering for verification_status and source
    if (filters.value.verification_status) {
      data = data.filter(r => r.verification_status === filters.value.verification_status)
    }
    if (filters.value.source) {
      data = data.filter(r => r.source === filters.value.source)
    }
    
    results.value = data
    selectedRows.value = []
  } catch (error) {
    console.error('Error loading results:', error)
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await getVennResultsStats()
  } catch (error) {
    console.error('Error loading stats:', error)
  }
}

async function loadFilters() {
  try {
    const [orgs, vars] = await Promise.all([
      getOrganizations(),
      getVennVariables()
    ])
    organizations.value = orgs
    vennVariables.value = vars
  } catch (error) {
    console.error('Error loading filters:', error)
  }
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedRows.value = []
  } else {
    selectedRows.value = results.value.map(r => r.id)
  }
}

function openVerifyModal(result) {
  selectedResult.value = result
  verifyForm.value = {
    verification_status: 'verified',
    verified_by: localStorage.getItem('verifier_name') || '',
    verification_notes: '',
    corrected_value: null
  }
  showVerifyModal.value = true
}

function closeVerifyModal() {
  showVerifyModal.value = false
  selectedResult.value = null
}

async function openDetailModal(result) {
  selectedResult.value = result
  showDetailModal.value = true
  await loadEvidence(result.id)
}

async function loadEvidence(resultId) {
  loadingEvidence.value = true
  try {
    evidenceList.value = await getEvidenceByResult(resultId)
  } catch (error) {
    console.error('Error loading evidence:', error)
    evidenceList.value = []
  } finally {
    loadingEvidence.value = false
  }
}

async function handleValidateEvidence(evidence, isValid) {
  const verifiedBy = localStorage.getItem('verifier_name') || prompt('Tu nombre:')
  if (!verifiedBy) return
  
  localStorage.setItem('verifier_name', verifiedBy)
  
  try {
    await validateEvidence(evidence.id, {
      is_valid: isValid,
      validated_by: verifiedBy,
      validation_notes: isValid ? 'Aprobado manualmente' : 'Rechazado manualmente'
    })
    await loadEvidence(selectedResult.value.id)
  } catch (error) {
    console.error('Error validating evidence:', error)
    alert('Error: ' + (error.response?.data?.detail || error.message))
  }
}

function getSourceTypeLabel(type) {
  const labels = {
    'main_page': '🏠 Página Principal',
    'subpage': '📄 Subpágina',
    'pdf': '📕 PDF',
    'social_media': '📱 Red Social',
    'news': '📰 Noticias',
    'government': '🏛️ Gobierno',
    'registry': '📋 Registro',
    'search_result': '🔍 Búsqueda',
    'description': '📝 Descripción',
    'other': '📎 Otro'
  }
  return labels[type] || type
}

function closeDetailModal() {
  showDetailModal.value = false
  selectedResult.value = null
}

async function approveResult() {
  if (!verifyForm.value.verified_by) return
  
  localStorage.setItem('verifier_name', verifyForm.value.verified_by)
  
  try {
    await verifyVennResult(selectedResult.value.id, {
      verification_status: 'verified',
      verified_by: verifyForm.value.verified_by,
      verification_notes: verifyForm.value.verification_notes || null,
      corrected_value: verifyForm.value.corrected_value
    })
    closeVerifyModal()
    await Promise.all([loadData(), loadStats()])
  } catch (error) {
    console.error('Error verifying result:', error)
    alert('Error al verificar: ' + (error.response?.data?.detail || error.message))
  }
}

async function rejectResult() {
  if (!verifyForm.value.verified_by) {
    alert('Por favor, ingresa tu nombre')
    return
  }
  
  localStorage.setItem('verifier_name', verifyForm.value.verified_by)
  
  try {
    await verifyVennResult(selectedResult.value.id, {
      verification_status: 'rejected',
      verified_by: verifyForm.value.verified_by,
      verification_notes: verifyForm.value.verification_notes || null
    })
    closeVerifyModal()
    await Promise.all([loadData(), loadStats()])
  } catch (error) {
    console.error('Error rejecting result:', error)
    alert('Error al rechazar: ' + (error.response?.data?.detail || error.message))
  }
}

async function bulkVerify(status) {
  const verifiedBy = prompt('Tu nombre:')
  if (!verifiedBy) return
  
  localStorage.setItem('verifier_name', verifiedBy)
  
  try {
    await bulkVerifyVennResults(selectedRows.value, status, verifiedBy)
    await Promise.all([loadData(), loadStats()])
  } catch (error) {
    console.error('Error in bulk verify:', error)
    alert('Error: ' + (error.response?.data?.detail || error.message))
  }
}

// Helpers
function getRowClass(row) {
  return {
    'row-pending': row.verification_status === 'pending',
    'row-verified': row.verification_status === 'verified',
    'row-rejected': row.verification_status === 'rejected'
  }
}

function getStatusLabel(status) {
  const labels = {
    pending: '⏳ Pendiente',
    verified: '✅ Verificado',
    rejected: '❌ Rechazado',
    modified: '✏️ Modificado'
  }
  return labels[status] || status
}

function getSourceLabel(source) {
  const labels = {
    manual: '👤 Manual',
    automatic: '🤖 Automático',
    mixed: '🔀 Mixto'
  }
  return labels[source] || source
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('es-CO')
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('es-CO')
}

function truncateUrl(url) {
  if (!url) return ''
  try {
    const parsed = new URL(url)
    return parsed.hostname + (parsed.pathname.length > 20 ? parsed.pathname.substring(0, 20) + '...' : parsed.pathname)
  } catch {
    return url.substring(0, 40) + '...'
  }
}

// Lifecycle
onMounted(async () => {
  await Promise.all([loadFilters(), loadStats()])
  await loadData()
})
</script>

<style scoped>
.venn-results-view {
  padding: 1rem;
  max-width: 1600px;
  margin: 0 auto;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: var(--shadow);
}

.summary-card.pending { border-left: 4px solid #f59e0b; }
.summary-card.verified { border-left: 4px solid #10b981; }
.summary-card.rejected { border-left: 4px solid #ef4444; }

.summary-icon {
  font-size: 2rem;
}

.summary-content {
  display: flex;
  flex-direction: column;
}

.summary-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text);
}

.summary-label {
  font-size: 0.875rem;
  color: var(--text-muted);
}

.verification-progress {
  padding: 1rem;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.progress-percent {
  color: var(--colombia-yellow);
  font-weight: 700;
}

.progress-bar-container {
  background: var(--border);
  border-radius: 4px;
  height: 8px;
  overflow: hidden;
}

.progress-bar {
  background: linear-gradient(90deg, var(--colombia-yellow), var(--colombia-blue));
  height: 100%;
  transition: width 0.3s ease;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.bulk-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  background: var(--colombia-blue);
  color: white;
}

.selected-count {
  font-weight: 600;
}

.bulk-buttons {
  display: flex;
  gap: 0.5rem;
}

.table-container {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th,
.table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.table th {
  background: var(--bg-secondary);
  font-weight: 600;
  font-size: 0.875rem;
}

.row-pending { background: rgba(245, 158, 11, 0.05); }
.row-verified { background: rgba(16, 185, 129, 0.05); }
.row-rejected { background: rgba(239, 68, 68, 0.05); }

.variable-badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: var(--colombia-blue);
  color: white;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-yes {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: #10b981;
  color: white;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
}

.badge-no {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: #ef4444;
  color: white;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
}

.original-value {
  display: block;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.source-badge {
  display: inline-block;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.source-automatic { background: #dbeafe; color: #1e40af; }
.source-manual { background: #fef3c7; color: #92400e; }
.source-mixed { background: #e0e7ff; color: #3730a3; }

.score-badge {
  display: inline-block;
  margin-left: 0.25rem;
  padding: 0.1rem 0.3rem;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.urls-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.url-link {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
  color: var(--colombia-blue);
  text-decoration: none;
}

.url-link:hover {
  text-decoration: underline;
}

.more-urls, .more-proxies {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.proxies-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.proxy-tag {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 0.7rem;
  color: var(--text);
}

.date-info {
  font-size: 0.8rem;
}

.verification-info {
  font-size: 0.8rem;
}

.status-badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-pending { background: #fef3c7; color: #92400e; }
.status-verified { background: #d1fae5; color: #065f46; }
.status-rejected { background: #fee2e2; color: #991b1b; }
.status-modified { background: #e0e7ff; color: #3730a3; }

.verified-by, .verified-at {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.action-buttons {
  display: flex;
  gap: 0.25rem;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--card-bg);
  border-radius: var(--radius);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.modal-content.modal-large {
  max-width: 900px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-muted);
}

.modal-body {
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border);
}

.verify-info {
  background: var(--bg-secondary);
  padding: 1rem;
  border-radius: var(--radius);
  margin-bottom: 1rem;
}

.verify-info p {
  margin: 0.5rem 0;
}

.verify-urls, .verify-proxies {
  margin-bottom: 1rem;
}

.verify-urls h4, .verify-proxies h4 {
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.verify-urls ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.verify-urls li {
  padding: 0.25rem 0;
}

.verify-urls a {
  color: var(--colombia-blue);
  word-break: break-all;
  font-size: 0.85rem;
}

.proxy-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

.detail-section {
  margin-bottom: 1.5rem;
}

.detail-section h4 {
  font-size: 1rem;
  margin-bottom: 0.75rem;
  color: var(--colombia-blue);
}

.detail-section dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem 1rem;
}

.detail-section dt {
  font-weight: 500;
  color: var(--text-muted);
}

.detail-section dd {
  margin: 0;
}

.url-list-detail {
  list-style: none;
  padding: 0;
  margin: 0;
}

.url-list-detail li {
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
}

.url-link-detail {
  color: var(--colombia-blue);
  word-break: break-all;
  font-size: 0.9rem;
}

.proxy-tags-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.proxy-tag-large {
  display: inline-block;
  padding: 0.4rem 0.8rem;
  background: var(--colombia-blue);
  color: white;
  border-radius: 4px;
  font-size: 0.875rem;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 3rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border);
  border-top-color: var(--colombia-yellow);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.mb-3 { margin-bottom: 1rem; }
.mb-0 { margin-bottom: 0; }
.text-center { text-align: center; }
.text-muted { color: var(--text-muted); }
.gap-2 { gap: 0.5rem; }
.flex { display: flex; }

.btn-success {
  background: #10b981;
  color: white;
}

.btn-success:hover {
  background: #059669;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

/* Evidence Panel Styles */
.evidence-section {
  border-top: 2px solid var(--colombia-yellow);
  padding-top: 1rem;
}

.loading-evidence {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  color: var(--text-muted);
}

.spinner-small {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--colombia-yellow);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.no-evidence {
  padding: 1rem;
  text-align: center;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border-radius: var(--radius);
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.evidence-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  transition: border-color 0.2s;
}

.evidence-card:hover {
  border-color: var(--colombia-blue);
}

.evidence-card.evidence-invalid {
  opacity: 0.6;
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.evidence-source {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.source-type-badge {
  display: inline-block;
  padding: 0.2rem 0.5rem;
  background: var(--colombia-blue);
  color: white;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.evidence-url {
  color: var(--colombia-blue);
  font-size: 0.85rem;
  text-decoration: none;
}

.evidence-url:hover {
  text-decoration: underline;
}

.validation-valid {
  color: #10b981;
  font-weight: 600;
  font-size: 0.85rem;
}

.validation-invalid {
  color: #ef4444;
  font-weight: 600;
  font-size: 0.85rem;
}

.evidence-fragment {
  margin-bottom: 0.75rem;
}

.evidence-fragment strong {
  display: block;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.25rem;
}

.fragment-text {
  background: white;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.75rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--text);
  font-style: italic;
  max-height: 150px;
  overflow-y: auto;
}

.matched-highlight {
  margin-top: 0.5rem;
  font-size: 0.85rem;
}

.matched-highlight mark {
  background: var(--colombia-yellow);
  padding: 0.1rem 0.3rem;
  border-radius: 2px;
}

.evidence-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.meta-item {
  font-size: 0.75rem;
  color: var(--text-muted);
  background: rgba(0, 0, 0, 0.05);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.evidence-selector {
  margin-bottom: 0.75rem;
}

.evidence-selector code {
  display: block;
  background: #1e293b;
  color: #94a3b8;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  overflow-x: auto;
  white-space: nowrap;
}

.evidence-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.mb-2 { margin-bottom: 0.5rem; }
</style>
