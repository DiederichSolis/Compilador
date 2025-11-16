function main() {
  let nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  let i: integer = 0;
  let sum: integer = 0;
  let min: integer = 9999;
  let max: integer = -9999;

  while (i < 10) {
    let v: integer = nums[i];
    sum = sum + v;
    if (v < min) {
      min = v;
    }
    if (v > max) {
      max = v;
    }
    i = i + 1;
  }

  let avg: integer = sum / 10;

  // imprime sum, min, max, avg
  print(sum);
  print(min);
  print(max);
  print(avg);

  // pruebas lógicas combinadas
  if (sum == 55 && min == 1 && max == 10 && avg == 5) {
    print(1);
  } else {
    print(0);
  }

  // for + operador ternario
  let res: integer = 0;
  for (let j: integer = 0; j < 6; j = j + 1) {
    let val: integer = j < 3 ? 1 : 2;
    res = res + val;
  }

  print(res);
}