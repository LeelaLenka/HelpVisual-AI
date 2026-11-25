import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

/** The public pages' 3D scene, drawn entirely in code: a geodesic sphere whose vertices are glowing
 *  "neurons" joined by thin links, a soft core, two orbital rings with travelling lights, and a field
 *  of slow particles. Palette: turquoise #178582, gold #BFA181, platinum #D1E8E2.
 *
 *  Cost control: about 1,300 points and one line mesh, device pixel ratio capped at 1.75, rendering
 *  paused while the canvas is off screen or the tab is hidden, and a single still frame when the
 *  reader prefers reduced motion. Loaded lazily (see SceneBackground) so app pages never load it. */

const TURQUOISE = new THREE.Color("#2fb3ad");
const GOLD = new THREE.Color("#bfa181");
const PLATINUM = new THREE.Color("#d1e8e2");

/** A round, soft-edged sprite so points render as glows instead of squares. */
function glowTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.7)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/** Deterministic pseudo-random numbers, so the scene looks the same on every visit. */
function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function Sphere({ sprite }: { sprite: THREE.Texture }) {
  const { nodes, nodeColors, links } = useMemo(() => {
    const ico = new THREE.IcosahedronGeometry(1.55, 3);
    const pos = ico.getAttribute("position");
    // Unique vertices (the geometry repeats them per face).
    const key = (x: number, y: number, z: number) => `${x.toFixed(3)},${y.toFixed(3)},${z.toFixed(3)}`;
    const unique = new Map<string, THREE.Vector3>();
    for (let i = 0; i < pos.count; i++) {
      const v = new THREE.Vector3().fromBufferAttribute(pos, i);
      unique.set(key(v.x, v.y, v.z), v);
    }
    const pts = [...unique.values()];
    const rand = seeded(7);
    const nodes = new Float32Array(pts.length * 3);
    const nodeColors = new Float32Array(pts.length * 3);
    pts.forEach((p, i) => {
      nodes.set([p.x, p.y, p.z], i * 3);
      const c = rand() < 0.12 ? GOLD : rand() < 0.5 ? TURQUOISE : PLATINUM;
      nodeColors.set([c.r, c.g, c.b], i * 3);
    });
    // Links: the sphere's edges, thinned so it reads as a network rather than a mesh.
    const edges = new THREE.EdgesGeometry(ico, 1);
    const ep = edges.getAttribute("position");
    const kept: number[] = [];
    for (let i = 0; i < ep.count; i += 2) {
      if (rand() < 0.55) {
        kept.push(ep.getX(i), ep.getY(i), ep.getZ(i), ep.getX(i + 1), ep.getY(i + 1), ep.getZ(i + 1));
      }
    }
    // A few long "synapses" through the inside.
    for (let k = 0; k < 18; k++) {
      const a = pts[Math.floor(rand() * pts.length)]!;
      const b = pts[Math.floor(rand() * pts.length)]!;
      kept.push(a.x, a.y, a.z, b.x * 0.2, b.y * 0.2, b.z * 0.2);
    }
    ico.dispose();
    edges.dispose();
    return { nodes, nodeColors, links: new Float32Array(kept) };
  }, []);

  const group = useRef<THREE.Group>(null);
  const core = useRef<THREE.Sprite>(null);
  const { pointer } = useThree();

  useFrame((state, delta) => {
    const g = group.current;
    if (!g) return;
    g.rotation.y += delta * 0.08;
    // Gentle parallax toward the pointer.
    g.rotation.x += (pointer.y * 0.25 - g.rotation.x) * 0.03;
    g.position.x += (pointer.x * 0.12 - g.position.x) * 0.03;
    if (core.current) {
      const s = 2.1 + Math.sin(state.clock.elapsedTime * 0.9) * 0.12;
      core.current.scale.set(s, s, 1);
    }
  });

  return (
    <group ref={group}>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[links, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color={TURQUOISE} transparent opacity={0.28} blending={THREE.AdditiveBlending} depthWrite={false} />
      </lineSegments>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[nodes, 3]} />
          <bufferAttribute attach="attributes-color" args={[nodeColors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.075} map={sprite} vertexColors transparent depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
      <sprite ref={core}>
        <spriteMaterial map={sprite} color="#178582" transparent opacity={0.35} depthWrite={false} blending={THREE.AdditiveBlending} />
      </sprite>
    </group>
  );
}

function Orbit({ radius, tilt, speed, color, sprite }: {
  radius: number; tilt: [number, number]; speed: number; color: THREE.Color; sprite: THREE.Texture;
}) {
  const ring = useMemo(() => {
    const pts = new THREE.EllipseCurve(0, 0, radius, radius, 0, Math.PI * 2).getPoints(160);
    return new THREE.BufferGeometry().setFromPoints(pts.map((p) => new THREE.Vector3(p.x, p.y, 0)));
  }, [radius]);
  const light = useRef<THREE.Sprite>(null);
  const group = useRef<THREE.Group>(null);
  useFrame((state) => {
    const t = state.clock.elapsedTime * speed;
    light.current?.position.set(Math.cos(t) * radius, Math.sin(t) * radius, 0);
    if (group.current) group.current.rotation.z += speed * 0.002;
  });
  return (
    <group rotation={[tilt[0], tilt[1], 0]}>
      <group ref={group}>
        <lineLoop geometry={ring}>
          <lineBasicMaterial color={color} transparent opacity={0.35} blending={THREE.AdditiveBlending} depthWrite={false} />
        </lineLoop>
        <sprite ref={light} scale={[0.32, 0.32, 1]}>
          <spriteMaterial map={sprite} color={color} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
        </sprite>
      </group>
    </group>
  );
}

function Particles({ sprite }: { sprite: THREE.Texture }) {
  const positions = useMemo(() => {
    const rand = seeded(42);
    const n = 900;
    const arr = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 2.4 + rand() * 5;
      const th = rand() * Math.PI * 2;
      const ph = Math.acos(2 * rand() - 1);
      arr.set([r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th) * 0.6, r * Math.cos(ph)], i * 3);
    }
    return arr;
  }, []);
  const ref = useRef<THREE.Points>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y -= delta * 0.015;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.035} map={sprite} color={PLATINUM} transparent opacity={0.55} depthWrite={false} blending={THREE.AdditiveBlending} />
    </points>
  );
}

export default function NeuralSphere({ offsetX = 0, className = "" }: { offsetX?: number; className?: string }) {
  const sprite = useMemo(() => glowTexture(), []);
  const wrap = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const reduce = useMemo(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(Boolean(entry?.isIntersecting) && !document.hidden));
    io.observe(el);
    const onVis = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  useEffect(() => () => sprite.dispose(), [sprite]);

  return (
    <div ref={wrap} className={`absolute inset-0 ${className}`} aria-hidden="true">
      <Canvas
        dpr={[1, 1.75]}
        camera={{ position: [0, 0, 6.2], fov: 45 }}
        frameloop={reduce ? "demand" : visible ? "always" : "never"}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      >
        <group position={[offsetX, 0, 0]}>
          <Sphere sprite={sprite} />
          <Orbit radius={2.35} tilt={[1.2, 0.3]} speed={0.35} color={GOLD} sprite={sprite} />
          <Orbit radius={2.8} tilt={[1.45, -0.5]} speed={-0.22} color={PLATINUM} sprite={sprite} />
          <Particles sprite={sprite} />
        </group>
      </Canvas>
    </div>
  );
}
