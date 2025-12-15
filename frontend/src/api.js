/**
 * API client for backend communication
 * Handles all HTTP requests to the FastAPI backend
 */
import axios from 'axios'

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor for logging and auth
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API] Response error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// ============== Organization API ==============

/**
 * Get all organizations
 * @param {number} skip - Number of items to skip
 * @param {number} limit - Max number of items to return
 * @returns {Promise<Array>} List of organizations
 */
export async function getOrganizations(skip = 0, limit = 100) {
  const response = await api.get('/organizations', {
    params: { skip, limit }
  })
  return response.data
}

/**
 * Get a single organization by ID
 * @param {number} id - Organization ID
 * @returns {Promise<Object>} Organization details
 */
export async function getOrganization(id) {
  const response = await api.get(`/organizations/${id}`)
  return response.data
}

/**
 * Create a new organization
 * @param {Object} data - Organization data
 * @returns {Promise<Object>} Created organization
 */
export async function createOrganization(data) {
  const response = await api.post('/organizations', data)
  return response.data
}

// Legacy aliases for backwards compatibility
export const getAssociations = getOrganizations
export const getAssociation = getOrganization
export const createAssociation = createOrganization

// ============== Variables API ==============

/**
 * Get variables for an organization
 * @param {number} organizationId - Organization ID
 * @returns {Promise<Array>} List of variables
 */
export async function getVariables(organizationId) {
  const response = await api.get(`/organizations/${organizationId}/variables`)
  return response.data
}

/**
 * Save a new variable
 * @param {Object} data - Variable data
 * @returns {Promise<Object>} Created variable
 */
export async function saveVariable(data) {
  const response = await api.post('/variables', data)
  return response.data
}

/**
 * Verify or unverify a variable
 * @param {number} variableId - Variable ID
 * @param {boolean} verified - Verification status
 * @returns {Promise<Object>} Updated variable
 */
export async function verifyVariable(variableId, verified) {
  const response = await api.patch(`/variables/${variableId}/verify`, { verified })
  return response.data
}

/**
 * Get all unique variable keys
 * @returns {Promise<Object>} Object with keys array
 */
export async function getVariableKeys() {
  const response = await api.get('/variables/keys')
  return response.data
}

// ============== Scraping API ==============

/**
 * Launch scraping for an organization
 * @param {number} organizationId - Organization ID (optional)
 * @param {boolean} allOrganizations - Scrape all organizations
 * @returns {Promise<Object>} Scraping status
 */
export async function launchScraping(organizationId = null, allOrganizations = false) {
  const response = await api.post('/scrape', {
    organization_id: organizationId,
    all_organizations: allOrganizations
  })
  return response.data
}

// ============== Venn Diagram API ==============

/**
 * Get Venn diagram data for specified variables
 * @param {Array<string>} vars - Variable keys to include
 * @returns {Promise<Object>} Venn diagram data
 */
export async function getVennData(vars) {
  const response = await api.get('/venn/data', {
    params: { vars: vars.join(',') }
  })
  return response.data
}

/**
 * Get available variable keys for Venn diagram
 * @returns {Promise<Object>} Available keys with stats
 */
export async function getAvailableVennKeys() {
  const response = await api.get('/venn/available-keys')
  return response.data
}

/**
 * Preview Venn data for debugging
 * @param {Array<string>} vars - Variable keys
 * @param {number} limit - Max organizations to preview
 * @returns {Promise<Object>} Preview data
 */
export async function previewVennData(vars, limit = 5) {
  const response = await api.get('/venn/preview', {
    params: { vars: vars.join(','), limit }
  })
  return response.data
}

// ============== Map API ==============

/**
 * Get location data for map visualization
 * @param {Array<string>} vars - Variable keys to include (optional)
 * @returns {Promise<Object>} GeoJSON FeatureCollection
 */
export async function getMapLocations(vars = null) {
  const params = {}
  if (vars && vars.length > 0) {
    params.vars = vars.join(',')
  }
  const response = await api.get('/map/locations', { params })
  return response.data
}

/**
 * Get organizations for simple marker map
 * @returns {Promise<Object>} GeoJSON FeatureCollection
 */
export async function getOrganizationsForMap() {
  const response = await api.get('/map/organizations')
  return response.data
}

// Legacy alias
export const getAssociationsForMap = getOrganizationsForMap

// ============== Health Check ==============

/**
 * Check API health status
 * @returns {Promise<Object>} Health status
 */
export async function checkHealth() {
  const response = await api.get('/health')
  return response.data
}

// ============== Geography API ==============

/**
 * Get all Colombian departments
 * @returns {Promise<Array>} List of departments
 */
export async function getDepartments() {
  const response = await api.get('/geography/departments')
  return response.data
}

/**
 * Get municipalities, optionally filtered by department
 * @param {string} departmentCode - Department code filter (optional)
 * @returns {Promise<Array>} List of municipalities
 */
export async function getMunicipalities(departmentCode = null) {
  const params = {}
  if (departmentCode) {
    params.department_code = departmentCode
  }
  const response = await api.get('/geography/municipalities', { params })
  return response.data
}

/**
 * Find nearest municipality to given coordinates
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} maxDistanceKm - Maximum search radius in km (default 100)
 * @returns {Promise<Object>} Nearest municipality data
 */
export async function findNearestMunicipality(lat, lng, maxDistanceKm = 100) {
  const response = await api.get('/geography/municipalities/nearest', {
    params: { lat, lng, max_distance_km: maxDistanceKm }
  })
  return response.data
}

/**
 * Reverse geocode using OpenStreetMap Nominatim to get precise location
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @returns {Promise<Object|null>} Location data with municipality/city name
 */
export async function reverseGeocode(lat, lng) {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&addressdetails=1&accept-language=es`,
      {
        headers: {
          'User-Agent': 'RecolectorDeInformacion/1.0'
        }
      }
    )
    if (!response.ok) return null
    const data = await response.json()
    return {
      municipality: data.address?.city || data.address?.town || data.address?.municipality || data.address?.village || null,
      department: data.address?.state || null,
      country: data.address?.country || null,
      displayName: data.display_name || null
    }
  } catch (error) {
    console.error('Reverse geocode error:', error)
    return null
  }
}

/**
 * Get municipality count
 * @returns {Promise<Object>} { total: number }
 */
export async function getMunicipalitiesCount() {
  const response = await api.get('/geography/municipalities/count')
  return response.data
}

// ============== Organization Management API ==============

/**
 * Get all organizations with their links
 * @returns {Promise<Array>} List of organizations with links
 */
export async function getOrganizationsWithLinks() {
  const response = await api.get('/organizations/full')
  return response.data
}

/**
 * Create an organization with links
 * @param {Object} data - Organization data with links array
 * @returns {Promise<Object>} Created organization
 */
export async function createOrganizationWithLinks(data) {
  const response = await api.post('/organizations/full', data)
  return response.data
}

/**
 * Update an organization with links
 * @param {number} id - Organization ID
 * @param {Object} data - Organization data with links array
 * @returns {Promise<Object>} Updated organization
 */
export async function updateOrganizationWithLinks(id, data) {
  const response = await api.put(`/organizations/${id}`, data)
  return response.data
}

/**
 * Delete an organization and all its links
 * @param {number} id - Organization ID
 */
export async function deleteOrganizationFull(id) {
  await api.delete(`/organizations/${id}`)
}

// Legacy aliases for backwards compatibility
export const getAssociationsWithLinks = getOrganizationsWithLinks
export const createAssociationWithLinks = createOrganizationWithLinks
export const updateAssociationWithLinks = updateOrganizationWithLinks
export const deleteAssociationFull = deleteOrganizationFull

// ============== Venn Variables API ==============

/**
 * Get all Venn variables with their proxies
 * @returns {Promise<Array>} List of variables with proxies
 */
export async function getVennVariables() {
  const response = await api.get('/venn-variables')
  return response.data
}

/**
 * Create a Venn variable
 * @param {Object} data - Variable data
 * @returns {Promise<Object>} Created variable
 */
export async function createVennVariable(data) {
  const response = await api.post('/venn-variables', data)
  return response.data
}

/**
 * Update a Venn variable
 * @param {number} id - Variable ID
 * @param {Object} data - Variable data
 * @returns {Promise<Object>} Updated variable
 */
export async function updateVennVariable(id, data) {
  const response = await api.put(`/venn-variables/${id}`, data)
  return response.data
}

/**
 * Delete a Venn variable
 * @param {number} id - Variable ID
 */
export async function deleteVennVariable(id) {
  await api.delete(`/venn-variables/${id}`)
}

/**
 * Create a proxy for a variable
 * @param {number} variableId - Variable ID
 * @param {Object} data - Proxy data
 * @returns {Promise<Object>} Created proxy
 */
export async function createVennProxy(variableId, data) {
  const response = await api.post(`/venn-variables/${variableId}/proxies`, data)
  return response.data
}

/**
 * Update a proxy
 * @param {number} proxyId - Proxy ID
 * @param {Object} data - Proxy data
 * @returns {Promise<Object>} Updated proxy
 */
export async function updateVennProxy(proxyId, data) {
  const response = await api.put(`/venn-variables/proxies/${proxyId}`, data)
  return response.data
}

/**
 * Delete a proxy
 * @param {number} proxyId - Proxy ID
 */
export async function deleteVennProxy(proxyId) {
  await api.delete(`/venn-variables/proxies/${proxyId}`)
}

// ============== Venn Results API ==============

/**
 * Get all Venn results with optional filters
 * @param {Object} params - Filter parameters
 * @returns {Promise<Array>} List of results
 */
export async function getVennResults(params = {}) {
  const response = await api.get('/venn-results', { params })
  return response.data
}

/**
 * Get Venn results pending verification
 * @param {Object} params - Filter parameters
 * @returns {Promise<Array>} List of pending results
 */
export async function getVennResultsPending(params = {}) {
  const response = await api.get('/venn-results/pending-verification', { params })
  return response.data
}

/**
 * Verify a Venn result
 * @param {number} resultId - Result ID
 * @param {Object} data - Verification data
 * @returns {Promise<Object>} Updated result
 */
export async function verifyVennResult(resultId, data) {
  const response = await api.post(`/venn-results/${resultId}/verify`, data)
  return response.data
}

/**
 * Get verification statistics
 * @returns {Promise<Object>} Statistics
 */
export async function getVennResultsStats() {
  const response = await api.get('/venn-results/verification-stats')
  return response.data
}

/**
 * Bulk verify multiple results
 * @param {Array<number>} resultIds - Result IDs
 * @param {string} verificationStatus - Status (verified/rejected)
 * @param {string} verifiedBy - Verifier name
 * @param {string} verificationNotes - Notes
 * @returns {Promise<Object>} Bulk result
 */
export async function bulkVerifyVennResults(resultIds, verificationStatus, verifiedBy, verificationNotes = null) {
  const params = new URLSearchParams()
  resultIds.forEach(id => params.append('result_ids', id))
  params.append('verification_status', verificationStatus)
  params.append('verified_by', verifiedBy)
  if (verificationNotes) params.append('verification_notes', verificationNotes)
  
  const response = await api.post(`/venn-results/bulk-verify?${params.toString()}`)
  return response.data
}

// ============== Scraping Configuration API ==============

/**
 * Get all scraping configurations
 * @returns {Promise<Array>} List of configurations
 */
export async function getScrapingConfigs() {
  const response = await api.get('/scraping/configs')
  return response.data
}

/**
 * Create a scraping configuration
 * @param {Object} data - Configuration data
 * @returns {Promise<Object>} Created configuration
 */
export async function createScrapingConfig(data) {
  const response = await api.post('/scraping/configs', data)
  return response.data
}

/**
 * Delete a scraping configuration
 * @param {number} id - Configuration ID
 */
export async function deleteScrapingConfig(id) {
  await api.delete(`/scraping/configs/${id}`)
}

// ============== Scraping Sessions API ==============

/**
 * Get all scraping sessions
 * @returns {Promise<Array>} List of sessions
 */
export async function getScrapingSessions() {
  const response = await api.get('/scraping/sessions')
  return response.data
}

/**
 * Launch a new scraping session
 * @param {Object} data - Session launch data (config_id, association_ids, variable_ids)
 * @returns {Promise<Object>} Session info with session_id
 */
export async function launchScrapingSession(data) {
  const response = await api.post('/scraping/sessions/launch', data)
  return response.data
}

/**
 * Cancel a running scraping session
 * @param {number} sessionId - Session ID
 */
export async function cancelScrapingSession(sessionId) {
  await api.post(`/scraping/sessions/${sessionId}/cancel`)
}

// ============== Scraped Data API ==============

/**
 * Get scraped data with filters and pagination
 * @param {Object} params - Filter and pagination parameters
 * @returns {Promise<Object>} Object with data array and total count
 */
export async function getScrapedData(params = {}) {
  const response = await api.get('/scraping/data', { params })
  return response.data
}

/**
 * Get scraped data summary statistics
 * @returns {Promise<Object>} Summary with counts
 */
export async function getScrapedDataSummary() {
  const response = await api.get('/scraping/data/summary')
  return response.data
}

/**
 * Verify or unverify scraped data
 * @param {number} dataId - Data ID
 * @param {boolean} verified - Verification status
 * @returns {Promise<Object>} Updated data
 */
export async function verifyScrapedData(dataId, verified) {
  const response = await api.post(`/scraping/data/${dataId}/verify`, { verified })
  return response.data
}

/**
 * Update scraped data
 * @param {number} dataId - Data ID
 * @param {Object} data - Updated data fields
 * @returns {Promise<Object>} Updated data
 */
export async function updateScrapedData(dataId, data) {
  const response = await api.put(`/scraping/data/${dataId}`, data)
  return response.data
}

/**
 * Delete scraped data
 * @param {number} dataId - Data ID
 */
export async function deleteScrapedData(dataId) {
  await api.delete(`/scraping/data/${dataId}`)
}

// ============== Match Evidence API ==============

/**
 * Get match evidence with filters
 * @param {Object} filters - Filter parameters
 * @returns {Promise<Array>} List of evidence records
 */
export async function getMatchEvidence(filters = {}) {
  const response = await api.get('/match-evidence/', { params: filters })
  return response.data
}

/**
 * Get evidence statistics
 * @returns {Promise<Object>} Evidence stats
 */
export async function getEvidenceStats() {
  const response = await api.get('/match-evidence/stats')
  return response.data
}

/**
 * Get evidence for a specific Venn result
 * @param {number} vennResultId - Venn result ID
 * @returns {Promise<Array>} List of evidence records
 */
export async function getEvidenceByResult(vennResultId) {
  const response = await api.get(`/match-evidence/by-result/${vennResultId}`)
  return response.data
}

/**
 * Validate a single evidence record
 * @param {number} evidenceId - Evidence ID
 * @param {Object} validation - Validation data (is_valid, validated_by, validation_notes)
 * @returns {Promise<Object>} Updated evidence
 */
export async function validateEvidence(evidenceId, validation) {
  const response = await api.put(`/match-evidence/${evidenceId}/validate`, validation)
  return response.data
}

/**
 * Bulk validate multiple evidence records
 * @param {Array<number>} evidenceIds - Array of evidence IDs
 * @param {boolean} isValid - Validation result
 * @param {string} validatedBy - Validator identifier
 * @param {string} notes - Optional notes
 * @returns {Promise<Object>} Bulk validation result
 */
export async function bulkValidateEvidence(evidenceIds, isValid, validatedBy, notes = null) {
  const response = await api.post('/match-evidence/bulk-validate', {
    evidence_ids: evidenceIds,
    is_valid: isValid,
    validated_by: validatedBy,
    validation_notes: notes
  })
  return response.data
}

// ============== Tosmana/QCA API ==============

/**
 * Get truth table data for QCA analysis
 * @returns {Promise<Object>} Truth table with organizations as cases and variables as conditions
 */
export async function getTosmanaData() {
  const response = await api.get('/venn-results/tosmana')
  return response.data
}

// Export default instance for custom requests
export default api
