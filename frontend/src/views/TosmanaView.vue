<!--
  Tosmana/QCA View - Truth Table for Qualitative Comparative Analysis
  Features:
  - Truth table with organizations as cases and Venn variables as conditions
  - Binary proxy values (0/1)
  - Export to CSV for Tosmana software
  - Color-coded cells for easy visual analysis
-->
<template>
  <div class="tosmana-view">
    <h1 class="mb-3">📊 Análisis QCA / Tosmana</h1>
    <p class="text-muted mb-3">
      Tabla de verdad para Análisis Comparativo Cualitativo (QCA).
      Cada fila es un caso (organización) y cada columna es una condición (variable Venn).
    </p>

    <!-- Stats -->
    <div class="stats-grid">
      <div class="stat-card yellow">
        <div class="stat-value">{{ stats.cases }}</div>
        <div class="stat-label">Casos (Organizaciones)</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-value">{{ stats.conditions }}</div>
        <div class="stat-label">Condiciones (Variables)</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value">{{ stats.configurations }}</div>
        <div class="stat-label">Configuraciones Únicas</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value">{{ stats.coverage }}%</div>
        <div class="stat-label">Cobertura de Datos</div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-3">
      <div class="card-header">
        <h2 class="card-title">🔧 Filtros</h2>
      </div>
      <div class="filters-grid">
        <div class="form-group mb-0">
          <label class="form-label">Alcance Territorial</label>
          <select v-model="filters.scope" class="form-control" @change="loadData">
            <option value="">Todos los alcances</option>
            <option value="MUNICIPAL">🏘️ Municipal</option>
            <option value="DEPARTAMENTAL">🏛️ Departamental</option>
            <option value="REGIONAL">🌎 Regional</option>
            <option value="NACIONAL">🇨🇴 Nacional</option>
            <option value="INTERNACIONAL">🌐 Internacional</option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Estado de Verificación</label>
          <select v-model="filters.verificationStatus" class="form-control" @change="loadData">
            <option value="">Todos</option>
            <option value="verified">✅ Solo Verificados</option>
            <option value="pending">⏳ Solo Pendientes</option>
          </select>
        </div>
        <div class="form-group mb-0">
          <label class="form-label">Mostrar</label>
          <select v-model="filters.showMode" class="form-control" @change="updateDisplay">
            <option value="binary">Binario (0/1)</option>
            <option value="symbols">Símbolos (✓/✗)</option>
            <option value="colors">Solo Colores</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="card mb-3">
      <div class="flex gap-2 flex-wrap">
        <button @click="loadData" class="btn btn-primary" :disabled="loading">
          {{ loading ? '⏳ Cargando...' : '🔄 Actualizar' }}
        </button>
        <button @click="exportCSV" class="btn btn-secondary" :disabled="!truthTable.length">
          📥 Exportar CSV (Tosmana)
        </button>
        <button @click="exportJSON" class="btn btn-outline" :disabled="!truthTable.length">
          📄 Exportar JSON
        </button>
        <button @click="showHelp = true" class="btn btn-outline">
          ❓ Ayuda QCA
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
    </div>

    <!-- Error -->
    <div v-if="error" class="alert alert-danger">
      {{ error }}
    </div>

    <!-- Truth Table -->
    <div v-if="!loading && truthTable.length" class="card">
      <div class="card-header">
        <h2 class="card-title">📋 Tabla de Verdad</h2>
        <span class="text-muted">
          {{ truthTable.length }} casos × {{ conditions.length }} condiciones
        </span>
      </div>
      
      <div class="table-container truth-table-container">
        <table class="table truth-table">
          <thead>
            <tr>
              <th class="case-header sticky-col">Caso (Organización)</th>
              <th class="scope-header">Alcance</th>
              <th 
                v-for="cond in conditions" 
                :key="cond.id" 
                class="condition-header"
                :title="cond.description || cond.name"
              >
                {{ truncateCondition(cond.name) }}
              </th>
              <th class="config-header">Configuración</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in truthTable" :key="row.id" :class="getRowClass(row)">
              <td class="case-cell sticky-col">
                <strong>{{ row.name }}</strong>
              </td>
              <td class="scope-cell">
                <span :class="'scope-badge scope-' + row.scope?.toLowerCase()">
                  {{ formatScope(row.scope) }}
                </span>
              </td>
              <td 
                v-for="cond in conditions" 
                :key="cond.id"
                :class="getCellClass(row.values[cond.id])"
                :title="getCellTooltip(row, cond)"
              >
                {{ formatValue(row.values[cond.id]) }}
              </td>
              <td class="config-cell">
                <code>{{ row.configuration }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Configuration Summary -->
    <div v-if="!loading && configurations.length" class="card">
      <div class="card-header">
        <h2 class="card-title">🔢 Resumen de Configuraciones</h2>
        <span class="text-muted">{{ configurations.length }} configuraciones únicas</span>
      </div>
      <div class="configurations-grid">
        <div 
          v-for="config in configurations" 
          :key="config.pattern" 
          class="config-card"
          :class="{ 'config-highlight': config.count > 1 }"
        >
          <div class="config-pattern">
            <code>{{ config.pattern }}</code>
          </div>
          <div class="config-count">
            {{ config.count }} caso{{ config.count !== 1 ? 's' : '' }}
          </div>
          <div class="config-cases">
            {{ config.cases.slice(0, 3).join(', ') }}
            <span v-if="config.cases.length > 3">
              +{{ config.cases.length - 3 }} más
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Help Modal -->
    <div v-if="showHelp" class="modal-overlay" @click.self="showHelp = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>❓ Guía de Análisis QCA</h3>
          <button @click="showHelp = false" class="close-btn">×</button>
        </div>
        <div class="modal-body">
          <h4>¿Qué es QCA?</h4>
          <p>
            El Análisis Comparativo Cualitativo (QCA) es un método para analizar 
            relaciones causales complejas usando lógica booleana.
          </p>
          
          <h4>Interpretación de la Tabla</h4>
          <ul>
            <li><strong>Casos (filas)</strong>: Cada organización es un caso</li>
            <li><strong>Condiciones (columnas)</strong>: Variables Venn como condiciones causales</li>
            <li><strong>1</strong>: La condición está presente</li>
            <li><strong>0</strong>: La condición está ausente</li>
            <li><strong>Configuración</strong>: Patrón binario único del caso</li>
          </ul>
          
          <h4>Usando Tosmana</h4>
          <ol>
            <li>Exporta los datos en CSV</li>
            <li>Abre Tosmana (software gratuito)</li>
            <li>Importa el archivo CSV</li>
            <li>Define tu variable outcome</li>
            <li>Ejecuta el análisis de minimización</li>
          </ol>
          
          <h4>Recursos</h4>
          <p>
            <a href="https://www.tosmana.net/" target="_blank">Descargar Tosmana</a> |
            <a href="https://compasss.org/" target="_blank">Recursos QCA (COMPASSS)</a>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getVennResults, getVennVariables, getOrganizations } from '../api.js'

// State
const loading = ref(true)
const error = ref(null)
const showHelp = ref(false)

const truthTable = ref([])
const conditions = ref([])
const configurations = ref([])

const filters = ref({
  scope: '',
  verificationStatus: '',
  showMode: 'binary'
})

// Stats
const stats = computed(() => {
  const uniqueConfigs = new Set(truthTable.value.map(r => r.configuration))
  const totalCells = truthTable.value.length * conditions.value.length
  const filledCells = truthTable.value.reduce((acc, row) => {
    return acc + Object.values(row.values).filter(v => v !== null && v !== undefined).length
  }, 0)
  
  return {
    cases: truthTable.value.length,
    conditions: conditions.value.length,
    configurations: uniqueConfigs.size,
    coverage: totalCells > 0 ? Math.round((filledCells / totalCells) * 100) : 0
  }
})

// Load data
const loadData = async () => {
  loading.value = true
  error.value = null
  
  try {
    // Load variables (conditions)
    const varsResult = await getVennVariables()
    conditions.value = varsResult || []
    
    // Load organizations (cases)
    const orgsResult = await getOrganizations()
    let organizations = orgsResult || []
    
    // Apply scope filter
    if (filters.value.scope) {
      organizations = organizations.filter(o => 
        o.territorial_scope === filters.value.scope
      )
    }
    
    // Load results
    const resultsResult = await getVennResults()
    const results = resultsResult || []
    
    // Apply verification filter
    let filteredResults = results
    if (filters.value.verificationStatus === 'verified') {
      filteredResults = results.filter(r => r.verification_status === 'verified')
    } else if (filters.value.verificationStatus === 'pending') {
      filteredResults = results.filter(r => r.verification_status === 'pending')
    }
    
    // Build truth table
    const resultMap = {}
    for (const r of filteredResults) {
      const key = `${r.organization_id}-${r.venn_variable_id}`
      resultMap[key] = r
    }
    
    truthTable.value = organizations.map(org => {
      const values = {}
      let configBits = ''
      
      for (const cond of conditions.value) {
        const key = `${org.id}-${cond.id}`
        const result = resultMap[key]
        values[cond.id] = result ? (result.value ? 1 : 0) : null
        configBits += result ? (result.value ? '1' : '0') : '-'
      }
      
      return {
        id: org.id,
        name: org.name,
        scope: org.territorial_scope,
        values,
        configuration: configBits
      }
    })
    
    // Calculate configurations summary
    const configMap = {}
    for (const row of truthTable.value) {
      if (!configMap[row.configuration]) {
        configMap[row.configuration] = { pattern: row.configuration, count: 0, cases: [] }
      }
      configMap[row.configuration].count++
      configMap[row.configuration].cases.push(row.name)
    }
    configurations.value = Object.values(configMap).sort((a, b) => b.count - a.count)
    
  } catch (err) {
    console.error('Error loading QCA data:', err)
    error.value = 'Error al cargar los datos: ' + err.message
  } finally {
    loading.value = false
  }
}

// Formatting helpers
const formatValue = (value) => {
  if (value === null || value === undefined) return '-'
  
  switch (filters.value.showMode) {
    case 'symbols':
      return value ? '✓' : '✗'
    case 'colors':
      return ''
    default:
      return value ? '1' : '0'
  }
}

const formatScope = (scope) => {
  const scopes = {
    'MUNICIPAL': '🏘️',
    'DEPARTAMENTAL': '🏛️',
    'REGIONAL': '🌎',
    'NACIONAL': '🇨🇴',
    'INTERNACIONAL': '🌐'
  }
  return scopes[scope] || scope || '-'
}

const truncateCondition = (name) => {
  return name.length > 15 ? name.substring(0, 12) + '...' : name
}

const getCellClass = (value) => {
  if (value === null || value === undefined) return 'cell-unknown'
  return value ? 'cell-true' : 'cell-false'
}

const getRowClass = (row) => {
  const hasAllTrue = Object.values(row.values).every(v => v === 1)
  const hasAllFalse = Object.values(row.values).every(v => v === 0)
  return {
    'row-all-true': hasAllTrue,
    'row-all-false': hasAllFalse
  }
}

const getCellTooltip = (row, cond) => {
  const value = row.values[cond.id]
  if (value === null) return `${row.name} - ${cond.name}: Sin datos`
  return `${row.name} - ${cond.name}: ${value ? 'Presente (1)' : 'Ausente (0)'}`
}

// Export functions
const exportCSV = () => {
  // Header
  let csv = 'Caso,' + conditions.value.map(c => `"${c.name}"`).join(',') + ',Configuracion\n'
  
  // Rows
  for (const row of truthTable.value) {
    const values = conditions.value.map(c => {
      const v = row.values[c.id]
      return v === null ? '' : v
    })
    csv += `"${row.name}",${values.join(',')},${row.configuration}\n`
  }
  
  // Download
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `qca_truth_table_${new Date().toISOString().split('T')[0]}.csv`
  link.click()
}

const exportJSON = () => {
  const data = {
    metadata: {
      exported_at: new Date().toISOString(),
      cases: truthTable.value.length,
      conditions: conditions.value.length
    },
    conditions: conditions.value,
    truth_table: truthTable.value,
    configurations: configurations.value
  }
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `qca_data_${new Date().toISOString().split('T')[0]}.json`
  link.click()
}

const updateDisplay = () => {
  // Just re-render by triggering reactivity
  truthTable.value = [...truthTable.value]
}

// Lifecycle
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.tosmana-view {
  padding: 1rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 1rem;
  text-align: center;
  border-left: 4px solid;
}

.stat-card.yellow { border-color: var(--colombia-yellow); }
.stat-card.blue { border-color: var(--colombia-blue); }
.stat-card.green { border-color: #10b981; }
.stat-card.red { border-color: var(--colombia-red); }

.stat-value {
  font-size: 2rem;
  font-weight: bold;
}

.stat-label {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

/* Truth Table */
.truth-table-container {
  overflow-x: auto;
  max-height: 600px;
  overflow-y: auto;
}

.truth-table {
  font-size: 0.9rem;
  border-collapse: collapse;
}

.truth-table th,
.truth-table td {
  padding: 0.5rem 0.75rem;
  text-align: center;
  border: 1px solid var(--border-color);
  white-space: nowrap;
}

.sticky-col {
  position: sticky;
  left: 0;
  background: var(--card-bg);
  z-index: 1;
  text-align: left !important;
}

.case-header, .case-cell {
  min-width: 200px;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.condition-header {
  min-width: 80px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  height: 100px;
  font-size: 0.8rem;
}

.scope-cell {
  min-width: 60px;
}

.scope-badge {
  display: inline-block;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

/* Cell colors */
.cell-true {
  background: rgba(16, 185, 129, 0.3);
  color: #059669;
  font-weight: bold;
}

.cell-false {
  background: rgba(239, 68, 68, 0.2);
  color: #dc2626;
}

.cell-unknown {
  background: rgba(156, 163, 175, 0.2);
  color: var(--text-muted);
}

.config-cell {
  font-family: monospace;
  font-size: 0.8rem;
  background: rgba(0, 0, 0, 0.05);
}

/* Row highlighting */
.row-all-true {
  background: rgba(16, 185, 129, 0.1);
}

.row-all-false {
  background: rgba(239, 68, 68, 0.05);
}

/* Configurations Summary */
.configurations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  padding: 1rem;
}

.config-card {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid var(--border-color);
}

.config-highlight {
  border-color: var(--colombia-blue);
  background: rgba(0, 48, 135, 0.05);
}

.config-pattern {
  font-family: monospace;
  font-size: 1.2rem;
  margin-bottom: 0.5rem;
}

.config-count {
  font-weight: bold;
  color: var(--colombia-blue);
}

.config-cases {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}

/* Modal */
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
  border-radius: 12px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-body {
  padding: 1.5rem;
}

.modal-body h4 {
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: var(--colombia-blue);
}

.modal-body ul, .modal-body ol {
  margin-left: 1.5rem;
  margin-bottom: 1rem;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-muted);
}

.close-btn:hover {
  color: var(--text-color);
}
</style>
