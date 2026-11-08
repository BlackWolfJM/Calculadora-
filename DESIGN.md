# Diseño de Calculadoras

La interfaz usa una hoja de estudio con fondo papel (#F5F3EE), texto tinta
(#24332F) y verde mineral (#216653) para las acciones principales. El fondo
blanco separa la zona editable de la navegación. Las reglas finas y los
números de paso marcan la secuencia de lectura.

- Segoe UI para controles y explicaciones. Consolas para editar expresiones y
  leer la normalización. KaTeX local para resultado y fórmulas de los pasos.
- Una acción primaria por operación. El historial permanece en la navegación
  lateral y admite selección y activación por teclado.
- Ctrl+Enter resuelve, Ctrl+L devuelve el foco al editor, Ctrl+N inicia otra
  resolución y Ctrl+H abre el historial. El foco tiene borde visible de 2 px.
- Los estados de error incluyen texto y subrayado en la entrada. El resultado
  anterior se identifica mientras se edita la siguiente expresión.
- Las acciones frecuentes responden sin animación. El tema de la aplicación
  es claro y usa los mismos tokens en el historial y la zona de trabajo.

El producto existente resuelve derivadas, integrales indefinidas y ecuaciones.
Los pasos y la comprobación dependen de la respuesta del motor. El historial
es local. La dirección visual y los atajos son decisiones de este rediseño.
Fuentes de contexto: README.md, 12-diseno-de-interfaz.md y el contrato visual
histórico de TASK-001.
