// Port of `estimate_head_pose` from the visual training notebook
// (research/learner-state/notebooks/mindbridge-visual-model-01.ipynb), which uses
// cv2.solvePnP(SOLVEPNP_ITERATIVE) + cv2.Rodrigues + cv2.RQDecomp3x3.
// Tests compare this file against values produced by OpenCV itself.

import {
  determinant3,
  frobeniusNorm,
  type Matrix,
  multiply,
  multiplyVector,
  nearestRotation,
  solve,
  symmetricEigen,
  transpose,
  type Vector,
} from "./linearAlgebra";

export type Landmark = { x: number; y: number };

export type HeadPose = { pitch: number; yaw: number; roll: number };

/** Landmark indices used for head pose: nose tip, chin, eye outer corners, mouth corners. */
export const HEAD_POSE_LANDMARKS = [1, 152, 33, 263, 61, 291] as const;

/** Generic 3D face model used in the notebook, in the same order as HEAD_POSE_LANDMARKS. */
const MODEL_POINTS: Vector[] = [
  [0.0, 0.0, 0.0],
  [0.0, -330.0, -65.0],
  [-225.0, 170.0, -135.0],
  [225.0, 170.0, -135.0],
  [-150.0, -150.0, -125.0],
  [150.0, -150.0, -125.0],
];

const MAX_REFINEMENT_ITERATIONS = 200;

type Camera = { focal: number; cx: number; cy: number };

function rodriguesToMatrix(r: Vector): Matrix {
  const theta = Math.hypot(r[0], r[1], r[2]);
  if (theta < 1e-15) return [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const [x, y, z] = r.map((value) => value / theta);
  const c = Math.cos(theta);
  const s = Math.sin(theta);
  const k = 1 - c;
  return [
    [c + x * x * k, x * y * k - z * s, x * z * k + y * s],
    [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
    [z * x * k - y * s, z * y * k + x * s, c + z * z * k],
  ];
}

function matrixToRodrigues(m: Matrix): Vector {
  const cosTheta = Math.min(1, Math.max(-1, (m[0][0] + m[1][1] + m[2][2] - 1) / 2));
  const theta = Math.acos(cosTheta);
  if (theta < 1e-12) return [0, 0, 0];

  if (Math.PI - theta < 1e-6) {
    // Near 180°: recover the axis from the symmetric part.
    const axis = [
      Math.sqrt(Math.max(0, (m[0][0] + 1) / 2)),
      Math.sqrt(Math.max(0, (m[1][1] + 1) / 2)),
      Math.sqrt(Math.max(0, (m[2][2] + 1) / 2)),
    ];
    if (m[0][1] < 0) axis[1] = -axis[1];
    if (m[0][2] < 0) axis[2] = -axis[2];
    if (axis[0] === 0 && m[1][2] < 0) axis[2] = -axis[2];
    return axis.map((value) => value * theta);
  }

  const factor = theta / (2 * Math.sin(theta));
  return [
    (m[2][1] - m[1][2]) * factor,
    (m[0][2] - m[2][0]) * factor,
    (m[1][0] - m[0][1]) * factor,
  ];
}

function project(point: Vector, rotation: Matrix, translation: Vector, camera: Camera): Vector {
  const c = multiplyVector(rotation, point).map((value, i) => value + translation[i]);
  return [camera.focal * (c[0] / c[2]) + camera.cx, camera.focal * (c[1] / c[2]) + camera.cy];
}

/** Initial pose from the Direct Linear Transform, as in OpenCV for non-planar points. */
function initialPose(imagePoints: Vector[], camera: Camera): { r: Vector; t: Vector } {
  const normalized = imagePoints.map(([u, v]) => [
    (u - camera.cx) / camera.focal,
    (v - camera.cy) / camera.focal,
  ]);

  const rows: Matrix = [];
  MODEL_POINTS.forEach(([X, Y, Z], i) => {
    const x = -normalized[i][0];
    const y = -normalized[i][1];
    rows.push([X, Y, Z, 1, 0, 0, 0, 0, x * X, x * Y, x * Z, x]);
    rows.push([0, 0, 0, 0, X, Y, Z, 1, y * X, y * Y, y * Z, y]);
  });

  const { values, vectors } = symmetricEigen(multiply(transpose(rows), rows));
  const smallest = values.indexOf(Math.min(...values));
  let p = vectors.map((row) => row[smallest]);

  let rr: Matrix = [p.slice(0, 3), p.slice(4, 7), p.slice(8, 11)];
  if (determinant3(rr) < 0) {
    p = p.map((value) => -value);
    rr = [p.slice(0, 3), p.slice(4, 7), p.slice(8, 11)];
  }
  const scale = frobeniusNorm(rr);
  const rotation = nearestRotation(rr);
  const factor = frobeniusNorm(rotation) / scale;
  return { r: matrixToRodrigues(rotation), t: [p[3], p[7], p[11]].map((v) => v * factor) };
}

function residuals(params: Vector, imagePoints: Vector[], camera: Camera): Vector {
  const rotation = rodriguesToMatrix(params.slice(0, 3));
  const translation = params.slice(3, 6);
  return MODEL_POINTS.flatMap((point, i) => {
    const [u, v] = project(point, rotation, translation, camera);
    return [u - imagePoints[i][0], v - imagePoints[i][1]];
  });
}

/** Levenberg–Marquardt refinement of the reprojection error in pixels. */
function refine(start: Vector, imagePoints: Vector[], camera: Camera): Vector | null {
  let params = [...start];
  let error = residuals(params, imagePoints, camera);
  let cost = error.reduce((s, e) => s + e * e, 0);
  let lambda = 1e-3;

  for (let iteration = 0; iteration < MAX_REFINEMENT_ITERATIONS; iteration++) {
    const jacobian: Matrix = error.map(() => new Array<number>(6).fill(0));
    for (let j = 0; j < 6; j++) {
      const step = 1e-7 * Math.max(1, Math.abs(params[j]));
      const plus = [...params];
      const minus = [...params];
      plus[j] += step;
      minus[j] -= step;
      const ePlus = residuals(plus, imagePoints, camera);
      const eMinus = residuals(minus, imagePoints, camera);
      for (let i = 0; i < error.length; i++) jacobian[i][j] = (ePlus[i] - eMinus[i]) / (2 * step);
    }

    const jt = transpose(jacobian);
    const jtj = multiply(jt, jacobian);
    const gradient = multiplyVector(jt, error);

    let improved = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      const damped = jtj.map((row, i) => row.map((v, j) => (i === j ? v * (1 + lambda) : v)));
      const delta = solve(
        damped,
        gradient.map((g) => -g),
      );
      if (delta.some((d) => !Number.isFinite(d))) return null;
      const candidate = params.map((v, i) => v + delta[i]);
      const candidateError = residuals(candidate, imagePoints, camera);
      const candidateCost = candidateError.reduce((s, e) => s + e * e, 0);

      if (candidateCost <= cost) {
        const change = Math.hypot(...delta);
        params = candidate;
        error = candidateError;
        const previous = cost;
        cost = candidateCost;
        lambda = Math.max(lambda / 10, 1e-12);
        improved = true;
        if (change < 1e-12 || previous - cost <= 1e-15 * Math.max(1, previous)) return params;
        break;
      }
      lambda *= 10;
    }
    if (!improved) return params;
  }
  return params;
}

/** cv2.RQDecomp3x3 Euler angles (degrees) of a rotation matrix. */
export function rqDecompositionAngles(input: Matrix): HeadPose {
  const M = input.map((row) => [...row]);

  let s = M[2][1];
  let c = M[2][2];
  let z = 1 / Math.sqrt(c * c + s * s + Number.EPSILON);
  c *= z;
  s *= z;
  const qx: Matrix = [
    [1, 0, 0],
    [0, c, s],
    [0, -s, c],
  ];
  let R = multiply(M, qx);
  R[2][1] = 0;

  s = -R[2][0];
  c = R[2][2];
  z = 1 / Math.sqrt(c * c + s * s + Number.EPSILON);
  c *= z;
  s *= z;
  const qy: Matrix = [
    [c, 0, -s],
    [0, 1, 0],
    [s, 0, c],
  ];
  let N = multiply(R, qy);
  N[2][0] = 0;

  s = N[1][0];
  c = N[1][1];
  z = 1 / Math.sqrt(c * c + s * s + Number.EPSILON);
  c *= z;
  s *= z;
  const qz: Matrix = [
    [c, s, 0],
    [-s, c, 0],
    [0, 0, 1],
  ];
  R = multiply(N, qz);
  R[1][0] = 0;
  N = R;

  // Resolve the decomposition ambiguity exactly as OpenCV does.
  if (N[0][0] < 0) {
    if (N[1][1] < 0) {
      qz[0][0] *= -1;
      qz[0][1] *= -1;
      qz[1][0] *= -1;
      qz[1][1] *= -1;
    } else {
      qz[0][0] *= -1;
      qz[0][1] *= -1;
      qz[2][0] *= -1;
      qz[2][1] *= -1;
    }
  } else if (N[1][1] < 0) {
    qz[1][0] *= -1;
    qz[1][1] *= -1;
    qz[2][0] *= -1;
    qz[2][1] *= -1;
  }

  const degrees = 180 / Math.PI;
  const clamp = (v: number) => Math.min(1, Math.max(-1, v));
  return {
    pitch: Math.acos(clamp(qx[1][1])) * (qx[1][2] >= 0 ? 1 : -1) * degrees,
    yaw: Math.acos(clamp(qy[0][0])) * (qy[2][0] >= 0 ? 1 : -1) * degrees,
    roll: Math.acos(clamp(qz[0][0])) * (qz[0][1] >= 0 ? 1 : -1) * degrees,
  };
}

/**
 * Raw head pose (before the notebook's pitch/roll normalisation) from MediaPipe
 * normalised landmarks of a `width` x `height` frame. Returns null if it cannot be solved.
 */
export function estimateHeadPose(
  landmarks: readonly Landmark[],
  width: number,
  height: number,
): HeadPose | null {
  const camera: Camera = { focal: width, cx: width / 2, cy: height / 2 };
  const imagePoints = HEAD_POSE_LANDMARKS.map((index) => [
    landmarks[index].x * width,
    landmarks[index].y * height,
  ]);

  const start = initialPose(imagePoints, camera);
  const refined = refine([...start.r, ...start.t], imagePoints, camera);
  if (!refined || refined.some((v) => !Number.isFinite(v))) return null;

  return rqDecompositionAngles(rodriguesToMatrix(refined.slice(0, 3)));
}
