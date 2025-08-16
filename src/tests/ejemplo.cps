// Variable mal tipada: espera Int pero le doy String
let x : integer = "hola";

// Const mal tipada: espera String pero le doy número
const y : string = 42;

// Uso de variable no declarada
z = 5;

// Función dice que retorna Int pero retorna String
function suma(a: integer, b: integer) : integer {
    return "oops";
}

// Función dice que no retorna nada pero sí retorna valor
function foo() : void {
    return 10;
}

// break fuera de un bucle
break;

// continue fuera de un bucle
continue;

class Persona {
    let edad : integer;

    // Método con return inválido: dice void pero retorna valor
    function getEdad() : void {
        return edad;
    }

    // Acceso a miembro inexistente
    function prueba() {
        this.nombre;   // 'nombre' no está definido en la clase
    }
}
