class Punto {
    var x: float;
    var y: float;

    function mover(dx: float, dy: float): void {
        this.x = this.x + dx;
        this.y = this.y + dy;
    }
}

class Punto3D : Punto {
    var z: float;

    function mover(dx: float, dy: float, dz: float): void {
        this.x = this.x + dx;
        this.y = this.y + dy;
        this.z = this.z + dz;
    }
}

function distancia(a: Punto, b: Punto): float {
    let dx: float = a.x - b.x;   // float - float
    let dy: float = a.y - b.y;
    return dx * dx + dy * dy;
}

function main(): void {
    let p1: Punto = new Punto();
    let p2: Punto = new Punto();

    p1.x = 3.0;   // float literal
    p1.y = 4.0;
    p2.x = 0.0;     // int literal (se promueve en operaciones)
    p2.y = 0.0;

    const pi: float = 3.14159;

    let d: float = distancia(p1, p2);

    // array homogéneo de float
    let lista: float[] = [1.0, 2.0, 3.0];
    foreach (n in lista) {
        print(n);
    }
}