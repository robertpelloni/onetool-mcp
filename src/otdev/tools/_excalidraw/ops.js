() => {
  // Internal drawing helper — not exposed as tools.
  // Called from Python via browser_evaluate after bootstrap.js has run.

  window._batch_draw = (shapes, edges, frames) => {
    const now = Date.now();
    const rng = () => Math.floor(Math.random() * 9999999);

    // One live read for positions of elements the user may have moved
    const liveMap = {};
    for (const el of window.__drawApi.read()) {
      liveMap[el.id] = el;
    }

    // Phase 1: shapes
    for (const s of shapes) {
      const { id, label, x, y, w, h, shape, styleProps } = s;
      const textId   = id + '-text';
      const fontSize = styleProps.fontSize || 16;
      const lineCount = label.split('\n').length;
      const textH    = lineCount * fontSize * 1.25;

      window.__drawElements[id] = {
        id, type: shape, x, y, width: w, height: h,
        strokeColor:     styleProps.strokeColor     || '#1e1e1e',
        backgroundColor: styleProps.backgroundColor || '#ffffff',
        strokeWidth:     styleProps.strokeWidth     || 2,
        strokeStyle:     styleProps.strokeStyle     || 'solid',
        roughness:       styleProps.roughness       ?? 1,
        opacity:         styleProps.opacity         ?? 100,
        roundness:       'roundness' in styleProps ? styleProps.roundness : { type: 3 },
        fillStyle: 'solid', angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [{ type: 'text', id: textId }],
      };
      window.__drawElements[textId] = {
        id: textId, type: 'text',
        x: x + 8, y: y + (h - textH) / 2, width: w - 16, height: textH,
        text: label,
        fontSize,
        fontFamily:    styleProps.fontFamily    || 1,
        textAlign:     styleProps.textAlign     || 'center',
        verticalAlign: styleProps.verticalAlign || 'middle',
        strokeColor:   styleProps.color         || '#1e1e1e',
        backgroundColor: 'transparent',
        fillStyle: 'solid', strokeWidth: 1, roughness: 1,
        opacity: 100, angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [], containerId: id, lineHeight: 1.25, baseline: 18,
        originalText: label, autoResize: true,
      };
    }

    // Phase 2: edges
    const gap = 8;
    // Pre-compute parallel edge groups for y-offset separation
    const pairCount = {};
    const pairIndex = {};
    for (const e of edges) {
      const key = e.srcId + '|' + e.dstId;
      pairCount[key] = (pairCount[key] || 0) + 1;
    }
    const pairSeen = {};
    for (const e of edges) {
      const key = e.srcId + '|' + e.dstId;
      pairIndex[e.id] = pairSeen[key] || 0;
      pairSeen[key] = (pairSeen[key] || 0) + 1;
    }
    const parallelSpacing = 20;
    for (const e of edges) {
      const { id, srcId, dstId, label, startArrowhead, endArrowhead, strokeStyle } = e;
      // Prefer live position (user-moved), fall back to freshly placed
      const src = liveMap[srcId] || window.__drawElements[srcId];
      const dst = liveMap[dstId] || window.__drawElements[dstId];
      if (!src || !dst) continue;

      const pairKey = srcId + '|' + dstId;
      const n = pairCount[pairKey] || 1;
      const idx = pairIndex[id] || 0;
      const yOff = n > 1 ? (idx - (n - 1) / 2) * parallelSpacing : 0;

      const sx = src.x + src.width  + gap,  sy = src.y + src.height / 2 + yOff;
      const ex = dst.x              - gap,  ey = dst.y + dst.height  / 2 + yOff;

      // Back-fill boundElements on src and dst in cache
      const srcEl = window.__drawElements[srcId] || src;
      const dstEl = window.__drawElements[dstId] || dst;
      window.__drawElements[srcId] = { ...srcEl,
        boundElements: [...(srcEl.boundElements||[]), { type: 'arrow', id }] };
      window.__drawElements[dstId] = { ...dstEl,
        boundElements: [...(dstEl.boundElements||[]), { type: 'arrow', id }] };

      const labelId = id + '-label';
      const boundEls = label ? [{ type: 'text', id: labelId }] : [];
      window.__drawElements[id] = {
        id, type: 'arrow',
        x: sx, y: sy, width: ex - sx, height: ey - sy,
        points: [[0, 0], [ex - sx, ey - sy]],
        strokeColor: '#1e1e1e', backgroundColor: 'transparent',
        fillStyle: 'solid', strokeWidth: 2, roughness: 1,
        strokeStyle: strokeStyle || 'solid',
        opacity: 100, angle: 0, groupIds: [], frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: boundEls, roundness: { type: 2 },
        startArrowhead: startArrowhead ?? null,
        endArrowhead:   endArrowhead   ?? 'arrow',
        startBinding: { elementId: srcId, focus: 0, gap },
        endBinding:   { elementId: dstId, focus: 0, gap },
      };
      if (label) {
        const mx = sx + (ex - sx) / 2;
        const my = sy + (ey - sy) / 2;
        const fontSize = 14;
        window.__drawElements[labelId] = {
          id: labelId, type: 'text',
          x: mx - 60, y: my - fontSize,
          width: 120, height: fontSize * 1.25,
          text: label, fontSize,
          fontFamily: 1, textAlign: 'center', verticalAlign: 'middle',
          strokeColor: '#1e1e1e', backgroundColor: 'transparent',
          fillStyle: 'solid', strokeWidth: 1, roughness: 1,
          opacity: 100, angle: 0, groupIds: [], frameId: null,
          isDeleted: false, link: null, locked: false,
          version: 1, versionNonce: rng(), updated: now,
          boundElements: [], containerId: id, lineHeight: 1.25, baseline: 18,
          originalText: label, autoResize: true,
        };
      }
    }

    // Phase 3: subgraphs — rendered as a bounding rectangle pushed to the back
    const pad = 40;
    for (const f of frames) {
      const { id, label, memberIds, savedBounds } = f;
      // Erase previous rect + label if they exist (redraw always)
      delete window.__drawElements[id];
      delete window.__drawElements[id + '-label'];

      let x, y, w, h;
      if (savedBounds) {
        ({ x, y, w, h } = savedBounds);
      } else {
        // Compute bounds from freshly placed elements (or live for existing ones)
        const members = memberIds.map(mid =>
          window.__drawElements[mid] || liveMap[mid]
        ).filter(Boolean);
        if (!members.length) continue;
        const minX = Math.min(...members.map(e => e.x));
        const minY = Math.min(...members.map(e => e.y));
        const maxX = Math.max(...members.map(e => e.x + (e.width  || 160)));
        const maxY = Math.max(...members.map(e => e.y + (e.height || 60)));
        x = minX - pad;
        y = minY - pad * 2;
        w = (maxX - minX) + pad * 2;
        h = (maxY - minY) + pad * 3;
      }

      const labelId = id + '-label';
      const fontSize = 13;
      const groupIds = [id];
      const groupRect = {
        id, type: 'rectangle',
        x, y, width: w, height: h,
        strokeColor: '#868e96',
        backgroundColor: 'transparent',
        strokeWidth: 1, strokeStyle: 'dashed', roughness: 0, opacity: 80,
        fillStyle: 'solid', angle: 0, groupIds, frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [{ type: 'text', id: labelId }], roundness: null,
      };
      // Container child — Excalidraw positions it; verticalAlign drives top placement
      const labelEl = {
        id: labelId, type: 'text',
        x: x + 8, y: y + 8, width: w - 16, height: fontSize * 1.25,
        text: label, fontSize,
        fontFamily: 1, textAlign: 'center', verticalAlign: 'top',
        strokeColor: '#868e96', backgroundColor: 'transparent',
        fillStyle: 'solid', strokeWidth: 1, roughness: 0,
        opacity: 80, angle: 0, groupIds, frameId: null,
        isDeleted: false, link: null, locked: false,
        version: 1, versionNonce: rng(), updated: now,
        boundElements: [], containerId: id, lineHeight: 1.25, baseline: 13,
        originalText: label, autoResize: true,
      };

      // Add every member (and its bound text) to the same groupIds so they
      // move together with the bounding rect when selected as a group.
      // Fall back to liveMap for elements not yet in __drawElements.
      for (const mid of memberIds) {
        const el = window.__drawElements[mid] || liveMap[mid];
        if (el) {
          window.__drawElements[mid] = {
            ...el,
            groupIds: [...(el.groupIds || []), id],
          };
        }
        const tid = mid + '-text';
        const tel = window.__drawElements[tid] || liveMap[tid];
        if (tel) {
          window.__drawElements[tid] = {
            ...tel,
            groupIds: [...(tel.groupIds || []), id],
          };
        }
      }

      // Insert rect + label at BEGINNING so they render behind all other elements
      window.__drawElements = { [id]: groupRect, [labelId]: labelEl, ...window.__drawElements };

      // NOTE: frame-based implementation (kept for reference, not active)
      // const frameEl = {
      //   id, type: 'frame',
      //   x, y, width: w, height: h,
      //   name: label,
      //   strokeWidth: 1, strokeStyle: 'solid', roughness: 0, opacity: 100,
      //   fillStyle: 'solid', angle: 0, groupIds: [], frameId: null,
      //   isDeleted: false, link: null, locked: false,
      //   version: 1, versionNonce: rng(), updated: now,
      //   boundElements: [],
      // };
      // for (const mid of memberIds) {
      //   if (window.__drawElements[mid])
      //     window.__drawElements[mid] = { ...window.__drawElements[mid], frameId: id };
      //   const tid = mid + '-text';
      //   if (window.__drawElements[tid])
      //     window.__drawElements[tid] = { ...window.__drawElements[tid], frameId: id };
      // }
      // window.__drawElements = { [id]: frameEl, ...window.__drawElements };
    }

    // Single updateScene for all phases
    window.__drawApi._raw.updateScene({ elements: Object.values(window.__drawElements) });
    return true;
  };

  window._batch_erase = (ids) => {
    for (const id of ids) {
      delete window.__drawElements[id];
      delete window.__drawElements[id + '-text'];
      delete window.__drawElements[id + '-label'];
    }
    window.__drawApi._raw.updateScene({ elements: Object.values(window.__drawElements) });
    return true;
  };

  return true;
}
