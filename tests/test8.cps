function main() {
  let arr = [10, 20, 30];
  let s: integer = 0;
  let i: integer = 0;

  while (i < 3) {
    let temp: integer = arr[i];
    s = s + temp;
    i = i + 1;
  }

  print(s);
}