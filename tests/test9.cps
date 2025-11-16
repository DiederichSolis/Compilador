function fact(n: integer): integer {
  if (n <= 1) {
    return 1;
  }

  let sub: integer = fact(n - 1);
  let res: integer = n * sub;
  return res;
}

function main() {
  let r: integer = fact(5);
  print(r);
}