
# Compiscript — Especificación de Código Intermedio (TAC)

> **Propósito.** Este documento define el *Three-Address Code (TAC)* que generará el compilador de **Compiscript**. Sirve como contrato entre el generador de TAC y la posterior fase de generación de código nativo/assembler.

---

## 1. Modelo y Convenciones

- **Forma base**: cuadruplas `(op, arg1, arg2, res)`; también hay pseudo‐ops con 1–2 campos.
- **Operandos**:
  - **Temporales**: `t0, t1, t2, ...` (reutilizables).
  - **Variables**: nombres tal cual aparecen en el código fuente (mapeadas por tabla de símbolos a offsets/segmentos).
  - **Literales**: `#<valor>` (por ejemplo `#0`, `#1`, `#-5`, `#3.14`, `#"hola"`).
  - **Etiquetas**: `L0, L1, ...` (puntos de salto).
- **Tipos**: las instrucciones asumen que el *checker semántico* ya validó tipos compatibles. Si un backend lo requiere, puede usar sufijos opcionales (`ADD.i32`, `ADD.f64`, etc.).
- **Orden de evaluación**: izquierda → derecha, salvo que se indique explícitamente.
- **Short-circuit**: `&&` y `||` se implementan con saltos y etiquetas (no existen instrucciones lógicas con ambos operandos materializados por defecto).

---

## 2. Conjunto de Instrucciones

### 2.1 Movimiento / Asignación

| Instrucción | Forma                  | Semántica                                          |
|-------------|------------------------|----------------------------------------------------|
| `ASSIGN`    | `ASSIGN src dst`       | `dst = src` (copia de valor)                       |

> *Nota*: El *backend* decidirá si `dst` está en registro/memoria. Si se usan direcciones/loads explícitos, ver §2.5.

### 2.2 Aritmética y Unarios

| Instrucción | Forma                      | Semántica                 |
|-------------|----------------------------|---------------------------|
| `ADD`       | `ADD a b t`                | `t = a + b`               |
| `SUB`       | `SUB a b t`                | `t = a - b`               |
| `MUL`       | `MUL a b t`                | `t = a * b`               |
| `DIV`       | `DIV a b t`                | `t = a / b`               |
| `NEG`       | `NEG a t`                  | `t = -a`                  |

### 2.3 Comparación

Dos estilos válidos (el proyecto puede usar 2.3.1 ó 2.3.2 — recomendamos 2.3.1 por uniformidad con `IFZ/IFNZ`).

#### 2.3.1 Comparación a booleans (en temp)

| Instrucción | Forma            | Semántica         |
|-------------|------------------|-------------------|
| `LT`        | `LT a b t`       | `t = (a < b)`     |
| `LE`        | `LE a b t`       | `t = (a <= b)`    |
| `GT`        | `GT a b t`       | `t = (a > b)`     |
| `GE`        | `GE a b t`       | `t = (a >= b)`    |
| `EQ`        | `EQ a b t`       | `t = (a == b)`    |
| `NE`        | `NE a b t`       | `t = (a != b)`    |

#### 2.3.2 Comparación con salto directo (opcional)

| Instrucción | Forma                | Semántica                             |
|-------------|----------------------|---------------------------------------|
| `IFLT`      | `IFLT a b L`         | `if (a < b) goto L`                   |
| `IFLE`      | `IFLE a b L`         | `if (a <= b) goto L`                  |
| `IFGT`      | `IFGT a b L`         | `if (a > b) goto L`                   |
| `IFGE`      | `IFGE a b L`         | `if (a >= b) goto L`                  |
| `IFEQ`      | `IFEQ a b L`         | `if (a == b) goto L`                  |
| `IFNE`      | `IFNE a b L`         | `if (a != b) goto L`                  |

### 2.4 Control de Flujo

| Instrucción | Forma            | Semántica                         |
|-------------|------------------|-----------------------------------|
| `LABEL`     | `LABEL Lx`       | Define etiqueta de salto          |
| `GOTO`      | `GOTO Lx`        | Salto incondicional               |
| `IFZ`       | `IFZ t Lx`       | `if (t == 0) goto Lx`             |
| `IFNZ`      | `IFNZ t Lx`      | `if (t != 0) goto Lx`             |

> **Short-circuit**: se logra combinando `IFZ/IFNZ` y etiquetas (ver §4).

### 2.5 Memoria (opcional según alcance del proyecto)

| Instrucción | Forma              | Semántica                                      |
|-------------|--------------------|------------------------------------------------|
| `NEW`       | `NEW size t`       | `t = alloc(size)`                              |
| `NEWARR`    | `NEWARR n t`       | `t = alloc(n * elem_size)`                     |
| `ALOAD`     | `ALOAD base idx t` | `t = *(base + idx*elem_size)`                  |
| `ASTORE`    | `ASTORE t base idx`| `*(base + idx*elem_size) = t`                  |
| `GETF`      | `GETF obj off t`   | `t = *(obj + off)`                             |
| `SETF`      | `SETF t obj off`   | `*(obj + off) = t`                             |

> En un *frontend* simple, `a[i]` y `obj.f` pueden descomponerse con estas instrucciones o resolverse en *backend*.

### 2.6 Funciones y Llamadas

| Instrucción | Forma                         | Semántica/Contrato                              |
|-------------|-------------------------------|--------------------------------------------------|
| `ENTER`     | `ENTER f, frame_size`         | Pro‐logo lógico (reserva AR si aplica)          |
| `LEAVE`     | `LEAVE f`                     | Epi‐logo lógico                                 |
| `PARAM`     | `PARAM x`                     | Empuja argumento `x` (ver orden abajo)          |
| `CALL`      | `CALL f, n_args, t_ret`       | Llama `f`; guarda retorno en `t_ret` (o `-` si void) |
| `RET`       | `RET x` / `RET`               | Retorna valor `x` (o vacío si `void`)           |

**Convención de llamada (del proyecto):**  
- **Orden de `PARAM`**: izquierda → derecha (eval y emite en ese orden).  
- **Retorno**: siempre capturado en un temporal `t_ret` provisto a `CALL`.  
- **Etiquetas de función**: `f_<nombre>` (usadas con `LABEL`).

### 2.7 I/O (si el lenguaje lo incluye)

| Instrucción | Forma          | Semántica             |
|-------------|----------------|-----------------------|
| `PRINT`     | `PRINT x`      | salida estandar       |

---

## 3. Reglas de Traducción (patrones)

### 3.1 Asignación
```
dst = E
---------------------------
t = eval(E)
ASSIGN t dst
```

### 3.2 Expresión binaria
```
E = E1 op E2
---------------------------
a = eval(E1)
b = eval(E2)
t = new_temp()
OP op a b t
free(a), free(b)     # si eran temporales
return t
```

### 3.3 Comparación a boolean
```
E = (a < b)
---------------------------
t1 = eval(a); t2 = eval(b)
t = new_temp()
LT t1 t2 t
free(t1), free(t2)
return t
```

### 3.4 If (sin else)
```
if (B) S
---------------------------
Lt = new_label(); Lend = new_label()
genBool(B, Lt, Lend)
LABEL Lt
gen(S)
LABEL Lend
```

### 3.5 If-Else
```
if (B) S1 else S2
---------------------------
Lt = new_label(); Lf = new_label(); Lend = new_label()
genBool(B, Lt, Lf)
LABEL Lt
gen(S1)
GOTO Lend
LABEL Lf
gen(S2)
LABEL Lend
```

### 3.6 While
```
while (B) S
---------------------------
Ltest = new_label(); Lbody = new_label(); Lend = new_label()
LABEL Ltest
genBool(B, Lbody, Lend)
LABEL Lbody
gen(S)
GOTO Ltest
LABEL Lend
```

### 3.7 Booleanos con Short-Circuit — `genBool(E, Lt, Lf)`

- `E = E1 && E2`  
  ```
  Lmid = new_label()
  genBool(E1, Lmid, Lf)
  LABEL Lmid
  genBool(E2, Lt, Lf)
  ```

- `E = E1 || E2`  
  ```
  Lmid = new_label()
  genBool(E1, Lt, Lmid)
  LABEL Lmid
  genBool(E2, Lt, Lf)
  ```

- `E = !E1`  
  ```
  genBool(E1, Lf, Lt)
  ```

- `E = (a < b)` (estilo 2.3.1)  
  ```
  t1 = eval(a); t2 = eval(b); t = new_temp()
  LT t1 t2 t
  IFNZ t Lt
  GOTO Lf
  ```

- `E = (a < b)` (estilo 2.3.2)  
  ```
  IFLT a b Lt
  GOTO Lf
  ```

### 3.8 Funciones

- **Definición**
  ```
  fun f(p1, p2, ...): T {
    body
    return x;
  }
  ---------------------------
  LABEL f_f
  ENTER f_f, frame_size
    ... TAC(body) ...
    RET x            # si no hay return explícito y T != void, definir política
  LEAVE f_f
  ```

- **Llamada**
  ```
  y = f(a, b)
  ---------------------------
  PARAM a
  PARAM b
  CALL f_f, 2, t0
  ASSIGN t0 y
  ```

### 3.9 `break` / `continue` (si aplica)
- Mantener pila (`loopStack`) con `{Ltest, Lend}` por bucle.
- `break` → `GOTO Lend`
- `continue` → `GOTO Ltest`

---

## 4. Registros de Activación (informativo)

- **Tabla de Símbolos** almacena por símbolo: `scope`, `type`, `size`, `offset`, `kind(var|param|func)`.
- Para **funciones**: `params[]` con offsets, `frame_size`, `func_label` (`f_<name>`).
- **Convención**: offsets de parámetros primero, luego locales; el *backend* decide base (`fp/sp`).

---

## 5. Invariantes y Errores

- No se emiten instrucciones con operandos no tipados o no declarados (el semántico lo impide).
- `CALL` a función `void` debe usar `t_ret = -` o ignorarse el destino.
- Si hay *runtime checks* (e.g. división entre cero, OOB arrays), pueden emitirse como llamadas a helpers o `IFZ` + salto a rutina de error.

---

## 6. Ejemplo End‑to‑End

Código:
```c
var a:int; var b:int; var c:int;
c = a + b * 2;

if (a < b || a == b) {
  c = 1;
} else {
  c = 0;
}

fun sum(x:int, y:int):int {
  return x + y;
}

var r:int;
r = sum(1,2);
```

TAC (posible):
```
# c = a + b * 2
MUL b #2 t0
ADD a t0 t1
ASSIGN t1 c

# if (a < b || a == b) { c = 1; } else { c = 0; }
L0:
LT a b t2
IFNZ t2 L1
EQ a b t3
IFNZ t3 L1
GOTO L2
LABEL L1
ASSIGN #1 c
GOTO L3
LABEL L2
ASSIGN #0 c
LABEL L3

# fun sum
LABEL f_sum
ENTER f_sum, 8          # ejemplo: 2 params x 4 bytes
ADD x y t4
RET t4
LEAVE f_sum

# r = sum(1,2);
PARAM #1
PARAM #2
CALL f_sum, 2, t5
ASSIGN t5 r
```

---

## 7. Checklist de Implementación

- [ ] Visitor del AST emite TAC para: `ASSIGN`, aritmética, comparaciones.
- [ ] `genBool` con etiquetas para `&&`/`||`/`!` y `IFZ/IFNZ`.
- [ ] `while`, `if`, `if-else`; (si aplica) `break`/`continue`.
- [ ] Funciones: `ENTER`/`LEAVE`, `PARAM`/`CALL`, `RET`.
- [ ] Tabla de símbolos extendida con offsets/labels/frame_size.
- [ ] Gestor de temporales con *reciclaje* (free list simple).
- [ ] Tests de éxito y fallo por categoría.
- [ ] IDE muestra/descarga TAC.

---

**Fin de la especificación.**
