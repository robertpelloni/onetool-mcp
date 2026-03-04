// Bootstrap script — injected once when excalidraw.com first loads.
() => {
  const root = document.getElementById('root');
  const rk = Object.keys(root).find(k => k.startsWith('__reactContainer'));
  function findApi(fiber, depth) {
    if (!fiber || depth > 30) return null;
    const sn = fiber.stateNode;
    if (sn && typeof sn.getSceneElements === 'function') return sn;
    return findApi(fiber.child, depth + 1) || findApi(fiber.sibling, depth);
  }
  const api = findApi(root[rk], 0);
  if (!api) return false;

  // Element cache — required because updateScene() is a full replacement
  window.__drawElements = {};

  window.__drawApi = {
    backend: 'excalidraw',
    clear:  () => { window.__drawElements = {}; api.resetScene(); },
    read:   () => api.getSceneElements(),
    upsert: (el) => {
      window.__drawElements[el.id] = el;
      api.updateScene({ elements: Object.values(window.__drawElements) });
    },
    erase:  (id) => {
      delete window.__drawElements[id];
      api.updateScene({ elements: Object.values(window.__drawElements) });
    },
    update: (elements) => {
      window.__drawElements = Object.fromEntries(elements.map(e => [e.id, e]));
      api.updateScene({ elements });
    },
    scroll: (dx, dy) => api.setAppState(s => ({
              scrollX: s.scrollX + dx, scrollY: s.scrollY + dy })),
    zoom:   (level) => {
      if (level !== 0) {
        api.setAppState({ zoom: { value: level } });
        return;
      }
      // Fit-to-content: compute bounds from our element cache (always authoritative
      // after updateScene, unlike getSceneElements which may lag for explicit-position draws).
      const els = Object.values(window.__drawElements || {})
        .filter(e => !e.isDeleted && e.type !== 'text');
      if (!els.length) { api.scrollToContent(); return; }
      const margin = 60;
      const minX = Math.min(...els.map(e => e.x));
      const minY = Math.min(...els.map(e => e.y));
      const maxX = Math.max(...els.map(e => e.x + (e.width  || 0)));
      const maxY = Math.max(...els.map(e => e.y + (e.height || 0)));
      const sceneW = maxX - minX + margin * 2;
      const sceneH = maxY - minY + margin * 2;
      const vpW = window.innerWidth  || 1280;
      const vpH = window.innerHeight || 720;
      const zoomVal = Math.min(1, vpW / sceneW, vpH / sceneH);
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      api.setAppState({
        scrollX: vpW / 2 - cx * zoomVal,
        scrollY: vpH / 2 - cy * zoomVal,
        zoom: { value: zoomVal },
      });
    },
    _raw:   api,
  };
  return true;
}
