# Sistema de Expresiones Lógicas Venn

## Descripción General

El sistema permite definir intersecciones Venn mediante expresiones booleanas complejas que combinan proxies con operadores AND y OR. Esto supera las limitaciones de los diagramas Venn tradicionales, permitiendo análisis más sofisticados.

## Arquitectura

### Estructura de Datos

Las expresiones lógicas se almacenan como árboles JSON en la columna `logic_expression`:

```json
{
  "type": "OR",
  "children": [
    {"type": "proxy", "id": 1},
    {"type": "proxy", "id": 2},
    {
      "type": "AND",
      "children": [
        {"type": "proxy", "id": 3},
        {"type": "proxy", "id": 4}
      ]
    }
  ]
}
```

### Tipos de Nodos

| Tipo | Descripción | Campos |
|------|-------------|--------|
| `proxy` | Referencia a un proxy existente | `id`: ID del proxy |
| `AND` | Operador lógico AND | `children`: Lista de nodos hijos |
| `OR` | Operador lógico OR | `children`: Lista de nodos hijos |

## Uso desde el Chat

### Listar Variables

```
Usuario: "Lista las variables Venn"
Sistema: 📊 5 variables Venn:
         • Justicia (Estructural/Social) (5 proxies)
         • Verdad (Cultura/Colectividad) (5 proxies)
         ...
```

### Ver Variable Específica

```
Usuario: "Muestra la variable Justicia"
Sistema: 📊 Variable Venn: Justicia (Estructural/Social)
         📝 Descripción: Sin descripción
         
         Proxies (5):
         1. Existen mercados campesinos locales...
         2. La propiedad de los recursos económicos...
         ...
```

### Crear Intersección Simple

```
Usuario: "Crea intersección con los proxies 'mercados campesinos', 'recursos económicos' operación AND"
Sistema: ✅ Intersección creada correctamente
         - Modo: proxy-based
         - Operación: AND (todos deben cumplirse)
```

### Crear Intersección con Expresión Lógica

```
Usuario: "Crea intersección: 'mercados campesinos' OR 'recursos económicos' OR ('procesos civiles' AND 'planes de desarrollo')"
Sistema: ✅ Intersección creada correctamente
         - Modo: Expresión lógica
         - Expresión: Proxy1 OR Proxy2 OR (Proxy3 AND Proxy4)
```

## Evaluación de Expresiones

El evaluador recorre el árbol de forma recursiva:

1. **Nodo `proxy`**: Verifica si el proxy tiene match en el contenido de la organización
2. **Nodo `AND`**: Retorna `true` solo si TODOS los hijos son `true`
3. **Nodo `OR`**: Retorna `true` si AL MENOS UN hijo es `true`

### Ejemplo de Evaluación

Para la expresión `A OR B OR (C AND D)`:

```
Organización X:
- Proxy A: encontrado ✓
- Proxy B: no encontrado ✗
- Proxy C: encontrado ✓
- Proxy D: no encontrado ✗

Evaluación:
- A = true
- B = false
- (C AND D) = (true AND false) = false
- A OR B OR (C AND D) = true OR false OR false = true

Resultado: ✓ Organización X cumple la intersección
```

## Parser de Expresiones Textuales

La función `parse_logic_expression_text()` convierte texto a estructura JSON:

### Entrada
```
"Existen mercados" OR "La propiedad" OR ("Procesos civiles" AND "Planes de desarrollo")
```

### Proceso
1. Tokeniza la expresión respetando comillas y paréntesis
2. Busca cada texto entre comillas en la BD de proxies
3. Construye el árbol respetando precedencia de operadores
4. AND tiene mayor precedencia que OR

### Salida
```json
{
  "type": "OR",
  "children": [
    {"type": "proxy", "id": 1},
    {"type": "proxy", "id": 2},
    {
      "type": "AND",
      "children": [
        {"type": "proxy", "id": 3},
        {"type": "proxy", "id": 4}
      ]
    }
  ],
  "matched_proxies": [
    {"id": 1, "term": "Existen mercados...", "variable": "Justicia"},
    ...
  ]
}
```

## Modelo de Base de Datos

### Tabla `venn_intersections`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | INTEGER | Clave primaria |
| `name` | VARCHAR | Nombre de la intersección |
| `description` | TEXT | Descripción opcional |
| `operation` | ENUM | 'intersection' (AND) o 'union' (OR) para modo legacy |
| `use_proxies` | BOOLEAN | True si usa proxies directamente |
| `use_logic_expression` | BOOLEAN | True si usa expresión lógica |
| `logic_expression` | JSONB | Árbol de expresión lógica |
| `expression_display` | VARCHAR | Representación legible de la expresión |
| `include_ids` | ARRAY[INTEGER] | IDs de variables (modo legacy) |
| `include_proxy_ids` | ARRAY[INTEGER] | IDs de proxies (modo simple) |

## Compatibilidad

El sistema mantiene retrocompatibilidad con tres modos:

1. **Modo variable**: Intersecciones basadas en variables completas
2. **Modo proxy simple**: Lista de proxies con operación única (AND/OR)
3. **Modo expresión lógica**: Árboles booleanos complejos

## Integración con QCA/Tosmana

Los resultados de las intersecciones pueden exportarse como tablas de verdad:

| Organización | Proxy A | Proxy B | Proxy C | Proxy D | Resultado |
|--------------|---------|---------|---------|---------|-----------|
| Org 1 | 1 | 0 | 1 | 1 | 1 |
| Org 2 | 0 | 0 | 1 | 0 | 0 |
| Org 3 | 1 | 1 | 0 | 0 | 1 |

Este formato es directamente importable en herramientas de Análisis Cualitativo Comparativo (QCA) como Tosmana o fsQCA.

## Limitaciones Conocidas

1. **Profundidad máxima**: Expresiones con más de 5 niveles de anidamiento pueden afectar rendimiento
2. **Búsqueda de proxies**: El parser busca por texto parcial, lo que puede generar ambigüedades
3. **Sin operador NOT**: Actualmente no se soporta negación lógica

## Extensiones Futuras

- Soporte para operador NOT
- Operadores de umbral (ej: "al menos 2 de 3")
- Pesos diferenciados en operadores OR
- Exportación directa a formato fsQCA
