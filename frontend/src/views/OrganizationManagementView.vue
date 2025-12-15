<!--
  Organization Management View - CRUD for women-led peace organizations
  Colombia-focused with territorial scope selection via map
-->
<template>
  <div class="organization-management-view">
    <h1 class="page-title">👩 Gestión de Organizaciones</h1>
    <p class="text-muted mb-3">Administra organizaciones de mujeres constructoras de paz y sus enlaces</p>

    <!-- Stats -->
    <div class="stats-grid">
      <div class="stat-card yellow">
        <div class="stat-value">{{ organizations.length }}</div>
        <div class="stat-label">Total Organizaciones</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-value">{{ totalLinks }}</div>
        <div class="stat-label">Links Configurados</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value">{{ scopeCounts.nacional }}</div>
        <div class="stat-label">Cobertura Nacional</div>
      </div>
      <div class="stat-card orange">
        <div class="stat-value">{{ scopeCounts.regional }}</div>
        <div class="stat-label">Cobertura Regional</div>
      </div>
      <div class="stat-card purple">
        <div class="stat-value">{{ scopeCounts.internacional }}</div>
        <div class="stat-label">🌐 Internacional</div>
      </div>
    </div>

    <!-- Actions bar -->
    <div class="card">
      <div class="flex justify-between items-center flex-wrap gap-2">
        <div class="info-banner">
          <span class="info-icon">💡</span>
          <span>Las organizaciones se crean y validan desde el <router-link to="/chat" class="chat-link">Chat con el Asistente IA</router-link></span>
        </div>
        <div class="flex gap-2">
          <select v-model="filterScope" class="form-select" style="width: 180px;">
            <option value="">🌎 Todas las coberturas</option>
            <option value="municipal">🏘️ Municipal</option>
            <option value="departamental">🏛️ Departamental</option>
            <option value="regional">🌏 Regional</option>
            <option value="nacional">🇨🇴 Nacional</option>
            <option value="internacional">🌐 Internacional</option>
          </select>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="🔍 Buscar organizaciones..."
            class="form-control"
            style="width: 250px;"
          />
        </div>
      </div>
    </div>

    <!-- Edit form (only for editing existing organizations, not for creating new ones) -->
    <div v-if="editingOrganization" class="card form-card">
      <h2 class="card-title mb-2">
        ✏️ Editar Organización
      </h2>
      <form @submit.prevent="saveOrganization">
        <!-- Basic info -->
        <div class="grid grid-2">
          <div class="form-group">
            <label class="form-label">Nombre de la Organización *</label>
            <input
              v-model="formData.name"
              type="text"
              class="form-control"
              required
              placeholder="Ej: Colectivo de Mujeres por la Paz"
            />
          </div>
          <div class="form-group">
            <label class="form-label">URL Principal</label>
            <input
              v-model="formData.url"
              type="url"
              class="form-control"
              placeholder="https://ejemplo.com.co"
            />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Descripción</label>
          <textarea
            v-model="formData.description"
            class="form-control"
            rows="2"
            placeholder="Describe las actividades y propósito de la organización..."
          ></textarea>
        </div>

        <!-- New Organization Fields Section -->
        <div class="details-section mt-3">
          <h3 class="section-title">👩‍🌾 Datos de la Organización</h3>
          <p class="text-muted mb-2">Información adicional sobre la organización</p>
          
          <div class="grid grid-3">
            <div class="form-group">
              <label class="form-label">Años Activa</label>
              <input
                v-model.number="formData.years_active"
                type="number"
                class="form-control"
                min="0"
                placeholder="Ej: 15"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Número de Mujeres</label>
              <input
                v-model.number="formData.women_count"
                type="number"
                class="form-control"
                min="0"
                placeholder="Ej: 50"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Enfoque/Origen</label>
              <select v-model="formData.approach" class="form-select">
                <option value="unknown">❓ Desconocido</option>
                <option value="bottom_up">🌱 Desde abajo (comunitaria)</option>
                <option value="top_down">🏛️ Desde arriba (gubernamental)</option>
                <option value="mixed">🔄 Mixto</option>
              </select>
            </div>
          </div>
          
          <div class="grid grid-2 mt-2">
            <div class="form-group">
              <label class="form-label">Nombre del Líder</label>
              <input
                v-model="formData.leader_name"
                type="text"
                class="form-control"
                placeholder="Nombre del representante legal o líder"
              />
            </div>
            <div class="form-group">
              <label class="form-label">¿El líder es mujer?</label>
              <select v-model="formData.leader_is_woman" class="form-select">
                <option :value="null">No especificado</option>
                <option :value="true">Sí</option>
                <option :value="false">No</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Territorial Scope Section -->
        <div class="scope-section mt-3">
          <h3 class="section-title">🗺️ Cobertura Territorial</h3>
          <p class="text-muted mb-2">Selecciona el alcance geográfico de la organización</p>
          
          <div class="scope-selector">
            <div 
              class="scope-option" 
              :class="{ active: formData.territorial_scope === 'municipal' && !formData.is_international }"
              @click="!formData.is_international && (formData.territorial_scope = 'municipal')"
            >
              <span class="scope-option-icon">🏘️</span>
              <span class="scope-option-label">Municipal</span>
              <span class="scope-option-desc">Un municipio</span>
            </div>
            <div 
              class="scope-option" 
              :class="{ active: formData.territorial_scope === 'departamental' && !formData.is_international }"
              @click="!formData.is_international && (formData.territorial_scope = 'departamental')"
            >
              <span class="scope-option-icon">🏛️</span>
              <span class="scope-option-label">Departamental</span>
              <span class="scope-option-desc">Un departamento</span>
            </div>
            <div 
              class="scope-option" 
              :class="{ active: formData.territorial_scope === 'regional' && !formData.is_international }"
              @click="!formData.is_international && (formData.territorial_scope = 'regional')"
            >
              <span class="scope-option-icon">🌎</span>
              <span class="scope-option-label">Regional</span>
              <span class="scope-option-desc">Varios departamentos</span>
            </div>
            <div 
              class="scope-option" 
              :class="{ active: formData.territorial_scope === 'nacional' && !formData.is_international }"
              @click="!formData.is_international && (formData.territorial_scope = 'nacional')"
            >
              <span class="scope-option-icon">🇨🇴</span>
              <span class="scope-option-label">Nacional</span>
              <span class="scope-option-desc">Todo el país</span>
            </div>
            <div 
              class="scope-option" 
              :class="{ active: formData.is_international }"
              @click="formData.is_international = true; formData.territorial_scope = 'internacional'"
            >
              <span class="scope-option-icon">🌐</span>
              <span class="scope-option-label">Internacional</span>
              <span class="scope-option-desc">Alcance global</span>
            </div>
          </div>

          <!-- Department/Municipality Selection -->
          <div v-if="formData.territorial_scope !== 'nacional' && !formData.is_international" class="location-selection mt-3">
            <div class="grid grid-2">
              <div class="form-group">
                <label class="form-label">
                  {{ formData.territorial_scope === 'regional' ? 'Departamentos *' : 'Departamento *' }}
                </label>
                <select 
                  v-if="formData.territorial_scope !== 'regional'"
                  v-model="formData.department_code" 
                  class="form-select"
                  @change="onDepartmentChange"
                >
                  <option value="">Selecciona un departamento</option>
                  <option v-for="dept in departments" :key="dept.code" :value="dept.code">
                    {{ dept.name }}
                  </option>
                </select>
                <!-- Multi-select for regional -->
                <div v-else class="department-checkboxes">
                  <div v-for="dept in departments" :key="dept.code" class="checkbox-item">
                    <input 
                      type="checkbox" 
                      :id="'dept-' + dept.code"
                      :value="dept.code"
                      v-model="formData.department_codes"
                    />
                    <label :for="'dept-' + dept.code">{{ dept.name }}</label>
                  </div>
                </div>
              </div>
              
              <div class="form-group" v-if="formData.territorial_scope === 'municipal'">
                <label class="form-label">Municipio *</label>
                <select 
                  v-model="formData.municipality_code" 
                  class="form-select"
                  :disabled="!formData.department_code"
                >
                  <option value="">Selecciona un municipio</option>
                  <option v-for="mun in filteredMunicipalities" :key="mun.code" :value="mun.code">
                    {{ mun.name }}
                  </option>
                </select>
              </div>
            </div>
          </div>

          <!-- Interactive Map for location selection -->
          <div class="map-picker mt-3">
            <div class="flex justify-between items-center mb-2">
              <label class="form-label mb-0">📍 Ubicación en el Mapa (opcional)</label>
              <button type="button" @click="clearMapLocation" class="btn btn-sm btn-outline">
                🗑️ Limpiar
              </button>
            </div>
            <p class="text-muted" style="font-size: 0.85rem;">
              Haz clic en el mapa para seleccionar las coordenadas de la sede principal
            </p>
            <div ref="mapPickerContainer" class="map-picker-container"></div>
            <div v-if="formData.latitude && formData.longitude" class="coordinates-display">
              <span class="badge badge-primary">
                📍 {{ formData.latitude.toFixed(4) }}, {{ formData.longitude.toFixed(4) }}
              </span>
              <span v-if="selectedLocationName" class="badge badge-success ml-1">
                {{ selectedLocationName }}
              </span>
            </div>
          </div>
        </div>

        <!-- Links section -->
        <div class="links-section mt-3">
          <div class="flex justify-between items-center mb-2">
            <h3 class="section-title">🔗 Links para Scraping</h3>
            <button type="button" @click="addLink" class="btn btn-sm btn-accent">
              ➕ Añadir Link
            </button>
          </div>
          
          <div v-if="formData.links.length === 0" class="alert alert-info">
            No hay links configurados. Añade links para habilitar el scraping de datos.
          </div>

          <div v-for="(link, index) in formData.links" :key="index" class="link-item">
            <div class="grid grid-3 gap-2 items-end">
              <div class="form-group mb-0">
                <label class="form-label" style="font-size: 0.8rem;">URL del Link *</label>
                <input
                  v-model="link.url"
                  type="url"
                  class="form-control"
                  required
                  placeholder="https://..."
                />
              </div>
              <div class="form-group mb-0">
                <label class="form-label" style="font-size: 0.8rem;">Tipo</label>
                <select v-model="link.link_type" class="form-control">
                  <option value="main">🌐 Principal</option>
                  <option value="social">📱 Red Social</option>
                  <option value="data">📊 Datos</option>
                  <option value="registry">📋 Registro Oficial</option>
                  <option value="gov">🏛️ Gobierno</option>
                  <option value="other">📎 Otro</option>
                </select>
              </div>
              <div class="flex gap-1">
                <div class="form-group mb-0" style="flex: 1;">
                  <label class="form-label" style="font-size: 0.8rem;">Prioridad</label>
                  <input
                    v-model.number="link.priority"
                    type="number"
                    min="1"
                    max="10"
                    class="form-control"
                  />
                </div>
                <button
                  type="button"
                  @click="removeLink(index)"
                  class="btn-icon-delete"
                  title="Eliminar link"
                >
                  🗑️
                </button>
              </div>
            </div>
            <div class="form-group mt-1 mb-0">
              <input
                v-model="link.description"
                type="text"
                class="form-control"
                placeholder="Descripción del link (opcional)"
                style="font-size: 0.85rem;"
              />
            </div>
          </div>
        </div>

        <div class="flex gap-2 mt-3">
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? '⏳ Guardando...' : '💾 Guardar Organización' }}
          </button>
          <button type="button" @click="cancelEdit" class="btn btn-outline">
            Cancelar
          </button>
        </div>
      </form>
    </div>

    <!-- Organizations list -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">📋 Lista de Organizaciones</h2>
        <span class="badge badge-primary">{{ filteredOrganizations.length }} de {{ organizations.length }}</span>
      </div>

      <div v-if="loading" class="loading">
        <div class="spinner"></div>
      </div>

      <div v-else-if="filteredOrganizations.length === 0" class="alert alert-info">
        {{ searchQuery || filterScope ? 'No se encontraron organizaciones con ese criterio' : 'No hay organizaciones registradas.' }}
      </div>

      <div v-else class="organizations-grid">
        <div v-for="org in filteredOrganizations" :key="org.id" class="organization-card" :class="'scope-' + (org.is_international ? 'internacional' : ((org.territorial_scope || 'municipal').toLowerCase()))">
          <div class="organization-header">
            <div>
              <h3>{{ org.name }}</h3>
              <div class="scope-badge-container">
                <span class="badge" :class="getScopeBadgeClass(org.territorial_scope, org.is_international)">
                  {{ getScopeLabel(org.territorial_scope, org.is_international) }}
                </span>
                <span v-if="org.department_name && !org.is_international" class="badge badge-primary">
                  {{ org.department_name }}
                </span>
              </div>
            </div>
            <div class="organization-actions">
              <button @click="editOrganization(org)" class="btn-icon" title="Editar">
                ✏️
              </button>
              <button @click="confirmDelete(org)" class="btn-icon btn-icon-danger" title="Eliminar">
                🗑️
              </button>
            </div>
          </div>
          
          <p v-if="org.description" class="text-muted description">
            {{ truncate(org.description, 100) }}
          </p>

          <div class="organization-meta">
            <span v-if="org.url" class="meta-item">
              <a :href="org.url" target="_blank" rel="noopener">🔗 Sitio Web</a>
            </span>
            <span v-if="org.latitude && org.longitude" class="meta-item location">
              📍 {{ org.latitude.toFixed(4) }}, {{ org.longitude.toFixed(4) }}
            </span>
          </div>

          <!-- Links summary -->
          <div class="links-summary">
            <div class="links-header" @click="toggleLinks(org.id)">
              <span>🔗 {{ org.links?.length || 0 }} links para scraping</span>
              <span class="toggle-icon">{{ expandedLinks.includes(org.id) ? '▼' : '▶' }}</span>
            </div>
            <div v-if="expandedLinks.includes(org.id)" class="links-list">
              <div v-for="link in org.links" :key="link.id" class="link-preview">
                <span class="link-type-badge" :class="'type-' + link.link_type">
                  {{ getLinkTypeLabel(link.link_type) }}
                </span>
                <a :href="link.url" target="_blank" rel="noopener" class="link-url">
                  {{ truncate(link.url, 40) }}
                </a>
                <span v-if="link.priority" class="link-priority">P{{ link.priority }}</span>
              </div>
              <div v-if="!org.links?.length" class="text-muted" style="font-size: 0.8rem;">
                Sin links configurados
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <div v-if="deletingOrganization" class="modal-overlay" @click="deletingOrganization = null">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>⚠️ Confirmar Eliminación</h3>
          <button @click="deletingOrganization = null" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
          <p>¿Estás seguro de que deseas eliminar la organización <strong>{{ deletingOrganization.name }}</strong>?</p>
          <p class="text-muted">Esta acción eliminará también todos los links asociados y no se puede deshacer.</p>
        </div>
        <div class="modal-footer">
          <button @click="deletingOrganization = null" class="btn btn-outline">Cancelar</button>
          <button @click="deleteOrganization" class="btn btn-danger">
            🗑️ Eliminar
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import OSM from 'ol/source/OSM'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import { Style, Fill, Stroke, Circle as CircleStyle, Icon } from 'ol/style'
import { fromLonLat, toLonLat } from 'ol/proj'
import {
  getOrganizationsWithLinks,
  createOrganizationWithLinks,
  updateOrganizationWithLinks,
  deleteOrganizationFull,
  getDepartments,
  getMunicipalities,
  findNearestMunicipality,
  reverseGeocode
} from '../api'

import 'ol/ol.css'

// Colombia constants
const COLOMBIA_CENTER = [-74.2973, 4.5709]
const COLOMBIA_ZOOM = 5.5

// Departments and municipalities - will be loaded from API
const departments = ref([])
const municipalities = ref([])
const loadingGeo = ref(false)

// State
const loading = ref(false)
const saving = ref(false)
const showAddForm = ref(false)
const searchQuery = ref('')
const filterScope = ref('')
const organizations = ref([])
const editingOrganization = ref(null)
const deletingOrganization = ref(null)
const expandedLinks = ref([])
const selectedLocationName = ref('')
const mapPickerContainer = ref(null)

// Map instance
let pickerMap = null
let markerLayer = null
let markerSource = null
let highlightLayer = null
let highlightSource = null

// Form data
const defaultFormData = () => ({
  name: '',
  url: '',
  description: '',
  latitude: null,
  longitude: null,
  territorial_scope: 'municipal',
  is_international: false,
  department_code: '',
  // New fields
  years_active: null,
  women_count: null,
  leader_is_woman: null,
  leader_name: '',
  approach: 'unknown',
  municipality_code: '',
  department_codes: [],
  links: []
})

const formData = ref(defaultFormData())

// Computed
const filteredOrganizations = computed(() => {
  let result = organizations.value
  
  if (filterScope.value) {
    if (filterScope.value === 'internacional') {
      result = result.filter(o => o.is_international)
    } else {
      result = result.filter(o => (o.territorial_scope || '').toLowerCase() === filterScope.value && !o.is_international)
    }
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(o =>
      o.name.toLowerCase().includes(query) ||
      o.description?.toLowerCase().includes(query) ||
      o.url?.toLowerCase().includes(query)
    )
  }
  
  return result
})

const filteredMunicipalities = computed(() => {
  if (!formData.value.department_code) return []
  return municipalities.value.filter(m => m.department_code === formData.value.department_code)
})

const totalLinks = computed(() => {
  return organizations.value.reduce((sum, o) => sum + (o.links?.length || 0), 0)
})

const scopeCounts = computed(() => {
  const counts = { municipal: 0, departamental: 0, regional: 0, nacional: 0, internacional: 0 }
  organizations.value.forEach(o => {
    if (o.is_international) {
      counts.internacional++
    } else {
      const scope = (o.territorial_scope || 'municipal').toLowerCase()
      counts[scope] = (counts[scope] || 0) + 1
    }
  })
  return counts
})

// Handler for international toggle
function onInternationalChange() {
  if (formData.value.is_international) {
    formData.value.territorial_scope = 'internacional'
    formData.value.department_code = ''
    formData.value.municipality_code = ''
    formData.value.department_codes = []
  } else {
    formData.value.territorial_scope = 'municipal'
  }
}

// Methods
async function loadGeographyData() {
  loadingGeo.value = true
  try {
    // Load departments
    const deptData = await getDepartments()
    departments.value = deptData.map(d => ({
      code: d.code,
      name: d.name,
      lat: d.lat,
      lon: d.lon
    }))
    console.log(`[Geo] Loaded ${departments.value.length} departments`)
  } catch (error) {
    console.error('Error loading geography data:', error)
  } finally {
    loadingGeo.value = false
  }
}

async function loadMunicipalitiesForDepartment(deptCode) {
  if (!deptCode) {
    municipalities.value = []
    return
  }
  try {
    const muniData = await getMunicipalities(deptCode)
    municipalities.value = muniData.map(m => ({
      code: m.code,
      name: m.name,
      department_code: m.department_code,
      lat: m.lat,
      lon: m.lon
    }))
    console.log(`[Geo] Loaded ${municipalities.value.length} municipalities for dept ${deptCode}`)
  } catch (error) {
    console.error('Error loading municipalities:', error)
    municipalities.value = []
  }
}

async function loadOrganizations() {
  loading.value = true
  try {
    organizations.value = await getOrganizationsWithLinks()
  } catch (error) {
    console.error('Error loading organizations:', error)
    organizations.value = []
  } finally {
    loading.value = false
  }
}

function initMapPicker() {
  if (!mapPickerContainer.value) return
  
  // Marker layer for clicked point
  markerSource = new VectorSource()
  markerLayer = new VectorLayer({
    source: markerSource,
    style: new Style({
      image: new CircleStyle({
        radius: 12,
        fill: new Fill({ color: '#CE1126' }),
        stroke: new Stroke({ color: 'white', width: 3 })
      })
    })
  })
  
  // Highlight layer for municipality area (larger circle)
  highlightSource = new VectorSource()
  highlightLayer = new VectorLayer({
    source: highlightSource,
    style: new Style({
      image: new CircleStyle({
        radius: 30,
        fill: new Fill({ color: 'rgba(0, 136, 204, 0.3)' }),
        stroke: new Stroke({ color: '#0088CC', width: 2 })
      })
    })
  })

  pickerMap = new Map({
    target: mapPickerContainer.value,
    layers: [
      new TileLayer({ source: new OSM() }),
      highlightLayer,
      markerLayer
    ],
    view: new View({
      center: fromLonLat(COLOMBIA_CENTER),
      zoom: COLOMBIA_ZOOM
    })
  })

  // Click handler for location selection
  pickerMap.on('click', async (event) => {
    const coords = toLonLat(event.coordinate)
    formData.value.longitude = coords[0]
    formData.value.latitude = coords[1]
    updateMarker(coords[1], coords[0])
    
    // Try to find municipality using Nominatim for precision, then match with our catalog
    try {
      // First try Nominatim for precise municipality and department name
      const geoResult = await reverseGeocode(coords[1], coords[0])
      
      if (geoResult && geoResult.municipality) {
        const municipalityName = geoResult.municipality.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        const departmentName = geoResult.department ? geoResult.department.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '') : ''
        
        // Load all municipalities to search
        const allMunis = await getMunicipalities()
        
        // Find matching municipalities by name
        const nameMatches = allMunis.filter(m => {
          const catalogName = m.name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
          return catalogName === municipalityName || catalogName.includes(municipalityName) || municipalityName.includes(catalogName)
        })
        
        let matchedMuni = null
        
        if (nameMatches.length === 1) {
          // Only one match, use it
          matchedMuni = nameMatches[0]
        } else if (nameMatches.length > 1 && departmentName) {
          // Multiple matches, disambiguate using department name
          matchedMuni = nameMatches.find(m => {
            const catalogDept = m.department_name.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            return catalogDept.includes(departmentName) || departmentName.includes(catalogDept)
          })
          // If no department match, find the nearest one by coordinates
          if (!matchedMuni) {
            matchedMuni = nameMatches.reduce((closest, current) => {
              const closestDist = Math.sqrt(Math.pow(closest.lat - coords[1], 2) + Math.pow(closest.lon - coords[0], 2))
              const currentDist = Math.sqrt(Math.pow(current.lat - coords[1], 2) + Math.pow(current.lon - coords[0], 2))
              return currentDist < closestDist ? current : closest
            })
          }
        } else if (nameMatches.length > 1) {
          // Multiple matches, no department info - use nearest by coordinates
          matchedMuni = nameMatches.reduce((closest, current) => {
            const closestDist = Math.sqrt(Math.pow(closest.lat - coords[1], 2) + Math.pow(closest.lon - coords[0], 2))
            const currentDist = Math.sqrt(Math.pow(current.lat - coords[1], 2) + Math.pow(current.lon - coords[0], 2))
            return currentDist < closestDist ? current : closest
          })
        }
        
        if (matchedMuni) {
          selectedLocationName.value = `${matchedMuni.name}, ${matchedMuni.department_name}`
          
          // Auto-select department
          if (formData.value.department_code !== matchedMuni.department_code) {
            formData.value.department_code = matchedMuni.department_code
            await loadMunicipalitiesForDepartment(matchedMuni.department_code)
          }
          
          // Auto-select municipality
          formData.value.municipality_code = matchedMuni.code
          highlightMunicipality(matchedMuni.lat, matchedMuni.lon)
          return
        }
      }
      
      // Fallback: use our nearest calculation
      const nearest = await findNearestMunicipality(coords[1], coords[0])
      if (nearest) {
        selectedLocationName.value = `${nearest.name}, ${nearest.department_name}`
        
        if (formData.value.department_code !== nearest.department_code) {
          formData.value.department_code = nearest.department_code
          await loadMunicipalitiesForDepartment(nearest.department_code)
        }
        
        formData.value.municipality_code = nearest.code
        highlightMunicipality(nearest.lat, nearest.lon)
      }
    } catch (err) {
      console.error('Error finding municipality:', err)
      // Fallback to local department search
      const dept = findNearestDepartment(coords[1], coords[0])
      if (dept) {
        selectedLocationName.value = dept.name
        if (!formData.value.department_code) {
          formData.value.department_code = dept.code
        }
      }
    }
  })
}

function updateMarker(lat, lon) {
  if (!markerSource) return
  markerSource.clear()
  
  const marker = new Feature({
    geometry: new Point(fromLonLat([lon, lat]))
  })
  markerSource.addFeature(marker)
}

function highlightMunicipality(lat, lon) {
  if (!highlightSource) return
  highlightSource.clear()
  
  // Create multiple concentric circles for a more visible area highlight
  const sizes = [40, 25, 15]
  const opacities = [0.15, 0.25, 0.35]
  
  sizes.forEach((size, index) => {
    const circle = new Feature({
      geometry: new Point(fromLonLat([lon, lat]))
    })
    circle.setStyle(new Style({
      image: new CircleStyle({
        radius: size,
        fill: new Fill({ color: `rgba(0, 102, 255, ${opacities[index]})` }),
        stroke: new Stroke({ 
          color: index === 0 ? 'rgba(0, 102, 255, 0.5)' : 'transparent', 
          width: 2 
        })
      })
    }))
    highlightSource.addFeature(circle)
  })
  
  // Zoom to the municipality
  if (pickerMap) {
    pickerMap.getView().animate({
      center: fromLonLat([lon, lat]),
      zoom: 10,
      duration: 500
    })
  }
}

function findNearestDepartment(lat, lon) {
  let nearest = null
  let minDist = Infinity
  
  departments.value.forEach(dept => {
    const dist = Math.sqrt(Math.pow(dept.lat - lat, 2) + Math.pow(dept.lon - lon, 2))
    if (dist < minDist) {
      minDist = dist
      nearest = dept
    }
  })
  
  return nearest
}

function clearMapLocation() {
  formData.value.latitude = null
  formData.value.longitude = null
  selectedLocationName.value = ''
  if (markerSource) markerSource.clear()
  if (highlightSource) highlightSource.clear()
}

function onDepartmentChange() {
  formData.value.municipality_code = ''
  const dept = departments.value.find(d => d.code === formData.value.department_code)
  if (dept && pickerMap) {
    pickerMap.getView().animate({
      center: fromLonLat([dept.lon, dept.lat]),
      zoom: 8,
      duration: 500
    })
  }
}

function addLink() {
  formData.value.links.push({
    url: '',
    link_type: 'main',
    description: '',
    priority: formData.value.links.length + 1
  })
}

function removeLink(index) {
  formData.value.links.splice(index, 1)
}

async function saveOrganization() {
  saving.value = true
  try {
    const data = {
      ...formData.value,
      links: formData.value.links.filter(l => l.url)
    }
    
    // Clean up based on scope and international status
    if (data.is_international) {
      data.department_code = null
      data.municipality_code = null
      data.department_codes = null
      data.territorial_scope = 'internacional'
    } else if (data.territorial_scope === 'nacional') {
      data.department_code = null
      data.municipality_code = null
      data.department_codes = null
    } else if (data.territorial_scope === 'regional') {
      data.department_code = null
      data.municipality_code = null
    } else if (data.territorial_scope === 'departamental') {
      data.municipality_code = null
      data.department_codes = null
    } else {
      data.department_codes = null
    }

    // Only allow editing existing organizations, not creating new ones
    if (editingOrganization.value) {
      await updateOrganizationWithLinks(editingOrganization.value.id, data)
    } else {
      // This should not happen anymore - organizations are created via chat
      alert('Las nuevas organizaciones se crean desde el chat con el asistente IA')
      return
    }

    await loadOrganizations()
    cancelEdit()
  } catch (error) {
    console.error('Error saving organization:', error)
    alert('Error al guardar la organización')
  } finally {
    saving.value = false
  }
}

function editOrganization(org) {
  editingOrganization.value = org
  formData.value = {
    name: org.name,
    url: org.url || '',
    description: org.description || '',
    latitude: org.latitude,
    longitude: org.longitude,
    territorial_scope: (org.territorial_scope || 'municipal').toLowerCase(),
    is_international: org.is_international || false,
    department_code: org.department_code || '',
    municipality_code: org.municipality_code || '',
    department_codes: org.department_codes || [],
    // New fields
    years_active: org.years_active || null,
    women_count: org.women_count || null,
    leader_is_woman: org.leader_is_woman,
    leader_name: org.leader_name || '',
    approach: (org.approach || 'unknown').toLowerCase(),
    links: (org.links || []).map(l => ({
      id: l.id,
      url: l.url,
      link_type: l.link_type,
      description: l.description || '',
      priority: l.priority
    }))
  }
  showAddForm.value = false
  
  // Update map if coordinates exist - wait for map to be initialized
  if (org.latitude && org.longitude) {
    // Wait longer to ensure map is fully initialized
    setTimeout(() => {
      if (pickerMap && markerSource) {
        updateMarker(org.latitude, org.longitude)
        pickerMap.getView().animate({
          center: fromLonLat([org.longitude, org.latitude]),
          zoom: 10,
          duration: 500
        })
      } else {
        // Retry if map not ready yet
        setTimeout(() => {
          if (pickerMap && markerSource) {
            updateMarker(org.latitude, org.longitude)
            pickerMap.getView().animate({
              center: fromLonLat([org.longitude, org.latitude]),
              zoom: 10,
              duration: 500
            })
          }
        }, 300)
      }
    }, 250)
  }
}

function cancelEdit() {
  editingOrganization.value = null
  showAddForm.value = false
  formData.value = defaultFormData()
  selectedLocationName.value = ''
  if (markerSource) markerSource.clear()
  if (pickerMap) {
    pickerMap.getView().animate({
      center: fromLonLat(COLOMBIA_CENTER),
      zoom: COLOMBIA_ZOOM,
      duration: 300
    })
  }
}

function confirmDelete(org) {
  deletingOrganization.value = org
}

async function deleteOrganization() {
  try {
    await deleteOrganizationFull(deletingOrganization.value.id)
    await loadOrganizations()
    deletingOrganization.value = null
  } catch (error) {
    console.error('Error deleting organization:', error)
    alert('Error al eliminar la organización')
  }
}

function toggleLinks(orgId) {
  const index = expandedLinks.value.indexOf(orgId)
  if (index >= 0) {
    expandedLinks.value.splice(index, 1)
  } else {
    expandedLinks.value.push(orgId)
  }
}

function getScopeBadgeClass(scope, isInternational = false) {
  if (isInternational) return 'badge-purple'
  const normalizedScope = scope?.toLowerCase() || 'municipal'
  const classes = {
    'municipal': 'badge-primary',
    'departamental': 'badge-success',
    'regional': 'badge-accent',
    'nacional': 'badge-danger',
    'internacional': 'badge-purple'
  }
  return classes[normalizedScope] || 'badge-primary'
}

function getScopeLabel(scope, isInternational = false) {
  if (isInternational) return '🌐 Internacional'
  const normalizedScope = scope?.toLowerCase() || 'municipal'
  const labels = {
    'municipal': '🏘️ Municipal',
    'departamental': '🏛️ Departamental',
    'regional': '🌎 Regional',
    'nacional': '🇨🇴 Nacional',
    'internacional': '🌐 Internacional'
  }
  return labels[normalizedScope] || '🏘️ Municipal'
}

function getLinkTypeLabel(type) {
  const labels = {
    main: '🌐 Principal',
    social: '📱 Social',
    data: '📊 Datos',
    registry: '📋 Registro',
    gov: '🏛️ Gobierno',
    other: '📎 Otro'
  }
  return labels[type] || type
}

function truncate(text, maxLength) {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

// Watch for department change to load municipalities
watch(() => formData.value.department_code, async (newDeptCode) => {
  if (newDeptCode) {
    await loadMunicipalitiesForDepartment(newDeptCode)
  } else {
    municipalities.value = []
  }
}, { immediate: false })

// Watch for municipality change to update map
watch(() => formData.value.municipality_code, (newMuniCode) => {
  if (newMuniCode && municipalities.value.length > 0) {
    const muni = municipalities.value.find(m => m.code === newMuniCode)
    if (muni && muni.lat && muni.lon) {
      // Update form coordinates
      formData.value.latitude = muni.lat
      formData.value.longitude = muni.lon
      
      // Update map marker and highlight
      updateMarker(muni.lat, muni.lon)
      highlightMunicipality(muni.lat, muni.lon)
      
      // Update display name
      const dept = departments.value.find(d => d.code === formData.value.department_code)
      selectedLocationName.value = `${muni.name}, ${dept?.name || ''}`
    }
  }
}, { immediate: false })

// Watch for form visibility to init map
watch([showAddForm, editingOrganization], ([show, editing]) => {
  if (show || editing) {
    setTimeout(() => initMapPicker(), 100)
  }
}, { immediate: false })

// Lifecycle
onMounted(async () => {
  await loadGeographyData()
  loadOrganizations()
})

onUnmounted(() => {
  if (pickerMap) {
    pickerMap.setTarget(null)
    pickerMap = null
  }
})
</script>

<style scoped>
/* Premium Dark Theme - Organization Management */
.organization-management-view {
  max-width: 1400px;
  margin: 0 auto;
}

/* Info Banner */
.info-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  background: linear-gradient(135deg, rgba(91, 127, 255, 0.15), rgba(139, 92, 246, 0.1));
  border: 1px solid rgba(91, 127, 255, 0.3);
  border-radius: 12px;
  color: #BABABD;
  font-size: 0.9rem;
}

.info-icon {
  font-size: 1.2rem;
}

.chat-link {
  color: #5B7FFF;
  font-weight: 600;
  text-decoration: none;
  transition: color 0.2s ease;
}

.chat-link:hover {
  color: #8B5CF6;
  text-decoration: underline;
}

.form-card {
  border-left: 4px solid #5B7FFF;
  background: rgba(26, 26, 36, 0.7);
}

.section-title {
  font-size: 1.1rem;
  color: #FFFFFF;
  font-weight: 600;
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Details Section (new fields) */
.details-section {
  background: rgba(91, 127, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 1.5rem;
  margin-top: 1rem;
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
}

.scope-section {
  background: rgba(91, 127, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 1.5rem;
  margin-top: 1rem;
}

.scope-selector {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}

.scope-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.25rem 1rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.25s ease;
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  text-align: center;
}

.scope-option:hover {
  border-color: #5B7FFF;
  background: rgba(255, 255, 255, 0.06);
  transform: translateY(-2px);
  box-shadow: 0 0 20px rgba(91, 127, 255, 0.15);
}

.scope-option.active {
  border-color: #5B7FFF;
  background: linear-gradient(135deg, rgba(91, 127, 255, 0.15), rgba(139, 92, 246, 0.1));
  box-shadow: 0 0 30px rgba(91, 127, 255, 0.2);
}

.scope-option-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  filter: drop-shadow(0 0 8px rgba(91, 127, 255, 0.3));
}

.scope-option-label {
  font-weight: 600;
  color: #FFFFFF;
  font-size: 0.95rem;
}

.scope-option-desc {
  font-size: 0.75rem;
  color: #5A5A6E;
  margin-top: 0.25rem;
}

.department-checkboxes {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  max-height: 200px;
  overflow-y: auto;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
}

.department-checkboxes label {
  color: #BABABD;
  font-size: 0.85rem;
}

.map-picker-container {
  width: 100%;
  height: 300px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.3);
}

.coordinates-display {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.5rem;
}

.organizations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 1.25rem;
}

.organization-card {
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 1.25rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;
}

.organization-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  border-radius: 16px 16px 0 0;
}

.organization-card.scope-municipal::before { background: linear-gradient(90deg, #5B7FFF, #8B5CF6); }
.organization-card.scope-departamental::before { background: linear-gradient(90deg, #34D399, #10B981); }
.organization-card.scope-regional::before { background: linear-gradient(90deg, #FBBF24, #F59E0B); }
.organization-card.scope-nacional::before { background: linear-gradient(90deg, #F87171, #EF4444); }
.organization-card.scope-internacional::before { background: linear-gradient(90deg, #8B5CF6, #7C3AED); }

.badge-purple {
  background: rgba(128, 0, 255, 0.15);
  color: #A78BFA;
}

.organization-card:hover {
  background: rgba(34, 34, 46, 0.8);
  box-shadow: 0 0 40px rgba(91, 127, 255, 0.15);
  transform: translateY(-2px);
  border-color: rgba(91, 127, 255, 0.2);
}

.organization-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.organization-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #FFFFFF;
}

.scope-badge-container {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}

.organization-actions {
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
  border-radius: 8px;
}

.btn-icon:hover {
  opacity: 1;
  background: rgba(91, 127, 255, 0.1);
}

.btn-icon-danger:hover {
  background: rgba(248, 113, 113, 0.1);
}

.btn-icon-delete {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
  font-size: 1rem;
  color: #F87171;
  align-self: flex-end;
  transition: all 0.2s;
  border-radius: 8px;
}

.btn-icon-delete:hover {
  background: rgba(248, 113, 113, 0.1);
}

.description {
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
  color: #BABABD;
}

.organization-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 0.5rem 0;
}

.meta-item {
  font-size: 0.85rem;
  color: #5A5A6E;
}

.meta-item a {
  color: #8BA4FF;
  text-decoration: none;
  font-weight: 500;
}

.meta-item a:hover {
  text-decoration: underline;
  color: #5B7FFF;
}

.meta-item.location {
  color: #FBBF24;
}

.links-summary {
  margin-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.75rem;
}

.links-header {
  display: flex;
  justify-content: space-between;
  cursor: pointer;
  font-size: 0.9rem;
  color: #BABABD;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
  border-radius: 8px;
  transition: all 0.2s;
}

.links-header:hover {
  background: rgba(91, 127, 255, 0.1);
  color: #FFFFFF;
}

.toggle-icon {
  color: #5A5A6E;
}

.links-list {
  margin-top: 0.5rem;
  padding-left: 0.5rem;
}

.link-preview {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.link-type-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 12px;
  font-size: 0.7rem;
  white-space: nowrap;
  font-weight: 500;
}

.type-main { background: rgba(91, 127, 255, 0.15); color: #8BA4FF; }
.type-social { background: rgba(217, 70, 239, 0.15); color: #D946EF; }
.type-data { background: rgba(52, 211, 153, 0.15); color: #34D399; }
.type-registry { background: rgba(251, 191, 36, 0.15); color: #FBBF24; }
.type-gov { background: rgba(96, 165, 250, 0.15); color: #60A5FA; }
.type-other { background: rgba(138, 138, 158, 0.15); color: #8A8A9E; }

.link-url {
  color: #8BA4FF;
  text-decoration: none;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-url:hover {
  text-decoration: underline;
  color: #5B7FFF;
}

.link-priority {
  background: rgba(255, 255, 255, 0.06);
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  color: #5A5A6E;
}

.link-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  transition: all 0.2s;
}

.link-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(91, 127, 255, 0.2);
}

.links-section {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 1rem;
  margin-top: 1rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 10, 15, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal {
  background: #12121A;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 1.5rem;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 60px rgba(91, 127, 255, 0.1);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.modal-header h3 {
  margin: 0;
  color: #FFFFFF;
}

.modal-body {
  color: #BABABD;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.btn-close {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #5A5A6E;
  transition: all 0.2s;
  padding: 0.25rem;
  border-radius: 8px;
}

.btn-close:hover {
  color: #FFFFFF;
  background: rgba(255, 255, 255, 0.1);
}

.grid-3 {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
}

/* International toggle styles */
.international-toggle {
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgba(128, 0, 255, 0.1) 0%, rgba(64, 0, 128, 0.1) 100%);
  border-radius: 12px;
  border: 1px solid rgba(128, 0, 255, 0.2);
}

.toggle-container {
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.toggle-container input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
  height: 0;
  width: 0;
}

.toggle-checkmark {
  position: relative;
  display: inline-block;
  width: 20px;
  height: 20px;
  background: #2A2A3C;
  border: 2px solid #8B5CF6;
  border-radius: 4px;
  margin-right: 0.5rem;
  transition: all 0.2s;
}

.toggle-container input:checked ~ .toggle-checkmark {
  background: #8B5CF6;
}

.toggle-checkmark:after {
  content: "";
  position: absolute;
  display: none;
  left: 6px;
  top: 2px;
  width: 5px;
  height: 10px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.toggle-container input:checked ~ .toggle-checkmark:after {
  display: block;
}

.toggle-label {
  font-weight: 600;
  color: #FFFFFF;
}

.scope-selector.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.stat-card.purple {
  background: linear-gradient(135deg, rgba(128, 0, 255, 0.15) 0%, rgba(64, 0, 128, 0.15) 100%);
  border-color: rgba(128, 0, 255, 0.3);
}

.stat-card.purple .stat-value {
  color: #A78BFA;
}

@media (max-width: 768px) {
  .scope-selector {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .grid-3 {
    grid-template-columns: 1fr;
  }
  
  .department-checkboxes {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .organizations-grid {
    grid-template-columns: 1fr;
  }
}
</style>
