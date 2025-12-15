<!--
  Main App component - Colombia Theme
  Asistente OSC - Organizaciones de Mujeres Constructoras de Paz
-->
<template>
  <div id="app">
    <!-- Navigation -->
    <nav class="nav">
      <router-link to="/" class="nav-brand">
        <span class="brand-icon">🕊️</span>
        <span class="brand-text">Asistente OSC</span>
      </router-link>
      <ul class="nav-links">
        <li><router-link to="/">🏠 Inicio</router-link></li>
        <li><router-link to="/chat" class="nav-highlight">💬 Asistente</router-link></li>
        <li><router-link to="/organizations">👩 Organizaciones</router-link></li>
        <li><router-link to="/venn">🔵 Venn</router-link></li>
        <li><router-link to="/venn-results">🔍 Verificación</router-link></li>
        <li><router-link to="/tosmana">📊 QCA</router-link></li>
        <li><router-link to="/map">🗺️ Mapa</router-link></li>
        <li><router-link to="/data-results">📈 Resultados</router-link></li>
      </ul>
    </nav>

    <!-- Main content -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- Footer -->
    <footer class="footer">
      <div class="footer-content">
        <p class="footer-brand">🕊️ Asistente OSC Colombia</p>
        <p class="footer-sub">Sistema de recopilación y análisis de datos de organizaciones de mujeres constructoras de paz</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
// App component - handles navigation layout
// Colombian theme applied through CSS variables
</script>

<style scoped>
/* Component-specific styles are in main.css */
</style>
