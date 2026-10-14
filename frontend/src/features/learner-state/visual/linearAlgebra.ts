// Small dense linear-algebra helpers for head-pose estimation.
// Matrices are arrays of rows; sizes are tiny (at most 12 x 12).

export type Matrix = number[][];
export type Vector = number[];

export function transpose(a: Matrix): Matrix {
  return a[0].map((_, column) => a.map((row) => row[column]));
}

export function multiply(a: Matrix, b: Matrix): Matrix {
  return a.map((row) =>
    b[0].map((_, column) => row.reduce((sum, value, k) => sum + value * b[k][column], 0)),
  );
}

export function multiplyVector(a: Matrix, v: Vector): Vector {
  return a.map((row) => row.reduce((sum, value, k) => sum + value * v[k], 0));
}

export function determinant3(m: Matrix): number {
  return (
    m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
    m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
    m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
  );
}

export function frobeniusNorm(m: Matrix): number {
  return Math.sqrt(m.reduce((sum, row) => sum + row.reduce((s, v) => s + v * v, 0), 0));
}

/**
 * Eigen-decomposition of a symmetric matrix with the cyclic Jacobi method.
 * Returns eigenvalues and the matching eigenvectors as columns of `vectors`.
 */
export function symmetricEigen(input: Matrix): { values: Vector; vectors: Matrix } {
  const n = input.length;
  const a = input.map((row) => [...row]);
  const v: Matrix = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)),
  );

  for (let sweep = 0; sweep < 100; sweep++) {
    let offDiagonal = 0;
    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) offDiagonal += a[p][q] * a[p][q];
    }
    if (offDiagonal < 1e-30) break;

    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        if (Math.abs(a[p][q]) < 1e-300) continue;
        const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
        const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;

        for (let k = 0; k < n; k++) {
          const akp = a[k][p];
          const akq = a[k][q];
          a[k][p] = c * akp - s * akq;
          a[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = a[p][k];
          const aqk = a[q][k];
          a[p][k] = c * apk - s * aqk;
          a[q][k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = v[k][p];
          const vkq = v[k][q];
          v[k][p] = c * vkp - s * vkq;
          v[k][q] = s * vkp + c * vkq;
        }
      }
    }
  }

  return { values: a.map((row, i) => row[i]), vectors: v };
}

/** Nearest rotation matrix to `m` (the U·Vᵀ factor of its SVD). */
export function nearestRotation(m: Matrix): Matrix {
  const { values, vectors } = symmetricEigen(multiply(transpose(m), m));
  const inverseSqrt = vectors.map((row) => row.map((value, j) => value / Math.sqrt(values[j])));
  return multiply(m, multiply(inverseSqrt, transpose(vectors)));
}

/** Solve a small linear system with Gaussian elimination and partial pivoting. */
export function solve(a: Matrix, b: Vector): Vector {
  const n = b.length;
  const m = a.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++) {
      if (Math.abs(m[row][col]) > Math.abs(m[pivot][col])) pivot = row;
    }
    [m[col], m[pivot]] = [m[pivot], m[col]];
    for (let row = col + 1; row < n; row++) {
      const factor = m[row][col] / m[col][col];
      for (let k = col; k <= n; k++) m[row][k] -= factor * m[col][k];
    }
  }
  const x = new Array<number>(n).fill(0);
  for (let row = n - 1; row >= 0; row--) {
    let sum = m[row][n];
    for (let k = row + 1; k < n; k++) sum -= m[row][k] * x[k];
    x[row] = sum / m[row][row];
  }
  return x;
}
