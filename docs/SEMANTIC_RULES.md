# Compiscript — Reglas Semánticas

Este documento resume las validaciones implementadas por `src/semantic/checker.py` y los tipos/símbolos definidos en `types.py`, `symbol_table.py` y `symbols.py`.

## 1. Ámbitos y símbolos

- **Ámbitos** (`Scope.kind`): `GLOBAL`, `FUNCTION`, `CLASS`, `BLOCK` (pila).  
- **Búsqueda**: `lookup` recorre desde el *scope* actual hacia los padres.  
- **Símbolos**:
  - `VariableSymbol` (`is_const` para prohibir reasignación).
  - `FunctionSymbol` (lista de `ParamSymbol`, tipo de retorno).
  - `ClassSymbol` (campos, métodos y `parent` para herencia básica).
- **Sombreado**: permitido en *scopes* anidados; redefinir en el mismo *scope* es error.

## 2. Tipos

- **Primitivos**: `Int`, `Float`, `Bool`, `String`, `Null`, `Void`.
- **Compuestos**: `Array<T>`, `Class(name, members)`.
- **Compatibilidad** (subconjunto):
  - `Int` ↔ `Float`: promociones numéricas en binarios aritméticos.
  - `Null` es compatible con referencias (`Class`, `Array`); no con primitivos.
  - `Void` solo en `return` de funciones `: Void` o como tipo de función.

## 3. Declaraciones

- **`let`/`const`**: requieren inicializador si hay anotación de tipo estricto.  
  - `const` no puede ser reasignado.  
- **Funciones**:
  - Declaración previa: las funciones se **registran** antes de visitar cuerpos.
  - Chequeo de **aridad** y **tipos de parámetros** en llamadas.
  - **Return**:
    - Toda ruta de salida en funciones con retorno no-`Void` debe retornar un valor del tipo declarado.
    - En `: Void` se permite `return;` o ausencia de `return`.

## 4. Expresiones y operadores

- **Aritméticos** (`+ - * / %`):
  - Operan sobre `Int`/`Float` (promoción a `Float` si hay mezcla).
  - `+` con `String` permite concatenación (`String + (Int|Float|Bool|String)` → `String`).
- **Relacionales** (`< <= > >=`): requieren comparables (`Int`/`Float`/`String` lexicográfico).
- **Igualdad** (`== !=`): comparables con el mismo dominio o `Null` con referencias.
- **Lógicos** (`&& || !`): operandos `Bool`; resultado `Bool`.
- **Indexación** (`a[i]`) sobre `Array<T>` → tipo `T`.
- **Acceso a campo** (`obj.x`) sobre `ClassType` según `members`.

## 5. Asignaciones

- Lado izquierdo debe ser **lvalue** válido: identificador, `obj.campo`, `arr[i]`.
- Tipos del RHS deben ser **asignables** al tipo del LHS (reglas de compatibilidad).  
- Asignar a `const` es **error**.

## 6. Control de flujo

- **`if/else`**: condición `Bool`.
- **`while` / `do-while` / `for`**: condición `Bool`.
- **`break`/`continue`**: solo válidos dentro de bucles; gestionados con pila de etiquetas.
- Detección básica de *dead code* mediante marca `TERMINATED` tras `return`/`break`/`continue`/`goto` equivalentes.

## 7. Clases y objetos (básico)

- **Declaración**: `class C { let x: Int; func m(a: Int): Int { ... } }`
- **Instanciación**: `new C()` produce `ClassType("C")` y habilita acceso `obj.x`, `obj.m(...)`.
- **Herencia**: campo `parent` (si se usa) debe ser clase conocida. Accesos se resuelven ascendiendo.

## 8. Arreglos

- Creación `new T[n]` → `Array<T>`; `n` debe ser `Int`.
- `a[i]` lectura/escritura valida límites si la info está disponible (best-effort).
- Las longitudes asociadas a variables se rastrean en `TacGen` (`_arr_len`).

## 9. Funciones integradas

- **`print(x)`**: acepta cualquier tipo; se valida aridad=1.

## 10. Diagnósticos (ejemplos)

- Uso de variable no declarada.
- Doble declaración en el mismo ámbito.
- Llamada a función con aridad/tipos incompatibles.
- Retorno faltante o tipo incorrecto.
- Asignación a `const`.
- Tipos incompatibles en binarios/lógicos/relacionales.
