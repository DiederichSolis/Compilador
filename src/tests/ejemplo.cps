// === Programa de smoke-test para TAC ===

const N: integer = 5;

function cuadrado(x: integer): integer {
  return x * x;
}

function max(a: integer, b: integer): integer {
  if (a > b) {
    return a;
  } else {
    return b;
  }
}

function main(): void {
  // ints
  let i: integer = 0;
  let acc: integer = 0;

  // array de enteros
  let arr: integer[] = [1, 2, 3, 4, 5];

  // while + indexación + llamada a función
  while (i < N) {
    acc = acc + cuadrado(arr[i]);
    i = i + 1;
  }

  // for con init; cond; step
  for (let j: integer = 0; j < 3; j = j + 1) {
    acc = acc + j;
  }

  // foreach (el iterador se declara implícitamente en tu checker)
  foreach (x in arr) {
    acc = acc + x;
  }

  // lógico + comparación
  let ok: boolean = (acc > 0) && true;
  if (ok) {
    print("acc = " + acc);
  } else {
    print("acc = 0");
  }

  // floats simples (si tu TAC aún no soporta float, puedes comentar esto)
  let f: float = 3.0;
  let g: float = 2.0;
  let h: float = f / g;   // no se usa, pero fuerza generación de expr float

  // pequeña prueba de max()
  let m: integer = max(10, 7);
  acc = acc + m;

  print("final = " + acc);
}
