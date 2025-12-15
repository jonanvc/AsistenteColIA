<!--
  Venn View - Interactive Venn diagram visualization
  Features:
  - Select variables to compare
  - D3.js powered Venn diagram
  - Export to SVG or PDF
-->
<template>
  <div class="venn-view">
    <h1 class="mb-3">🔄 Diagrama de Venn</h1>

    <!-- Configuration panel -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Configuración</h2>
      </div>
      
      <div class="form-group">
        <label class="form-label">Selecciona las variables a comparar:</label>
        <div v-if="loadingKeys" class="loading">
          <div class="spinner"></div>
        </div>
        <div v-else class="checkbox-group">
          <label v-for="key in availableKeys" :key="key.key" class="checkbox-item">
            <input 
              type="checkbox" 
              :value="key.key" 
              v-model="selectedKeys"
              :disabled="selectedKeys.length >= 5 && !selectedKeys.includes(key.key)"
            />
            <span>{{ key.key }} ({{ key.association_count }} asoc.)</span>
          </label>
        </div>
        <p class="text-muted mt-1">Selecciona entre 2 y 5 variables</p>
      </div>

      <div class="flex gap-2 flex-wrap">
        <button 
          @click="generateVenn" 
          class="btn btn-primary" 
          :disabled="selectedKeys.length < 2 || loading"
        >
          {{ loading ? '⏳ Generando...' : '📊 Generar Diagrama' }}
        </button>
        <button 
          @click="exportSVG" 
          class="btn btn-secondary" 
          :disabled="!vennData"
        >
          📥 Exportar SVG
        </button>
        <button 
          @click="exportPDF" 
          class="btn btn-accent" 
          :disabled="!vennData"
        >
          📄 Exportar PDF
        </button>
      </div>
    </div>

    <!-- Error message -->
    <div v-if="error" class="alert alert-danger">
      {{ error }}
    </div>

    <!-- Venn Diagram -->
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Diagrama</h2>
        <span v-if="vennData" class="text-muted">
          {{ vennData.total_organizations }} organizaciones | {{ vennData.sets?.length || 0 }} conjuntos
        </span>
      </div>
      
      <div v-if="!vennData && !loading" class="text-center" style="padding: 3rem;">
        <p>Selecciona variables y genera el diagrama</p>
      </div>
      
      <div v-if="loading" class="loading" style="min-height: 400px;">
        <div class="spinner"></div>
      </div>
      
      <div ref="vennContainer" class="venn-container"></div>
    </div>

    <!-- Intersection details -->
    <div v-if="vennData && vennData.intersections?.length > 0" class="card">
      <div class="card-header">
        <h2 class="card-title">📋 Detalles de Intersecciones</h2>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Conjuntos</th>
            <th>Tamaño</th>
            <th>Elementos (muestra)</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(inter, idx) in vennData.intersections" :key="idx">
            <td>{{ inter.sets.join(' ∩ ') }}</td>
            <td>{{ inter.size }}</td>
            <td>{{ inter.elements?.slice(0, 5).join(', ') || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { getAvailableVennKeys, getVennData } from '../api.js'

// State
const availableKeys = ref([])
const selectedKeys = ref([])
const loadingKeys = ref(true)
const loading = ref(false)
const error = ref(null)
const vennData = ref(null)
const vennContainer = ref(null)

// Colors for sets
const colors = [
  'rgba(255, 99, 132, 0.5)',
  'rgba(54, 162, 235, 0.5)',
  'rgba(255, 206, 86, 0.5)',
  'rgba(75, 192, 192, 0.5)',
  'rgba(153, 102, 255, 0.5)'
]

const strokeColors = [
  'rgba(255, 99, 132, 1)',
  'rgba(54, 162, 235, 1)',
  'rgba(255, 206, 86, 1)',
  'rgba(75, 192, 192, 1)',
  'rgba(153, 102, 255, 1)'
]

// Load available keys
const loadKeys = async () => {
  try {
    loadingKeys.value = true
    const result = await getAvailableVennKeys()
    availableKeys.value = result.keys || []
  } catch (err) {
    console.error('Error loading keys:', err)
    error.value = 'Error al cargar las variables disponibles'
  } finally {
    loadingKeys.value = false
  }
}

// Generate Venn diagram
const generateVenn = async () => {
  if (selectedKeys.value.length < 2) {
    error.value = 'Selecciona al menos 2 variables'
    return
  }

  try {
    loading.value = true
    error.value = null
    vennData.value = null

    const data = await getVennData(selectedKeys.value)
    vennData.value = data

    await nextTick()
    drawVennDiagram(data)
  } catch (err) {
    console.error('Error generating Venn:', err)
    error.value = 'Error al generar el diagrama'
  } finally {
    loading.value = false
  }
}

// Draw Venn diagram using D3
const drawVennDiagram = (data) => {
  if (!vennContainer.value || !data.sets || data.sets.length === 0) return

  // Clear previous
  d3.select(vennContainer.value).selectAll('*').remove()

  const width = 700
  const height = 500
  const sets = data.sets

  // Create SVG
  const svg = d3.select(vennContainer.value)
    .append('svg')
    .attr('id', 'venn-svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)

  // Calculate positions based on number of sets
  const centerX = width / 2
  const centerY = height / 2
  const baseRadius = 100

  // Position circles
  const circleData = sets.map((set, i) => {
    const angle = (2 * Math.PI * i) / sets.length - Math.PI / 2
    const distance = sets.length > 2 ? 80 : 60
    const x = centerX + Math.cos(angle) * distance
    const y = centerY + Math.sin(angle) * distance
    const radius = baseRadius + Math.sqrt(set.size) * 2
    
    return {
      ...set,
      x,
      y,
      radius: Math.min(radius, 150),
      color: colors[i % colors.length],
      strokeColor: strokeColors[i % strokeColors.length]
    }
  })

  // Draw circles
  svg.selectAll('circle')
    .data(circleData)
    .enter()
    .append('circle')
    .attr('cx', d => d.x)
    .attr('cy', d => d.y)
    .attr('r', d => d.radius)
    .attr('fill', d => d.color)
    .attr('stroke', d => d.strokeColor)
    .attr('stroke-width', 2)
    .style('mix-blend-mode', 'multiply')

  // Add labels
  svg.selectAll('.set-label')
    .data(circleData)
    .enter()
    .append('text')
    .attr('class', 'set-label')
    .attr('x', d => d.x)
    .attr('y', d => d.y - d.radius - 10)
    .attr('text-anchor', 'middle')
    .attr('font-size', '14px')
    .attr('font-weight', 'bold')
    .attr('fill', d => d.strokeColor)
    .text(d => `${d.name} (${d.size})`)

  // Add size labels inside circles
  svg.selectAll('.size-label')
    .data(circleData)
    .enter()
    .append('text')
    .attr('class', 'size-label')
    .attr('x', d => d.x)
    .attr('y', d => d.y)
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '18px')
    .attr('font-weight', 'bold')
    .attr('fill', '#333')
    .text(d => d.size)

  // Add intersection labels if 2-3 sets
  if (data.intersections && sets.length <= 3) {
    const mainIntersection = data.intersections.find(i => i.sets.length === sets.length)
    if (mainIntersection) {
      svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', '16px')
        .attr('font-weight', 'bold')
        .attr('fill', '#333')
        .text(`∩: ${mainIntersection.size}`)
    }
  }

  // Add title
  svg.append('text')
    .attr('x', centerX)
    .attr('y', 30)
    .attr('text-anchor', 'middle')
    .attr('font-size', '18px')
    .attr('font-weight', 'bold')
    .attr('fill', '#2c3e50')
    .text(`Diagrama de Venn: ${selectedKeys.value.join(', ')}`)
}

// Export to SVG
const exportSVG = () => {
  const svgElement = document.getElementById('venn-svg')
  if (!svgElement) return

  const serializer = new XMLSerializer()
  const svgString = serializer.serializeToString(svgElement)
  const blob = new Blob([svgString], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = 'venn-diagram.svg'
  link.click()

  URL.revokeObjectURL(url)
}

// Export to PDF
const exportPDF = async () => {
  try {
    const { default: html2canvas } = await import('html2canvas')
    const { default: jsPDF } = await import('jspdf')

    const svgElement = document.getElementById('venn-svg')
    if (!svgElement) return

    // Convert SVG to canvas
    const canvas = await html2canvas(vennContainer.value, {
      backgroundColor: '#ffffff',
      scale: 2
    })

    // Create PDF
    const pdf = new jsPDF('l', 'mm', 'a4')
    const imgData = canvas.toDataURL('image/png')
    const pdfWidth = pdf.internal.pageSize.getWidth()
    const pdfHeight = (canvas.height * pdfWidth) / canvas.width

    pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight)
    pdf.save('venn-diagram.pdf')
  } catch (err) {
    console.error('Error exporting PDF:', err)
    alert('Error al exportar PDF. Asegúrate de que las dependencias están instaladas.')
  }
}

// Lifecycle
onMounted(() => {
  loadKeys()
})
</script>

<style scoped>
/* Premium Dark Theme - Venn Diagram */
.venn-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 500px;
  background: rgba(26, 26, 36, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 2rem;
}

.text-muted {
  color: #5A5A6E;
  font-size: 0.9rem;
}
</style>
