# Compiscript — Especificación de Código Intermedio (TAC)

> **Objetivo:** Definir la representación intermedia **TAC** (Three-Address Code) generada por `ir/backend/tac_generator.py` y consumida por `ir/tac/*` para visualización y futuros *backends*.

---

## 1) Modelo y convenciones

- **Operando** (`Operand = str`):
  - **Temporales**: `t0`, `t1`, …
  - **Locales**: `%x` (variables/params en el *frame* actual)
  - **Globales**: `@NOMBRE`
  - **Literales**: `#5`, `#3.14`, `#"hola"`, `#true`, `#null`
- **Función**:
  ```
  .func nombre(p1, p2) : RetType
    .locals K
    ...             # instrucciones
  .endfunc
  ```
  - `RetType ∈ {Int, Float, Bool, String, Void, Class, Array<…>}` (string nominal).
  - `.locals K` es un metadato (conteo calculado por el generador).

## 2) Instrucciones principales

> La sintaxis mostrada corresponde al método `__str__` de cada clase en `instructions.py`.

### 2.1 Asignación y movimiento

- `move SRC -> DST` → `move %a, %x` se imprime como:  
  ```
  move %a, %x
  ```

### 2.2 Unarias y Binarias

- **Unarias**: `dst = <op> a`
  - `neg` (numérico), `not` (lógico)
  - Ej.: `t0 = neg %x`, `t1 = not %b`
- **Binarias**: `dst = a <op> b`
  - Aritméticas: `+ - * / %`
  - Comparación: `< <= > >= == !=`
  - Lógicas cortocircuito se modelan con *labels/goto* (no como binario directo).

### 2.3 Control de flujo

- `label L`  
- `goto L`  
- `if_goto cond, L`      (salta si `cond` es verdadero)  
- `if_false cond, L`     (salta si `cond` es falso)  
- `ret v` / `ret`        (con o sin valor)

> **Peephole:** se elimina el patrón `goto L` seguido inmediatamente de `label L`.

### 2.4 Llamadas

- `param a` (empuja argumento **en orden de aparición**)  
- `call fname, nArgs, dst` — guarda retorno en `dst`; si no hay valor, usar `dst = #void` o no usar `dst`.  
- Convención simple:
  1. Emitir cada `param`.
  2. `call f, N, tX` y (opcionalmente) limpiar los temporales si hubiera *stack model* más adelante.

### 2.5 Objetos y campos

- `new ClassName -> dst`      → `dst = new ClassName`
- `getf obj, field -> dst`    → `dst = getf %obj, "x"`
- `setf obj, field, val`      → `setf %obj, "x", t0`

### 2.6 Arreglos

- `newarr ElemType, size -> dst` → `dst = newarr Int, %n`
- `aload arr, idx -> dst`        → `dst = aload %a, %i`
- `astore arr, idx, val`         → `astore %a, %i, t0`

### 2.7 E/S simple

- `print a` → salida a consola (solo para *debugging* y demo).

## 3) Ejemplo completo

```tac
.func max(a, b) : Int
  .locals 1
  t0 = %a > %b
  ifFalse t0, Lelse1
  ret %a
  goto Lend2
label Lelse1:
  ret %b
label Lend2:
.endfunc
```

## 4) Reglas de tipos (resumen)

- Los operadores aritméticos operan sobre `Int/Float`; resultado promueve a `Float` si hay mezcla.
- Comparaciones devuelven `Bool`.
- `not` exige `Bool`; `neg` exige numérico.
- `aload/astore` solo sobre `Array<T>`; `getf/setf` solo sobre `Class` con miembro existente.
- `call` valida aridad y tipos de parámetros contra la firma registrada.

## 5) Convenciones de temporales y labels

- Temporales generados por `Emitter.t()` (`t0`, `t1`, …); **vida corta** — recomputables.
- Labels generados por `Emitter.L()` (`L0`, `L1`, …) o con nombre lógico (`Lret0`, etc.).
- `Emitter.last_is_terminal()` ayuda a evitar *fallthroughs* tras `ret/goto` duplicados.

## 6) Optimizaciones posibles

- *Peephole* adicional: `move x, y` seguido de uso único → *copy propagation*.
- *Constant folding*: `t0 = #3 + #4` → `t0 = #7`.
- Eliminación de temporales muertos (*dead code elimination*).
