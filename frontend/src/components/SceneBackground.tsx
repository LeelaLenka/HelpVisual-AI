import { Component, lazy, Suspense, useMemo, type ReactNode } from "react";

const NeuralSphere = lazy(() => import("./NeuralSphere"));

function hasWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/** If the 3D scene fails (old GPU, lost context), the gradient below stays and the page still works. */
class Guard extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/** Dark brand backdrop with the 3D neural sphere on top. The gradient is drawn first, so the
 *  surface looks finished before three.js has loaded and on devices without WebGL. */
export default function SceneBackground({ offsetX = 0 }: { offsetX?: number }) {
  const webgl = useMemo(hasWebGL, []);
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden bg-navy">
      <div className="absolute inset-0 bg-[radial-gradient(45%_55%_at_70%_45%,rgba(23,133,130,0.28),transparent_70%),radial-gradient(30%_35%_at_15%_85%,rgba(191,161,129,0.10),transparent_70%)]" />
      {webgl && (
        <Guard>
          <Suspense fallback={null}>
            <div className="pointer-events-auto absolute inset-0">
              <NeuralSphere offsetX={offsetX} />
            </div>
          </Suspense>
        </Guard>
      )}
      <div className="absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_120%,rgba(10,24,40,0.9),transparent_60%)]" />
    </div>
  );
}
