<!--
  Home View - Dashboard
  Asistente de Recopilación y Análisis de Datos de Organizaciones 
  de la Sociedad Civil Lideradas por Mujeres en Colombia
-->
<template>
  <div class="home-view">
    <!-- Hero section -->
    <div class="hero-section">
      <h1 class="page-title">🕊️ Organizaciones de Mujeres Constructoras de Paz</h1>
      <p class="hero-subtitle">
        Asistente de recopilación y análisis de datos de organizaciones de la sociedad civil lideradas por mujeres en Colombia
      </p>
    </div>
    
    <!-- Stats cards with Colombian colors -->
    <div class="stats-grid">
      <div class="stat-card yellow">
        <div class="stat-value">{{ stats.organizations }}</div>
        <div class="stat-label">Organizaciones</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-value">{{ stats.departments }}</div>
        <div class="stat-label">Departamentos</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value">{{ stats.variables }}</div>
        <div class="stat-label">Variables Venn</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value">{{ stats.womenLed }}</div>
        <div class="stat-label">Lideradas por Mujeres</div>
      </div>
    </div>

    <!-- Main CTA: Agent Chat -->
    <div class="card cta-card">
      <div class="cta-content">
        <div class="cta-icon">👩‍💼</div>
        <div class="cta-text">
          <h2>Asistente Inteligente</h2>
          <p>Busca organizaciones de mujeres constructoras de paz en Colombia, gestiona variables Venn y más</p>
        </div>
        <router-link to="/chat" class="btn btn-large btn-gradient">
          💬 Iniciar Chat con IA
        </router-link>
      </div>
    </div>

    <!-- Quick actions -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">⚡ Acciones Rápidas</h2>
      </div>
      <div class="flex gap-2 flex-wrap">
        <router-link to="/chat" class="btn btn-primary">
          💬 Asistente IA
        </router-link>
        <router-link to="/organization-management" class="btn btn-secondary">
          📋 Ver Organizaciones
        </router-link>
        <router-link to="/map" class="btn btn-secondary">
          🗺️ Mapa Colombia
        </router-link>
        <router-link to="/venn" class="btn btn-warning">
          🔵 Diagrama Venn
        </router-link>
        <router-link to="/data-results" class="btn btn-outline">
          📈 Resultados
        </router-link>
      </div>
    </div>

    <!-- Colombian Regions Overview -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">🌎 Regiones de Colombia</h2>
      </div>
      <div class="regions-overview">
        <div class="region-item caribe">
          <span class="region-icon">🏖️</span>
          <span class="region-name">Caribe</span>
          <span class="region-count">{{ regionCounts.caribe || 0 }}</span>
        </div>
        <div class="region-item pacifico">
          <span class="region-icon">🌊</span>
          <span class="region-name">Pacífico</span>
          <span class="region-count">{{ regionCounts.pacifico || 0 }}</span>
        </div>
        <div class="region-item andina">
          <span class="region-icon">⛰️</span>
          <span class="region-name">Andina</span>
          <span class="region-count">{{ regionCounts.andina || 0 }}</span>
        </div>
        <div class="region-item orinoquia">
          <span class="region-icon">🐄</span>
          <span class="region-name">Orinoquía</span>
          <span class="region-count">{{ regionCounts.orinoquia || 0 }}</span>
        </div>
        <div class="region-item amazonia">
          <span class="region-icon">🌳</span>
          <span class="region-name">Amazonía</span>
          <span class="region-count">{{ regionCounts.amazonia || 0 }}</span>
        </div>
        <div class="region-item insular">
          <span class="region-icon">🏝️</span>
          <span class="region-name">Insular</span>
          <span class="region-count">{{ regionCounts.insular || 0 }}</span>
        </div>
      </div>
    </div>

    <!-- API Status -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">🔌 Estado del Sistema</h2>
      </div>
      <div :class="['alert', apiStatus.ok ? 'alert-success' : 'alert-danger']">
        {{ apiStatus.ok ? '✅ API funcionando correctamente - Conectado a Colombia' : '❌ Error de conexión con API' }}
      </div>
    </div>

    <!-- Recent organizations -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">📝 Organizaciones Recientes</h2>
        <router-link to="/organization-management" class="btn btn-sm btn-outline">Ver todas</router-link>
      </div>
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
      </div>
      <div v-else-if="recentOrganizations.length === 0" class="empty-state">
        <span class="empty-icon">📋</span>
        <p>No hay organizaciones registradas</p>
        <p class="empty-hint">Usa el chat con IA para buscar y agregar organizaciones de mujeres constructoras de paz</p>
        <router-link to="/chat" class="btn btn-primary btn-sm">💬 Ir al Chat</router-link>
      </div>
      <div v-else class="organizations-grid">
        <div 
          v-for="org in recentOrganizations" 
          :key="org.id" 
          class="organization-card"
          :class="'scope-' + ((org.territorial_scope || 'municipal').toLowerCase())"
        >
          <div class="organization-header">
            <div>
              <h3 class="organization-name">
                {{ org.name }}
                <span v-if="org.leader_is_woman" class="leader-badge" title="Liderada por mujer">👩‍💼</span>
                <span v-if="org.is_peace_building" class="peace-badge" title="Construcción de paz">🕊️</span>
              </h3>
              <div class="badge-container">
                <span class="badge" :class="getScopeBadgeClass(org.territorial_scope, org.is_international)">
                  {{ getScopeLabel(org.territorial_scope, org.is_international) }}
                </span>
                <span v-if="org.department_name" class="badge badge-primary">
                  {{ org.department_name }}
                </span>
              </div>
            </div>
            <div class="organization-actions">
              <a v-if="org.url" :href="org.url" target="_blank" class="btn-icon" title="Visitar web">
                🔗
              </a>
              <button @click="scrapeSingle(org.id)" class="btn-icon" title="Ejecutar scraping">
                🔍
              </button>
            </div>
          </div>
          <p v-if="org.description" class="organization-desc">{{ truncate(org.description, 80) }}</p>
          <div class="organization-meta">
            <span v-if="org.women_count" class="meta-item">👥 {{ org.women_count }} mujeres</span>
            <span v-if="org.years_active" class="meta-item">📅 {{ org.years_active }} años</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getOrganizations, launchScraping, checkHealth } from '../api.js'

// State
const stats = ref({
  organizations: 0,
  departments: 32,
  variables: 0,
  womenLed: 0
})
const regionCounts = ref({
  caribe: 0,
  pacifico: 0,
  andina: 0,
  orinoquia: 0,
  amazonia: 0,
  insular: 0
})
const recentOrganizations = ref([])
const loading = ref(true)
const scraping = ref(false)
const apiStatus = ref({ ok: false })

// Methods
const getScopeBadgeClass = (scope, isInternational = false) => {
  if (isInternational) return 'badge-purple'
  const normalizedScope = (scope || 'municipal').toLowerCase()
  const classes = {
    'municipal': 'badge-primary',
    'departamental': 'badge-success',
    'regional': 'badge-accent',
    'nacional': 'badge-danger',
    'internacional': 'badge-purple'
  }
  return classes[normalizedScope] || 'badge-primary'
}

const getScopeLabel = (scope, isInternational = false) => {
  if (isInternational) return '🌐 Internacional'
  const normalizedScope = (scope || 'municipal').toLowerCase()
  const labels = {
    'municipal': '🏘️ Municipal',
    'departamental': '🏛️ Dpto',
    'regional': '🌎 Regional',
    'nacional': '🇨🇴 Nacional',
    'internacional': '🌐 Internacional'
  }
  return labels[normalizedScope] || '🏘️ Municipal'
}

// Mapeo de departamentos a regiones de Colombia (códigos DANE)
const DEPARTMENT_TO_REGION = {
  // Región Caribe: Atlántico, Bolívar, Cesar, Córdoba, La Guajira, Magdalena, Sucre, San Andrés
  '08': 'caribe', '13': 'caribe', '20': 'caribe', '23': 'caribe', 
  '44': 'caribe', '47': 'caribe', '70': 'caribe', '88': 'caribe',
  // Región Pacífica: Cauca, Chocó, Nariño, Valle del Cauca
  '19': 'pacifico', '27': 'pacifico', '52': 'pacifico', '76': 'pacifico',
  // Región Andina: Antioquia, Bogotá, Boyacá, Caldas, Cundinamarca, Huila, N. Santander, Quindío, Risaralda, Santander, Tolima
  '05': 'andina', '11': 'andina', '15': 'andina', '17': 'andina', 
  '25': 'andina', '41': 'andina', '54': 'andina', '63': 'andina', 
  '66': 'andina', '68': 'andina', '73': 'andina',
  // Región Orinoquía: Meta, Arauca, Casanare, Vichada
  '50': 'orinoquia', '81': 'orinoquia', '85': 'orinoquia', '95': 'orinoquia',
  // Región Amazonía: Caquetá, Putumayo, Amazonas, Guainía, Guaviare, Vaupés
  '18': 'amazonia', '86': 'amazonia', '91': 'amazonia', '94': 'amazonia', '97': 'amazonia', '99': 'amazonia'
  // Nota: San Andrés (88) está en Caribe; la región Insular se omite ya que San Andrés es el único departamento
}

const loadData = async () => {
  try {
    loading.value = true
    // Get all organizations to count properly
    const allOrganizations = await getOrganizations(0, 1000)
    recentOrganizations.value = allOrganizations.slice(0, 10)
    stats.value.organizations = allOrganizations.length
    
    // Count women-led organizations
    stats.value.womenLed = allOrganizations.filter(o => o.leader_is_woman).length
    
    // Count by region based on department_code
    const counts = { caribe: 0, pacifico: 0, andina: 0, orinoquia: 0, amazonia: 0, insular: 0 }
    allOrganizations.forEach(org => {
      if (org.department_code) {
        const region = DEPARTMENT_TO_REGION[org.department_code]
        if (region) {
          counts[region]++
        }
      }
    })
    regionCounts.value = counts
    
    // Check API health
    await checkHealth()
    apiStatus.value.ok = true
  } catch (error) {
    console.error('Error loading data:', error)
    apiStatus.value.ok = false
  } finally {
    loading.value = false
  }
}

const launchAllScraping = async () => {
  try {
    scraping.value = true
    await launchScraping(null, true)
    alert('Scraping iniciado para todas las organizaciones')
  } catch (error) {
    console.error('Error launching scraping:', error)
    alert('Error al iniciar scraping')
  } finally {
    scraping.value = false
  }
}

const scrapeSingle = async (id) => {
  try {
    await launchScraping(id)
    alert(`Scraping iniciado para organización ${id}`)
  } catch (error) {
    console.error('Error:', error)
    alert('Error al iniciar scraping')
  }
}

const truncate = (text, maxLength) => {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

// Lifecycle
onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* Premium Dark Theme - Home View */
.home-view {
  max-width: 1400px;
  margin: 0 auto;
}

.hero-section {
  text-align: center;
  margin-bottom: 2rem;
  padding: 1rem;
}

.hero-subtitle {
  color: #5A5A6E;
  font-size: 1.1rem;
  margin-top: 0.5rem;
}

.regions-overview {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 1rem;
}

@media (max-width: 992px) {
  .regions-overview {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 576px) {
  .regions-overview {
    grid-template-columns: repeat(2, 1fr);
  }
}

.region-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.25rem 1rem;
  border-radius: 16px;
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.25s ease;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.region-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
}

.region-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 0 40px rgba(91, 127, 255, 0.15);
  border-color: rgba(91, 127, 255, 0.2);
}

.region-item.caribe::before {
  background: linear-gradient(90deg, #22D3EE, #06B6D4);
}
.region-item.caribe:hover {
  box-shadow: 0 0 40px rgba(34, 211, 238, 0.2);
}

.region-item.pacifico::before {
  background: linear-gradient(90deg, #A78BFA, #8B5CF6);
}
.region-item.pacifico:hover {
  box-shadow: 0 0 40px rgba(139, 92, 246, 0.2);
}

.region-item.andina::before {
  background: linear-gradient(90deg, #FBBF24, #F59E0B);
}
.region-item.andina:hover {
  box-shadow: 0 0 40px rgba(251, 191, 36, 0.2);
}

.region-item.orinoquia::before {
  background: linear-gradient(90deg, #34D399, #10B981);
}
.region-item.orinoquia:hover {
  box-shadow: 0 0 40px rgba(52, 211, 153, 0.2);
}

.region-item.amazonia::before {
  background: linear-gradient(90deg, #22C55E, #16A34A);
}
.region-item.amazonia:hover {
  box-shadow: 0 0 40px rgba(34, 197, 94, 0.2);
}

.region-item.insular::before {
  background: linear-gradient(90deg, #60A5FA, #3B82F6);
}
.region-item.insular:hover {
  box-shadow: 0 0 40px rgba(96, 165, 250, 0.2);
}

.region-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  filter: drop-shadow(0 0 8px rgba(91, 127, 255, 0.3));
}

.region-name {
  font-weight: 600;
  color: #FFFFFF;
  font-size: 0.9rem;
}

.region-count {
  font-size: 1.25rem;
  font-weight: 700;
  color: #8BA4FF;
  margin-top: 0.25rem;
}

/* Table - Premium Dark Theme */
.table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(26, 26, 36, 0.5);
  border-radius: 12px;
  overflow: hidden;
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

.table tbody tr {
  transition: background 0.2s ease;
}

.table tbody tr:hover {
  background: rgba(91, 127, 255, 0.05);
}

.table strong {
  color: #FFFFFF;
}

.text-center {
  text-align: center;
}

/* Alert styles */
.alert {
  padding: 1rem 1.25rem;
  border-radius: 12px;
  font-weight: 500;
}

.alert-success {
  background: rgba(52, 211, 153, 0.15);
  border: 1px solid rgba(52, 211, 153, 0.3);
  color: #34D399;
}

.alert-danger {
  background: rgba(248, 113, 113, 0.15);
  border: 1px solid rgba(248, 113, 113, 0.3);
  color: #F87171;
}

/* Badge styles */
.badge-primary {
  background: rgba(91, 127, 255, 0.15);
  color: #8BA4FF;
}

.badge-success {
  background: rgba(52, 211, 153, 0.15);
  color: #34D399;
}

.badge-accent {
  background: rgba(251, 191, 36, 0.15);
  color: #FBBF24;
}

.badge-danger {
  background: rgba(248, 113, 113, 0.15);
  color: #F87171;
}

.badge-purple {
  background: rgba(128, 0, 255, 0.15);
  color: #A78BFA;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state p {
  color: #5A5A6E;
  margin-bottom: 1rem;
}

/* Organizations grid - same as management page */
.organizations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
}

.organization-card {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
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
  border-radius: 12px 12px 0 0;
}

.organization-card.scope-municipal::before { background: linear-gradient(90deg, #5B7FFF, #8B5CF6); }
.organization-card.scope-departamental::before { background: linear-gradient(90deg, #34D399, #10B981); }
.organization-card.scope-regional::before { background: linear-gradient(90deg, #FBBF24, #F59E0B); }
.organization-card.scope-nacional::before { background: linear-gradient(90deg, #F87171, #EF4444); }

.organization-card:hover {
  background: rgba(255, 255, 255, 0.06);
  transform: translateY(-2px);
  box-shadow: 0 0 30px rgba(91, 127, 255, 0.1);
  border-color: rgba(91, 127, 255, 0.2);
}

.organization-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.organization-name {
  font-size: 1rem;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 0.5rem 0;
}

.badge-container {
  display: flex;
  gap: 0.5rem;
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
  border-radius: 6px;
  text-decoration: none;
}

.btn-icon:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

.organization-desc {
  font-size: 0.85rem;
  color: #8A8A9E;
  margin: 0.5rem 0;
  line-height: 1.4;
}

.organization-links {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.links-count {
  font-size: 0.8rem;
  color: #5A5A6E;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 2rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(91, 127, 255, 0.2);
  border-top-color: #5B7FFF;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* CTA Card for Agent Chat */
.cta-card {
  background: linear-gradient(135deg, rgba(255, 205, 0, 0.1), rgba(0, 56, 147, 0.15), rgba(206, 17, 38, 0.1));
  border: 2px solid rgba(255, 205, 0, 0.3);
  padding: 2rem;
}

.cta-content {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.cta-icon {
  font-size: 4rem;
  flex-shrink: 0;
}

.cta-text {
  flex: 1;
  min-width: 200px;
}

.cta-text h2 {
  margin: 0 0 0.5rem 0;
  color: #FFFFFF;
  font-size: 1.5rem;
}

.cta-text p {
  margin: 0;
  color: #B0B0C0;
  font-size: 1rem;
}

.btn-large {
  padding: 1rem 2rem;
  font-size: 1.1rem;
  border-radius: 12px;
}

.btn-gradient {
  background: linear-gradient(135deg, #FFCD00 0%, #003893 50%, #CE1126 100%);
  color: white;
  border: none;
  font-weight: 600;
  box-shadow: 0 4px 20px rgba(255, 205, 0, 0.3);
  transition: all 0.3s ease;
}

.btn-gradient:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 30px rgba(255, 205, 0, 0.4);
}

@media (max-width: 768px) {
  .cta-content {
    flex-direction: column;
    text-align: center;
  }
  
  .cta-icon {
    font-size: 3rem;
  }
}
</style>
