<!--
  Agent Chat View - Main Interface for Multi-Agent System
  Allows users to interact with AI agents via natural language
-->
<template>
  <div class="chat-view">
    <!-- Hero section -->
    <div class="hero-section">
      <h1 class="page-title">🕊️ Asistente de Organizaciones</h1>
      <p class="hero-subtitle">
        Consulta información sobre organizaciones de mujeres constructoras de paz en Colombia
      </p>
    </div>

    <!-- Main chat container -->
    <div class="chat-container">
      <!-- Messages area -->
      <div class="messages-area" ref="messagesContainer">
        <!-- Welcome message -->
        <div v-if="messages.length === 0" class="welcome-message">
          <div class="welcome-icon">🕊️</div>
          <h2>¡Bienvenido al Asistente de Organizaciones!</h2>
          <p>Puedo ayudarte a buscar información sobre organizaciones de la sociedad civil lideradas por mujeres constructoras de paz en Colombia.</p>
          
          <div class="example-queries">
            <h3>Ejemplos de consultas:</h3>
            <div class="examples-grid">
              <button 
                v-for="example in examples" 
                :key="example.query"
                class="example-btn"
                @click="sendExample(example.query)"
              >
                <span class="example-icon">💡</span>
                <span class="example-text">{{ example.query }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Chat messages -->
        <div v-for="(message, index) in messages" :key="index" class="message-wrapper">
          <div :class="['message', message.role]">
            <div class="message-avatar">
              {{ message.role === 'user' ? '👤' : '🤖' }}
            </div>
            <div class="message-content">
              <div class="message-header">
                <span class="message-role">{{ message.role === 'user' ? 'Tú' : 'Asistente' }}</span>
                <span class="message-time">{{ formatTime(message.timestamp) }}</span>
              </div>
              <div class="message-text" v-html="formatMessage(message.content)"></div>
              
              <!-- Metadata for assistant messages -->
              <div v-if="message.role === 'assistant' && message.metadata" class="message-metadata">
                <span v-if="message.metadata.iterations" class="metadata-item">
                  ⚙️ {{ message.metadata.iterations }} iteraciones
                </span>
                <span v-if="message.metadata.success" class="metadata-item success">
                  ✅ Completado
                </span>
                <span v-else-if="message.metadata.success === false" class="metadata-item error">
                  ⚠️ Con errores
                </span>
              </div>
              
              <!-- Feedback buttons -->
              <div v-if="message.role === 'assistant'" class="feedback-buttons">
                <button 
                  class="feedback-btn positive"
                  :class="{ active: message.feedback === 'positive' }"
                  @click="submitFeedback(index, 1, 'positive')"
                  title="Respuesta útil"
                >
                  👍
                </button>
                <button 
                  class="feedback-btn negative"
                  :class="{ active: message.feedback === 'negative' }"
                  @click="submitFeedback(index, 0, 'negative')"
                  title="Respuesta no útil"
                >
                  👎
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Loading indicator -->
        <div v-if="isLoading" class="message-wrapper">
          <div class="message assistant loading">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
              <div class="loading-indicator">
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-text">Procesando tu consulta...</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="input-area">
        <div class="input-container">
          <textarea
            v-model="inputMessage"
            @keydown.enter="handleEnter"
            placeholder="Escribe tu consulta sobre organizaciones de mujeres constructoras de paz..."
            :disabled="isLoading"
            rows="1"
            ref="inputField"
          ></textarea>
          <button 
            class="send-btn" 
            @click="sendMessage"
            :disabled="!inputMessage.trim() || isLoading"
          >
            <span v-if="isLoading">⏳</span>
            <span v-else>📤</span>
          </button>
        </div>
        <div class="input-hint">
          Presiona Enter para enviar, Shift+Enter para nueva línea
        </div>
      </div>
    </div>

    <!-- Side panel: Agent Status -->
    <div class="side-panel">
      <div class="panel-card">
        <h3>🔄 Estado del Sistema</h3>
        <div class="status-item">
          <span class="status-dot" :class="systemStatus.status"></span>
          <span>{{ systemStatus.status === 'operational' ? 'Operativo' : 'Verificando...' }}</span>
        </div>
        <div class="agents-status">
          <div v-for="(status, agent) in systemStatus.agents" :key="agent" class="agent-status">
            <span class="agent-icon">{{ getAgentIcon(agent) }}</span>
            <span class="agent-name">{{ formatAgentName(agent) }}</span>
            <span class="status-badge" :class="status">{{ status }}</span>
          </div>
        </div>
      </div>

      <div class="panel-card">
        <h3>📊 Sesión Actual</h3>
        <div class="session-info">
          <div class="info-row">
            <span class="info-label">Mensajes:</span>
            <span class="info-value">{{ messages.length }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Sesión:</span>
            <span class="info-value session-id">{{ sessionId ? sessionId.substring(0, 8) + '...' : 'Nueva' }}</span>
          </div>
        </div>
        <button class="btn btn-outline btn-sm" @click="clearChat">
          🗑️ Limpiar Chat
        </button>
      </div>

      <div class="panel-card">
        <h3>📈 Visualización del Grafo</h3>
        <button class="btn btn-secondary btn-sm" @click="showGraphModal = true">
          🔍 Ver Flujo de Agentes
        </button>
      </div>
    </div>

    <!-- Graph Visualization Modal -->
    <div v-if="showGraphModal" class="modal-overlay" @click.self="showGraphModal = false">
      <div class="modal-content graph-modal">
        <div class="modal-header">
          <h2>🔄 Flujo de Agentes</h2>
          <button class="modal-close" @click="showGraphModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="graph-container">
            <div ref="mermaidContainer" class="mermaid-diagram"></div>
          </div>
          <div class="graph-description" v-html="formatMessage(graphVisualization.description)"></div>
        </div>
      </div>
    </div>

    <!-- Pending Validations Panel (floating) -->
    <div v-if="pendingValidations.length > 0" class="validations-panel">
      <div class="validations-header">
        <h4>⏳ Validaciones Pendientes ({{ pendingValidations.length }})</h4>
      </div>
      <div class="validations-list">
        <div v-for="validation in pendingValidations" :key="validation.id" class="validation-card">
          <div class="validation-type">
            <span v-if="validation.item_type === 'organization'">👩 Organización</span>
            <span v-else-if="validation.item_type === 'info_source'">📚 Fuente</span>
            <span v-else>📝 Actualización</span>
          </div>
          <div class="validation-name">
            {{ validation.pending_data.nombre || validation.pending_data.name || 'Sin nombre' }}
          </div>
          <div class="validation-confidence">
            Confianza: {{ (validation.confidence_score * 100).toFixed(0) }}%
          </div>
          <div class="validation-actions">
            <button class="btn btn-sm btn-success" @click="approveValidation(validation)" title="Aprobar">
              ✅
            </button>
            <button class="btn btn-sm btn-secondary" @click="openValidationModal(validation)" title="Revisar/Modificar">
              ✏️
            </button>
            <button class="btn btn-sm btn-danger" @click="rejectValidation(validation)" title="Rechazar">
              ❌
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Validation Edit Modal -->
    <div v-if="showValidationModal && currentValidation" class="modal-overlay" @click.self="showValidationModal = false">
      <div class="modal-content validation-modal">
        <div class="modal-header">
          <h2>
            <span v-if="currentValidation.item_type === 'organization'">👩 Revisar Organización</span>
            <span v-else-if="currentValidation.item_type === 'info_source'">📚 Revisar Fuente</span>
            <span v-else>📝 Revisar Datos</span>
          </h2>
          <button class="modal-close" @click="showValidationModal = false">✕</button>
        </div>
        <div class="modal-body">
          <!-- Organization Form -->
          <div v-if="currentValidation.item_type === 'organization'" class="validation-form">
            <div class="form-group">
              <label>Nombre de la Organización *</label>
              <input v-model="validationModifications.nombre" type="text" class="form-control" />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Departamento</label>
                <input v-model="validationModifications.departamento" type="text" class="form-control" />
              </div>
              <div class="form-group">
                <label>Municipio</label>
                <input v-model="validationModifications.municipio" type="text" class="form-control" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Alcance Territorial</label>
                <select v-model="validationModifications.alcance_territorial" class="form-control">
                  <option value="municipal">Municipal</option>
                  <option value="departamental">Departamental</option>
                  <option value="regional">Regional</option>
                  <option value="nacional">Nacional</option>
                </select>
              </div>
              <div class="form-group">
                <label>Enfoque/Origen</label>
                <select v-model="validationModifications.approach" class="form-control">
                  <option value="bottom_up">🌱 Desde abajo (comunitaria)</option>
                  <option value="top_down">🏛️ Desde arriba (gubernamental)</option>
                  <option value="mixed">🔄 Mixto</option>
                  <option value="unknown">❓ Desconocido</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Años Activa</label>
                <input v-model.number="validationModifications.years_active" type="number" class="form-control" />
              </div>
              <div class="form-group">
                <label>Número de Mujeres</label>
                <input v-model.number="validationModifications.women_count" type="number" class="form-control" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Nombre del Líder</label>
                <input v-model="validationModifications.leader_name" type="text" class="form-control" />
              </div>
              <div class="form-group">
                <label>¿El líder es mujer?</label>
                <select v-model="validationModifications.leader_is_woman" class="form-control">
                  <option :value="true">Sí</option>
                  <option :value="false">No</option>
                  <option :value="null">No especificado</option>
                </select>
              </div>
            </div>
            <div class="form-group">
              <label>URL / Sitio Web</label>
              <input v-model="validationModifications.url" type="url" class="form-control" />
            </div>
            <div class="form-group">
              <label>Descripción / Actividad Principal</label>
              <textarea v-model="validationModifications.actividad_principal" class="form-control" rows="2"></textarea>
            </div>
          </div>
          
          <!-- Info Source Form -->
          <div v-else-if="currentValidation.item_type === 'info_source'" class="validation-form">
            <div class="form-group">
              <label>Nombre de la Fuente *</label>
              <input v-model="validationModifications.name" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label>URL *</label>
              <input v-model="validationModifications.url" type="url" class="form-control" />
            </div>
            <div class="form-group">
              <label>Tipo de Fuente</label>
              <select v-model="validationModifications.source_type" class="form-control">
                <option value="government">🏛️ Gobierno</option>
                <option value="registry">📋 Registro Oficial</option>
                <option value="ngo">🌱 ONG</option>
                <option value="academic">🎓 Académico</option>
                <option value="news">📰 Noticias</option>
                <option value="cooperative">🤝 Cooperativa</option>
                <option value="international">🌍 Internacional</option>
                <option value="other">📎 Otro</option>
              </select>
            </div>
            <div class="form-group">
              <label>Descripción</label>
              <textarea v-model="validationModifications.description" class="form-control" rows="2"></textarea>
            </div>
          </div>

          <!-- Agent Reasoning -->
          <div v-if="currentValidation.agent_reasoning" class="agent-reasoning">
            <h4>💡 Razonamiento del Agente:</h4>
            <p>{{ currentValidation.agent_reasoning }}</p>
          </div>

          <!-- Source URLs -->
          <div v-if="currentValidation.source_urls && currentValidation.source_urls.length" class="source-urls">
            <h4>🔗 Fuentes:</h4>
            <ul>
              <li v-for="url in currentValidation.source_urls" :key="url">
                <a :href="url" target="_blank" rel="noopener">{{ url }}</a>
              </li>
            </ul>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showValidationModal = false">Cancelar</button>
          <button class="btn btn-danger" @click="submitValidationDecision('rejected')">❌ Rechazar</button>
          <button class="btn btn-success" @click="submitValidationDecision('approved')">✅ Aprobar</button>
          <button class="btn btn-primary" @click="submitValidationDecision('modified')">💾 Guardar Modificaciones</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { marked } from 'marked';
import mermaid from 'mermaid';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Initialize mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#5B7FFF',
    primaryTextColor: '#FFFFFF',
    primaryBorderColor: '#8B5CF6',
    lineColor: '#8B8B9E',
    secondaryColor: '#2A2A3C',
    tertiaryColor: '#1A1A2E',
    background: '#1A1A2E',
    mainBkg: '#2A2A3C',
    nodeBorder: '#5B7FFF',
    clusterBkg: '#2A2A3C',
    titleColor: '#FFFFFF',
    edgeLabelBackground: '#2A2A3C'
  },
  flowchart: {
    curve: 'basis',
    padding: 20
  }
});

export default {
  name: 'AgentChatView',
  
  data() {
    return {
      inputMessage: '',
      messages: [],
      isLoading: false,
      sessionId: null,
      showGraphModal: false,
      showValidationModal: false,
      currentValidation: null,
      validationModifications: {},
      pendingValidations: [],
      systemStatus: {
        status: 'checking',
        agents: {}
      },
      graphVisualization: {
        mermaid: '',
        description: ''
      },
      examples: [
        { query: "Busca organizaciones de mujeres constructoras de paz en Cauca" },
        { query: "¿Qué colectivos de mujeres víctimas hay en Nariño?" },
        { query: "Información sobre organizaciones de derechos humanos en Meta" },
        { query: "Lista de fundaciones de mujeres en Chocó" },
        { query: "Organizaciones de mujeres trabajando en reconciliación" }
      ]
    }
  },

  async mounted() {
    await this.checkSystemStatus();
    await this.loadGraphVisualization();
    this.loadSessionHistory();
    this.focusInput();
  },

  methods: {
    async sendMessage() {
      if (!this.inputMessage.trim() || this.isLoading) return;

      const userMessage = this.inputMessage.trim();
      this.inputMessage = '';
      
      // Add user message
      this.messages.push({
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString()
      });
      
      this.scrollToBottom();
      this.isLoading = true;

      try {
        const response = await fetch(`${API_BASE}/chat/send`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: userMessage,
            session_id: this.sessionId
          })
        });

        const data = await response.json();
        
        // Update session ID
        if (data.session_id) {
          this.sessionId = data.session_id;
        }

        // Add assistant message
        this.messages.push({
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString(),
          metadata: {
            success: data.success,
            iterations: data.iterations,
            errors: data.metadata?.errors || [],
            requires_validation: data.requires_validation
          },
          pending_organizations: data.pending_organizations || [],
          pending_sources: data.pending_sources || []
        });
        
        // Load pending validations if any
        if (data.requires_validation) {
          await this.loadPendingValidations();
        }

      } catch (error) {
        console.error('Error sending message:', error);
        this.messages.push({
          role: 'assistant',
          content: 'Lo siento, hubo un error al procesar tu solicitud. Por favor, intenta de nuevo.',
          timestamp: new Date().toISOString(),
          metadata: { success: false, errors: [error.message] }
        });
      } finally {
        this.isLoading = false;
        this.scrollToBottom();
        this.focusInput();
      }
    },

    sendExample(query) {
      this.inputMessage = query;
      this.sendMessage();
    },

    handleEnter(event) {
      if (event.shiftKey) {
        // Allow new line with Shift+Enter
        return;
      }
      // Prevent default only for Enter without Shift
      event.preventDefault();
      this.sendMessage();
    },

    async submitFeedback(messageIndex, score, type) {
      const message = this.messages[messageIndex];
      message.feedback = type;

      try {
        await fetch(`${API_BASE}/chat/feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            session_id: this.sessionId,
            score: score,
            comment: type === 'positive' ? 'Respuesta útil' : 'Respuesta no útil'
          })
        });
      } catch (error) {
        console.error('Error submitting feedback:', error);
      }
    },

    async checkSystemStatus() {
      try {
        const response = await fetch(`${API_BASE}/chat/status`);
        this.systemStatus = await response.json();
      } catch (error) {
        console.error('Error checking system status:', error);
        this.systemStatus = { status: 'error', agents: {} };
      }
    },

    async loadGraphVisualization() {
      try {
        const response = await fetch(`${API_BASE}/chat/graph`);
        this.graphVisualization = await response.json();
      } catch (error) {
        console.error('Error loading graph:', error);
      }
    },

    async renderMermaidDiagram() {
      if (!this.graphVisualization.mermaid || !this.$refs.mermaidContainer) return;
      
      try {
        // Clear previous content
        this.$refs.mermaidContainer.innerHTML = '';
        
        // Generate unique ID
        const id = 'mermaid-' + Date.now();
        
        // Render the diagram
        const { svg } = await mermaid.render(id, this.graphVisualization.mermaid);
        this.$refs.mermaidContainer.innerHTML = svg;
      } catch (error) {
        console.error('Error rendering mermaid:', error);
        // Fallback to showing code
        this.$refs.mermaidContainer.innerHTML = `<pre class="mermaid-fallback">${this.graphVisualization.mermaid}</pre>`;
      }
    },

    loadSessionHistory() {
      const savedSession = localStorage.getItem('chat_session_id');
      if (savedSession) {
        this.sessionId = savedSession;
        this.loadHistory();
      }
    },

    async loadHistory() {
      if (!this.sessionId) return;

      try {
        const response = await fetch(`${API_BASE}/chat/history/${this.sessionId}`);
        if (response.ok) {
          const data = await response.json();
          this.messages = data.messages.map(m => ({
            role: m.role,
            content: m.content,
            timestamp: m.timestamp
          }));
        }
      } catch (error) {
        console.error('Error loading history:', error);
      }
    },

    async clearChat() {
      if (this.sessionId) {
        try {
          await fetch(`${API_BASE}/chat/history/${this.sessionId}`, {
            method: 'DELETE'
          });
        } catch (error) {
          console.error('Error clearing history:', error);
        }
      }
      
      this.messages = [];
      this.sessionId = null;
      localStorage.removeItem('chat_session_id');
    },

    formatMessage(content) {
      if (!content) return '';
      return marked(content, { breaks: true });
    },

    formatTime(timestamp) {
      if (!timestamp) return '';
      const date = new Date(timestamp);
      return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    },

    formatAgentName(agent) {
      const names = {
        guardrails: 'Guardrails',
        orchestrator: 'Orquestador',
        scraper: 'Buscador',
        classifier: 'Clasificador',
        evaluator: 'Evaluador',
        venn_agent: 'Agente Venn',
        db_agent: 'Base de Datos',
        validator: 'Validador',
        synthesizer: 'Sintetizador',
        finalizer: 'Finalizador'
      };
      return names[agent] || agent;
    },

    getAgentIcon(agent) {
      const icons = {
        guardrails: '🛡️',
        orchestrator: '🎯',
        scraper: '🔍',
        classifier: '📊',
        evaluator: '✅',
        venn_agent: '🔵',
        db_agent: '🗄️',
        validator: '✔️',
        synthesizer: '🧠',
        finalizer: '📝'
      };
      return icons[agent] || '🤖';
    },

    // Validation Methods
    async loadPendingValidations() {
      if (!this.sessionId) return;
      
      try {
        const response = await fetch(`${API_BASE}/validations/session/${this.sessionId}`);
        if (response.ok) {
          const data = await response.json();
          this.pendingValidations = data.validations || [];
        }
      } catch (error) {
        console.error('Error loading pending validations:', error);
      }
    },

    openValidationModal(validation) {
      this.currentValidation = validation;
      this.validationModifications = { ...validation.pending_data };
      this.showValidationModal = true;
    },

    async submitValidationDecision(decision) {
      if (!this.currentValidation) return;
      
      try {
        const body = {
          decision: decision
        };
        
        if (decision === 'modified') {
          body.modifications = this.validationModifications;
        }
        
        const response = await fetch(`${API_BASE}/validations/${this.currentValidation.id}/decide`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        
        if (response.ok) {
          const result = await response.json();
          
          // Add confirmation message to chat
          const actionText = decision === 'approved' ? 'aprobada' : 
                            decision === 'rejected' ? 'rechazada' : 'modificada y guardada';
          const itemType = this.currentValidation.item_type === 'organization' ? 'organización' : 'fuente de información';
          
          this.messages.push({
            role: 'assistant',
            content: `✅ **${itemType.charAt(0).toUpperCase() + itemType.slice(1)} ${actionText}**\n\n${result.message}`,
            timestamp: new Date().toISOString(),
            metadata: { success: true }
          });
          
          // Remove from pending list
          this.pendingValidations = this.pendingValidations.filter(v => v.id !== this.currentValidation.id);
          
          this.showValidationModal = false;
          this.currentValidation = null;
          this.scrollToBottom();
        }
      } catch (error) {
        console.error('Error submitting validation:', error);
      }
    },

    async approveValidation(validation) {
      this.currentValidation = validation;
      await this.submitValidationDecision('approved');
    },

    async rejectValidation(validation) {
      this.currentValidation = validation;
      await this.submitValidationDecision('rejected');
    },

    getApproachLabel(approach) {
      const labels = {
        'bottom_up': '🌱 Desde abajo (comunitaria)',
        'top_down': '🏛️ Desde arriba (gubernamental)',
        'mixed': '🔄 Mixto',
        'unknown': '❓ Desconocido'
      };
      return labels[approach] || approach;
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },

    focusInput() {
      this.$nextTick(() => {
        const input = this.$refs.inputField;
        if (input) {
          input.focus();
        }
      });
    }
  },

  watch: {
    sessionId(newVal) {
      if (newVal) {
        localStorage.setItem('chat_session_id', newVal);
      }
    },
    showGraphModal(newVal) {
      if (newVal) {
        // Wait for DOM to update, then render
        this.$nextTick(() => {
          this.renderMermaidDiagram();
        });
      }
    }
  }
}
</script>

<style scoped>
.chat-view {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: var(--space-4);
  height: calc(100vh - 120px);
  padding: var(--space-4);
}

.hero-section {
  grid-column: 1 / -1;
  text-align: center;
  padding: var(--space-4);
  background: linear-gradient(135deg, var(--colombia-yellow) 0%, var(--colombia-blue) 50%, var(--colombia-red) 100%);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-4);
}

.page-title {
  color: white;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.hero-subtitle {
  color: rgba(255,255,255,0.9);
  margin-top: var(--space-2);
}

/* Chat Container */
.chat-container {
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* Welcome Message */
.welcome-message {
  text-align: center;
  padding: var(--space-8);
  animation: fadeIn 0.5s ease;
}

.welcome-icon {
  font-size: 4rem;
  margin-bottom: var(--space-4);
}

.welcome-message h2 {
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.welcome-message p {
  color: var(--text-secondary);
  margin-bottom: var(--space-6);
}

.example-queries h3 {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-3);
}

.examples-grid {
  display: grid;
  gap: var(--space-2);
  max-width: 600px;
  margin: 0 auto;
}

.example-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.example-btn:hover {
  background: var(--bg-hover);
  border-color: var(--colombia-yellow);
  transform: translateX(4px);
}

.example-icon {
  font-size: 1.2rem;
}

.example-text {
  color: var(--text-primary);
}

/* Messages */
.message-wrapper {
  animation: slideIn 0.3s ease;
}

.message {
  display: flex;
  gap: var(--space-3);
  max-width: 85%;
}

.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message.assistant {
  margin-right: auto;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: var(--colombia-blue);
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, var(--colombia-yellow), var(--colombia-blue));
}

.message-content {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
}

.message.user .message-content {
  background: var(--colombia-blue);
  border-color: var(--colombia-blue);
}

.message.user .message-text {
  color: white;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
  font-size: var(--text-xs);
}

.message-role {
  font-weight: 600;
  color: var(--text-secondary);
}

.message.user .message-role {
  color: rgba(255,255,255,0.8);
}

.message-time {
  color: var(--text-muted);
}

.message.user .message-time {
  color: rgba(255,255,255,0.6);
}

.message-text {
  color: var(--text-primary);
  line-height: 1.6;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3) {
  margin-top: var(--space-3);
  margin-bottom: var(--space-2);
  color: var(--text-primary);
}

.message-text :deep(ul),
.message-text :deep(ol) {
  padding-left: var(--space-4);
  margin: var(--space-2) 0;
}

.message-text :deep(code) {
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.message-text :deep(pre) {
  background: var(--bg-tertiary);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  overflow-x: auto;
}

/* Message Metadata */
.message-metadata {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
  font-size: var(--text-xs);
}

.metadata-item {
  padding: 2px 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
}

.metadata-item.success {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
}

.metadata-item.error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--error);
}

/* Feedback Buttons */
.feedback-buttons {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.feedback-btn {
  padding: 4px 8px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  opacity: 0.6;
}

.feedback-btn:hover {
  opacity: 1;
}

.feedback-btn.active {
  opacity: 1;
}

.feedback-btn.positive.active {
  background: rgba(16, 185, 129, 0.2);
  border-color: var(--success);
}

.feedback-btn.negative.active {
  background: rgba(239, 68, 68, 0.2);
  border-color: var(--error);
}

/* Loading Indicator */
.loading-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.loading-dot {
  width: 8px;
  height: 8px;
  background: var(--colombia-yellow);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dot:nth-child(2) { animation-delay: -0.16s; }
.loading-dot:nth-child(3) { animation-delay: 0; }

.loading-text {
  color: var(--text-muted);
  font-size: var(--text-sm);
  margin-left: var(--space-2);
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* Input Area */
.input-area {
  padding: var(--space-4);
  background: var(--bg-tertiary);
  border-top: 1px solid var(--border-color);
}

.input-container {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
}

.input-container textarea {
  flex: 1;
  padding: var(--space-3);
  background: var(--bg-primary);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-base);
  resize: none;
  min-height: 48px;
  max-height: 120px;
  transition: border-color var(--transition-fast);
}

.input-container textarea:focus {
  outline: none;
  border-color: var(--colombia-yellow);
}

.input-container textarea::placeholder {
  color: var(--text-muted);
}

.send-btn {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, var(--colombia-yellow), var(--colombia-blue));
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 1.4rem;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  text-align: center;
}

/* Side Panel */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.panel-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  border: 1px solid var(--border-color);
}

.panel-card h3 {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-color);
}

.status-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-dot.operational {
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
}

.status-dot.error {
  background: var(--error);
}

.agents-status {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.agent-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.agent-icon {
  font-size: 1rem;
}

.agent-name {
  flex: 1;
  color: var(--text-secondary);
}

.status-badge {
  font-size: var(--text-xs);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-muted);
}

.status-badge.active {
  background: rgba(16, 185, 129, 0.1);
  color: var(--success);
}

.session-info {
  margin-bottom: var(--space-3);
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-sm);
  padding: var(--space-1) 0;
}

.info-label {
  color: var(--text-muted);
}

.info-value {
  color: var(--text-primary);
}

.session-id {
  font-family: monospace;
  font-size: var(--text-xs);
}

.btn-sm {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  width: 100%;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
}

.modal-content {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.modal-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: var(--space-4);
  overflow-y: auto;
}

.graph-container {
  background: var(--bg-tertiary);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  overflow-x: auto;
}

.mermaid-code {
  font-family: monospace;
  font-size: var(--text-sm);
  color: var(--text-primary);
  white-space: pre-wrap;
}

.mermaid-diagram {
  width: 100%;
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.mermaid-diagram svg {
  max-width: 100%;
  height: auto;
}

.mermaid-fallback {
  font-family: monospace;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: pre-wrap;
  background: var(--bg-primary);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
}

.graph-description {
  color: var(--text-secondary);
  line-height: 1.6;
}

/* Pending Validations Panel */
.validations-panel {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 320px;
  max-height: 400px;
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 2px solid var(--colombia-yellow);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  z-index: 100;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.validations-header {
  background: linear-gradient(135deg, var(--colombia-yellow), var(--colombia-blue));
  padding: var(--space-3);
  color: white;
}

.validations-header h4 {
  margin: 0;
  font-size: var(--text-sm);
}

.validations-list {
  padding: var(--space-2);
  max-height: 320px;
  overflow-y: auto;
}

.validation-card {
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-2);
  border: 1px solid var(--border-color);
}

.validation-type {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-bottom: var(--space-1);
}

.validation-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.validation-confidence {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.validation-actions {
  display: flex;
  gap: var(--space-2);
}

.validation-actions .btn {
  flex: 1;
  padding: var(--space-1) var(--space-2);
  font-size: 1rem;
}

/* Validation Modal */
.validation-modal {
  max-width: 700px;
}

.validation-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.form-group label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

.form-group .form-control {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.form-group .form-control:focus {
  outline: none;
  border-color: var(--colombia-yellow);
}

.form-group textarea.form-control {
  resize: vertical;
  min-height: 60px;
}

.agent-reasoning {
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-top: var(--space-3);
  border-left: 3px solid var(--colombia-blue);
}

.agent-reasoning h4 {
  margin: 0 0 var(--space-2) 0;
  font-size: var(--text-sm);
  color: var(--colombia-yellow);
}

.agent-reasoning p {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.source-urls {
  margin-top: var(--space-3);
}

.source-urls h4 {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.source-urls ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.source-urls li {
  padding: var(--space-1) 0;
}

.source-urls a {
  color: var(--colombia-blue);
  font-size: var(--text-sm);
  word-break: break-all;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4);
  border-top: 1px solid var(--border-color);
  background: var(--bg-tertiary);
}

.btn-success {
  background: var(--success);
  color: white;
}

.btn-success:hover {
  background: #059669;
}

.btn-danger {
  background: var(--error);
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive */
@media (max-width: 768px) {
  .chat-view {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100vh - 120px);
  }

  .side-panel {
    order: -1;
    flex-direction: row;
    flex-wrap: wrap;
  }

  .panel-card {
    flex: 1;
    min-width: 200px;
  }

  .hero-section {
    padding: var(--space-3);
  }

  .page-title {
    font-size: 1.5rem;
  }

  .message {
    max-width: 95%;
  }

  .validations-panel {
    width: calc(100% - 40px);
    right: 20px;
    left: 20px;
  }

  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
