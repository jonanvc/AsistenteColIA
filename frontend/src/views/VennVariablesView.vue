<!--
  Venn Variables View - CRUD for Venn variables and their proxies
  Define variables for Venn diagrams and configure proxy search terms
-->
<template>
  <div class="venn-variables-view">
    <h1 class="mb-3">🔬 Variables y Proxies para Diagramas Venn</h1>

    <div class="info-banner card">
      <p>
        <strong>📊 Configuración de Variables:</strong> Define las variables que se utilizarán en los diagramas de Venn.
        Cada variable puede tener múltiples "proxies" que son términos o patrones de búsqueda usados durante el scraping
        para detectar la presencia de esa variable en una organización.
      </p>
    </div>

    <!-- Actions bar -->
    <div class="card">
      <div class="flex justify-between items-center flex-wrap gap-2">
        <button @click="showAddForm = !showAddForm" class="btn btn-primary">
          {{ showAddForm ? '✕ Cancelar' : '➕ Nueva Variable' }}
        </button>
        <div class="flex gap-2">
          <select v-model="filterCategory" class="form-control" style="width: 180px;">
            <option value="">Todas las categorías</option>
            <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
          </select>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="🔍 Buscar..."
            class="form-control"
            style="width: 200px;"
          />
        </div>
      </div>
    </div>

    <!-- Add/Edit Variable form -->
    <div v-if="showAddForm || editingVariable" class="card">
      <h2 class="card-title mb-2">
        {{ editingVariable ? '✏️ Editar Variable' : '➕ Nueva Variable' }}
      </h2>
      <form @submit.prevent="saveVariable">
        <div class="grid grid-3">
          <div class="form-group">
            <label class="form-label">Nombre *</label>
            <input
              v-model="variableForm.name"
              type="text"
              class="form-control"
              required
              placeholder="Ej: Sostenibilidad"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Código *</label>
            <input
              v-model="variableForm.code"
              type="text"
              class="form-control"
              required
              placeholder="Ej: SOST"
              maxlength="20"
            />
            <small class="text-muted">Código único para identificar la variable</small>
          </div>
          <div class="form-group">
            <label class="form-label">Categoría</label>
            <input
              v-model="variableForm.category"
              type="text"
              class="form-control"
              list="categories-list"
              placeholder="Ej: Ambiental"
            />
            <datalist id="categories-list">
              <option v-for="cat in categories" :key="cat" :value="cat" />
            </datalist>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Descripción</label>
          <textarea
            v-model="variableForm.description"
            class="form-control"
            rows="2"
            placeholder="Descripción de qué representa esta variable..."
          ></textarea>
        </div>
        <div class="grid grid-2">
          <div class="form-group">
            <label class="form-label">Color (para visualización)</label>
            <div class="flex gap-2 items-center">
              <input
                v-model="variableForm.color"
                type="color"
                class="form-control"
                style="width: 50px; height: 38px; padding: 2px;"
              />
              <input
                v-model="variableForm.color"
                type="text"
                class="form-control"
                placeholder="#3498db"
                style="flex: 1;"
              />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Peso (importancia)</label>
            <input
              v-model.number="variableForm.weight"
              type="number"
              min="0"
              max="100"
              step="0.1"
              class="form-control"
              placeholder="1.0"
            />
          </div>
        </div>

        <div class="flex gap-2 mt-3">
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? '⏳ Guardando...' : '💾 Guardar Variable' }}
          </button>
          <button type="button" @click="cancelEdit" class="btn btn-outline">
            Cancelar
          </button>
        </div>
      </form>
    </div>

    <!-- Variables list -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
    </div>

    <div v-else-if="filteredVariables.length === 0" class="card">
      <div class="alert alert-info">
        {{ searchQuery || filterCategory ? 'No se encontraron variables con ese criterio' : 'No hay variables definidas. Crea tu primera variable.' }}
      </div>
    </div>

    <div v-else class="variables-container">
      <div v-for="variable in filteredVariables" :key="variable.id" class="variable-card card">
        <div class="variable-header">
          <div class="variable-title">
            <span class="color-indicator" :style="{ background: variable.color || '#007bff' }"></span>
            <div>
              <h3>{{ variable.name }}</h3>
              <span class="variable-code">{{ variable.code }}</span>
            </div>
          </div>
          <div class="variable-actions">
            <button @click="editVariable(variable)" class="btn-icon" title="Editar variable">✏️</button>
            <button @click="confirmDeleteVariable(variable)" class="btn-icon" title="Eliminar variable">🗑️</button>
          </div>
        </div>

        <p v-if="variable.description" class="text-muted" style="font-size: 0.85rem; margin: 0.5rem 0;">
          {{ variable.description }}
        </p>

        <div class="variable-meta">
          <span v-if="variable.category" class="badge badge-category">{{ variable.category }}</span>
          <span v-if="variable.weight" class="badge badge-weight">Peso: {{ variable.weight }}</span>
          <span class="badge badge-proxies">{{ variable.proxies?.length || 0 }} proxies</span>
        </div>

        <!-- Proxies section -->
        <div class="proxies-section">
          <div class="proxies-header">
            <h4>🔍 Proxies de Búsqueda</h4>
            <button
              @click="showAddProxy(variable)"
              class="btn btn-outline"
              style="padding: 0.2rem 0.5rem; font-size: 0.8rem;"
            >
              ➕ Añadir Proxy
            </button>
          </div>

          <div v-if="!variable.proxies?.length" class="text-muted" style="font-size: 0.85rem; text-align: center; padding: 0.5rem;">
            Sin proxies configurados
          </div>

          <div v-else class="proxies-list">
            <div v-for="proxy in variable.proxies" :key="proxy.id" class="proxy-item">
              <div class="proxy-content">
                <span class="proxy-type" :class="'type-' + proxy.match_type">
                  {{ getMatchTypeLabel(proxy.match_type) }}
                </span>
                <span class="proxy-term">{{ proxy.search_term }}</span>
                <span v-if="proxy.weight !== 1" class="proxy-weight">×{{ proxy.weight }}</span>
              </div>
              <div class="proxy-actions">
                <button @click="editProxy(variable, proxy)" class="btn-icon" title="Editar">✏️</button>
                <button @click="deleteProxy(variable.id, proxy.id)" class="btn-icon" title="Eliminar">🗑️</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add/Edit Proxy Modal -->
    <div v-if="proxyModal.show" class="modal-overlay" @click="closeProxyModal">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>{{ proxyModal.editing ? '✏️ Editar Proxy' : '➕ Nuevo Proxy' }}</h3>
          <button @click="closeProxyModal" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Término de Búsqueda *</label>
            <input
              v-model="proxyModal.data.search_term"
              type="text"
              class="form-control"
              required
              placeholder="Ej: sostenible, eco-friendly, verde"
            />
            <small class="text-muted">El texto que se buscará en las páginas web</small>
          </div>
          <div class="grid grid-2">
            <div class="form-group">
              <label class="form-label">Tipo de Coincidencia</label>
              <select v-model="proxyModal.data.match_type" class="form-control">
                <option value="exact">Exacta</option>
                <option value="contains">Contiene</option>
                <option value="regex">Expresión Regular</option>
                <option value="fuzzy">Aproximada (Fuzzy)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Peso del Proxy</label>
              <input
                v-model.number="proxyModal.data.weight"
                type="number"
                min="0"
                max="10"
                step="0.1"
                class="form-control"
              />
              <small class="text-muted">Importancia relativa de este proxy</small>
            </div>
          </div>
          <div class="form-group">
            <label class="flex items-center gap-2">
              <input v-model="proxyModal.data.case_sensitive" type="checkbox" />
              <span>Distinguir mayúsculas/minúsculas</span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeProxyModal" class="btn btn-outline">Cancelar</button>
          <button @click="saveProxy" class="btn btn-primary" :disabled="!proxyModal.data.search_term">
            💾 Guardar
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Variable Confirmation -->
    <div v-if="deletingVariable" class="modal-overlay" @click="deletingVariable = null">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>⚠️ Confirmar Eliminación</h3>
          <button @click="deletingVariable = null" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
          <p>¿Eliminar la variable <strong>{{ deletingVariable.name }}</strong>?</p>
          <p class="text-muted">Se eliminarán también todos sus proxies asociados.</p>
        </div>
        <div class="modal-footer">
          <button @click="deletingVariable = null" class="btn btn-outline">Cancelar</button>
          <button @click="deleteVariable" class="btn btn-primary" style="background: #dc3545;">
            🗑️ Eliminar
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  getVennVariables,
  createVennVariable,
  updateVennVariable,
  deleteVennVariable,
  createVennProxy,
  updateVennProxy,
  deleteVennProxy
} from '../api'

// State
const loading = ref(false)
const saving = ref(false)
const showAddForm = ref(false)
const searchQuery = ref('')
const filterCategory = ref('')
const variables = ref([])
const editingVariable = ref(null)
const deletingVariable = ref(null)

// Form data
const defaultVariableForm = () => ({
  name: '',
  code: '',
  description: '',
  category: '',
  color: '#3498db',
  weight: 1.0
})

const variableForm = ref(defaultVariableForm())

// Proxy modal state
const proxyModal = ref({
  show: false,
  variableId: null,
  editing: null,
  data: {
    search_term: '',
    match_type: 'contains',
    weight: 1.0,
    case_sensitive: false
  }
})

// Computed
const categories = computed(() => {
  const cats = new Set()
  variables.value.forEach(v => {
    if (v.category) cats.add(v.category)
  })
  return Array.from(cats).sort()
})

const filteredVariables = computed(() => {
  let result = variables.value
  
  if (filterCategory.value) {
    result = result.filter(v => v.category === filterCategory.value)
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(v =>
      v.name.toLowerCase().includes(query) ||
      v.code.toLowerCase().includes(query) ||
      v.description?.toLowerCase().includes(query) ||
      v.proxies?.some(p => p.search_term.toLowerCase().includes(query))
    )
  }
  
  return result
})

// Methods
async function loadVariables() {
  loading.value = true
  try {
    variables.value = await getVennVariables()
  } catch (error) {
    console.error('Error loading variables:', error)
    alert('Error al cargar las variables')
  } finally {
    loading.value = false
  }
}

async function saveVariable() {
  saving.value = true
  try {
    if (editingVariable.value) {
      await updateVennVariable(editingVariable.value.id, variableForm.value)
    } else {
      await createVennVariable(variableForm.value)
    }
    await loadVariables()
    cancelEdit()
  } catch (error) {
    console.error('Error saving variable:', error)
    alert('Error al guardar la variable')
  } finally {
    saving.value = false
  }
}

function editVariable(variable) {
  editingVariable.value = variable
  variableForm.value = {
    name: variable.name,
    code: variable.code,
    description: variable.description || '',
    category: variable.category || '',
    color: variable.color || '#3498db',
    weight: variable.weight || 1.0
  }
  showAddForm.value = false
}

function cancelEdit() {
  editingVariable.value = null
  showAddForm.value = false
  variableForm.value = defaultVariableForm()
}

function confirmDeleteVariable(variable) {
  deletingVariable.value = variable
}

async function deleteVariable() {
  try {
    await deleteVennVariable(deletingVariable.value.id)
    await loadVariables()
    deletingVariable.value = null
  } catch (error) {
    console.error('Error deleting variable:', error)
    alert('Error al eliminar la variable')
  }
}

// Proxy methods
function showAddProxy(variable) {
  proxyModal.value = {
    show: true,
    variableId: variable.id,
    editing: null,
    data: {
      search_term: '',
      match_type: 'contains',
      weight: 1.0,
      case_sensitive: false
    }
  }
}

function editProxy(variable, proxy) {
  proxyModal.value = {
    show: true,
    variableId: variable.id,
    editing: proxy,
    data: {
      search_term: proxy.search_term,
      match_type: proxy.match_type,
      weight: proxy.weight,
      case_sensitive: proxy.case_sensitive
    }
  }
}

function closeProxyModal() {
  proxyModal.value.show = false
}

async function saveProxy() {
  try {
    if (proxyModal.value.editing) {
      await updateVennProxy(proxyModal.value.editing.id, proxyModal.value.data)
    } else {
      await createVennProxy(proxyModal.value.variableId, proxyModal.value.data)
    }
    await loadVariables()
    closeProxyModal()
  } catch (error) {
    console.error('Error saving proxy:', error)
    alert('Error al guardar el proxy')
  }
}

async function deleteProxy(variableId, proxyId) {
  if (!confirm('¿Eliminar este proxy?')) return
  try {
    await deleteVennProxy(proxyId)
    await loadVariables()
  } catch (error) {
    console.error('Error deleting proxy:', error)
    alert('Error al eliminar el proxy')
  }
}

function getMatchTypeLabel(type) {
  const labels = {
    exact: '=',
    contains: '∋',
    regex: '.*',
    fuzzy: '≈'
  }
  return labels[type] || type
}

// Lifecycle
onMounted(() => {
  loadVariables()
})
</script>

<style scoped>
/* Premium Dark Theme - Venn Variables */
.info-banner {
  background: rgba(91, 127, 255, 0.1);
  border: 1px solid rgba(91, 127, 255, 0.2);
  border-left: 4px solid #5B7FFF;
  border-radius: 12px;
  padding: 1rem 1.25rem;
}

.info-banner p {
  margin: 0;
  line-height: 1.5;
  color: #BABABD;
}

.variables-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 1.25rem;
}

.variable-card {
  padding: 1.25rem;
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  transition: all 0.25s ease;
}

.variable-card:hover {
  background: rgba(34, 34, 46, 0.8);
  transform: translateY(-2px);
  box-shadow: 0 0 40px rgba(91, 127, 255, 0.15);
}

.variable-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.variable-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.color-indicator {
  width: 12px;
  height: 40px;
  border-radius: 6px;
  box-shadow: 0 0 12px currentColor;
}

.variable-title h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #FFFFFF;
}

.variable-code {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.8rem;
  color: #8A8A9E;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
}

.variable-actions {
  display: flex;
  gap: 0.25rem;
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

.variable-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.5rem 0;
}

.badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  font-weight: 500;
}

.badge-category {
  background: rgba(91, 127, 255, 0.15);
  color: #8BA4FF;
}

.badge-weight {
  background: rgba(251, 191, 36, 0.15);
  color: #FBBF24;
}

.badge-proxies {
  background: rgba(52, 211, 153, 0.15);
  color: #34D399;
}

.proxies-section {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.proxies-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.proxies-header h4 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: #BABABD;
}

.proxies-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.proxy-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.proxy-item:hover {
  background: rgba(91, 127, 255, 0.1);
  border-color: rgba(91, 127, 255, 0.2);
}

.proxy-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.proxy-type {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.7rem;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

.type-exact { background: rgba(52, 211, 153, 0.2); color: #34D399; }
.type-contains { background: rgba(96, 165, 250, 0.2); color: #60A5FA; }
.type-regex { background: rgba(167, 139, 250, 0.2); color: #A78BFA; }
.type-fuzzy { background: rgba(251, 191, 36, 0.2); color: #FBBF24; }

.proxy-term {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  word-break: break-word;
  color: #BABABD;
}

.proxy-weight {
  font-size: 0.75rem;
  color: #5A5A6E;
}

.proxy-actions {
  display: flex;
  gap: 0.2rem;
}

.proxy-actions .btn-icon {
  font-size: 0.85rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 768px) {
  .grid-3 {
    grid-template-columns: 1fr;
  }
  
  .variables-container {
    grid-template-columns: 1fr;
  }
}
</style>
