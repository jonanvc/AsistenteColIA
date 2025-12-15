# Informe Técnico: Agente de Análisis Booleano para Organizaciones de Paz

## 1. Introducción

El presente documento describe la arquitectura y el diseño de un agente software desarrollado para el análisis sistemático de organizaciones de la sociedad civil lideradas por mujeres constructoras de paz en Colombia. El sistema resuelve el problema de identificar, categorizar y evaluar organizaciones a partir de información pública disponible en la web, transformando contenido textual no estructurado en indicadores binarios que permiten análisis cualitativos comparativos.

El agente aborda tres problemáticas fundamentales: la dispersión de información sobre organizaciones en múltiples fuentes web, la necesidad de operacionalizar conceptos abstractos (como "construcción de paz" o "justicia social") en indicadores medibles, y la generación de representaciones visuales que faciliten el análisis comparativo mediante diagramas de Venn y tablas de verdad compatibles con metodologías QCA/Tosmana.

## 2. Arquitectura del Agente

La arquitectura sigue un modelo de capas con separación clara de responsabilidades. El sistema se organiza en cuatro módulos principales que operan de forma secuencial pero desacoplada.

La **capa de adquisición de datos** implementa un scraper web que extrae contenido textual desde URLs asociadas a cada organización. Este módulo gestiona las solicitudes HTTP, el parsing de HTML y la limpieza inicial del texto. Las organizaciones se clasifican por ámbito territorial (municipal, departamental, regional o nacional), lo que permite segmentar los análisis geográficamente.

La **capa de matching semántico** compara el contenido scrapeado contra un conjunto de proxies textuales predefinidos. Cada proxy representa una expresión lingüística asociada a una variable analítica. El sistema detecta coincidencias mediante búsqueda textual y genera un registro de trazabilidad que incluye la URL de origen, el fragmento de texto donde se encontró la coincidencia y la referencia temporal.

La **capa de evaluación lógica** procesa los matches individuales mediante expresiones booleanas configurables. El usuario define condiciones que combinan variables mediante operadores AND y OR, con soporte para agrupaciones mediante paréntesis. El evaluador recorre la estructura de árbol lógico y produce un valor binario final (0 o 1) para cada organización.

La **capa de visualización** transforma los resultados en múltiples formatos de salida: diagramas de Venn que muestran las intersecciones entre variables, tablas de verdad exportables para análisis QCA/Tosmana, y representaciones geográficas sobre mapas que permiten identificar patrones territoriales.

## 3. Decisiones de Diseño Clave

La separación entre scraping, matching y evaluación lógica responde a la necesidad de mantener cada etapa independiente y testeable. El scraping puede ejecutarse de forma programada sin afectar las reglas de matching existentes. Los proxies pueden modificarse sin requerir nuevo scraping si el contenido ya está almacenado. Las expresiones lógicas pueden reconfigurarse sin alterar los matches subyacentes.

El uso de proxies binarios simplifica el modelo analítico. Cada proxy produce un valor 0 o 1 según se detecte o no en el contenido de la organización. Esta discretización permite aplicar directamente las herramientas de análisis cualitativo comparativo y evita la complejidad de trabajar con scores continuos que requerirían umbrales arbitrarios.

La representación de condiciones mediante estructuras de árbol lógico en formato JSON permite expresiones de complejidad arbitraria. Una intersección puede definirse como `(A AND B) OR (C AND D)`, donde cada nodo del árbol contiene el tipo de operación y referencias a los proxies o subexpresiones hijas. Esta estructura facilita la evaluación recursiva y el almacenamiento persistente de las configuraciones.

La trazabilidad completa de los matches constituye un requisito fundamental para la validez del análisis. Cada resultado binario puede rastrearse hasta el fragmento de texto original y la URL de donde provino, lo que permite auditar y corregir falsos positivos durante la fase de verificación humana.

## 4. Principales Desafíos Encontrados

El problema de los falsos positivos en el scraping representa el desafío más significativo. La detección de coincidencias textuales produce inevitablemente matches espurios cuando el contexto semántico difiere del esperado. Una organización puede mencionar términos relevantes en contextos negativos o hipotéticos que no deberían contabilizarse como presencia de la variable.

La ambigüedad territorial genera dificultades en la asignación de organizaciones a ámbitos geográficos específicos. Organizaciones con presencia en múltiples municipios o que operan en zonas fronterizas entre departamentos no encajan limpiamente en las categorías predefinidas.

Las limitaciones de los diagramas de Venn clásicos restringen el análisis a un máximo de tres o cuatro variables simultáneas antes de que la visualización pierda legibilidad. Para análisis con cinco o más variables, el diagrama tradicional resulta impracticable.

La necesidad de combinar operadores AND y OR de forma flexible excede las capacidades de las intersecciones Venn simples. Los investigadores requieren expresiones como "organizaciones que cumplan (A y B) o (C y D)", lo que no puede representarse mediante una única intersección Venn convencional.

La escalabilidad del sistema de scraping presenta limitaciones cuando el número de organizaciones y URLs crece significativamente. El procesamiento secuencial de cientos de páginas web introduce latencias que afectan la usabilidad del sistema.

## 5. Soluciones Adoptadas

Para mitigar los falsos positivos, se implementó un sistema de verificación humana asistida. Los matches se presentan al usuario con el contexto textual completo, permitiendo confirmar o rechazar cada detección. El sistema aprende de estas correcciones para mejorar la precisión en iteraciones futuras. Se evaluaron alternativas basadas en modelos de lenguaje para clasificación semántica, pero el costo computacional y la opacidad de las decisiones motivaron la preferencia por el enfoque de verificación explícita.

La ambigüedad territorial se resolvió permitiendo la asignación múltiple. Una organización puede asociarse a varios códigos de departamento o municipio simultáneamente, y las consultas territoriales incluyen todas las organizaciones con presencia en el área especificada. Esta solución preserva la información sin forzar clasificaciones excluyentes.

Las limitaciones de los diagramas de Venn se abordaron mediante la integración con tablas de verdad estilo QCA/Tosmana. Para análisis complejos, el usuario trabaja con la representación tabular y reserva los diagramas Venn para comunicar resultados de subconjuntos de tres o cuatro variables. El sistema genera automáticamente ambos formatos desde los mismos datos subyacentes.

La flexibilidad en expresiones lógicas se logró mediante el motor de evaluación basado en árboles. El usuario construye expresiones arbitrariamente complejas combinando AND, OR y paréntesis. El parser convierte la expresión textual en estructura JSON y el evaluador procesa recursivamente el árbol. Esta arquitectura permite añadir nuevos operadores (como NOT o XOR) sin modificar el núcleo del evaluador.

La escalabilidad se mejoró mediante procesamiento asíncrono y colas de tareas. El scraping de cada organización se encola como tarea independiente, permitiendo paralelización y reintentos automáticos ante fallos. Un programador de tareas ejecuta actualizaciones periódicas fuera de horarios de uso intensivo.

## 6. Conclusión

La arquitectura modular adoptada permite mantener y evolucionar cada componente de forma independiente. La separación entre adquisición, matching, evaluación y visualización facilita la incorporación de nuevas fuentes de datos, la modificación de proxies y la experimentación con diferentes configuraciones lógicas sin afectar el resto del sistema.

El uso de proxies binarios con trazabilidad completa satisface los requisitos de transparencia y auditabilidad propios de la investigación en ciencias sociales. Los resultados pueden verificarse y reproducirse siguiendo la cadena de evidencia desde el valor final hasta el fragmento de texto original.

Como extensiones futuras se plantea la incorporación de modelos de lenguaje para asistir en la detección semántica contextual, reduciendo la tasa de falsos positivos sin sacrificar la explicabilidad. También se considera la implementación de análisis temporales que permitan rastrear la evolución de los indicadores de cada organización a lo largo del tiempo, aprovechando el historial de scraping almacenado.

---

*Documento elaborado como parte del desarrollo del sistema de análisis de organizaciones de paz. El proceso de diseño incluyó el apoyo de herramientas de inteligencia artificial para la validación de modelos lógicos y la mejora de la documentación técnica.*
