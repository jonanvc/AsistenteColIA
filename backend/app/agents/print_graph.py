#!/usr/bin/env python3
"""
Script para visualizar el grafo del sistema multi-agente.
Genera una imagen PNG del flujo de agentes.

Uso:
    python print_graph.py [output_path]
    
Ejemplo:
    python print_graph.py grafo_agentes.png
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys


def create_agent_graph_visualization(output_path="agent_graph.png"):
    """
    Crea una visualización del grafo de agentes usando solo matplotlib.
    No requiere instalación adicional de librerías externas.
    """
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    ax.set_title(
        "Sistema Multi-Agente para Organizaciones de Mujeres Constructoras de Paz",
        fontsize=16, fontweight='bold', pad=20
    )
    
    # Definir posiciones de los nodos (x, y)
    positions = {
        'start': (50, 95),
        'guardrails': (50, 82),
        'blocked': (20, 68),
        'orchestrator': (50, 68),
        'scraper': (20, 50),
        'classifier': (35, 50),
        'evaluator': (50, 50),
        'venn': (65, 50),
        'finalizer': (80, 50),
        'end': (50, 20),
    }
    
    # Definir colores y etiquetas de los nodos (sin emojis para compatibilidad)
    nodes = {
        'start': {'label': 'USUARIO', 'color': '#FFD700', 'shape': 'circle'},
        'guardrails': {'label': 'GUARDRAILS\n(GPT-4o-mini)', 'color': '#FF6B6B', 'shape': 'box'},
        'blocked': {'label': 'BLOQUEADO', 'color': '#FF4444', 'shape': 'box'},
        'orchestrator': {'label': 'ORQUESTADOR\n(GPT-4o)', 'color': '#4ECDC4', 'shape': 'box'},
        'scraper': {'label': 'SCRAPER\n(GPT-4o-mini\n+ Tavily)', 'color': '#45B7D1', 'shape': 'box'},
        'classifier': {'label': 'CLASIFICADOR\n(GPT-4o)', 'color': '#96CEB4', 'shape': 'box'},
        'evaluator': {'label': 'EVALUADOR\n(GPT-4o)', 'color': '#FFEAA7', 'shape': 'box'},
        'venn': {'label': 'VENN AGENT\n(GPT-4o-mini)', 'color': '#9B59B6', 'shape': 'box'},
        'finalizer': {'label': 'FINALIZADOR\n(GPT-4o-mini)', 'color': '#DDA0DD', 'shape': 'box'},
        'end': {'label': 'RESPUESTA', 'color': '#98D8C8', 'shape': 'circle'},
    }
    
    # Dibujar nodos
    for node_id, props in nodes.items():
        x, y = positions[node_id]
        if props['shape'] == 'circle':
            circle = plt.Circle((x, y), 4, color=props['color'], ec='black', lw=2, zorder=3)
            ax.add_patch(circle)
            ax.text(x, y, props['label'], ha='center', va='center', fontsize=9, fontweight='bold', zorder=4)
        else:
            width, height = 14, 8
            rect = mpatches.FancyBboxPatch(
                (x - width/2, y - height/2), width, height,
                boxstyle="round,pad=0.3,rounding_size=1",
                facecolor=props['color'], edgecolor='black', linewidth=2, zorder=3
            )
            ax.add_patch(rect)
            ax.text(x, y, props['label'], ha='center', va='center', fontsize=8, fontweight='bold', zorder=4)
    
    # Definir aristas (edges)
    edges = [
        ('start', 'guardrails', '', 'black'),
        ('guardrails', 'orchestrator', 'válido', 'green'),
        ('guardrails', 'blocked', 'inválido', 'red'),
        ('blocked', 'end', '', 'red'),
        ('orchestrator', 'scraper', '', 'blue'),
        ('orchestrator', 'classifier', '', 'blue'),
        ('orchestrator', 'evaluator', '', 'blue'),
        ('orchestrator', 'venn', '', 'purple'),
        ('orchestrator', 'finalizer', '', 'blue'),
        ('scraper', 'evaluator', '', 'gray'),
        ('classifier', 'evaluator', '', 'gray'),
        ('venn', 'finalizer', '', 'purple'),
        ('evaluator', 'orchestrator', 'correcciones', 'orange'),
        ('evaluator', 'finalizer', 'aprobado', 'green'),
        ('finalizer', 'end', '', 'black'),
    ]
    
    def draw_arrow(start, end, label='', color='black', offset=0):
        x1, y1 = positions[start]
        x2, y2 = positions[end]
        
        # Ajustar puntos de inicio y fin para no solapar con nodos
        dx = x2 - x1
        dy = y2 - y1
        dist = (dx**2 + dy**2)**0.5
        if dist > 0:
            # Acortar la flecha para que no entre en el nodo
            shrink = 5
            x1_adj = x1 + (dx/dist) * shrink
            y1_adj = y1 + (dy/dist) * shrink
            x2_adj = x2 - (dx/dist) * shrink
            y2_adj = y2 - (dy/dist) * shrink
        else:
            x1_adj, y1_adj = x1, y1
            x2_adj, y2_adj = x2, y2
        
        # Añadir offset para flechas paralelas
        if offset != 0:
            perp_x = -dy/dist * offset if dist > 0 else 0
            perp_y = dx/dist * offset if dist > 0 else 0
            x1_adj += perp_x
            y1_adj += perp_y
            x2_adj += perp_x
            y2_adj += perp_y
        
        ax.annotate(
            '', xy=(x2_adj, y2_adj), xytext=(x1_adj, y1_adj),
            arrowprops=dict(arrowstyle='->', color=color, lw=1.5),
            zorder=2
        )
        
        # Etiqueta de la arista
        if label:
            mid_x = (x1_adj + x2_adj) / 2 + (2 if offset >= 0 else -2)
            mid_y = (y1_adj + y2_adj) / 2
            ax.text(mid_x, mid_y, label, fontsize=7, color=color, 
                   ha='center', va='center', 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor=color))
    
    # Dibujar aristas
    for start, end, label, color in edges:
        # Offset para evitar superposición en evaluator->orchestrator
        offset = 2 if (start == 'evaluator' and end == 'orchestrator') else 0
        draw_arrow(start, end, label, color, offset)
    
    # Leyenda
    legend_elements = [
        mpatches.Patch(facecolor='#FFD700', edgecolor='black', label='Usuario'),
        mpatches.Patch(facecolor='#FF6B6B', edgecolor='black', label='Guardrails'),
        mpatches.Patch(facecolor='#4ECDC4', edgecolor='black', label='Orquestador'),
        mpatches.Patch(facecolor='#45B7D1', edgecolor='black', label='Scraper'),
        mpatches.Patch(facecolor='#96CEB4', edgecolor='black', label='Clasificador'),
        mpatches.Patch(facecolor='#FFEAA7', edgecolor='black', label='Evaluador'),
        mpatches.Patch(facecolor='#9B59B6', edgecolor='black', label='Venn Agent'),
        mpatches.Patch(facecolor='#DDA0DD', edgecolor='black', label='Finalizador'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)
    
    # Guardar imagen
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"✅ Grafo exportado a: {output_path}")
    
    # Mostrar también
    plt.show()
    
    return output_path


def print_mermaid_diagram():
    """Imprime el diagrama en formato Mermaid para usar en documentación."""
    mermaid = """
```mermaid
graph TD
    A[👤 Usuario] --> B{🛡️ Guardrails}
    B -->|Válido| C[🎯 Orquestador]
    B -->|Inválido| X[❌ Bloqueado]
    
    C --> D[🔍 Scraper]
    C --> E[📊 Clasificador]
    C --> F[✅ Evaluador]
    C --> V[📈 Venn Agent]
    C --> G[📝 Finalizador]
    
    D --> F
    E --> F
    V --> G
    F -->|Aprobado| G
    F -->|Correcciones| C
    
    G --> H[💬 Respuesta]
    X --> H
    
    style A fill:#FFD700
    style B fill:#FF6B6B
    style C fill:#4ECDC4
    style D fill:#45B7D1
    style E fill:#96CEB4
    style F fill:#FFEAA7
    style V fill:#9B59B6
    style G fill:#DDA0DD
    style H fill:#98D8C8
    style X fill:#FF6B6B
```
"""
    print(mermaid)
    return mermaid


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "agent_graph.png"
    
    print("=" * 60)
    print("Sistema Multi-Agente - Visualización del Grafo")
    print("=" * 60)
    print()
    
    # Generar imagen PNG
    create_agent_graph_visualization(output)
    
    print()
    print("=" * 60)
    print("Diagrama Mermaid (para documentación):")
    print("=" * 60)
    print_mermaid_diagram()
