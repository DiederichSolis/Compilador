function fib(n: integer): integer {
  if (n <= 1) {
    return n;
  }
  let a: integer = fib(n - 1);
  let b: integer = fib(n - 2);
  let r: integer = a + b;
  return r;
}

function fact(n: integer): integer {
  if (n <= 1) {
    return 1;
  }
  let sub: integer = fact(n - 1);
  let r: integer = n * sub;
  return r;
}

function pow(base: integer, exp: integer): integer {
  let res: integer = 1;
  let i: integer = 0;
  while (i < exp) {
    res = res * base;
    i = i + 1;
  }
  return res;
}

function sumArray(arr: integer[], n: integer): integer {
  let i: integer = 0;
  let s: integer = 0;
  while (i < n) {
    let v: integer = arr[i];
    s = s + v;
    i = i + 1;
  }
  return s;
}

function main() {
  // 1. probar fib, fact, pow
  let f5: integer = fib(5);    // 5
  let f7: integer = fib(7);    // 13
  let fact5: integer = fact(5); // 120
  let p: integer = pow(2, 8);   // 256

  print(f5);
  print(f7);
  print(fact5);
  print(p);

  // 2. array / sumArray
  let data = [3, 1, 4, 1, 5, 9];
  let total: integer = sumArray(data, 6);
  print(total);   // 23

  // 3. switch sobre (total / 5) -> 4
  let category: integer;
  let q: integer = total / 5;

  switch (q) {
    case 1:
      category = 10;
      break;
    case 2:
      category = 20;
      break;
    case 3:
      category = 30;
      break;
    case 4:
      category = 40;
      break;
    default:
      category = 99;
  }

  print(category);

  // 4. lógica combinada para validar todo
  if (f5 == 5 && f7 == 13 && fact5 == 120 && p == 256 && total == 23 && category == 40) {
    print(1);
  } else {
    print(0);
  }

  // 5. contar cuántos elementos son impares
  let i: integer = 0;
  let oddCount: integer = 0;

  while (i < 6) {
    let v: integer = data[i];
    if (v % 2 != 0) {
      oddCount = oddCount + 1;
    }
    i = i + 1;
  }

  print(oddCount);
}