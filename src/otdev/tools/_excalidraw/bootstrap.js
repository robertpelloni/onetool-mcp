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
    zoom:   (level) => level === 0
              ? api.scrollToContent()
              : api.setAppState({ zoom: { value: level } }),
    _raw:   api,
  };
  return true;
}
