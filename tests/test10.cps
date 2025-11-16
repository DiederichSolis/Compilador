class Counter {
  let value: integer;

  function constructor(start: integer) {
    this.value = start;
  }

  function inc(): integer {
    this.value = this.value + 1;
    return this.value;
  }
}

function main() {
  let c: Counter = new Counter(5);
  let x: integer = c.inc();
  print(x);
}