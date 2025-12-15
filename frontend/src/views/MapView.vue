<!--
  Map View - OpenLayers map centered on Colombia
  Features:
  - Display organizations on Colombia map
  - Filter by territorial scope (municipal, departamental, regional, nacional)
  - Export to PDF, SVG, PNG, JPG
  - Colombian regions visualization
-->
<template>
  <div class="map-view">
    <h1 class="page-title">🇨🇴 Mapa de Colombia</h1>
    <p class="text-muted mb-3">Visualización de organizaciones en el territorio colombiano</p>

    <!-- Stats -->
    <div class="stats-grid">
      <div class="stat-card yellow">
        <div class="stat-value">{{ featureCount }}</div>
        <div class="stat-label">Organizaciones</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-value">{{ departmentCount }}</div>
        <div class="stat-label">Departamentos</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value">{{ regionCount }}</div>
        <div class="stat-label">Regiones</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value">{{ nationalCount }}</div>
        <div class="stat-label">Cobertura Nacional</div>
      </div>
    </div>

    <!-- Configuration panel -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">⚙️ Configuración del Mapa</h2>
      </div>
      
      <div class="grid grid-3">
        <div class="form-group">
          <label class="form-label">Tipo de visualización:</label>
          <select v-model="mapType" class="form-select" @change="updateMap">
            <option value="markers">🔵 Marcadores simples</option>
            <option value="choropleth">🎨 Coroplético (por cobertura)</option>
            <option value="regions">🗺️ Regiones naturales</option>
          </select>
        </div>
        
        <div class="form-group">
          <label class="form-label">Filtrar por cobertura:</label>
          <select v-model="filterScope" class="form-select" @change="updateMap">
            <option value="">Todas las coberturas</option>
            <option value="municipal">🏘️ Municipal</option>
            <option value="departamental">🏛️ Departamental</option>
            <option value="regional">🌎 Regional</option>
            <option value="nacional">🇨🇴 Nacional</option>
            <option value="internacional">🌐 Internacional</option>
          </select>
        </div>

        <div class="form-group" v-if="mapType === 'choropleth'">
          <label class="form-label">Variable para colorear:</label>
          <select v-model="selectedVariable" class="form-select" @change="updateMap">
            <option value="">Seleccionar variable</option>
            <option v-for="key in availableKeys" :key="key" :value="key">
              {{ key }}
            </option>
          </select>
        </div>
        
        <div class="form-group">
          <label class="form-label">🔵 Filtrar por Variable Venn:</label>
          <select v-model="selectedVennVariable" class="form-select" @change="onVennVariableChange">
            <option :value="null">Sin filtro Venn</option>
            <option v-for="v in vennVariables" :key="v.id" :value="v.id">
              {{ v.name }}
            </option>
          </select>
        </div>
      </div>

      <div class="flex gap-2 flex-wrap">
        <button @click="updateMap" class="btn btn-primary" :disabled="loading">
          {{ loading ? '⏳ Cargando...' : '🔄 Actualizar Mapa' }}
        </button>
        <button @click="centerOnColombia" class="btn btn-accent">
          🇨🇴 Centrar en Colombia
        </button>
        <button @click="toggleDepartments" class="btn btn-secondary">
          {{ showDepartments ? '🙈 Ocultar Dptos' : '👁️ Mostrar Dptos' }}
        </button>
      </div>
    </div>

    <!-- Error message -->
    <div v-if="error" class="alert alert-danger">
      {{ error }}
    </div>

    <!-- Map container -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">🗺️ Mapa Interactivo</h2>
        <div class="flex gap-2 items-center">
          <span class="badge badge-primary">{{ featureCount }} ubicaciones</span>
          <div class="export-buttons">
            <button @click="exportToPDF" class="btn-export btn-export-pdf" title="Exportar a PDF">
              📄 PDF
            </button>
            <button @click="exportToSVG" class="btn-export btn-export-svg" title="Exportar a SVG">
              🖼️ SVG
            </button>
            <button @click="exportToPNG" class="btn-export btn-export-png" title="Exportar a PNG">
              🖼️ PNG
            </button>
            <button @click="exportToJPG" class="btn-export btn-export-jpg" title="Exportar a JPG">
              📷 JPG
            </button>
          </div>
        </div>
      </div>
      <div ref="mapContainer" class="map-container"></div>
    </div>

    <!-- Colombian Regions Legend -->
    <div v-if="mapType === 'regions'" class="card">
      <div class="card-header">
        <h2 class="card-title">🌈 Regiones Naturales de Colombia</h2>
      </div>
      <div class="grid grid-3">
        <div class="region-card caribe" @click="zoomToRegion('caribe')">
          <h4>🏖️ Caribe</h4>
          <p class="text-muted">Costa norte, cultura vallenata</p>
        </div>
        <div class="region-card pacifico" @click="zoomToRegion('pacifico')">
          <h4>🌊 Pacífico</h4>
          <p class="text-muted">Biodiversidad, comunidades afro</p>
        </div>
        <div class="region-card andina" @click="zoomToRegion('andina')">
          <h4>⛰️ Andina</h4>
          <p class="text-muted">Cordilleras, zona cafetera</p>
        </div>
        <div class="region-card orinoquia" @click="zoomToRegion('orinoquia')">
          <h4>🐄 Orinoquía</h4>
          <p class="text-muted">Llanos orientales</p>
        </div>
        <div class="region-card amazonia" @click="zoomToRegion('amazonia')">
          <h4>🌳 Amazonía</h4>
          <p class="text-muted">Selva amazónica, pueblos indígenas</p>
        </div>
        <div class="region-card insular" @click="zoomToRegion('insular')">
          <h4>🏝️ Insular</h4>
          <p class="text-muted">San Andrés y Providencia</p>
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div v-if="mapType === 'choropleth' && selectedVariable" class="card">
      <div class="card-header">
        <h2 class="card-title">📊 Leyenda</h2>
      </div>
      <div class="legend">
        <div class="legend-item">
          <span class="legend-color" style="background: linear-gradient(135deg, #00A86B, #228B22);"></span>
          <span>Valor alto</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: linear-gradient(135deg, #40E0D0, #008B8B);"></span>
          <span>Valor medio-alto</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: linear-gradient(135deg, #FCD116, #FFB347);"></span>
          <span>Valor medio</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: linear-gradient(135deg, #FF6B35, #C71585);"></span>
          <span>Valor medio-bajo</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: linear-gradient(135deg, #CE1126, #a30d1d);"></span>
          <span>Valor bajo</span>
        </div>
      </div>
    </div>

    <!-- Venn Variable Legend -->
    <div v-if="colorByVenn && selectedVennVariable" class="card">
      <div class="card-header">
        <h2 class="card-title">🔵 Leyenda Variable Venn</h2>
        <span class="text-muted">{{ getSelectedVennVariableName() }}</span>
      </div>
      <div class="legend venn-legend">
        <div class="legend-item">
          <span class="legend-color" style="background: #10b981;"></span>
          <span>✓ Cumple la variable</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: #ef4444;"></span>
          <span>✗ No cumple la variable</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: #9ca3af;"></span>
          <span>? Sin datos</span>
        </div>
      </div>
      <div class="venn-stats">
        <span class="venn-stat positive">✓ {{ getVennCount(true) }} cumplen</span>
        <span class="venn-stat negative">✗ {{ getVennCount(false) }} no cumplen</span>
        <span class="venn-stat unknown">? {{ getVennCount(null) }} sin datos</span>
      </div>
    </div>

    <!-- Feature info popup -->
    <div v-if="selectedFeature" class="card feature-card">
      <div class="card-header">
        <h2 class="card-title">📍 {{ selectedFeature.name }}</h2>
        <button @click="selectedFeature = null" class="btn-close">✕</button>
      </div>
      <div class="feature-info">
        <div class="feature-badges mb-2">
          <span v-if="selectedFeature.scope" class="badge" :class="getScopeBadgeClass(selectedFeature.scope)">
            {{ getScopeLabel(selectedFeature.scope) }}
          </span>
          <span v-if="selectedFeature.department" class="badge badge-primary">
            {{ selectedFeature.department }}
          </span>
        </div>
        <p v-if="selectedFeature.description" class="mb-1">
          <strong>📝 Descripción:</strong> {{ selectedFeature.description }}
        </p>
        <p v-if="selectedFeature.url" class="mb-1">
          <strong>🔗 Web:</strong> 
          <a :href="selectedFeature.url" target="_blank" class="text-primary">{{ selectedFeature.url }}</a>
        </p>
        <div v-if="Object.keys(selectedFeature.variables || {}).length > 0" class="mt-2">
          <strong>📊 Variables:</strong>
          <ul class="feature-vars">
            <li v-for="(value, key) in selectedFeature.variables" :key="key">
              <span class="var-key">{{ key }}:</span> 
              <span class="var-value">{{ formatValue(value) }}</span>
            </li>
          </ul>
        </div>
        <div v-if="selectedFeature.vennSummary && selectedFeature.vennSummary.length > 0" class="mt-2">
          <strong>🔵 Variables Venn:</strong>
          <div class="venn-summary">
            <span 
              v-for="v in selectedFeature.vennSummary" 
              :key="v.id" 
              class="venn-item"
              :class="{ 'venn-true': v.value, 'venn-false': !v.value }"
            >
              {{ v.name }}: {{ v.value ? '✓' : '✗' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import OSM from 'ol/source/OSM'
import XYZ from 'ol/source/XYZ'
import GeoJSON from 'ol/format/GeoJSON'
import { Style, Fill, Stroke, Circle as CircleStyle, Text, Icon } from 'ol/style'
import { fromLonLat, toLonLat } from 'ol/proj'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import { getOrganizationsForMap, getMapLocations, getVariableKeys, getVennVariables, getVennResults } from '../api.js'

// Import OpenLayers CSS
import 'ol/ol.css'

// Colombia geographic constants
const COLOMBIA_CENTER = [-74.2973, 4.5709]  // [lon, lat]
const COLOMBIA_ZOOM = 5.5
const COLOMBIA_BOUNDS = {
  north: 13.4,
  south: -4.2,
  east: -66.8,
  west: -79.0
}

// Colombian regions for visualization
const REGIONS = {
  caribe: { center: [-74.5, 10.5], zoom: 7, color: '#40E0D0' },
  pacifico: { center: [-77.0, 4.0], zoom: 7, color: '#008B8B' },
  andina: { center: [-74.0, 5.5], zoom: 7, color: '#6F4E37' },
  orinoquia: { center: [-70.0, 5.0], zoom: 7, color: '#228B22' },
  amazonia: { center: [-72.0, 0.5], zoom: 7, color: '#00A86B' },
  insular: { center: [-81.7, 12.5], zoom: 9, color: '#FF6B35' }
}

// State
const mapContainer = ref(null)
const mapType = ref('markers')
const filterScope = ref('')
const selectedVariable = ref('')
const loading = ref(false)
const error = ref(null)
const featureCount = ref(0)
const departmentCount = ref(0)
const regionCount = ref(0)
const nationalCount = ref(0)
const showDepartments = ref(true)
const selectedFeature = ref(null)
const availableKeys = ref([])

// Venn Variables filter state
const vennVariables = ref([])
const selectedVennVariable = ref(null)
const colorByVenn = ref(false)
const vennResultsMap = ref({})

// Map instances
let map = null
let vectorLayer = null
let vectorSource = null
let departmentsLayer = null

// Colors for territorial scopes
const SCOPE_COLORS = {
  municipal: '#003893',
  departamental: '#008B8B',
  regional: '#FF6B35',
  nacional: '#CE1126',
  internacional: '#8B5CF6'
}

// Colors for Venn variable values
const VENN_COLORS = {
  true: '#10b981',    // Green for positive
  false: '#ef4444',   // Red for negative
  unknown: '#9ca3af'  // Gray for unknown
}

// Initialize map
const initMap = () => {
  if (!mapContainer.value) return

  // Create vector source and layer
  vectorSource = new VectorSource()
  vectorLayer = new VectorLayer({
    source: vectorSource,
    style: featureStyle
  })

  // Create map
  map = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({
        source: new OSM()
      }),
      vectorLayer
    ],
    view: new View({
      center: fromLonLat(COLOMBIA_CENTER),
      zoom: COLOMBIA_ZOOM,
      minZoom: 4,
      maxZoom: 18
    })
  })

  // Click handler
  map.on('click', (e) => {
    const feature = map.forEachFeatureAtPixel(e.pixel, f => f)
    if (feature) {
      const props = feature.getProperties()
      const orgId = props.organization_id
      
      // Build Venn summary for this organization
      const vennSummary = []
      if (orgId) {
        vennVariables.value.forEach(v => {
          const key = `${orgId}-${v.id}`
          if (vennResultsMap.value[key] !== undefined) {
            vennSummary.push({
              id: v.id,
              name: v.name,
              value: vennResultsMap.value[key]
            })
          }
        })
      }
      
      selectedFeature.value = {
        name: props.name || 'Sin nombre',
        description: props.description,
        url: props.url,
        scope: props.territorial_scope,
        department: props.department_name,
        variables: props.variables || {},
        vennSummary: vennSummary
      }
    } else {
      selectedFeature.value = null
    }
  })

  // Pointer cursor on features
  map.on('pointermove', (e) => {
    const hit = map.hasFeatureAtPixel(e.pixel)
    map.getTargetElement().style.cursor = hit ? 'pointer' : ''
  })
}

// Feature style function
const featureStyle = (feature) => {
  const props = feature.getProperties()
  const scope = (props.territorial_scope || 'municipal').toLowerCase()
  let color = SCOPE_COLORS[scope] || SCOPE_COLORS.municipal
  
  // Override color if colorByVenn is enabled
  if (colorByVenn.value && selectedVennVariable.value) {
    const orgId = props.organization_id
    const vennKey = `${orgId}-${selectedVennVariable.value}`
    const vennResult = vennResultsMap.value[vennKey]
    
    if (vennResult !== undefined) {
      color = vennResult ? VENN_COLORS.true : VENN_COLORS.false
    } else {
      color = VENN_COLORS.unknown
    }
  }
  
  let radius = 8
  if (scope === 'nacional') radius = 14
  else if (scope === 'regional') radius = 12
  else if (scope === 'departamental') radius = 10
  
  return new Style({
    image: new CircleStyle({
      radius: radius,
      fill: new Fill({ color: color }),
      stroke: new Stroke({ color: 'white', width: 2 })
    }),
    text: props.name ? new Text({
      text: props.name.length > 15 ? props.name.substring(0, 15) + '...' : props.name,
      offsetY: -20,
      font: '12px Poppins, sans-serif',
      fill: new Fill({ color: '#333' }),
      stroke: new Stroke({ color: 'white', width: 3 })
    }) : null
  })
}

// Load variable keys
const loadKeys = async () => {
  try {
    const response = await getVariableKeys()
    availableKeys.value = response.data || []
  } catch (err) {
    console.error('Error loading keys:', err)
  }
}

// Load Venn variables for filtering
const loadVennVariables = async () => {
  try {
    const response = await getVennVariables()
    vennVariables.value = response || []
  } catch (err) {
    console.error('Error loading Venn variables:', err)
  }
}

// Load Venn results to create a map for coloring
const loadVennResults = async () => {
  try {
    const results = await getVennResults({})
    const resultMap = {}
    results.forEach(r => {
      const key = `${r.organization_id}-${r.venn_variable_id}`
      resultMap[key] = r.value
    })
    vennResultsMap.value = resultMap
  } catch (err) {
    console.error('Error loading Venn results:', err)
  }
}

// Handle Venn variable change
const onVennVariableChange = async () => {
  if (selectedVennVariable.value) {
    colorByVenn.value = true
    await loadVennResults()
  } else {
    colorByVenn.value = false
  }
  // Force refresh styles
  if (vectorLayer) {
    vectorLayer.changed()
  }
}

// Update map data
const updateMap = async () => {
  if (!vectorSource) return
  
  loading.value = true
  error.value = null
  
  try {
    const params = {}
    if (filterScope.value) params.scope = filterScope.value
    if (selectedVariable.value) params.variable = selectedVariable.value
    
    const response = await getOrganizationsForMap(params)
    const organizations = response.data || []
    
    // Clear existing features
    vectorSource.clear()
    
    // Track stats
    const departments = new Set()
    const regions = new Set()
    let nationalCnt = 0
    
    // Add features
    organizations.forEach(org => {
      if (org.lat && org.lon) {
        // Determine scope based on is_international flag
        const effectiveScope = org.is_international ? 'internacional' : ((org.territorial_scope || 'municipal').toLowerCase())
        
        const feature = new Feature({
          geometry: new Point(fromLonLat([org.lon, org.lat])),
          organization_id: org.id,
          name: org.name,
          description: org.description,
          url: org.url,
          territorial_scope: effectiveScope,
          is_international: org.is_international,
          department_code: org.department_code,
          department_name: org.department_name,
          variables: org.variables || {}
        })
        vectorSource.addFeature(feature)
        
        // Stats
        if (org.department_code) departments.add(org.department_code)
        if (org.region) regions.add(org.region)
        if (effectiveScope === 'nacional') nationalCnt++
      }
    })
    
    featureCount.value = organizations.length
    departmentCount.value = departments.size
    regionCount.value = regions.size
    nationalCount.value = nationalCnt
    
  } catch (err) {
    console.error('Error updating map:', err)
    error.value = 'Error al cargar los datos del mapa'
  } finally {
    loading.value = false
  }
}

// Center on Colombia
const centerOnColombia = () => {
  if (!map) return
  map.getView().animate({
    center: fromLonLat(COLOMBIA_CENTER),
    zoom: COLOMBIA_ZOOM,
    duration: 800
  })
}

// Zoom to specific region
const zoomToRegion = (regionCode) => {
  const region = REGIONS[regionCode]
  if (!region || !map) return
  
  map.getView().animate({
    center: fromLonLat(region.center),
    zoom: region.zoom,
    duration: 800
  })
}

// Toggle departments visibility
const toggleDepartments = () => {
  showDepartments.value = !showDepartments.value
  if (departmentsLayer) {
    departmentsLayer.setVisible(showDepartments.value)
  }
}

// Get map canvas
const getMapCanvas = () => {
  return document.querySelector('.map-container canvas')
}

// Export to PDF
const exportToPDF = async () => {
  try {
    const canvas = getMapCanvas()
    if (!canvas) {
      alert('No se pudo capturar el mapa')
      return
    }

    const dataUrl = canvas.toDataURL('image/png')
    const dateStr = new Date().toLocaleDateString('es-CO')
    
    // Build HTML content for printing using array join to avoid Vue parsing issues
    const htmlParts = [
      '<!DOCTYPE html>',
      '<html>',
      '<head>',
      '<title>Mapa de Colombia - Organizaciones<\/title>',
      '<style>',
      'body { margin: 0; padding: 20px; font-family: Poppins, sans-serif; }',
      'h1 { color: #003893; border-bottom: 4px solid; border-image: linear-gradient(90deg, #FCD116, #003893, #CE1126) 1; padding-bottom: 10px; }',
      'img { max-width: 100%; border: 2px solid #ddd; border-radius: 8px; }',
      '.footer { margin-top: 20px; color: #666; font-size: 12px; }',
      '<\/style>',
      '<\/head>',
      '<body>',
      '<h1>🇨🇴 Mapa de Organizaciones - Colombia<\/h1>',
      '<p>Generado el ' + dateStr + '<\/p>',
      '<p><strong>Total organizaciones:<\/strong> ' + featureCount.value + '<\/p>',
      '<img src="' + dataUrl + '" alt="Mapa de Colombia">',
      '<div class="footer">',
      '<p>Proyecto Final IA - Visualización de Organizaciones Colombianas<\/p>',
      '<\/div>',
      '<script>window.onload = function() { window.print(); }<\/script>',
      '<\/body>',
      '<\/html>'
    ]
    
    const printWindow = window.open('', '_blank')
    printWindow.document.write(htmlParts.join('\n'))
    printWindow.document.close()
  } catch (err) {
    console.error('Error exporting to PDF:', err)
    alert('Error al exportar a PDF')
  }
}

// Export to SVG
const exportToSVG = () => {
  try {
    if (!vectorSource) return

    const features = vectorSource.getFeatures()
    if (features.length === 0) {
      alert('No hay datos para exportar')
      return
    }

    const svgWidth = 800
    const svgHeight = 600
    
    const extent = vectorSource.getExtent()
    const xScale = svgWidth / (extent[2] - extent[0])
    const yScale = svgHeight / (extent[3] - extent[1])
    const scale = Math.min(xScale, yScale) * 0.9

    let circles = ''
    features.forEach((feature) => {
      const geom = feature.getGeometry()
      if (geom) {
        const coords = geom.getCoordinates()
        const x = ((coords[0] - extent[0]) * scale) + 40
        const y = svgHeight - ((coords[1] - extent[1]) * scale) - 40
        const props = feature.getProperties()
        const scope = (props.territorial_scope || 'municipal').toLowerCase()
        const color = SCOPE_COLORS[scope] || SCOPE_COLORS.municipal
        const name = props.name || 'Sin nombre'
        
        circles += '<circle cx="' + x + '" cy="' + y + '" r="8" fill="' + color + '" stroke="white" stroke-width="2">'
        circles += '<title>' + name + '<\/title>'
        circles += '<\/circle>\n'
      }
    })

    const svgParts = [
      '<?xml version="1.0" encoding="UTF-8"?>',
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + svgWidth + '" height="' + svgHeight + '" viewBox="0 0 ' + svgWidth + ' ' + svgHeight + '">',
      '<defs>',
      '<linearGradient id="colombiaGradient" x1="0%" y1="0%" x2="100%" y2="0%">',
      '<stop offset="0%" style="stop-color:#FCD116"/>',
      '<stop offset="50%" style="stop-color:#003893"/>',
      '<stop offset="100%" style="stop-color:#CE1126"/>',
      '<\/linearGradient>',
      '<\/defs>',
      '<rect width="100%" height="100%" fill="#f5f7fa"/>',
      '<text x="20" y="35" font-family="Poppins, sans-serif" font-size="24" font-weight="bold" fill="#003893">',
      '🇨🇴 Mapa de Organizaciones - Colombia',
      '<\/text>',
      '<line x1="20" y1="45" x2="' + (svgWidth - 20) + '" y2="45" stroke="url(#colombiaGradient)" stroke-width="4"/>',
      '<g transform="translate(0, 60)">',
      circles,
      '<\/g>',
      '<g transform="translate(20, ' + (svgHeight - 80) + ')">',
      '<text font-family="Poppins, sans-serif" font-size="12" fill="#666">Leyenda:<\/text>',
      '<circle cx="80" cy="-3" r="6" fill="#003893"/><text x="92" y="2" font-size="10">Municipal<\/text>',
      '<circle cx="170" cy="-3" r="6" fill="#008B8B"/><text x="182" y="2" font-size="10">Departamental<\/text>',
      '<circle cx="280" cy="-3" r="6" fill="#FF6B35"/><text x="292" y="2" font-size="10">Regional<\/text>',
      '<circle cx="360" cy="-3" r="6" fill="#CE1126"/><text x="372" y="2" font-size="10">Nacional<\/text>',
      '<\/g>',
      '<\/svg>'
    ]
    
    const svgContent = svgParts.join('\n')
    downloadFile(svgContent, 'image/svg+xml', 'mapa-colombia-organizaciones', 'svg')
  } catch (err) {
    console.error('Error exporting to SVG:', err)
    alert('Error al exportar a SVG')
  }
}

// Export to PNG
const exportToPNG = () => {
  try {
    const canvas = getMapCanvas()
    if (!canvas) {
      alert('No se pudo capturar el mapa')
      return
    }

    canvas.toBlob((blob) => {
      if (blob) {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'mapa-colombia-organizaciones-' + new Date().toISOString().split('T')[0] + '.png'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
    }, 'image/png')
  } catch (err) {
    console.error('Error exporting to PNG:', err)
    alert('Error al exportar a PNG')
  }
}

// Export to JPG
const exportToJPG = () => {
  try {
    const canvas = getMapCanvas()
    if (!canvas) {
      alert('No se pudo capturar el mapa')
      return
    }

    // Create a white background canvas for JPG (JPG doesn't support transparency)
    const newCanvas = document.createElement('canvas')
    newCanvas.width = canvas.width
    newCanvas.height = canvas.height
    const ctx = newCanvas.getContext('2d')
    
    // Fill white background
    ctx.fillStyle = '#FFFFFF'
    ctx.fillRect(0, 0, newCanvas.width, newCanvas.height)
    
    // Draw original canvas
    ctx.drawImage(canvas, 0, 0)

    newCanvas.toBlob((blob) => {
      if (blob) {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'mapa-colombia-organizaciones-' + new Date().toISOString().split('T')[0] + '.jpg'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
    }, 'image/jpeg', 0.95)
  } catch (err) {
    console.error('Error exporting to JPG:', err)
    alert('Error al exportar a JPG')
  }
}

// Helper to download file
const downloadFile = (content, mimeType, baseName, extension) => {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = baseName + '-' + new Date().toISOString().split('T')[0] + '.' + extension
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// Helper functions
const getScopeBadgeClass = (scope) => {
  const classes = {
    municipal: 'badge-primary',
    departamental: 'badge-info',
    regional: 'badge-warning',
    nacional: 'badge-danger'
  }
  return classes[scope] || 'badge-primary'
}

const getScopeLabel = (scope) => {
  const labels = {
    municipal: '🏘️ Municipal',
    departamental: '🏛️ Departamental',
    regional: '🌎 Regional',
    nacional: '🇨🇴 Nacional'
  }
  return labels[scope] || scope
}

const formatValue = (value) => {
  if (typeof value === 'number') {
    return value.toLocaleString('es-CO')
  }
  return value
}

// Get selected Venn variable name
const getSelectedVennVariableName = () => {
  if (!selectedVennVariable.value) return ''
  const v = vennVariables.value.find(v => v.id === selectedVennVariable.value)
  return v ? v.name : ''
}

// Count organizations by Venn result
const getVennCount = (value) => {
  if (!selectedVennVariable.value || !vectorSource) return 0
  
  const features = vectorSource.getFeatures()
  let count = 0
  
  features.forEach(f => {
    const props = f.getProperties()
    const orgId = props.organization_id
    const vennKey = `${orgId}-${selectedVennVariable.value}`
    const vennResult = vennResultsMap.value[vennKey]
    
    if (value === null) {
      if (vennResult === undefined) count++
    } else if (vennResult === value) {
      count++
    }
  })
  
  return count
}

// Lifecycle
onMounted(async () => {
  initMap()
  await Promise.all([
    loadKeys(),
    loadVennVariables()
  ])
  updateMap()
})

onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
})
</script>

<style scoped>
/* Premium Dark Theme - Map View */
.map-view {
  max-width: 1400px;
  margin: 0 auto;
}

.map-container {
  width: 100%;
  height: 550px;
  border-radius: 16px;
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 0 40px rgba(0, 0, 0, 0.3);
}

.text-muted {
  color: #5A5A6E;
  font-size: 1rem;
}

.export-buttons {
  display: flex;
  gap: 0.5rem;
}

.btn-export {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-weight: 600;
}

.btn-export-pdf {
  background: linear-gradient(135deg, #F87171, #EF4444);
  color: white;
}

.btn-export-pdf:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(248, 113, 113, 0.4);
}

.btn-export-svg {
  background: linear-gradient(135deg, #5B7FFF, #3D5AE8);
  color: white;
}

.btn-export-svg:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(91, 127, 255, 0.4);
}

.btn-export-png {
  background: linear-gradient(135deg, #34D399, #10B981);
  color: white;
}

.btn-export-png:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(52, 211, 153, 0.4);
}

.btn-export-jpg {
  background: linear-gradient(135deg, #FBBF24, #F59E0B);
  color: #0A0A0F;
}

.btn-export-jpg:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(251, 191, 36, 0.4);
}

.region-card {
  padding: 1.25rem;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid transparent;
  position: relative;
  overflow: hidden;
}

.region-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.1), transparent);
  pointer-events: none;
}

.region-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.region-card.caribe {
  background: linear-gradient(135deg, #22D3EE, #06B6D4);
  color: white;
}

.region-card.pacifico {
  background: linear-gradient(135deg, #A78BFA, #8B5CF6);
  color: white;
}

.region-card.andina {
  background: linear-gradient(135deg, #FBBF24, #F59E0B);
  color: #0A0A0F;
}

.region-card.orinoquia {
  background: linear-gradient(135deg, #34D399, #10B981);
  color: white;
}

.region-card.amazonia {
  background: linear-gradient(135deg, #22C55E, #16A34A);
  color: white;
}

.region-card.insular {
  background: linear-gradient(135deg, #60A5FA, #3B82F6);
  color: white;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #BABABD;
}

.legend-color {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.feature-card {
  border-left: 4px solid #5B7FFF;
  background: rgba(26, 26, 36, 0.9);
  backdrop-filter: blur(10px);
}

.feature-info {
  padding: 1rem 0;
}

.feature-info p {
  margin-bottom: 0.5rem;
  color: #BABABD;
}

.feature-info p strong {
  color: #FFFFFF;
}

.feature-badges {
  display: flex;
  gap: 0.5rem;
}

.feature-vars {
  margin-top: 0.5rem;
  margin-left: 1.5rem;
  list-style: none;
}

.feature-vars li {
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.var-key {
  font-weight: 600;
  color: #8BA4FF;
}

.var-value {
  color: #BABABD;
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

.region-card h4 {
  font-size: 1.1rem;
  margin-bottom: 0.25rem;
  color: white;
}

.region-card.andina h4 {
  color: #0A0A0F;
}

.region-card .text-muted {
  font-size: 0.85rem;
  color: rgba(255,255,255,0.85);
}

.region-card.andina .text-muted {
  color: rgba(0,0,0,0.7);
}

.badge-info {
  background: rgba(34, 211, 238, 0.2);
  color: #22D3EE;
}

.badge-warning {
  background: rgba(251, 191, 36, 0.2);
  color: #FBBF24;
}

.badge-danger {
  background: rgba(248, 113, 113, 0.2);
  color: #F87171;
}

/* Venn Legend Styles */
.venn-legend {
  flex-direction: column;
  gap: 0.75rem;
}

.venn-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 1rem 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin-top: 1rem;
}

.venn-stat {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
}

.venn-stat.positive {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.venn-stat.negative {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.venn-stat.unknown {
  background: rgba(156, 163, 175, 0.2);
  color: #9ca3af;
}

/* Venn Summary in Popup */
.venn-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.venn-item {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}

.venn-item.venn-true {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}

.venn-item.venn-false {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}
</style>
