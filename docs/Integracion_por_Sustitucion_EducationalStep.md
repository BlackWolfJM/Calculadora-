# Integración por sustitución (cambio de variable)

> **Especificación didáctica y técnica** — Python + SymPy + LaTeX/KaTeX  
> **Alcance:** integrales escalares de una variable real, indefinidas y definidas.  
> **Fuentes del usuario:** Salas, Hille y Etgen, *Calculus: Una y varias variables*, vol. I, 4.ª ed., §5.6, pp. 299–307 (regla inversa de la cadena, sustitución, límites y despeje); el tratamiento de AST, modelos de datos, pruebas y validación es una **propuesta de ingeniería añadida**, no código extraído del libro.  
> **Estado:** especificación implementable, no una promesa de detección universal de sustituciones.

**Convenciones:** `x` es la variable original, `u` la auxiliar; `f_x` representa el integrando sin `dx`; `g_x` representa el cambio elegido; `d_g` representa `diff(g_x, x)`; `h_u` es el integrando transformado. Todas las antiderivadas indefinidas se interpretan **por componente conexa del dominio real**. El símbolo `+ C` es una anotación matemática del renderer, **no** un objeto `sympy.Symbol('C')` que deba diferenciarse. Las rutas mostradas son didácticas: no se permite reemplazarlas por un salto `sympy.integrate(f_x,x)`.

## 1. Árbol de Decisión: ¿Cuándo usar este método y cuándo NO usarlo?

### 1.1 Firma algebraica / patrón visual

Forma principal:

\[
\int F'(g(x))\,g'(x)\,dx = F(g(x))+C.
\]

Equivalente al reconocer una función exterior `h`:

\[
\int k\,h(g(x))g'(x)\,dx
   =k\int h(u)\,du,\qquad u=g(x),\quad k\ne0.
\]

**Firma suficiente, no necesaria:** un subárbol no constante `g(x)` se repite como argumento o base de otra operación; el resto contiene su derivada `g'(x)` salvo un factor numérico o simbólico *independiente de* `x`. El criterio general es más amplio: después de sustituir y, si hace falta, despejar `x(u)`, **toda** dependencia en `x` debe desaparecer de `h_u`.

Patrones prioritarios:

| Patrón original | Candidata `g(x)` | Evidencia esperada | Ruta |
|---|---|---|---|
| `g'(x)*sin(g(x))` | argumento de `sin` | `g'(x)` como factor | exacta |
| `c*g'(x)*(g(x))**n` | base de potencia | factor `c` independiente de `x` | ajuste |
| `g'(x)/g(x)` | denominador | cociente logarítmico | exacta / dominio |
| `x*sqrt(x+1)` | `x+1` | queda `x` residual, pero `x=u-1` | despeje |
| `x/sqrt(x**2+2*x+5)` | `x+1` tras cuadrado perfecto | suma transformada en `u` | preparación algebraica |
| `a≤x≤b` y `g'(x)*h(g(x))` | `g(x)` | límites `g(a),g(b)` | integral definida |

**Árbol lógico (prioridades sugeridas, no teorema de unicidad):**

```text
START -> parse seguro -> comprobar variable / dominio
  -> separar términos aditivos (si corresponde)
  -> normalización moderada (cancel, factor_terms, together; sin perder el dominio)
  -> ¿regla directa evidente? sí -> DIRECT_RULE
  -> generar candidatos interiores g(x) a partir del AST
  -> por cada g: calcular dg/dx; descartar si es 0 o indefinido
       -> cociente formal R(x)=f_x/(dg/dx), sin cancelar hipótesis de dominio
       -> reemplazar g(x) -> u y verificar que NO quede x
            -> sí: SUBSTITUTION_DIRECT o CONSTANT_ADJUSTMENT
            -> no: buscar x=X(u), con ramas y dominios justificados
                -> ¿puede escribirse todo como h(u)? sí -> SUBSTITUTION_SOLVE_X
                -> no: probar completar cuadrados / identidades elegibles
  -> si varios candidatos: puntuar pasos, complejidad e inteligibilidad
  -> si ninguno: delegar a otra técnica (partes, parcial, trigonométrica, etc.)
  -> construir EducationalStep de la transformación elegida
  -> verificar igualdad diferencial / cambio de variable y dominios
  -> renderizar; jamás presentar pasos no verificados como correctos
```

### 1.2 Condición exacta de detección en SymPy

**Advertencia importante:** `expr.is_Mul`, `expr.is_Pow`, `expr.has(sin)` o `expr.find(...)` son pistas estructurales, **no** pruebas suficientes. SymPy reorganiza productos, constantes y potencias; y simplificaciones pueden modificar el dominio de una expresión. La detección debe concluir con una **identidad comprobable**.

Contrato de aceptación para la rama simple:

1. Sea `candidate_g` un subárbol real, diferenciable y no constante en el dominio local.
2. Construir `d_g = diff(candidate_g, x)` y exigir `d_g != 0` no idénticamente; `d_g` puede anularse en puntos aislados, lo cual requiere controlar intervalos y no dividir allí ingenuamente.
3. Calcular un integrando `h_u` sin `x` tal que, en el dominio en estudio,
   `simplify(h_u.subs(u, candidate_g) * d_g - f_x) == 0`.
4. Exigir `x not in h_u.free_symbols` y que `h_u` sea integrable por una regla **más sencilla y verificable**. Si falla la prueba simbólica, usar prueba reforzada (`together`, `cancel`, `trigsimp`), y en último lugar comprobaciones numéricas **solo como diagnóstico, no como certificación**.
5. Si se reemplazó una raíz, logaritmo, factor cancelado o se invirtió una función, adjuntar restricciones de dominio y justificar la rama utilizada.

Para detectar ajuste constante, se busca `f_x = k * h(g(x)) * g'(x)` con `k.free_symbols` que no contenga `x`. **No basta** con que `f_x / g'(x)` sea una expresión válida: debe poder expresarse únicamente en `u`.

Ejemplo crucial: `exp(x**2)` **no** activa la ruta básica `u=x**2` solo por contener una composición. Falta el factor `2*x`; la sustitución da `exp(u)/(2*sqrt(u))` únicamente al elegir una rama de `x`, y no simplifica la integral elemental.

### 1.3 Orden de prioridad frente a otros métodos

1. Verificar dominio, estructura y algebra básica; preservar puntos excluidos.
2. Aplicar reglas inmediatas y linealidad si reducen el problema.
3. Probar sustitución exacta, luego ajuste constante.
4. Probar sustitución con despeje simple (afín o potencia bajo dominio justificado).
5. Si aparece una cuadrática, intentar completar cuadrados antes de elegir otra técnica.
6. Delegar según estructura a partes, identidades trigonométricas, fracciones parciales o sustitución trigonométrica. **No hay un orden universal obligatorio**: la aplicación debe escoger la vía que produzca una explicación más corta y válida.

### 1.4 Trampas comunes / cuándo descartarlo

- Elegir `u` sin poder eliminar `x` del integrando transformado.
- Suponer `dx=du` aunque `du/dx≠1`.
- Perder el factor constante (`5*x` frente a `du=2*x*dx`).
- Simplificar `x/x=1` y olvidarse de excluir `x=0` en el dominio original.
- Escribir `ln(u)` sin `abs` cuando `u` puede ser negativo; lo real es `ln|u|` en una componente de `u≠0`.
- Resolver `u=x**2` como `x=sqrt(u)` ignorando la rama `x<0`.
- En integral definida, cambiar los límites y **además** volver a sustituir `x` (doble cambio injustificado), o no cambiar límites.
- Suponer que toda sustitución debe ser inyectiva en `[a,b]`. Para una integral del tipo `h(g(x))*g'(x)` con las hipótesis del teorema, el cálculo por extremos sigue siendo válido aun cuando `g` no sea monótona.
- Tratar `integrate(...)` como generador de los pasos anteriores: solo es un oráculo auxiliar de resultados.

## 2. Mnemotecnia e Intuición Pedagógica

**«Lo de adentro es `u`; su derivada abre la puerta».** La sustitución deshace la regla de la cadena: al derivar `sin(x**3+2)`, aparece el coseno de la expresión interior multiplicado por la derivada de `x**3+2`. Integrar el producto invierte esa operación.

Con tres gestos del estudiante:

1. **Mirar dentro:** localizar la expresión compuesta.
2. **Derivar dentro:** calcular y comparar su diferencial.
3. **Reescribir todo:** convertir la integral *completa* a la nueva variable antes de integrar.

Recordatorio del factor: **«Si el diferencial trae más o menos, compenso con una constante».** En `5*x*(x**2+4)**3`, la derivada de `x**2+4` es `2*x`: por tanto, `5*x dx = (5/2)du`.

Para integrales definidas: **«Si cambio de variable, también cambio de extremos».** Para integrales indefinidas: **«Regreso a `x` y agrego `+C`».**

La sustitución no es una receta basada en la apariencia: es una identidad que puede comprobarse derivando el resultado.

## 3. Variables Simbólicas que el Motor debe extraer

| Variable | Tipo sugerido | Semántica / requisito |
|---|---|---|
| `x` | `Symbol` | variable original de integración |
| `u` | `Dummy(real=True)` | símbolo auxiliar sin colisiones |
| `f_x` | `Expr` | integrando original sin diferencial |
| `domain_x` | `Set` / estructura de intervalos | restricciones heredadas y singularidades |
| `original_bounds` | `(Expr,Expr) \| None` | si hay integral definida |
| `g_x` / `u_expr` | `Expr` | candidata elegida para `u` |
| `du_dx` | `Expr` | `diff(g_x,x)` |
| `dx_du` | `Expr \| None` | `diff(x_of_u,u)` para rama invertida, cuando exista |
| `x_of_u` | `Expr \| None` | inversa `x=X(u)` asociada a una rama válida |
| `branch_guard` | `Boolean` o texto validado | hipótesis local de inversa, radical o logaritmo |
| `const_factor` | `Expr` | factor `k` independiente de `x`, si se extrae explícitamente |
| `integrand_in_u` / `h_u` | `Expr` | todo el integrando convertido a `u`, sin símbolo `x` |
| `antideriv_in_u` | `Expr` | primitiva elegida en `u`, sin `+C` |
| `antideriv_in_x` | `Expr` | retorno a `x`, sin `+C` |
| `new_bounds` | `(Expr,Expr) \| None` | `g(a),g(b)` si es definida |
| `result_expr` | `Expr` | antiderivada sin constante, o valor definido |
| `proof_residual` | `Expr` | diferencia simplificada de ambos lados de la identidad |
| `step_trace` | `list[EducationalStep]` | pasos visibles de aprendizaje |
| `status` | enum | `verified`, `conditional`, `unsupported` o `rejected` |

**Modelo mínimo compatible con `EducationalStep`:**

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class EducationalStep:
    step_id: str
    rule_name: str
    explanation: str       # Toda expresión matemática: \\( ... \\)
    before_latex: str      # Contenido matemático puro, SIN delimitadores externos
    after_latex: str       # Contenido matemático puro, SIN delimitadores externos
    sub_steps: tuple['EducationalStep', ...] = field(default_factory=tuple)

# Metadatos por fuera del paso (evita mezclar cómputo y UI)
@dataclass(frozen=True)
class SubstitutionAnalysis:
    method_id: str
    u_expr: object
    du_dx: object
    integrand_in_u: object
    antideriv_in_u: object
    antideriv_in_x: object
    proof_residual: object
    status: str
    assumptions: tuple[str, ...] = ()
```

### 3.1 Aislar la matemática del render

- **Primero** obtener `Expr` exactas; **después** `latex(expr)` para las fórmulas de `before_latex`/`after_latex`.
- Nunca construir fórmulas mediante `str(expr)` sin `sympy.latex`.
- `explanation` debe estar en español y envolver cada fórmula en `\( ... \)`; los campos `before_latex`/`after_latex` contienen *solo* LaTeX, no Markdown ni delimitadores.
- Si se usan marcadores como `{u_latex}`, sustituirlos con un reemplazo literal de tokens; **no** pasar LaTeX con llaves sin escapar a `.format()`.
- Escribir `\ln\left|u\right|` cuando hay signo incierto, y `\operatorname{arsinh}` para la inversa hiperbólica. Ambos deben probarse en el renderer KaTeX de la aplicación.
- Guardar la estructura de los pasos como datos, en lugar de reconstruirla desde el resultado final.

### 3.2 Pseudocódigo de selección y verificación

```python
from sympy import Symbol, Dummy, diff, simplify, together, cancel
from sympy import preorder_traversal, sin, cos, exp, log, Pow

x = Symbol('x', real=True)
u = Dummy('u', real=True)

def candidate_subexpressions(expr, x):
    # Heurística: posibles interiores de funciones y bases de potencias.
    seen = set()
    for node in preorder_traversal(expr):
        if node.is_Function and node.args:
            g = node.args[0]
            if g.has(x) and g != x and g not in seen:
                seen.add(g)
                yield g
        if isinstance(node, Pow):
            g = node.base
            if g.has(x) and g != x and g not in seen:
                seen.add(g)
                yield g
    # Ampliar para denominadores y formas reescritas por together/factor.

def simple_substitution_candidate(expr, x, u, g):
    dg = diff(g, x)
    if dg == 0:
        return None
    # El cociente es una propuesta matemática; no dividir en puntos
    # donde dg vale cero sin controlar las hipótesis correspondientes.
    remainder = cancel(together(expr / dg))
    hu = remainder.subs(g, u)
    if x in hu.free_symbols:
        return None
    residual = simplify(hu.subs(u, g) * dg - expr)
    if residual != 0:
        return None
    return {'g': g, 'dg': dg, 'h_u': hu, 'residual': residual}

# Esta función NO es un integrador universal:
# puede no reconocer equivalencias trigonométricas, inversas con ramas,
# ni expresiones que requieran normalizaciones específicas.
```

**Prohibición de seguridad de entrada:** no usar `eval` ni `sympify` sin política de confianza sobre texto del usuario. El parser necesita operadores permitidos, límites de tamaño/profundidad, tiempo máximo y lista blanca de funciones; `parse_expr` tampoco debe ejecutarse directamente sobre texto no confiable sin aislamiento.

## 4. Secuencia Completa de Pasos y Subpasos (`EducationalStep`)

**Caso canónico parametrizado:** `f_x = k*h(g_x)*diff(g_x,x)`. Los marcadores `{..._latex}` son *tokens de plantilla*, no operaciones matemáticas aún resueltas. Se añade una rama alternativa para `x=X(u)` en el Paso 4 y otra para integral definida en los Pasos 7–8.

### Paso 1: `SUB_01_RECOGNIZE_PATTERN`
- **`rule_name`**: Reconocer la composición candidata.
- **`explanation`**: Buscamos una función interior \(u={u_latex}\) dentro del integrando \({expr_latex}\), cuya derivada pueda relacionarse con los factores restantes. La elección todavía es provisional y debe comprobarse.
- **`before_latex`**: `\int {expr_latex}\,dx`
- **`after_latex`**: `\int \underbrace{{expr_latex}}_{\text{composición por analizar}}\,dx`
- **`sub_steps`**:
  - **Subpaso 1.1**:
    - `rule_name`: Localizar argumentos y bases candidatas.
    - `explanation`: Identificamos el subárbol \({u_latex}\) como posible expresión interior.
    - `before_latex`: `{expr_latex}`
    - `after_latex`: `u={u_latex}`
  - **Subpaso 1.2**:
    - `rule_name`: Registrar restricciones de dominio.
    - `explanation`: Conservamos las condiciones \({domain_latex}\) antes de transformar el integrando.
    - `before_latex`: `\int {expr_latex}\,dx`
    - `after_latex`: `\int {expr_latex}\,dx\quad({domain_latex})`

### Paso 2: `SUB_02_SET_U`
- **`rule_name`**: Definir la nueva variable.
- **`explanation`**: Elegimos \(u={u_latex}\) para reemplazar la parte compuesta; esta igualdad es el cambio de variable propuesto.
- **`before_latex`**: `\int {expr_latex}\,dx`
- **`after_latex`**: `u={u_latex}`
- **`sub_steps`**:
  - **Subpaso 2.1**:
    - `rule_name`: Registrar mapeo simbólico.
    - `explanation`: La sustitución \(u={u_latex}\) debe vincularse al mismo subárbol de \({expr_latex}\) en todas sus apariciones.
    - `before_latex`: `{expr_latex}`
    - `after_latex`: `{u_latex}\mapsto u`

### Paso 3: `SUB_03_DIFFERENTIATE_U`
- **`rule_name`**: Hallar el diferencial correspondiente.
- **`explanation`**: Derivamos \(u={u_latex}\) respecto de \(x\): \(\frac{du}{dx}={du_dx_latex}\). Multiplicamos formalmente por \(dx\) para escribir \(du={du_dx_latex}\,dx\).
- **`before_latex`**: `u={u_latex}`
- **`after_latex`**: `\frac{du}{dx}={du_dx_latex}\quad\Longrightarrow\quad du={du_dx_latex}\,dx`
- **`sub_steps`**:
  - **Subpaso 3.1**:
    - `rule_name`: Derivar la expresión interior.
    - `explanation`: Calculamos \(\frac{d}{dx}({u_latex})={du_dx_latex}\) utilizando las reglas de derivación.
    - `before_latex`: `\frac{d}{dx}\left({u_latex}\right)`
    - `after_latex`: `{du_dx_latex}`
  - **Subpaso 3.2**:
    - `rule_name`: Escribir el diferencial.
    - `explanation`: El factor diferencial es \(du={du_dx_latex}\,dx\), no necesariamente \(du=dx\).
    - `before_latex`: `\frac{du}{dx}={du_dx_latex}`
    - `after_latex`: `du={du_dx_latex}\,dx`

### Paso 4: `SUB_04_MATCH_AND_ADJUST`
- **`rule_name`**: Ajustar coeficientes y eliminar la variable original.
- **`explanation`**: Comparamos el factor presente con \(du={du_dx_latex}\,dx\). Si difiere por una constante, extraemos \(k={const_factor_latex}\) y reescribimos el diferencial de modo que todos los términos restantes dependan únicamente de \(u\).
- **`before_latex`**: `\int {expr_latex}\,dx`
- **`after_latex`**: `\int {transformed_latex}\,du`
- **`sub_steps`**:
  - **Subpaso 4.1**:
    - `rule_name`: Calcular el ajuste.
    - `explanation`: Verificamos que el cociente de factores produzca \(k={const_factor_latex}\) independiente de \(x\), o bien continuamos por la rama de despeje.
    - `before_latex`: `{expr_latex}`
    - `after_latex`: `{const_factor_latex}\,{outer_in_u_latex}\,{du_dx_latex}`
  - **Subpaso 4.2**:
    - `rule_name`: Eliminar dependencias residuales.
    - `explanation`: Tras sustituir \(u={u_latex}\), el integrando transformado \({transformed_latex}\) no debe conservar la variable \(x\).
    - `before_latex`: `{expr_latex}\,dx`
    - `after_latex`: `{transformed_latex}\,du`
  - **Subpaso 4.3 — solo variante de despeje**:
    - `rule_name`: Sustituir también la variable exterior.
    - `explanation`: Si queda \(x\), despejamos una rama válida \(x={x_of_u_latex}\), reemplazamos toda aparición residual y usamos \(dx={dx_du_latex}\,du\).
    - `before_latex`: `x={x_of_u_latex}`
    - `after_latex`: `{transformed_latex}\,du`

### Paso 5: `SUB_05_REWRITE_IN_U`
- **`rule_name`**: Reescribir completamente la integral en la nueva variable.
- **`explanation`**: Sustituimos la función interior y su diferencial, obteniendo \(\int {transformed_latex}\,du\). No queda ninguna variable \(x\) en esta integral.
- **`before_latex`**: `\int {expr_latex}\,dx`
- **`after_latex`**: `\int {transformed_latex}\,du`
- **`sub_steps`**:
  - **Subpaso 5.1**:
    - `rule_name`: Comprobar identidad de cambio.
    - `explanation`: Verificamos que \({transformed_latex}\), al volver a \(u={u_latex}\) y multiplicarse por \(\frac{du}{dx}={du_dx_latex}\), recupere el integrando original.
    - `before_latex`: `{transformed_latex}\big|_{u={u_latex}}\,{du_dx_latex}`
    - `after_latex`: `{expr_latex}`

### Paso 6: `SUB_06_INTEGRATE_IN_U`
- **`rule_name`**: Integrar la expresión simplificada.
- **`explanation`**: Aplicamos una regla de integración reconocible a \(\int {transformed_latex}\,du\) para obtener una primitiva \({antideriv_u_latex}\). Esta etapa puede generar subpasos para distribuir, expandir o integrar términos individuales.
- **`before_latex`**: `\int {transformed_latex}\,du`
- **`after_latex`**: `{antideriv_u_latex}`
- **`sub_steps`**:
  - **Subpaso 6.1**:
    - `rule_name`: Identificar regla elemental.
    - `explanation`: Reconocemos qué regla elemental transforma \({transformed_latex}\) en la derivada de \({antideriv_u_latex}\).
    - `before_latex`: `\int {transformed_latex}\,du`
    - `after_latex`: `{antideriv_u_latex}`
  - **Subpaso 6.2**:
    - `rule_name`: Derivar para comprobar.
    - `explanation`: La verificación exige \(\frac{d}{du}({antideriv_u_latex})={transformed_latex}\).
    - `before_latex`: `\frac{d}{du}\left({antideriv_u_latex}\right)`
    - `after_latex`: `{transformed_latex}`

### Paso 7: `SUB_07_BACK_SUBSTITUTE`
- **`rule_name`**: Regresar a la variable original.
- **`explanation`**: En una integral indefinida reemplazamos \(u={u_latex}\) en \({antideriv_u_latex}\) y obtenemos \({antideriv_x_latex}\). Para una integral definida con límites ya transformados, este paso se sustituye por la evaluación de extremos.
- **`before_latex`**: `{antideriv_u_latex}`
- **`after_latex`**: `{antideriv_x_latex}`
- **`sub_steps`**:
  - **Subpaso 7.1 — indefinida**:
    - `rule_name`: Restaurar la función interior.
    - `explanation`: Sustituimos \(u\) por \({u_latex}\) en la primitiva.
    - `before_latex`: `{antideriv_u_latex}`
    - `after_latex`: `{antideriv_x_latex}`
  - **Subpaso 7.2 — definida**:
    - `rule_name`: Cambiar extremos antes de evaluar.
    - `explanation`: Convertimos \(x=a\) y \(x=b\) a \(u={lower_u_latex}\) y \(u={upper_u_latex}\), respectivamente; conservamos su orientación y evaluamos \({antideriv_u_latex}\).
    - `before_latex`: `\int_{a}^{b}{expr_latex}\,dx`
    - `after_latex`: `\left[{antideriv_u_latex}\right]_{{lower_u_latex}}^{{upper_u_latex}}`

### Paso 8: `SUB_08_ADD_C_OR_EVALUATE`
- **`rule_name`**: Agregar constante o evaluar extremos.
- **`explanation`**: Si la integral es indefinida, la familia de primitivas se expresa mediante \({antideriv_x_latex}+C\). Si es definida, calculamos la diferencia de valores en los extremos transformados sin introducir \(C\).
- **`before_latex`**: `{antideriv_x_latex}`
- **`after_latex`**: `{final_latex}`
- **`sub_steps`**:
  - **Subpaso 8.1 — indefinida**:
    - `rule_name`: Expresar familia de primitivas.
    - `explanation`: Añadimos \(C\) como constante arbitraria en cada componente conexa del dominio.
    - `before_latex`: `{antideriv_x_latex}`
    - `after_latex`: `{antideriv_x_latex}+C`
  - **Subpaso 8.2 — definida**:
    - `rule_name`: Aplicar teorema fundamental.
    - `explanation`: Evaluamos \(F({upper_u_latex})-F({lower_u_latex})\) en los límites transformados.
    - `before_latex`: `\left[{antideriv_u_latex}\right]_{{lower_u_latex}}^{{upper_u_latex}}`
    - `after_latex`: `{final_latex}`

### Paso 9: `SUB_09_VERIFY_RESULT`
- **`rule_name`**: Verificar el resultado y sus hipótesis.
- **`explanation`**: Para una integral indefinida, comprobamos que \(\frac{d}{dx}({antideriv_x_latex})={expr_latex}\) dentro de cada intervalo de validez. Para la definida, verificamos el cambio de extremos y la evaluación exacta.
- **`before_latex`**: `\frac{d}{dx}\left({antideriv_x_latex}\right)`
- **`after_latex`**: `{expr_latex}`
- **`sub_steps`**:
  - **Subpaso 9.1**:
    - `rule_name`: Simplificar residual simbólico.
    - `explanation`: La resta entre la derivada de la primitiva y el integrando debe simplificarse a \(0\), con las mismas hipótesis de dominio.
    - `before_latex`: `\frac{d}{dx}\left({antideriv_x_latex}\right)-({expr_latex})`
    - `after_latex`: `0`
  - **Subpaso 9.2**:
    - `rule_name`: Marcar estado de validación.
    - `explanation`: El motor marca la ruta como verificada solo cuando cada igualdad simbólica y restricción de dominio ha sido comprobada.
    - `before_latex`: `{proof_residual_latex}`
    - `after_latex`: `0\quad\text{(bajo las hipótesis registradas)}`

## 5. Variantes y Casos Especiales del Tema

### 5.1 Sustitución directa exacta — `SUB_EXACT`

**Firma:** `f_x = h(g_x)*g'(x)`. Por ejemplo, `3*x**2*cos(x**3+2)`. **Detector:** el candidato `g=x**3+2` deja `h_u=cos(u)` y residual cero. **Regla:** `du=3*x**2 dx`. **Pasos:** usar los 9 pasos anteriores sin subpaso 4.3; `const_factor=1`. **No usar:** si el diferencial no coincide y no se ha documentado un ajuste.

### 5.2 Ajuste de constante — `SUB_CONSTANT_FACTOR`

**Firma:** `f_x = k*h(g_x)*g'(x)`, `k` independiente de `x`. Ejemplo `5*x*(x**2+4)**3`, `g=x**2+4`, `du=2*x dx`, `k=5/2`. **Detector:** tras dividir por `du_dx`, `h_u=(5/2)*u**3`, residual cero. **Pasos:** activar 4.1 para mostrar explícitamente `5*x dx=(5/2)du`. **No usar:** cuando el cociente necesario depende de `x` sin una reescritura íntegra en `u`.

### 5.3 Despejar la variable original — `SUB_INVERSE_AFFINE`

**Firma:** `g=x+a`, pero existen factores externos de `x` que no están incluidos en `du`. Ejemplo `x*sqrt(x+1)`. **Detector:** `g=x+1` y al reemplazar directamente queda `x*sqrt(u)`; resolver `x=u-1`; `dx=du`. **Pasos específicos:** 2 `u=x+1`; 3 `du=dx`; 4.3 `x=u-1`; 5 transformar a `(u-1)*sqrt(u)`; 6 expandir a `u**(3/2)-u**(1/2)`; 7 volver a `x`; 8 `+C`; 9 derivar. **No usar:** si `x_of_u` no existe de forma unívoca en la región o si el resultado no simplifica.

### 5.4 Completación de cuadrados previa — `SUB_COMPLETE_SQUARE`

**Firma:** radical o denominador que contenga `a*x**2+b*x+c`, `a!=0`. Identidad previa `a*(x+b/(2*a))**2 + (c-b**2/(4*a))`. Ejemplo `x/sqrt(x**2+2*x+5)`: `x**2+2*x+5=(x+1)**2+4`; `u=x+1`; `x=u-1`, `du=dx`. **Detector:** `Poly(quadratic,x).degree()==2`, coeficientes en `x` constantes, discriminante y dominio analizados. **Pasos adicionales:** antes del paso 2, incorporar un subpaso de equivalencia algebraica con `before_latex=x^2+2x+5`, `after_latex=(x+1)^2+4`. **No confundir** esta preparación con sustitución trigonométrica: la nueva integral puede necesitar otra regla; en el ejemplo se emplea `asinh` (equivalente logarítmico).

### 5.5 Composición profunda — `SUB_NESTED`

**Firma:** `x*exp(x**2)*cos(exp(x**2))`. Una sustitución suficientemente exterior `u=exp(x**2)` aprovecha `du=2*x*exp(x**2)dx`. **Detector:** candidatos `x**2` y `exp(x**2)`; preferir el segundo porque deja `cos(u)/2` en un paso. **Pasos:** selección documentada, derivación por regla de la cadena, ajuste por `1/2`, integración y retorno. **No forzar** dos sustituciones cuando una sola es más clara. Si se realiza el camino anidado, guardar dos marcos de variables independientes y verificarlos.

### 5.6 Integral definida — `SUB_DEFINITE_BOUNDS`

**Firma:** `Integral(f_x,(x,a,b))`; aplicar `u=g(x)`, `A=g(a)`, `B=g(b)`, `∫_A^B h(u)du`. **Detector:** `isinstance(obj, Integral)` y `len(obj.limits[0])==3` para una integral simple; validar límites y continuidad en el intervalo. **Pasos:** cambiar los límites en 7.2, evaluar en 8.2 y no añadir `C`. **Caso borde:** `g(a)>g(b)` es perfectamente válido: el cambio conserva orientación; **no** ordenar límites sin cambiar el signo.

### 5.7 Logaritmos y componentes del dominio — `SUB_LOG_ABSOLUTE`

**Firma:** `f_x = g'(x)/g(x)` con `g(x)≠0`. Resultado real `log(Abs(g(x)))`, cuya presentación didáctica es `ln|g(x)|`. Ejemplo `x/(x**2-1)` produce `(1/2)*ln|x**2-1| + C` para `x != -1,1`. **Detector:** cociente y prueba `simplify(diff(log(Abs(g)),x) - g'/g)==0` bajo hipótesis reales en intervalos que excluyen ceros. **No** combinar constantes entre componentes desconectadas como si se hubiera demostrado continuidad global.

### 5.8 Potencias fraccionarias y ramas inversas — `SUB_BRANCH_GUARDED`

**Firma:** `u=x**2` con eventual `x=±sqrt(u)`, o radical que requiera `u≥0`. **Detector:** resolver las ramas y obtener imágenes de los intervalos de `x`. **Ruta pedagógica:** elegir una rama solo si se especifica el intervalo (por ejemplo, `x>0` o `x<0`) y registrar la condición en `branch_guard`. **Trampa:** reemplazar `sqrt(x**2)` por `x` sin `x≥0`; en general es `Abs(x)` para `x` real.

### 5.9 Candidatos que deben rechazarse — `SUB_REJECTED`

**Ejemplo:** `exp(x**2)` con `u=x**2` no genera un `h_u` elemental mediante la regla simple porque falta el factor `x`. Otro: `x**2*cos(x**2)` deja un factor `x` residual si se fuerza `u=x**2`. **Estado:** `rejected` para la ruta *simple*, **no** afirmar que la integral total sea imposible; redirigir a otra técnica simbólica o función especial.

### 5.10 Contrato formal de validación por variante

| Variante | Igualdad obligatoria | Restricciones adicionales |
|---|---|---|
| Exacta / ajuste | `simplify(h_u.subs(u,g)*diff(g,x)-f_x)==0` | factor independiente de `x` |
| Despeje | `simplify(g.subs(x,x_of_u)-u)==0` y equivalencia de diferenciales | rama, rango e inversa local |
| Cuadrática | `expand(completed_square-original_quadratic)==0` | signo del radical, dominio |
| Anidada | igualdad del diferencial por regla de cadena | orden de candidatos documentado |
| Definida | integral transformada por extremos y valor final | continuidad, orientación |
| Logaritmo | derivada de `log(Abs(g))` sobre dominio | `g!=0`, componentes |
| Rechazada | no se encontró `h_u` válido y más simple | reportar solo «ruta no aplicable» |

## 6. Casos de Prueba Verificables (Input -> Pasos -> Output)

**Regla de pruebas:** cada transición registra **valores LaTeX reales** (no marcadores), incluso las transformaciones intermedias. Los identificadores de fase corresponden a los Pasos 1–9 de la sección 4. Se omite el Paso 7 de regreso a `x` **únicamente** cuando el problema es definido y los extremos ya se transformaron. El texto `\int ...\,dx` es el contenido que debe ir en `before_latex`/`after_latex`, sin delimitadores externos; en pantalla se envuelve por el componente matemático.

### Caso T01: Básico — sustitución exacta

- **`input`**: `3*x**2*cos(x**3+2)`.
- **`method_id`**: `SUB_EXACT`.
- **`domain`**: \(x\in\mathbb R\).
- **`variables extraídas`**: `u=x**3+2`, `du=3*x**2*dx`, `k=1`, `h(u)=cos(u)`, `H(u)=sin(u)`.
- **`resultado final (canónico)`**: `sin(x**3 + 2)` (`+C` implícito).
- **`resultado final (LaTeX)`**: `\sin(x^3+2)+C`.

#### Paso 1: `SUB_01_T01`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: Reconocemos que el coseno contiene una función de \(x\) cuya derivada aparece multiplicada. Transformación concreta: \(\int 3x^2\cos(x^3+2)\,dx\) pasa a \(\int\underbrace{3x^2\cos(x^3+2)}_{\text{patrón compuesto}}\,dx\).
- **`before_latex`**: `\int 3x^2\cos(x^3+2)\,dx`
- **`after_latex`**: `\int\underbrace{3x^2\cos(x^3+2)}_{\text{patrón compuesto}}\,dx`

#### Paso 2: `SUB_02_T01`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: Tomamos como variable auxiliar el argumento del coseno. Transformación concreta: \(\int 3x^2\cos(x^3+2)\,dx\) pasa a \(u=x^3+2\).
- **`before_latex`**: `\int 3x^2\cos(x^3+2)\,dx`
- **`after_latex`**: `u=x^3+2`

#### Paso 3: `SUB_03_T01`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: Derivamos \(x^3+2\) término a término. Transformación concreta: \(u=x^3+2\) pasa a \(du=3x^2\,dx\).
- **`before_latex`**: `u=x^3+2`
- **`after_latex`**: `du=3x^2\,dx`

#### Paso 4: `SUB_04_T01`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: El diferencial coincide exactamente y el ajuste es \(k=1\). Transformación concreta: \(3x^2\,dx\) pasa a \(du\).
- **`before_latex`**: `3x^2\,dx`
- **`after_latex`**: `du`

#### Paso 5: `SUB_05_T01`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: Reemplazamos el argumento y el diferencial completos. Transformación concreta: \(\int 3x^2\cos(x^3+2)\,dx\) pasa a \(\int\cos(u)\,du\).
- **`before_latex`**: `\int 3x^2\cos(x^3+2)\,dx`
- **`after_latex`**: `\int\cos(u)\,du`

#### Paso 6: `SUB_06_T01`
- **`rule_name`**: Integración transformada.
- **`explanation`**: Aplicamos \(\int\cos(u)\,du=\sin(u)+C\), dejando \(C\) para el paso final. Transformación concreta: \(\int\cos(u)\,du\) pasa a \(\sin(u)\).
- **`before_latex`**: `\int\cos(u)\,du`
- **`after_latex`**: `\sin(u)`

#### Paso 7: `SUB_07_T01`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Retornamos a la variable \(x\) usando la definición de \(u\). Transformación concreta: \(\sin(u)\) pasa a \(\sin(x^3+2)\).
- **`before_latex`**: `\sin(u)`
- **`after_latex`**: `\sin(x^3+2)`

#### Paso 8: `SUB_08_T01`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: Es una integral indefinida y requiere constante arbitraria. Transformación concreta: \(\sin(x^3+2)\) pasa a \(\sin(x^3+2)+C\).
- **`before_latex`**: `\sin(x^3+2)`
- **`after_latex`**: `\sin(x^3+2)+C`

#### Paso 9: `SUB_09_T01`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: La regla de la cadena reproduce el integrando original. Transformación concreta: \(\frac{d}{dx}\sin(x^3+2)\) pasa a \(3x^2\cos(x^3+2)\).
- **`before_latex`**: `\frac{d}{dx}\sin(x^3+2)`
- **`after_latex`**: `3x^2\cos(x^3+2)`


### Caso T02: Intermedio — ajuste de constante

- **`input`**: `5*x*(x**2+4)**3`.
- **`method_id`**: `SUB_CONSTANT_FACTOR`.
- **`domain`**: \(x\in\mathbb R\).
- **`variables extraídas`**: `u=x**2+4`, `du=2*x*dx`, `k=5/2`, `h(u)=5*u**3/2`, `H(u)=5*u**4/8`.
- **`resultado final (canónico)`**: `5*(x**2 + 4)**4/8` (`+C` implícito).
- **`resultado final (LaTeX)`**: `\frac58(x^2+4)^4+C`.

#### Paso 1: `SUB_01_T02`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: Detectamos una potencia con base compuesta. Transformación concreta: \(\int5x(x^2+4)^3\,dx\) pasa a \(\int\underbrace{5x(x^2+4)^3}_{\text{potencia de composición}}\,dx\).
- **`before_latex`**: `\int5x(x^2+4)^3\,dx`
- **`after_latex`**: `\int\underbrace{5x(x^2+4)^3}_{\text{potencia de composición}}\,dx`

#### Paso 2: `SUB_02_T02`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: La expresión elevada al cubo es la candidata natural. Transformación concreta: \(\int5x(x^2+4)^3\,dx\) pasa a \(u=x^2+4\).
- **`before_latex`**: `\int5x(x^2+4)^3\,dx`
- **`after_latex`**: `u=x^2+4`

#### Paso 3: `SUB_03_T02`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: Su derivada proporciona el diferencial correcto. Transformación concreta: \(u=x^2+4\) pasa a \(du=2x\,dx\).
- **`before_latex`**: `u=x^2+4`
- **`after_latex`**: `du=2x\,dx`

#### Paso 4: `SUB_04_T02`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: Como \(du=2x\,dx\), el factor original requiere \(5/2\). Transformación concreta: \(5x\,dx\) pasa a \(\frac52\,du\).
- **`before_latex`**: `5x\,dx`
- **`after_latex`**: `\frac52\,du`

#### Paso 5: `SUB_05_T02`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: Ahora toda la integral depende de \(u\). Transformación concreta: \(\int5x(x^2+4)^3\,dx\) pasa a \(\frac52\int u^3\,du\).
- **`before_latex`**: `\int5x(x^2+4)^3\,dx`
- **`after_latex`**: `\frac52\int u^3\,du`

#### Paso 6: `SUB_06_T02`
- **`rule_name`**: Integración transformada.
- **`explanation`**: Aplicamos la regla de potencias y multiplicamos las constantes. Transformación concreta: \(\frac52\int u^3\,du\) pasa a \(\frac52\cdot\frac{u^4}{4}=\frac58u^4\).
- **`before_latex`**: `\frac52\int u^3\,du`
- **`after_latex`**: `\frac52\cdot\frac{u^4}{4}=\frac58u^4`

#### Paso 7: `SUB_07_T02`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Reponemos la expresión original de \(u\). Transformación concreta: \(\frac58u^4\) pasa a \(\frac58(x^2+4)^4\).
- **`before_latex`**: `\frac58u^4`
- **`after_latex`**: `\frac58(x^2+4)^4`

#### Paso 8: `SUB_08_T02`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: Agregamos la constante de integración. Transformación concreta: \(\frac58(x^2+4)^4\) pasa a \(\frac58(x^2+4)^4+C\).
- **`before_latex`**: `\frac58(x^2+4)^4`
- **`after_latex`**: `\frac58(x^2+4)^4+C`

#### Paso 9: `SUB_09_T02`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: Comprobamos el factor \(5\) mediante la regla de la cadena. Transformación concreta: \(\frac{d}{dx}\bigl[\frac58(x^2+4)^4\bigr]\) pasa a \(\frac58\cdot4(x^2+4)^3\cdot2x=5x(x^2+4)^3\).
- **`before_latex`**: `\frac{d}{dx}\bigl[\frac58(x^2+4)^4\bigr]`
- **`after_latex`**: `\frac58\cdot4(x^2+4)^3\cdot2x=5x(x^2+4)^3`


### Caso T03: Intermedio compuesto — despejar x

- **`input`**: `x*sqrt(x+1)`.
- **`method_id`**: `SUB_INVERSE_AFFINE`.
- **`domain`**: \(x>-1\) como intervalo diferenciable; la función integrando está definida también en \(x=-1\).
- **`variables extraídas`**: `u=x+1`, `du=dx`, `x(u)=u-1`, `k=1`, `h(u)=u**(3/2)-u**(1/2)`, `H(u)=2*u**(5/2)/5 - 2*u**(3/2)/3`.
- **`resultado final (canónico)`**: `2*(x+1)**(5/2)/5 - 2*(x+1)**(3/2)/3` (`+C` implícito).
- **`resultado final (LaTeX)`**: `\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}+C`.

#### Paso 1: `SUB_01_T03`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: El radical sugiere una sustitución, pero queda un factor \(x\) pendiente. Transformación concreta: \(\int x\sqrt{x+1}\,dx\) pasa a \(\int\underbrace{x\sqrt{x+1}}_{\text{radical con factor exterior}}\,dx\).
- **`before_latex`**: `\int x\sqrt{x+1}\,dx`
- **`after_latex`**: `\int\underbrace{x\sqrt{x+1}}_{\text{radical con factor exterior}}\,dx`

#### Paso 2: `SUB_02_T03`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: Elegimos el radicando como variable auxiliar. Transformación concreta: \(\int x\sqrt{x+1}\,dx\) pasa a \(u=x+1\).
- **`before_latex`**: `\int x\sqrt{x+1}\,dx`
- **`after_latex`**: `u=x+1`

#### Paso 3: `SUB_03_T03`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: La derivada de \(x+1\) es \(1\). Transformación concreta: \(u=x+1\) pasa a \(du=dx\).
- **`before_latex`**: `u=x+1`
- **`after_latex`**: `du=dx`

#### Paso 4: `SUB_04_T03`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: Despejamos \(x\) porque debe desaparecer del integrando. Transformación concreta: \(u=x+1\) pasa a \(x=u-1,\qquad dx=du\).
- **`before_latex`**: `u=x+1`
- **`after_latex`**: `x=u-1,\qquad dx=du`

#### Paso 5: `SUB_05_T03`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: Reemplazamos \(x\), el radical y el diferencial; distribuimos el producto. Transformación concreta: \(\int x\sqrt{x+1}\,dx\) pasa a \(\int(u-1)u^{1/2}\,du=\int(u^{3/2}-u^{1/2})\,du\).
- **`before_latex`**: `\int x\sqrt{x+1}\,dx`
- **`after_latex`**: `\int(u-1)u^{1/2}\,du=\int(u^{3/2}-u^{1/2})\,du`
 - **`sub_steps`**:
   - **Subpaso 5.1**:
     - `rule_name`: Distribución.
     - `explanation`: Aplicamos \((u-1)u^{1/2}=u^{3/2}-u^{1/2}\).
     - `before_latex`: `(u-1)u^{1/2}`
     - `after_latex`: `u^{3/2}-u^{1/2}`

#### Paso 6: `SUB_06_T03`
- **`rule_name`**: Integración transformada.
- **`explanation`**: Integramos por separado ambas potencias. Transformación concreta: \(\int(u^{3/2}-u^{1/2})\,du\) pasa a \(\frac25u^{5/2}-\frac23u^{3/2}\).
- **`before_latex`**: `\int(u^{3/2}-u^{1/2})\,du`
- **`after_latex`**: `\frac25u^{5/2}-\frac23u^{3/2}`

#### Paso 7: `SUB_07_T03`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Volvemos a \(x\) con \(u=x+1\). Transformación concreta: \(\frac25u^{5/2}-\frac23u^{3/2}\) pasa a \(\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}\).
- **`before_latex`**: `\frac25u^{5/2}-\frac23u^{3/2}`
- **`after_latex`**: `\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}`

#### Paso 8: `SUB_08_T03`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: Añadimos la constante en el intervalo de validez. Transformación concreta: \(\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}\) pasa a \(\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}+C\).
- **`before_latex`**: `\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}`
- **`after_latex`**: `\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}+C`

#### Paso 9: `SUB_09_T03`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: Factorizamos \(\sqrt{x+1}\) y recuperamos \(x\sqrt{x+1}\). Transformación concreta: \(\frac{d}{dx}\left(\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}\right)\) pasa a \((x+1)^{3/2}-(x+1)^{1/2}=x\sqrt{x+1}\).
- **`before_latex`**: `\frac{d}{dx}\left(\frac25(x+1)^{5/2}-\frac23(x+1)^{3/2}\right)`
- **`after_latex`**: `(x+1)^{3/2}-(x+1)^{1/2}=x\sqrt{x+1}`


### Caso T04: Avanzado — composición anidada

- **`input`**: `x*exp(x**2)*cos(exp(x**2))`.
- **`method_id`**: `SUB_NESTED`.
- **`domain`**: \(x\in\mathbb R\).
- **`variables extraídas`**: `u=exp(x**2)`, `du=2*x*exp(x**2)*dx`, `k=1/2`, `h(u)=cos(u)/2`, `H(u)=sin(u)/2`.
- **`resultado final (canónico)`**: `sin(exp(x**2))/2` (`+C` implícito).
- **`resultado final (LaTeX)`**: `\frac12\sin(e^{x^2})+C`.

#### Paso 1: `SUB_01_T04`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: Hay una función exponencial dentro de un coseno; una sustitución exterior evita pasos extra. Transformación concreta: \(\int xe^{x^2}\cos(e^{x^2})\,dx\) pasa a \(\int\underbrace{xe^{x^2}\cos(e^{x^2})}_{\text{composición profunda}}\,dx\).
- **`before_latex`**: `\int xe^{x^2}\cos(e^{x^2})\,dx`
- **`after_latex`**: `\int\underbrace{xe^{x^2}\cos(e^{x^2})}_{\text{composición profunda}}\,dx`

#### Paso 2: `SUB_02_T04`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: Elegimos todo el argumento del coseno como \(u\). Transformación concreta: \(\int xe^{x^2}\cos(e^{x^2})\,dx\) pasa a \(u=e^{x^2}\).
- **`before_latex`**: `\int xe^{x^2}\cos(e^{x^2})\,dx`
- **`after_latex`**: `u=e^{x^2}`

#### Paso 3: `SUB_03_T04`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: Aplicamos la regla de la cadena a la función exponencial compuesta. Transformación concreta: \(u=e^{x^2}\) pasa a \(du=2xe^{x^2}\,dx\).
- **`before_latex`**: `u=e^{x^2}`
- **`after_latex`**: `du=2xe^{x^2}\,dx`

#### Paso 4: `SUB_04_T04`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: Extraemos el factor \(1/2\) porque el diferencial contiene \(2x\). Transformación concreta: \(xe^{x^2}\,dx\) pasa a \(\frac12\,du\).
- **`before_latex`**: `xe^{x^2}\,dx`
- **`after_latex`**: `\frac12\,du`

#### Paso 5: `SUB_05_T04`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: La nueva integral carece de \(x\). Transformación concreta: \(\int xe^{x^2}\cos(e^{x^2})\,dx\) pasa a \(\frac12\int\cos(u)\,du\).
- **`before_latex`**: `\int xe^{x^2}\cos(e^{x^2})\,dx`
- **`after_latex`**: `\frac12\int\cos(u)\,du`

#### Paso 6: `SUB_06_T04`
- **`rule_name`**: Integración transformada.
- **`explanation`**: La primitiva de \(\cos(u)\) es \(\sin(u)\). Transformación concreta: \(\frac12\int\cos(u)\,du\) pasa a \(\frac12\sin(u)\).
- **`before_latex`**: `\frac12\int\cos(u)\,du`
- **`after_latex`**: `\frac12\sin(u)`

#### Paso 7: `SUB_07_T04`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Deshacemos la sustitución principal. Transformación concreta: \(\frac12\sin(u)\) pasa a \(\frac12\sin(e^{x^2})\).
- **`before_latex`**: `\frac12\sin(u)`
- **`after_latex`**: `\frac12\sin(e^{x^2})`

#### Paso 8: `SUB_08_T04`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: Agregamos la constante de integración. Transformación concreta: \(\frac12\sin(e^{x^2})\) pasa a \(\frac12\sin(e^{x^2})+C\).
- **`before_latex`**: `\frac12\sin(e^{x^2})`
- **`after_latex`**: `\frac12\sin(e^{x^2})+C`

#### Paso 9: `SUB_09_T04`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: Verificamos todas las capas de la regla de la cadena. Transformación concreta: \(\frac{d}{dx}\bigl[\frac12\sin(e^{x^2})\bigr]\) pasa a \(\frac12\cos(e^{x^2})\cdot e^{x^2}\cdot2x=xe^{x^2}\cos(e^{x^2})\).
- **`before_latex`**: `\frac{d}{dx}\bigl[\frac12\sin(e^{x^2})\bigr]`
- **`after_latex`**: `\frac12\cos(e^{x^2})\cdot e^{x^2}\cdot2x=xe^{x^2}\cos(e^{x^2})`


### Caso T05: Caso borde — logaritmo absoluto y dominio desconectado

- **`input`**: `x/(x**2-1)`.
- **`method_id`**: `SUB_LOG_ABSOLUTE`.
- **`domain`**: \(x\in(-\infty,-1)\cup(-1,1)\cup(1,\infty)\).
- **`variables extraídas`**: `u=x**2-1`, `du=2*x*dx`, `k=1/2`, `h(u)=1/(2*u)`, `H(u)=log(Abs(u))/2`.
- **`resultado final (canónico)`**: `log(Abs(x**2 - 1))/2` (`+C` implícito).
- **`resultado final (LaTeX)`**: `\frac12\ln|x^2-1|+C`.

#### Paso 1: `SUB_01_T05`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: El denominador tiene derivada proporcional al numerador; excluimos \(x=\pm1\). Transformación concreta: \(\int\frac{x}{x^2-1}\,dx\) pasa a \(\int\underbrace{\frac{x}{x^2-1}}_{\text{derivada sobre función}}\,dx\).
- **`before_latex`**: `\int\frac{x}{x^2-1}\,dx`
- **`after_latex`**: `\int\underbrace{\frac{x}{x^2-1}}_{\text{derivada sobre función}}\,dx`

#### Paso 2: `SUB_02_T05`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: Tomamos el denominador como \(u\). Transformación concreta: \(\int\frac{x}{x^2-1}\,dx\) pasa a \(u=x^2-1\).
- **`before_latex`**: `\int\frac{x}{x^2-1}\,dx`
- **`after_latex`**: `u=x^2-1`

#### Paso 3: `SUB_03_T05`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: Derivamos el denominador. Transformación concreta: \(u=x^2-1\) pasa a \(du=2x\,dx\).
- **`before_latex`**: `u=x^2-1`
- **`after_latex`**: `du=2x\,dx`

#### Paso 4: `SUB_04_T05`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: Se corrige el factor \(2\) del diferencial. Transformación concreta: \(x\,dx\) pasa a \(\frac12\,du\).
- **`before_latex`**: `x\,dx`
- **`after_latex`**: `\frac12\,du`

#### Paso 5: `SUB_05_T05`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: Reescribimos la fracción sin la variable original. Transformación concreta: \(\int\frac{x}{x^2-1}\,dx\) pasa a \(\frac12\int\frac1u\,du\).
- **`before_latex`**: `\int\frac{x}{x^2-1}\,dx`
- **`after_latex`**: `\frac12\int\frac1u\,du`

#### Paso 6: `SUB_06_T05`
- **`rule_name`**: Integración transformada.
- **`explanation`**: La primitiva real de \(1/u\) exige \(u\neq0\) y valor absoluto. Transformación concreta: \(\frac12\int\frac1u\,du\) pasa a \(\frac12\ln|u|\).
- **`before_latex`**: `\frac12\int\frac1u\,du`
- **`after_latex`**: `\frac12\ln|u|`
 - **`sub_steps`**:
   - **Subpaso 6.1**:
     - `rule_name`: Registro del dominio.
     - `explanation`: Como \(u\neq0\), la primitiva real es \(\ln|u|\).
     - `before_latex`: `u\neq0`
     - `after_latex`: `\ln|u|`

#### Paso 7: `SUB_07_T05`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Reemplazamos el denominador original. Transformación concreta: \(\frac12\ln|u|\) pasa a \(\frac12\ln|x^2-1|\).
- **`before_latex`**: `\frac12\ln|u|`
- **`after_latex`**: `\frac12\ln|x^2-1|`

#### Paso 8: `SUB_08_T05`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: En cada uno de los tres intervalos conexos puede elegirse una constante independiente. Transformación concreta: \(\frac12\ln|x^2-1|\) pasa a \(\frac12\ln|x^2-1|+C\).
- **`before_latex`**: `\frac12\ln|x^2-1|`
- **`after_latex`**: `\frac12\ln|x^2-1|+C`

#### Paso 9: `SUB_09_T05`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: Verificamos solo donde el denominador no se anula; el posible punto \(x=0\) no causa problema a la identidad final. Transformación concreta: \(\frac{d}{dx}\left[\frac12\ln|x^2-1|\right]\) pasa a \(\frac12\frac{2x}{x^2-1}=\frac{x}{x^2-1}\quad(x\ne\pm1)\).
- **`before_latex`**: `\frac{d}{dx}\left[\frac12\ln|x^2-1|\right]`
- **`after_latex`**: `\frac12\frac{2x}{x^2-1}=\frac{x}{x^2-1}\quad(x\ne\pm1)`


### Caso T06: Intermedio — integral definida con cambio de límites

- **`input`**: `Integral(2*x*exp(x**2),(x,0,1))`.
- **`method_id`**: `SUB_DEFINITE_BOUNDS`.
- **`domain`**: \(0\le x\le1\).
- **`variables extraídas`**: `u=x**2`, `du=2*x*dx`, `k=1`, `h(u)=exp(u)`, `H(u)=exp(u)`, `new_bounds=(0,1)`.
- **`resultado final (canónico)`**: `E - 1` (integral definida).
- **`resultado final (LaTeX)`**: `e-1`.

#### Paso 1: `SUB_01_T06`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: Identificamos la exponencial compuesta con diferencial completo. Transformación concreta: \(\int_0^1 2xe^{x^2}\,dx\) pasa a \(\int_0^1\underbrace{2xe^{x^2}}_{\text{compuesta}}\,dx\).
- **`before_latex`**: `\int_0^1 2xe^{x^2}\,dx`
- **`after_latex`**: `\int_0^1\underbrace{2xe^{x^2}}_{\text{compuesta}}\,dx`

#### Paso 2: `SUB_02_T06`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: Definimos \(u\) para convertir el exponente. Transformación concreta: \(\int_0^1 2xe^{x^2}\,dx\) pasa a \(u=x^2\).
- **`before_latex`**: `\int_0^1 2xe^{x^2}\,dx`
- **`after_latex`**: `u=x^2`

#### Paso 3: `SUB_03_T06`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: La derivada coincide con el factor del integrando. Transformación concreta: \(u=x^2\) pasa a \(du=2x\,dx\).
- **`before_latex`**: `u=x^2`
- **`after_latex`**: `du=2x\,dx`

#### Paso 4: `SUB_04_T06`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: No hay factor adicional, por lo que \(k=1\). Transformación concreta: \(2x\,dx\) pasa a \(du\).
- **`before_latex`**: `2x\,dx`
- **`after_latex`**: `du`

#### Paso 5: `SUB_05_T06`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: El integrando queda en \(u\) y los límites deben cambiar junto a la variable. Transformación concreta: \(\int_0^1 2xe^{x^2}\,dx\) pasa a \(\int_{u(0)}^{u(1)}e^u\,du\).
- **`before_latex`**: `\int_0^1 2xe^{x^2}\,dx`
- **`after_latex`**: `\int_{u(0)}^{u(1)}e^u\,du`

#### Paso 6: `SUB_06_T06`
- **`rule_name`**: Integración transformada.
- **`explanation`**: Calculamos la primitiva de la exponencial en la nueva variable. Transformación concreta: \(\int e^u\,du\) pasa a \(e^u\).
- **`before_latex`**: `\int e^u\,du`
- **`after_latex`**: `e^u`

#### Paso 7: `SUB_07_T06`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Evaluamos explícitamente los nuevos extremos en el orden original. Transformación concreta: \(u(0)=0^2,\quad u(1)=1^2\) pasa a \(\int_0^1 e^u\,du\).
- **`before_latex`**: `u(0)=0^2,\quad u(1)=1^2`
- **`after_latex`**: `\int_0^1 e^u\,du`
 - **`sub_steps`**:
   - **Subpaso 7.1**:
     - `rule_name`: Calcular extremos.
     - `explanation`: Los límites en \(x\) se trasladan mediante \(u=x^2\).
     - `before_latex`: `(u(0),u(1))`
     - `after_latex`: `(0,1)`

#### Paso 8: `SUB_08_T06`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: Aplicamos el teorema fundamental del cálculo; aquí no existe \(+C\) final. Transformación concreta: \(\int_0^1 e^u\,du\) pasa a \([e^u]_0^1=e^1-e^0=e-1\).
- **`before_latex`**: `\int_0^1 e^u\,du`
- **`after_latex`**: `[e^u]_0^1=e^1-e^0=e-1`

#### Paso 9: `SUB_09_T06`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: Comprobamos tanto la antiderivada como la diferencia de extremos. Transformación concreta: \(\frac{d}{dx}e^{x^2}=2xe^{x^2}\) pasa a \(\int_0^1 2xe^{x^2}\,dx=[e^{x^2}]_0^1=e-1\).
- **`before_latex`**: `\frac{d}{dx}e^{x^2}=2xe^{x^2}`
- **`after_latex`**: `\int_0^1 2xe^{x^2}\,dx=[e^{x^2}]_0^1=e-1`


### Caso T07: Avanzado — completar cuadrados y separar integrales

- **`input`**: `x/sqrt(x**2+2*x+5)`.
- **`method_id`**: `SUB_COMPLETE_SQUARE`.
- **`domain`**: \(x\in\mathbb R\), ya que \(x^2+2x+5=(x+1)^2+4>0\).
- **`variables extraídas`**: `u=x+1`, `du=dx`, `x(u)=u-1`, `completed_quadratic=(x+1)**2+4`, `h(u)=(u-1)/sqrt(u**2+4)`, `H(u)=sqrt(u**2+4)-asinh(u/2)`.
- **`resultado final (canónico)`**: `sqrt(x**2 + 2*x + 5) - asinh((x+1)/2)` (`+C` implícito).
- **`resultado final (LaTeX)`**: `\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)+C`.

#### Paso 1: `SUB_01_T07`
- **`rule_name`**: Reconocimiento del patrón.
- **`explanation`**: Completamos el cuadrado: \(x^2+2x+5=(x+1)^2+4\). Transformación concreta: \(\int\frac{x}{\sqrt{x^2+2x+5}}\,dx\) pasa a \(\int\frac{x}{\sqrt{(x+1)^2+4}}\,dx\).
- **`before_latex`**: `\int\frac{x}{\sqrt{x^2+2x+5}}\,dx`
- **`after_latex`**: `\int\frac{x}{\sqrt{(x+1)^2+4}}\,dx`
 - **`sub_steps`**:
   - **Subpaso 1.1**:
     - `rule_name`: Completar cuadrado.
     - `explanation`: La identidad \(x^2+2x+5=(x+1)^2+4\) se verifica expandiendo.
     - `before_latex`: `x^2+2x+5`
     - `after_latex`: `(x+1)^2+4`

#### Paso 2: `SUB_02_T07`
- **`rule_name`**: Elección de la sustitución.
- **`explanation`**: Seleccionamos el binomio que aparece al cuadrado. Transformación concreta: \(\int\frac{x}{\sqrt{(x+1)^2+4}}\,dx\) pasa a \(u=x+1\).
- **`before_latex`**: `\int\frac{x}{\sqrt{(x+1)^2+4}}\,dx`
- **`after_latex`**: `u=x+1`

#### Paso 3: `SUB_03_T07`
- **`rule_name`**: Derivación y diferencial.
- **`explanation`**: El diferencial no requiere factor de ajuste. Transformación concreta: \(u=x+1\) pasa a \(du=dx\).
- **`before_latex`**: `u=x+1`
- **`after_latex`**: `du=dx`

#### Paso 4: `SUB_04_T07`
- **`rule_name`**: Despeje y ajuste.
- **`explanation`**: Despejamos \(x\) y reescribimos la cuadrática. Transformación concreta: \(x+1=u\) pasa a \(x=u-1,\quad (x+1)^2+4=u^2+4\).
- **`before_latex`**: `x+1=u`
- **`after_latex`**: `x=u-1,\quad (x+1)^2+4=u^2+4`

#### Paso 5: `SUB_05_T07`
- **`rule_name`**: Reescritura integral.
- **`explanation`**: Separar la suma permite identificar dos primitivas conocidas. Transformación concreta: \(\int\frac{x}{\sqrt{(x+1)^2+4}}\,dx\) pasa a \(\int\frac{u-1}{\sqrt{u^2+4}}\,du=\int\frac{u}{\sqrt{u^2+4}}\,du-\int\frac{du}{\sqrt{u^2+4}}\).
- **`before_latex`**: `\int\frac{x}{\sqrt{(x+1)^2+4}}\,dx`
- **`after_latex`**: `\int\frac{u-1}{\sqrt{u^2+4}}\,du=\int\frac{u}{\sqrt{u^2+4}}\,du-\int\frac{du}{\sqrt{u^2+4}}`

#### Paso 6: `SUB_06_T07`
- **`rule_name`**: Integración transformada.
- **`explanation`**: Para la primera integral usamos una sustitución interna \(w=u^2+4\); para la segunda, \(\int du/\sqrt{u^2+a^2}=\operatorname{arsinh}(u/a)\) con \(a=2\). Transformación concreta: \(\int\frac{u}{\sqrt{u^2+4}}\,du-\int\frac{du}{\sqrt{u^2+4}}\) pasa a \(\sqrt{u^2+4}-\operatorname{arsinh}\!\left(\frac u2\right)\).
- **`before_latex`**: `\int\frac{u}{\sqrt{u^2+4}}\,du-\int\frac{du}{\sqrt{u^2+4}}`
- **`after_latex`**: `\sqrt{u^2+4}-\operatorname{arsinh}\!\left(\frac u2\right)`
 - **`sub_steps`**:
   - **Subpaso 6.1**:
     - `rule_name`: Separar y resolver.
     - `explanation`: Usamos linealidad y la identidad \(\frac{d}{du}\operatorname{arsinh}(u/2)=1/\sqrt{u^2+4}\).
     - `before_latex`: `\int\frac{u-1}{\sqrt{u^2+4}}\,du`
     - `after_latex`: `\sqrt{u^2+4}-\operatorname{arsinh}(u/2)`
   - **Subpaso 6.2**:
     - `rule_name`: Resolver explícitamente la primera integral con un cambio auxiliar.
     - `explanation`: Definimos \(w=u^2+4\), calculamos \(dw=2u\,du\) y obtenemos \(u\,du=\frac12dw\). De este modo, \(\int\frac{u}{\sqrt{u^2+4}}\,du=\frac12\int w^{-1/2}\,dw=\sqrt{w}=\sqrt{u^2+4}\).
     - `before_latex`: `\int\frac{u}{\sqrt{u^2+4}}\,du`
     - `after_latex`: `\frac12\int w^{-1/2}\,dw=\sqrt{w}=\sqrt{u^2+4}`
   - **Subpaso 6.3**:
     - `rule_name`: Reconocer y verificar la segunda primitiva.
     - `explanation`: Utilizamos \(\int\frac{du}{\sqrt{u^2+a^2}}=\operatorname{arsinh}(u/a)+C\) para \(a>0\). Con \(a=2\) comprobamos que \(\frac{d}{du}\operatorname{arsinh}(u/2)=1/\sqrt{u^2+4}\). Esta ruta requiere que el módulo de primitivas hiperbólicas esté disponible como dependencia.
     - `before_latex`: `\int\frac{du}{\sqrt{u^2+4}}`
     - `after_latex`: `\operatorname{arsinh}\!\left(\frac u2\right)`

#### Paso 7: `SUB_07_T07`
- **`rule_name`**: Retorno o transformación de límites.
- **`explanation`**: Restituimos \(u=x+1\) y la forma cuadrática original. Transformación concreta: \(\sqrt{u^2+4}-\operatorname{arsinh}\!\left(\frac u2\right)\) pasa a \(\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)\).
- **`before_latex`**: `\sqrt{u^2+4}-\operatorname{arsinh}\!\left(\frac u2\right)`
- **`after_latex`**: `\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)`

#### Paso 8: `SUB_08_T07`
- **`rule_name`**: Constante o evaluación.
- **`explanation`**: La integral es indefinida y el radicando es positivo para todo \(x\) real. Transformación concreta: \(\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)\) pasa a \(\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)+C\).
- **`before_latex`**: `\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)`
- **`after_latex`**: `\sqrt{x^2+2x+5}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)+C`

#### Paso 9: `SUB_09_T07`
- **`rule_name`**: Verificación de la igualdad.
- **`explanation`**: Las derivadas se combinan y recuperan exactamente el numerador \(x\). Transformación concreta: \(\frac{d}{dx}\left[\sqrt{(x+1)^2+4}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)\right]\) pasa a \(\frac{x+1}{\sqrt{(x+1)^2+4}}-\frac1{\sqrt{(x+1)^2+4}}=\frac{x}{\sqrt{x^2+2x+5}}\).
- **`before_latex`**: `\frac{d}{dx}\left[\sqrt{(x+1)^2+4}-\operatorname{arsinh}\!\left(\frac{x+1}{2}\right)\right]`
- **`after_latex`**: `\frac{x+1}{\sqrt{(x+1)^2+4}}-\frac1{\sqrt{(x+1)^2+4}}=\frac{x}{\sqrt{x^2+2x+5}}`

### Caso T08: borde negativo — no forzar una sustitución inexistente

- **`input`**: `exp(x**2)`.
- **`variables extraídas`**: `candidate_u=x**2`, `du_dx=2*x`, `quotient=exp(x**2)/(2*x)` en `x!=0`.
- **`domain`**: `x` real (el integrando original es continuo en todo `R`).
- **`status`**: `rejected` para la ruta de sustitución **simple**.

#### Paso 1: `SUB_01_T08`
- **`rule_name`**: Examinar composición exponencial.
- **`explanation`**: Detectamos la expresión interior \(x^2\) en \(e^{x^2}\); por sí sola no garantiza una sustitución útil.
- **`before_latex`**: `\int e^{x^2}\,dx`
- **`after_latex`**: `u=x^2\quad\text{(candidato)}`

#### Paso 2: `SUB_02_T08`
- **`rule_name`**: Derivar el candidato.
- **`explanation`**: La elección \(u=x^2\) produce \(du=2x\,dx\).
- **`before_latex`**: `u=x^2`
- **`after_latex`**: `du=2x\,dx`

#### Paso 3: `SUB_03_T08`
- **`rule_name`**: Comprobar factores.
- **`explanation`**: El integrando \(e^{x^2}\) no incluye el factor \(2x\) necesario para cambiar directamente a \(du\).
- **`before_latex`**: `e^{x^2}\,dx`
- **`after_latex`**: `\frac{e^u}{2x}\,du\quad\text{(todavía depende de }x\text{)}`

#### Paso 4: `SUB_04_T08`
- **`rule_name`**: Rechazar ruta simple.
- **`explanation`**: La condición \(x\notin\operatorname{free\_symbols}(h_u)\) falla; no podemos presentar la expresión provisional como una integral en una sola variable \(u\).
- **`before_latex`**: `\frac{e^u}{2x}\,du`
- **`after_latex`**: `\text{Sustitución elemental simple no aplicable}`

#### Paso 5: `SUB_05_T08`
- **`rule_name`**: Ofrecer una salida honesta.
- **`explanation`**: No existe una primitiva elemental para \(e^{x^2}\). Si la aplicación admite funciones especiales, puede mostrar \(\frac{\sqrt{\pi}}{2}\operatorname{erfi}(x)+C\) como resultado de un módulo distinto.
- **`before_latex`**: `\int e^{x^2}\,dx`
- **`after_latex`**: `\frac{\sqrt{\pi}}{2}\operatorname{erfi}(x)+C\quad\text{(función especial)}`
- **`resultado final (canónico)`**: `sqrt(pi)*erfi(x)/2`.
- **`resultado final (LaTeX)`**: `\frac{\sqrt{\pi}}{2}\operatorname{erfi}(x)+C`.

### 6.1 Pruebas automáticas en SymPy — derivación y equivalencias

Código ejecutable independiente para la verificación de los **siete casos resueltos**. El residuo de la derivada debe anularse en el dominio correspondiente; para valores absolutos SymPy puede producir una condición `Piecewise` en puntos singulares que se han excluido explícitamente.

```python
import sympy as sp

x = sp.symbols('x', real=True)
examples = [
    ('T01', 3*x**2*sp.cos(x**3+2), sp.sin(x**3+2), (-2, 0, 2)),
    ('T02', 5*x*(x**2+4)**3, sp.Rational(5,8)*(x**2+4)**4, (-2, 0, 2)),
    ('T03', x*sp.sqrt(x+1),
     sp.Rational(2,5)*(x+1)**sp.Rational(5,2)
     - sp.Rational(2,3)*(x+1)**sp.Rational(3,2), (0, 1, 3)),
    ('T04', x*sp.exp(x**2)*sp.cos(sp.exp(x**2)),
     sp.sin(sp.exp(x**2))/2, (-1, 0, 1)),
    ('T05', x/(x**2-1), sp.log(sp.Abs(x**2-1))/2,
     (-2, -sp.Rational(1,2), 0, sp.Rational(1,2), 2)),
    ('T06', 2*x*sp.exp(x**2), sp.exp(x**2), (0, sp.Rational(1,2), 1)),
    ('T07', x/sp.sqrt(x**2+2*x+5),
     sp.sqrt(x**2+2*x+5)-sp.asinh((x+1)/2), (-2, 0, 2)),
]

for name, integrand, antiderivative, points in examples:
    residual = sp.diff(antiderivative, x) - integrand
    # Primero igualdad global sencilla; si no decide (Abs, Piecewise),
    # comprobar cada región con hipótesis y/o evaluación exacta.
    global_result = sp.simplify(residual)
    if global_result != 0:
        assert all(sp.simplify(residual.subs(x, a)) == 0 for a in points), name
    print(name, 'OK')

assert sp.simplify(sp.integrate(2*x*sp.exp(x**2), (x,0,1))-(sp.E-1)) == 0
assert sp.expand((x+1)**2+4-(x**2+2*x+5)) == 0
print('Integral definida y completación de cuadrados: OK')
```

### 6.2 Matriz de cobertura del motor

| ID | Nivel | Variante | Dominio y precaución | Resultado esperado |
|---|---|---|---|---|
| T01 | básico | sustitución exacta | real | `sin(x**3+2)` |
| T02 | intermedio | ajuste constante | real | `5*(x**2+4)**4/8` |
| T03 | intermedio compuesto | despeje de `x` | radical, `x>=-1` | `2*(x+1)**(5/2)/5-2*(x+1)**(3/2)/3` |
| T04 | avanzado | composición profunda | real | `sin(exp(x**2))/2` |
| T05 | borde | logaritmo absoluto | excluir `-1,1` | `log(Abs(x**2-1))/2` |
| T06 | integral definida | nuevos límites | `[0,1]` | `E-1` |
| T07 | avanzado | completar cuadrados | real | `sqrt(x**2+2*x+5)-asinh((x+1)/2)` |
| T08 | ruta negativa | candidato rechazado | real | función especial `sqrt(pi)*erfi(x)/2` fuera del módulo simple |

### 6.3 Criterios de aceptación para la implementación

1. **Reconocimiento:** el método elegido no se basa exclusivamente en `is_Mul`/`is_Pow`, sino en una identidad simbólica verificada.
2. **Fidelidad:** cada transformación visible conserva la equivalencia matemática, con hipótesis explícitas cuando corresponda.
3. **Atomicidad:** existe traza de selección, derivación de `u`, ajuste, reescritura, integración, retorno o límites, constante o evaluación, comprobación.
4. **Conservación de dominio:** factor cancelado, radical, logaritmo e inversa no pierden restricciones originales.
5. **Didáctica:** las explicaciones contienen sus símbolos matemáticos dentro de `\(...\)`; los campos LaTeX de fórmula no incluyen delimitadores.
6. **Verificación:** las pruebas T01–T07 reproducen antiderivadas correctas; T06 reproduce además el valor de la integral definida.
7. **Rechazo honesto:** T08 nunca se presenta como sustitución elemental exitosa.
8. **Render:** KaTeX soporta las expresiones renderizadas que el proyecto decida habilitar; las salidas que KaTeX no soporte deben pasar por normalización de notación, no eliminar pasos.
9. **Extensibilidad:** si el caso T07 usa un método auxiliar (integral hiperbólica, logaritmos), este debe generar sus propias subtrazas; está prohibido ocultar un cálculo no trivial detrás de `integrate`.

**Fin de la especificación inicial del tema de sustitución.** Para integrar por partes, sustitución trigonométrica, potencias trigonométricas o fracciones parciales, crear un módulo separado con las mismas seis secciones, su propio detector y pruebas graduadas; sus criterios no deben mezclarse de manera implícita en este módulo.
