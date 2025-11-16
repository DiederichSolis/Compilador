# 🚀 Compiscript – Compilador Educativo Completo

<div align="center">

![Compiscript](https://img.shields.io/badge/Language-TypeScript_Subset-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![ANTLR4](https://img.shields.io/badge/Parser-ANTLR4-orange)
![MIPS](https://img.shields.io/badge/Target-MIPS_Assembly-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

**Compilador educativo completo para Compiscript**, un subconjunto de TypeScript diseñado para enseñanza de compiladores.

[Características](#-características) • [Instalación](#-instalación) • [Uso](#-uso) • [Arquitectura](#-arquitectura) • [Documentación](#-documentación)

</div>

---

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Características](#-características)
- [Instalación](#-instalación)
- [Uso Rápido](#-uso-rápido)
- [Pipeline de Compilación](#-pipeline-de-compilación)
- [TAC (Three-Address Code)](#-tac-three-address-code)
- [Backend MIPS](#-backend-mips)
- [IDE Integrado](#-ide-integrado)
- [Testing](#-testing)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Ejemplos](#-ejemplos)
- [Recursos](#-recursos)
- [Licencia](#-licencia)

---

## 🎯 Descripción

Compiscript es un compilador educativo completo que implementa todas las fases de compilación para un lenguaje basado en TypeScript. Diseñado para propósitos académicos, incluye:

- **Frontend completo**: análisis léxico, sintáctico y semántico
- **Representación intermedia**: Three-Address Code (TAC) optimizado
- **Backend MIPS**: generación de código ensamblador funcional
- **IDE integrado**: ambiente visual con Streamlit para análisis y depuración

---

## ✨ Características

### 🔍 Frontend
- ✅ Gramática ANTLR4 completa (Python target)
- ✅ Construcción de AST (Abstract Syntax Tree)
- ✅ Análisis semántico exhaustivo con tabla de símbolos
- ✅ Sistema robusto de tipos
- ✅ Validaciones: `const`, scope, tipos, control de flujo
- ✅ Diagnósticos detallados con ubicación exacta

### ⚙️ Código Intermedio (TAC)
- ✅ Generación de TAC estructurado
- ✅ Optimización peephole segura
- ✅ Soporte completo para:
  - Expresiones aritméticas y lógicas
  - Corto-circuito (AND/OR)
  - Operador ternario
  - Arrays y objetos
  - Funciones y llamadas
  - Estructuras de control (`if`, `while`, `for`, `switch`)

### 🛠️ Backend MIPS
- ✅ Generación de código MIPS32
- ✅ Compatible con MARS y SPIM
- ✅ Gestión automática de stack y registros
- ✅ Convención de llamada estándar
- ✅ Soporte para strings y concatenación
- ✅ Prolog/epilog automático

### 🖥️ IDE Streamlit
- ✅ Editor con resaltado de sintaxis
- ✅ Visualización de AST (Graphviz)
- ✅ Listado de tokens
- ✅ Tabla de símbolos interactiva
- ✅ Diagnósticos en tiempo real
- ✅ Inspección de TAC generado
- ✅ Código MIPS listo para ejecutar

---

## 📦 Instalación

### Prerrequisitos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/DiederichSolis/Compilador.git
cd Compilador

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
# En macOS/Linux:
source .venv/bin/activate
# En Windows:
.venv\Scripts\activate

# 4. Instalar dependencias
pip install -r requirements.txt
```

### Dependencias principales
```
antlr4-python3-runtime==4.13.1
streamlit>=1.28.0
graphviz>=0.20.1
pytest>=7.4.0
```

---

## 🚀 Uso Rápido

### 1. Compilación via CLI

Compila un programa Compiscript y genera TAC + MIPS:

```bash
PYTHONPATH=src python -m src.cli program/program.cps
```

**Salida:**
- `program.tac` - Código intermedio TAC
- `program.s` - Código ensamblador MIPS
- Diagnósticos en consola
- AST y tabla de símbolos

### 2. IDE Integrado

Lanza el IDE visual:

```bash
streamlit run src/ide/app.py
```

Luego abre tu navegador en `http://localhost:8501`

**Características del IDE:**
- 📝 Editor con resaltado
- 🌳 Visualización de AST
- 🔤 Lista de tokens
- 📊 Tabla de símbolos
- ⚠️ Diagnósticos semánticos/sintácticos
- ⚙️ Código TAC generado
- 🖥️ Código MIPS listo para MARS

---

## 🔄 Pipeline de Compilación

```
┌─────────────┐
│  Código     │
│ Compiscript │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Lexer     │  (ANTLR4)
│   Parser    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     AST     │  (Abstract Syntax Tree)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Análisis   │  (Semantic Checker)
│  Semántico  │  • Tipos
│             │  • Scope
└──────┬──────┘  • Validaciones
       │
       ▼
┌─────────────┐
│  TAC Gen    │  (Three-Address Code)
│             │  • Optimización peephole
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Backend   │  (MIPS Generator)
│    MIPS     │  • Asignación registros
│             │  • Gestión stack
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   .s file   │  (Ejecutable en MARS/SPIM)
└─────────────┘
```

---

## 🧱 TAC (Three-Address Code)

### Sintaxis Básica

**Temporales y Variables:**
```
tN           # Temporal N
%x           # Variable local x
#5           # Literal entero
#"hello"     # Literal string
#null        # Null
```

**Operaciones:**
```
t1 = t2 + t3          # Aritmética
t4 = t5 < t6          # Comparación
t7 = -t8              # Unario
%x = t9               # Asignación
```

**Control de Flujo:**
```
label L1:             # Etiqueta
goto L1               # Salto incondicional
if t1 goto L2         # Condicional
ifFalse t1 goto L3    # Condicional negado
```

**Funciones:**
```
param t1              # Pasar parámetro
call foo, 2 -> t2     # Llamar con 2 params, resultado en t2
ret t3                # Retornar valor
```

**Arrays:**
```
newarr t1 -> t2       # Crear array de tamaño t1
aload %arr, t1 -> t2  # Leer arr[t1]
astore t1, %arr, t2   # arr[t2] = t1
```

**I/O:**
```
print t1              # Imprimir valor
```

### Ejemplo Completo

**Código Compiscript:**
```typescript
let x: number = 10;
let y: number = x + 5;
if (y > 12) {
    print(y);
}
```

**TAC Generado:**
```
%x = #10
t0 = %x + #5
%y = t0
t1 = %y > #12
ifFalse t1 goto L1
print %y
label L1:
```

📖 **Documentación completa:** [`docs/TAC_SPEC.md`](docs/TAC_SPEC.md)

---

## 🖥️ Backend MIPS

### Características

- **Convención de llamada:** Parámetros vía stack, retorno en `$v0`
- **Registros:** 
  - `$t0-$t7`: temporales (asignación rotativa)
  - `$s0-$s7`: guardados (preservados)
  - `$ra`: return address
  - `$sp`: stack pointer
- **Stack frames:** Prolog/epilog automático
- **Strings:** Almacenados en `.data`, soporte para concatenación

### Ejemplo de Traducción

**TAC:**
```
%x = #10
%y = #20
t0 = %x + %y
print t0
```

**MIPS Generado:**
```mips
.data
.text
.globl main

main:
    # Prolog
    addi $sp, $sp, -12
    sw $ra, 8($sp)
    
    # %x = #10
    li $t0, 10
    sw $t0, 0($sp)
    
    # %y = #20
    li $t1, 20
    sw $t1, 4($sp)
    
    # t0 = %x + %y
    lw $t2, 0($sp)
    lw $t3, 4($sp)
    add $t0, $t2, $t3
    
    # print t0
    move $a0, $t0
    li $v0, 1
    syscall
    
    # Epilog
    lw $ra, 8($sp)
    addi $sp, $sp, 12
    jr $ra
```

**Ejecución:** Cargar en MARS o SPIM y ejecutar

---

## 🧪 Testing

### Ejecutar Tests

```bash
pytest -q
```

**Salida esperada:**
```
18 passed in 2.34s
```

### Cobertura de Tests

#### ✅ Frontend & Semántica
- Expresiones aritméticas y lógicas
- Operadores unarios y binarios
- Tipos primitivos y compuestos
- Variables `const` vs `let`
- Scope y shadowing
- Clases y objetos (`this`, `new`)
- Arrays y acceso

#### ✅ Control de Flujo
- `if/else`
- `while`, `do-while`
- `for`, `foreach`
- `switch/case`
- `break/continue`
- `return`

#### ✅ Generación TAC
- Expresiones complejas
- Corto-circuito (`&&`, `||`)
- Operador ternario
- Llamadas a funciones
- Estructuras de control
- Arrays y objetos

#### ✅ Backend MIPS
- ⚠️ **Nota:** Los tests de MIPS se demuestran ejecutando código en MARS (ver video)

---

## 📁 Estructura del Proyecto

```
compiscript-compiler/
│
├── src/
│   ├── parsing/              # Frontend (ANTLR)
│   │   ├── Compiscript.g4    # Gramática ANTLR4
│   │   ├── lexer.py          # Wrapper del lexer
│   │   ├── parser.py         # Wrapper del parser
│   │   └── ast_builder.py    # Construcción de AST
│   │
│   ├── semantic/             # Análisis semántico
│   │   ├── checker.py        # Validador principal
│   │   ├── symbol_table.py   # Tabla de símbolos
│   │   ├── types.py          # Sistema de tipos
│   │   └── diagnostics.py    # Errores y warnings
│   │
│   ├── ir/                   # Representación intermedia
│   │   ├── tac/
│   │   │   ├── instructions.py   # ISA TAC
│   │   │   ├── emitter.py        # Constructor de TAC
│   │   │   └── program.py        # Programa TAC
│   │   └── backend/
│   │       ├── tac_generator.py  # AST → TAC
│   │       └── mips/
│   │           └── generator.py  # TAC → MIPS
│   │
│   ├── ide/                  # IDE Streamlit
│   │   └── app.py
│   │
│   └── cli.py                # Interfaz de línea de comandos
│
├── tests/                    # Suite de tests
│   ├── test_expressions.py
│   ├── test_control_flow.py
│   ├── test_semantic.py
│   └── test_tac.py
│
├── docs/                     # Documentación
│   ├── ARCHITECTURE.md       # Arquitectura general
│   ├── IDE_GUIDE.md          # Guía del IDE
│   ├── SEMANTIC_RULES.md     # Reglas semánticas
│   └── TAC_SPEC.md           # Especificación TAC
│
├── program/
│   └── program.cps           # Programa de ejemplo
│
├── requirements.txt          # Dependencias
├── README.md                 # Este archivo
└── LICENSE                   # MIT License
```

---

## 💡 Ejemplos

### Ejemplo 1: Factorial

**Compiscript:**
```typescript
function factorial(n: number): number {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

let result: number = factorial(5);
print(result);  // 120
```

### Ejemplo 2: Arrays

**Compiscript:**
```typescript
let numbers: number[] = [1, 2, 3, 4, 5];
let sum: number = 0;

for (let i: number = 0; i < 5; i = i + 1) {
    sum = sum + numbers[i];
}

print(sum);  // 15
```

### Ejemplo 3: Objetos

**Compiscript:**
```typescript
class Point {
    x: number;
    y: number;
    
    constructor(x: number, y: number) {
        this.x = x;
        this.y = y;
    }
    
    distance(): number {
        return this.x * this.x + this.y * this.y;
    }
}

let p: Point = new Point(3, 4);
print(p.distance());  // 25
```

---

## 📚 Recursos

### 📖 Documentación

| Documento | Descripción |
|-----------|-------------|
| [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitectura completa del compilador |
| [`IDE_GUIDE.md`](docs/IDE_GUIDE.md) | Guía de uso del IDE |
| [`SEMANTIC_RULES.md`](docs/SEMANTIC_RULES.md) | Reglas de validación semántica |
| [`TAC_SPEC.md`](docs/TAC_SPEC.md) | Especificación completa de TAC |

### 🎥 Demostración

- **Video de ejecución MIPS en MARS:** [🔗 Ver video](#) *(Próximamente)*
- **Repositorio GitHub:** [🔗 github.com/DiederichSolis/Compilador](https://github.com/DiederichSolis/Compilador)

### 🛠️ Herramientas Recomendadas

- **MARS:** [MIPS Assembler and Runtime Simulator](http://courses.missouristate.edu/kenvollmar/mars/)
- **SPIM:** [MIPS Simulator](http://spimsimulator.sourceforge.net/)
- **ANTLR4:** [Documentación oficial](https://www.antlr.org/)

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [`LICENSE`](LICENSE) para más detalles.

```
MIT License

Copyright (c) 2024 Andy Fuentes, Diederich Solis, Davis Roldán

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 👨‍💻 Autores

**Andy Fuentes** | **Diederich Solis** | **Davis Roldán**

- GitHub: [@DiederichSolis](https://github.com/DiederichSolis)
- Repositorio: [Compilador Compiscript](https://github.com/DiederichSolis/Compilador)

---

## 🙏 Agradecimientos

- Inspirado en el diseño de compiladores educativos
- ANTLR4 por el excelente framework de parsing
- Comunidad de Python y herramientas open source

---

<div align="center">

**⭐ Si este proyecto te fue útil, considera darle una estrella en GitHub ⭐**

[Reportar Bug](https://github.com/DiederichSolis/Compilador/issues) • [Solicitar Feature](https://github.com/DiederichSolis/Compilador/issues) • [Documentación](docs/)

</div>