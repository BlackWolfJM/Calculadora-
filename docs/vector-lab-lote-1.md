# Laboratorio vectorial — Primer lote (01.01–01.10)

**Estado:** implementación parcial de la experiencia solicitada. Rama: `feat/vector-lab-lote-1-2026`.

## Integración realizada

El panel **Laboratorio vectorial** se abre desde la navegación de geometría de la aplicación existente. La lógica algebraica está separada en `src/domain/modules/vector_lab.py`; la interfaz Qt está en `src/presentation/vector_lab_widget.py`.

Las diez actividades exponen algún cálculo/explicación y una escena de flechas. Se admiten vectores con 2 o 3 componentes, entradas numéricas enteras, decimales finitos y fracciones, y operaciones exactas con SymPy. Las gráficas representan **solo la proyección xy**; los cálculos 3D sí conservan z, pero todavía no hay escena 3D nativa, cámara giratoria ni objetos arrastrables. Los pasos se presentan de forma expandible con el contrato `EducationalStep`.

## Matriz de cobertura realista

| ID | Operación conectada | Alcance pendiente | Estado |
| --- | --- | --- | --- |
| 01.01 | Distinción textual de magnitud escalar/vectorial y flecha | Clasificador interactivo con corrección | Parcial |
| 01.02 | Ubicación de punto, signos y cuadrantes; proyección xy | Octantes numerados, vista 3D y arrastre | Parcial |
| 01.03 | Vector libre y trasladado | Manipulación directa y guía interactiva | Parcial |
| 01.04 | Componentes exactas y flechas por eje xy | Proyección espacial z y editor por componente | Parcial |
| 01.05 | Desplazamiento B-A y distancia | Arrastre de puntos y comprobación espacial | Parcial |
| 01.06 | Igualdad por componentes | Animación de superposición | Parcial |
| 01.07 | Suma/resta, cabeza-cola y representación de paralelogramo | Animaciones fluidas y ajuste visual | Parcial |
| 01.08 | Producto escalar por vector con deslizador k | Animación de cambio de escala | Parcial |
| 01.09 | Conmutatividad, distributividad y asociatividad | Demostración general completa y actividades | Parcial |
| 01.10 | Combinación ku+v y prueba de colinealidad por rango | Dos coeficientes independientes y lugar alcanzable | Parcial |

## Comprobaciones

Archivo agregado: `tests/test_vector_lab.py` con pruebas de dimensiones, exactitud, traslación, suma, resta, escalares, colinealidad y casos degenerados.

No consta ejecución de `pytest`, `ruff`, `mypy` ni pruebas de interfaz para esta rama: **no afirmar que están aprobadas**. Requiere ejecutar el proyecto con sus dependencias reales. La integración es un prototipo revisable antes de marcar una sola habilidad como implementada y verificada.

## Trabajo posterior

- Conectar un renderizador espacial real a la graficadora disponible sin duplicar barras o parámetros.
- Convertir la entrada al registro de capacidades y ampliar el generador de pasos solo si el contrato existente lo requiere.
- Añadir arrastre, animaciones opt-in, clasificación de conceptos y ejercicios con feedback.
- Añadir pruebas `pytest-qt`, `ruff`, `mypy` y ejecutar la batería completa.
- Auditar contrastes de todos los temas y mantener un único menú «Personalizar gráfica».
