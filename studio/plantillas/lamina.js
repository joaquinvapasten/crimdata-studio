/* crim.data — ajuste de texto y gráficos (SVG sin librerías).
   1. Espera las fuentes.  2. Achica el texto que no cabe.  3. Dibuja los gráficos.
   Al terminar deja window.__listo = true y los problemas en window.__avisos. */
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const avisos = (window.__avisos = []);

  // ── utilidades ────────────────────────────────────────────────
  const nodo = (tag, at = {}, padre) => {
    const e = document.createElementNS(NS, tag);
    for (const k in at) e.setAttribute(k, at[k]);
    if (padre) padre.appendChild(e);
    return e;
  };
  const texto = (padre, x, y, s, clase, anchor = "start", extra = {}) => {
    const t = nodo("text", { x, y, class: clase, "text-anchor": anchor, ...extra }, padre);
    t.textContent = s;
    return t;
  };
  const ancho = (t) => t.getComputedTextLength();
  const medir = (svg, s, clase) => {
    const t = texto(svg, -9999, -9999, s, clase);
    const w = ancho(t);
    t.remove();
    return w;
  };
  const nf = (d) => new Intl.NumberFormat("es-CL", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmt = (g, v, d = g.decimales) =>
    v == null ? "" : (g.signo && v > 0 ? "+" : "") + (g.prefijo || "") + nf(d).format(v) + (g.sufijo || "");
  const decimalesDe = (paso) => Math.max(0, Math.min(3, -Math.floor(Math.log10(paso) + 1e-9)));

  function ticksLindos(min, max, n = 4) {
    if (min === max) { max = min + 1; min = Math.min(min, 0); }
    const bruto = (max - min) / n;
    const mag = 10 ** Math.floor(Math.log10(bruto));
    const r = bruto / mag;
    const paso = (r >= 7.5 ? 10 : r >= 3.5 ? 5 : r >= 1.5 ? 2 : 1) * mag;
    const a = Math.floor(min / paso + 1e-9) * paso;
    const b = Math.ceil(max / paso - 1e-9) * paso;
    const t = [];
    for (let v = a; v <= b + paso * 1e-6; v += paso) t.push(+v.toFixed(10));
    return { t, paso };
  }

  function colores(lam) {
    const cs = getComputedStyle(lam);
    const c = {};
    for (const k of ["s0", "s1", "s2", "s3", "s4", "gris", "grilla", "fondo", "t1", "t2", "t3"])
      c[k] = cs.getPropertyValue("--" + k).trim();
    c.serie = [c.s1, c.s2, c.s3, c.s4];
    return c;
  }

  // Barra con extremo de datos redondeado y base recta.
  function barraV(x, w, yv, yb, r) {
    const h = Math.abs(yb - yv);
    r = Math.min(r, h, w / 2);
    const s = yv < yb ? 1 : -1;
    return `M${x},${yb}V${yv + s * r}Q${x},${yv} ${x + r},${yv}H${x + w - r}Q${x + w},${yv} ${x + w},${yv + s * r}V${yb}Z`;
  }
  function barraH(xb, xv, y, h, r) {
    const w = Math.abs(xv - xb);
    r = Math.min(r, w, h / 2);
    const s = xv > xb ? 1 : -1;
    return `M${xb},${y}H${xv - s * r}Q${xv},${y} ${xv},${y + r}V${y + h - r}Q${xv},${y + h} ${xv - s * r},${y + h}H${xb}Z`;
  }

  // Separa etiquetas que chocan (en y) manteniendo el orden; devuelve posiciones nuevas.
  function repartir(items, gap, min, max) {
    const o = [...items].sort((a, b) => a.y - b.y);
    for (let it = 0; it < 60; it++) {
      let movido = false;
      for (let i = 1; i < o.length; i++) {
        const d = o[i].ly - o[i - 1].ly;
        if (d < gap) {
          const m = (gap - d) / 2;
          o[i - 1].ly -= m; o[i].ly += m; movido = true;
        }
      }
      for (const e of o) e.ly = Math.max(min, Math.min(max, e.ly));
      if (!movido) break;
    }
    return o;
  }

  function leyenda(svg, series, c, W, forma = "linea") {
    let x = 0;
    const y = 18;
    for (let i = 0; i < series.length; i++) {
      if (forma === "punto") nodo("circle", { cx: x + 10, cy: y, r: 9, fill: series[i].color }, svg);
      else nodo("rect", { x, y: y - 3, width: 30, height: 6, rx: 3, fill: series[i].color }, svg);
      const dx = forma === "punto" ? 30 : 42;
      const t = texto(svg, x + dx, y + 8, series[i].nombre, "g-serie");
      x += dx + ancho(t) + 40;
    }
    return 62;
  }

  // Muestra una de cada k etiquetas del eje x para que no se pisen (siempre la última).
  function pasoEtiquetas(svg, etiquetas, espacio, clase) {
    const w = Math.max(...etiquetas.map((e) => medir(svg, e, clase)));
    return Math.max(1, Math.ceil((w + 18) / espacio));
  }

  // ── barras (columnas) ─────────────────────────────────────────
  function barras(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    const et = g.etiquetas, vs = g.series[0].valores, n = et.length;
    const dest = new Set(g.destacar);
    const conEje = g.valores ? g.valores === "eje" : n > 12;
    const minV = Math.min(0, ...vs.filter((v) => v != null));
    const maxV = Math.max(0, ...vs.filter((v) => v != null));
    const { t: ticks, paso } = ticksLindos(minV, maxV, 4);
    const dom = conEje ? [ticks[0], ticks[ticks.length - 1]] : [minV, maxV];
    let izq = 0;
    if (conEje) izq = Math.max(...ticks.map((v) => medir(svg, fmt(g, v, decimalesDe(paso)), "g-eje"))) + 20;
    const arriba = 50, abajo = 58;
    const y = (v) => H - abajo - ((v - dom[0]) / (dom[1] - dom[0] || 1)) * (H - arriba - abajo);
    if (conEje)
      for (const v of ticks) {
        if (v !== 0) nodo("line", { x1: izq, x2: W, y1: y(v), y2: y(v), stroke: c.grilla, "stroke-width": 1.5 }, svg);
        texto(svg, izq - 20, y(v) + 8, fmt(g, v, decimalesDe(paso)), "g-eje", "end");
      }
    const slot = (W - izq) / n;
    const bw = Math.min(slot * 0.56, 84);
    const cada = pasoEtiquetas(svg, et, slot, "g-cat");
    et.forEach((e, i) => {
      const v = vs[i];
      const cx = izq + slot * i + slot / 2;
      const esDest = dest.has(e);
      if (v != null && v !== 0)
        nodo("path", { d: barraV(cx - bw / 2, bw, y(v), y(0), 7), fill: dest.size ? (esDest ? c.s1 : c.s0) : c.s1 }, svg);
      if (v != null && (!conEje || esDest)) {
        const yy = v >= 0 ? y(v) - 16 : y(v) + 34;
        texto(svg, cx, yy, fmt(g, v), "g-valor" + (esDest || !dest.size ? " fuerte" : ""), "middle");
      }
      if (i % cada === 0 || i === n - 1)
        texto(svg, cx, H - 14, e, "g-cat" + (esDest ? " fuerte" : ""), "middle");
    });
    nodo("line", { x1: izq, x2: W, y1: y(0), y2: y(0), stroke: c.t1, "stroke-width": 2, opacity: 0.55 }, svg);
  }

  // ── barras horizontales (ranking) ─────────────────────────────
  function barrasH(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    let filas = g.etiquetas.map((e, i) => ({ e, v: g.series[0].valores[i] }));
    if (g.orden === "desc" || g.orden === "mayor") filas.sort((a, b) => (b.v ?? -Infinity) - (a.v ?? -Infinity));
    if (g.orden === "asc" || g.orden === "menor") filas.sort((a, b) => (a.v ?? Infinity) - (b.v ?? Infinity));
    const dest = new Set(g.destacar);
    const n = filas.length;
    const izq = Math.min(Math.max(...filas.map((f) => medir(svg, f.e, "g-cat"))), W * 0.42) + 26;
    const der = Math.max(...filas.map((f) => medir(svg, fmt(g, f.v), "g-valor fuerte"))) + 18;
    const alto = Math.min(H / n, 88);
    const grosor = Math.min(alto * 0.5, 40);
    const y0 = (H - alto * n) / 2;
    const vals = filas.map((f) => f.v).filter((v) => v != null);
    const minV = Math.min(0, ...vals), maxV = Math.max(0, ...vals);
    const x = (v) => izq + ((v - minV) / (maxV - minV || 1)) * (W - izq - der);
    filas.forEach((f, i) => {
      const cy = y0 + alto * i + alto / 2;
      const esDest = dest.has(f.e);
      const t = texto(svg, izq - 26, cy + 9, f.e, "g-cat" + (esDest ? " fuerte" : ""), "end");
      if (ancho(t) > izq - 26) t.setAttribute("textLength", izq - 26), t.setAttribute("lengthAdjust", "spacingAndGlyphs");
      if (f.v == null) return;
      if (f.v !== 0)
        nodo("path", { d: barraH(x(0), x(f.v), cy - grosor / 2, grosor, 7), fill: dest.size ? (esDest ? c.s1 : c.s0) : c.s1 }, svg);
      const fuera = f.v >= 0 ? x(f.v) + 14 : x(f.v) - 14;
      texto(svg, fuera, cy + 9, fmt(g, f.v), "g-valor" + (esDest || !dest.size ? " fuerte" : ""), f.v >= 0 ? "start" : "end");
    });
    nodo("line", { x1: x(0), x2: x(0), y1: y0, y2: y0 + alto * n, stroke: c.t1, "stroke-width": 2, opacity: 0.55 }, svg);
  }

  // ── líneas ────────────────────────────────────────────────────
  function lineas(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    const et = g.etiquetas, n = et.length;
    const dest = new Set(g.destacar);
    const series = g.series.map((s, i) => ({
      ...s,
      color: dest.size && !dest.has(s.nombre) ? c.gris : c.serie[i],
      principal: !dest.size || dest.has(s.nombre),
    }));
    const arriba = series.length > 1 ? leyenda(svg, series, c, W) : 24;
    const vals = series.flatMap((s) => s.valores).filter((v) => v != null);
    let minV = Math.min(...vals), maxV = Math.max(...vals);
    if (g.desde_cero) minV = Math.min(0, minV), maxV = Math.max(0, maxV);
    else { const m = (maxV - minV) * 0.08 || 1; minV -= m; maxV += m; }
    const { t: ticks, paso } = ticksLindos(minV, maxV, 4);
    const dom = [ticks[0], ticks[ticks.length - 1]];
    const dT = decimalesDe(paso);
    const izq = Math.max(...ticks.map((v) => medir(svg, fmt(g, v, dT), "g-eje"))) + 22;

    // etiquetas finales: «Nombre  valor» (una serie: solo el valor)
    const ultimo = (s) => { for (let i = n - 1; i >= 0; i--) if (s.valores[i] != null) return i; return -1; };
    const finales = series.map((s) => {
      const i = ultimo(s);
      const nombre = series.length > 1 ? s.nombre : "";
      return { s, i, v: s.valores[i], nombre, w: medir(svg, fmt(g, s.valores[i]), "g-valor fuerte") + (nombre ? medir(svg, nombre, "g-cat") + 12 : 0) };
    });
    const der = Math.max(...finales.map((f) => f.w)) + 34;
    const abajo = 56;
    const x = (i) => izq + (n === 1 ? 0.5 : i / (n - 1)) * (W - izq - der);
    const y = (v) => H - abajo - ((v - dom[0]) / (dom[1] - dom[0] || 1)) * (H - arriba - abajo - 10);

    for (const v of ticks) {
      nodo("line", { x1: izq, x2: W - der + 16, y1: y(v), y2: y(v), stroke: v === 0 ? c.t1 : c.grilla, "stroke-width": v === 0 ? 2 : 1.5, opacity: v === 0 ? 0.55 : 1 }, svg);
      texto(svg, izq - 22, y(v) + 8, fmt(g, v, dT), "g-eje", "end");
    }
    const cada = pasoEtiquetas(svg, et, (W - izq - der) / Math.max(1, n - 1), "g-eje");
    et.forEach((e, i) => {
      const ultimaVisible = i === n - 1;
      const cercaDelFinal = !ultimaVisible && (n - 1 - i) < cada && i % cada === 0;
      if ((i % cada === 0 && !cercaDelFinal) || ultimaVisible) texto(svg, x(i), H - 12, e, "g-eje", "middle");
    });

    for (const a of g.anotaciones || []) {
      const i = et.indexOf(String(a.x));
      if (i < 0) { avisos.push(`anotación en «${a.x}» no coincide con ninguna etiqueta del eje`); continue; }
      nodo("line", { x1: x(i), x2: x(i), y1: arriba - 4, y2: H - abajo, stroke: c.t3, "stroke-width": 1.5, opacity: 0.6 }, svg);
      texto(svg, x(i) + 10, arriba + 16, a.texto, "g-anota");
    }

    const orden = [...series].sort((a, b) => a.principal - b.principal);
    for (const s of orden) {
      const tramos = [];
      let actual = [];
      s.valores.forEach((v, i) => { if (v == null) { if (actual.length) tramos.push(actual); actual = []; } else actual.push([x(i), y(v)]); });
      if (actual.length) tramos.push(actual);
      if (series.length === 1 && g.area !== false)
        for (const tr of tramos) {
          const d = "M" + tr.map((p) => p.join(",")).join("L") + `L${tr[tr.length - 1][0]},${y(dom[0])}L${tr[0][0]},${y(dom[0])}Z`;
          nodo("path", { d, fill: s.color, opacity: 0.1 }, svg);
        }
      for (const tr of tramos)
        nodo("path", { d: "M" + tr.map((p) => p.join(",")).join("L"), fill: "none", stroke: s.color, "stroke-width": s.principal ? 5 : 3.5, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    }

    const items = finales.filter((f) => f.i >= 0).map((f) => ({ ...f, y: y(f.v), ly: y(f.v) }));
    repartir(items, 36, arriba, H - abajo);
    for (const f of items) {
      const cx = x(f.i);
      nodo("circle", { cx, cy: f.y, r: 8.5, fill: f.s.color, stroke: c.fondo, "stroke-width": 4 }, svg);
      const lx = cx + 22;
      if (Math.abs(f.ly - f.y) > 6)
        nodo("path", { d: `M${cx + 11},${f.y}L${lx - 6},${f.ly}`, stroke: c.t3, "stroke-width": 1.5, fill: "none" }, svg);
      let tx = lx;
      if (f.nombre) {
        const t = texto(svg, tx, f.ly + 9, f.nombre, "g-cat");
        tx += ancho(t) + 12;
      }
      texto(svg, tx, f.ly + 9, fmt(g, f.v), "g-valor" + (f.s.principal ? " fuerte" : ""));
    }
  }

  // ── proporción (grilla de 10 × 10) ────────────────────────────
  function proporcion(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    const total = Number(g.total) || 100;
    const cats = g.etiquetas.map((e, i) => ({ nombre: e, v: g.series.length > 1 ? g.series[i]?.valores[0] : g.series[0].valores[i] }));
    const S = Math.min(H, W * 0.54);
    const gap = S * 0.02;
    const celda = (S - gap * 9) / 10;
    const oy = (H - S) / 2;
    let k = 0;
    const cuentas = cats.map((cat) => Math.round(((cat.v || 0) / total) * 100));
    if (cuentas.reduce((a, b) => a + b, 0) > 100) avisos.push("proporción: los valores suman más que el total");
    // si las categorías suman el total, la última es «el resto» y va en gris claro
    const suma = cats.reduce((a, cat) => a + (cat.v || 0), 0);
    const colorCat = cats.map((_, j) => (cats.length > 1 && j === cats.length - 1 && Math.abs(suma - total) < 1e-6 ? c.s0 : c.serie[j]));
    const colorDe = [];
    cuentas.forEach((q, j) => { for (let i = 0; i < q && colorDe.length < 100; i++) colorDe.push(colorCat[j]); });
    for (let fila = 0; fila < 10; fila++)
      for (let col = 0; col < 10; col++, k++)
        nodo("rect", { x: col * (celda + gap), y: oy + fila * (celda + gap), width: celda, height: celda, rx: celda * 0.18, fill: colorDe[k] || c.s0 }, svg);

    const x0 = S + Math.max(56, W * 0.07);
    const bloque = 196;
    let y = H / 2 - (cats.length * bloque) / 2 + 100;
    cats.forEach((cat, j) => {
      nodo("rect", { x: x0, y: y - 78, width: 24, height: 24, rx: 5, fill: colorCat[j] }, svg);
      const n = texto(svg, x0 + 42, y, fmt(g, cat.v), "g-grande");
      // si la cifra no cabe (p. ej. con decimales), se achica hasta el borde
      if (ancho(n) > W - x0 - 42) n.style.fontSize = `${(parseFloat(getComputedStyle(n).fontSize) * (W - x0 - 42)) / ancho(n)}px`;
      const t = texto(svg, x0, y + 52, cat.nombre, "g-cat");
      if (ancho(t) > W - x0) t.setAttribute("textLength", W - x0), t.setAttribute("lengthAdjust", "spacingAndGlyphs");
      y += bloque;
    });
  }

  // ── comparación (antes → después) ─────────────────────────────
  function comparacion(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    const [a, b] = g.series;
    let filas = g.etiquetas.map((e, i) => ({ e, a: a.valores[i], b: b.valores[i] }));
    if (g.orden === "desc" || g.orden === "mayor") filas.sort((p, q) => (q.b ?? -Infinity) - (p.b ?? -Infinity));
    if (g.orden === "asc" || g.orden === "menor") filas.sort((p, q) => (p.b ?? Infinity) - (q.b ?? Infinity));
    if (g.orden === "cambio") filas.sort((p, q) => (q.b - q.a) - (p.b - p.a));
    const dest = new Set(g.destacar);
    const arriba = leyenda(svg, [{ nombre: a.nombre, color: c.gris }, { nombre: b.nombre, color: c.s1 }], c, W, "punto") + 10;
    const abajo = 48;
    const n = filas.length;
    const vals = filas.flatMap((f) => [f.a, f.b]).filter((v) => v != null);
    let minV = Math.min(...vals), maxV = Math.max(...vals);
    if (g.desde_cero) minV = Math.min(0, minV);
    const { t: ticks, paso } = ticksLindos(minV, maxV, 4);
    const dT = decimalesDe(paso);
    const izq = Math.min(Math.max(...filas.map((f) => medir(svg, f.e, "g-cat"))), W * 0.36) + 30;
    const vw = Math.max(...vals.map((v) => medir(svg, fmt(g, v), "g-valor"))) + 22;
    const x = (v) => izq + vw + ((v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1)) * (W - izq - vw * 2);
    const alto = Math.min((H - arriba - abajo) / n, 96);
    const y0 = arriba;
    for (const v of ticks) {
      nodo("line", { x1: x(v), x2: x(v), y1: y0, y2: y0 + alto * n, stroke: c.grilla, "stroke-width": 1.5 }, svg);
      texto(svg, x(v), y0 + alto * n + 36, fmt(g, v, dT), "g-eje", "middle");
    }
    filas.forEach((f, i) => {
      const cy = y0 + alto * i + alto / 2;
      const esDest = dest.has(f.e);
      const t = texto(svg, izq - 30, cy + 9, f.e, "g-cat" + (esDest ? " fuerte" : ""), "end");
      if (ancho(t) > izq - 30) t.setAttribute("textLength", izq - 30), t.setAttribute("lengthAdjust", "spacingAndGlyphs");
      if (f.a == null || f.b == null) return;
      nodo("line", { x1: x(f.a), x2: x(f.b), y1: cy, y2: cy, stroke: c.s0, "stroke-width": 7, "stroke-linecap": "round" }, svg);
      nodo("circle", { cx: x(f.a), cy, r: 10, fill: c.gris, stroke: c.fondo, "stroke-width": 4 }, svg);
      nodo("circle", { cx: x(f.b), cy, r: 11, fill: c.s1, stroke: c.fondo, "stroke-width": 4 }, svg);
      const sube = f.b >= f.a;
      texto(svg, x(f.b) + (sube ? 24 : -24), cy + 9, fmt(g, f.b), "g-valor fuerte", sube ? "start" : "end");
      texto(svg, x(f.a) + (sube ? -22 : 22), cy + 9, fmt(g, f.a), "g-valor", sube ? "end" : "start");
    });
  }

  // Parte un texto en líneas que quepan en maxW.
  function envolver(svg, s, clase, maxW) {
    const lineas = [];
    let actual = "";
    for (const p of String(s).split(/\s+/)) {
      const prueba = actual ? actual + " " + p : p;
      if (actual && medir(svg, prueba, clase) > maxW) { lineas.push(actual); actual = p; }
      else actual = prueba;
    }
    if (actual) lineas.push(actual);
    return lineas;
  }

  // ── intervalos (estimación con su intervalo de confianza) ─────
  function intervalos(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    const series = g.series.map((s, i) => ({ ...s, color: i === 0 ? c.s1 : c.gris, principal: i === 0 }));
    const arriba = series.length > 1 && series.some((s) => s.nombre) ? leyenda(svg, series, c, W, "punto") + 20 : 14;
    const abajo = g.eje ? 108 : 64;
    const n = g.etiquetas.length;
    const vals = series.flatMap((s) => [...s.valores, ...s.inf, ...s.sup]).filter((v) => v != null);
    const { t: ticks, paso } = ticksLindos(Math.min(0, ...vals), Math.max(0, ...vals), 4);
    const dT = decimalesDe(paso);
    const envueltas = g.etiquetas.map((e) => envolver(svg, e, "g-cat", W * 0.34));
    const izq = Math.max(...envueltas.flat().map((l) => medir(svg, l, "g-cat"))) + 40;
    const der = Math.max(...series.flatMap((s) => s.valores.map((v) => medir(svg, fmt(g, v), "g-valor fuerte")))) + 30;
    const x = (v) => izq + ((v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1)) * (W - izq - der);
    const alto = (H - arriba - abajo) / n;
    const sep = Math.min(alto / (series.length + 0.8), 76);
    for (const v of ticks) {
      const cero = v === 0;
      nodo("line", { x1: x(v), x2: x(v), y1: arriba, y2: H - abajo + 10, stroke: cero ? c.t1 : c.grilla,
                     "stroke-width": cero ? 2 : 1.5, opacity: cero ? 0.55 : 1 }, svg);
      texto(svg, x(v), H - abajo + 50, fmt(g, v, dT), "g-eje", "middle");
    }
    if (g.eje) {
      const t = texto(svg, x(ticks[0]), H - 12, g.eje, "g-anota");
      const sobra = x(ticks[0]) + ancho(t) - W;  // si no cabe desde el eje, se corre a la izquierda
      if (sobra > 0) t.setAttribute("x", Math.max(0, x(ticks[0]) - sobra));
      if (ancho(t) > W) t.setAttribute("textLength", W), t.setAttribute("lengthAdjust", "spacingAndGlyphs");
    }
    envueltas.forEach((lineas, i) => {
      const cy = arriba + alto * i + alto / 2;
      lineas.forEach((l, k) => texto(svg, izq - 40, cy + 9 + (k - (lineas.length - 1) / 2) * 34, l, "g-cat", "end"));
      series.forEach((s, j) => {
        const v = s.valores[i], lo = s.inf[i], hi = s.sup[i];
        if (v == null) return;
        const yy = cy + (j - (series.length - 1) / 2) * sep;
        if (lo != null && hi != null)
          nodo("line", { x1: x(lo), x2: x(hi), y1: yy, y2: yy, stroke: s.color, "stroke-width": 7, "stroke-linecap": "round",
                         opacity: s.principal ? 1 : 0.85 }, svg);
        nodo("circle", { cx: x(v), cy: yy, r: s.principal ? 14 : 12, fill: s.color, stroke: c.fondo, "stroke-width": 4 }, svg);
        texto(svg, x(hi ?? v) + 22, yy + 9, fmt(g, v), "g-valor" + (s.principal ? " fuerte" : ""));
      });
    });
  }

  // ── íconos (una fila por país: bandera, nombre y un monito por unidad) ──
  const FORMAS = {
    persona: { w: 10, h: 16, d: "M5 0a2.6 2.6 0 1 1 0 5.2A2.6 2.6 0 0 1 5 0ZM1.6 6.2h6.8a1.6 1.6 0 0 1 1.6 1.6v4.4H8.2V16H5.6v-3.8H4.4V16H1.8v-3.8H0V7.8a1.6 1.6 0 0 1 1.6-1.6Z" },
    punto: { w: 10, h: 10, d: "M5 0a5 5 0 1 1 0 10A5 5 0 0 1 5 0Z" },
    cuadrado: { w: 10, h: 10, d: "M2.2 0h5.6A2.2 2.2 0 0 1 10 2.2v5.6A2.2 2.2 0 0 1 7.8 10H2.2A2.2 2.2 0 0 1 0 7.8V2.2A2.2 2.2 0 0 1 2.2 0Z" },
  };
  // Si los números son grandes, cada ícono vale una cantidad redonda (1, 2, 5, 10, 20…) para no pasar de `limite`.
  const unidadLinda = (max, limite) => {
    if (max <= limite) return 1;
    const bruto = max / (limite * 0.8), mag = 10 ** Math.floor(Math.log10(bruto)), r = bruto / mag;
    return (r <= 1 ? 1 : r <= 2 ? 2 : r <= 5 ? 5 : 10) * mag;
  };

  function iconos(caja, g, c) {
    const W = caja.clientWidth, H = caja.clientHeight;
    const svg = nodo("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, caja);
    const id = `g${caja.dataset.i}`;
    let filas = g.etiquetas.map((e, i) => ({ e, v: g.series[0].valores[i], b: g.banderas ? g.banderas[i] : null }));
    if (g.orden === "desc" || g.orden === "mayor") filas.sort((a, b) => (b.v ?? -Infinity) - (a.v ?? -Infinity));
    if (g.orden === "asc" || g.orden === "menor") filas.sort((a, b) => (a.v ?? Infinity) - (b.v ?? Infinity));
    for (const f of filas) if (g.banderas && !f.b) avisos.push(`íconos: no encontré la bandera de «${f.e}» (escribe el país como en el README o pon banderas: no)`);
    const dest = new Set(g.destacar);
    const forma = g.forma || FORMAS[g.icono] || FORMAS.persona; // g.forma: un ícono de Font Awesome
    const max = Math.max(0, ...filas.map((f) => f.v ?? 0));
    // Los íconos de Font Awesome tienen más detalle: necesitan ser más grandes, así que caben menos.
    const unidad = (g._unidad = g.unidad || unidadLinda(max, g.forma ? 60 : 150));
    const n = filas.length;

    const pie = unidad !== 1 ? 54 : 0;
    const alto = (H - pie) / n;
    const lado = g.banderas ? Math.min(alto * 0.5, 46) : 0;
    const nombre = Math.min(Math.max(...filas.map((f) => medir(svg, f.e, "g-cat fuerte"))), W * 0.3);
    const izq = nombre + (lado ? lado + 16 : 0) + 24;
    const der = Math.max(...filas.map((f) => medir(svg, fmt(g, f.v), "g-valor fuerte"))) + 18;
    const util = W - izq - der;

    // El ícono más grande que deje caber la fila más larga en su alto (todas las filas usan el mismo tamaño).
    const cuenta = (v) => Math.max(0, (v ?? 0) / unidad);
    const nmax = Math.max(1, ...filas.map((f) => Math.ceil(cuenta(f.v) - 1e-9)));
    // Mejor una sola línea por fila (así el largo se compara como una barra), salvo que los íconos queden diminutos.
    let h = Math.min(alto * 0.6, 58), w, paso, porLinea;
    const k = 1 + Math.min(0.3, (0.28 * forma.h) / forma.w); // paso entre íconos, en anchos de ícono
    const hUna = ((util / ((nmax - 1) * k + 1)) * forma.h) / forma.w;
    if (hUna >= Math.min(h, g.forma ? 26 : forma.h > forma.w ? 18 : 12)) h = Math.min(h, hUna);
    for (;;) {
      w = (h * forma.w) / forma.h;
      paso = w * k;
      porLinea = Math.max(1, Math.floor((util - w) / paso) + 1);
      if (Math.ceil(nmax / porLinea) * h * 1.16 <= alto * 0.84 || h < 7) break;
      h *= 0.95;
    }

    const defs = nodo("defs", {}, svg);
    const simbolo = nodo("symbol", { id: `${id}-ic`, viewBox: `0 0 ${forma.w} ${forma.h}` }, defs);
    nodo("path", { d: forma.d }, simbolo);
    const punteada = (y) => nodo("line", { x1: 0, x2: W, y1: y, y2: y, stroke: c.gris, "stroke-width": 2,
      "stroke-linecap": "round", "stroke-dasharray": "0.1 10", opacity: 0.7 }, svg);

    filas.forEach((f, i) => {
      const top = alto * i, cy = top + alto / 2;
      punteada(top + 1);
      const esDest = dest.has(f.e);
      const xNombre = izq - 24 - (lado ? lado + 16 : 0);
      const t = texto(svg, xNombre, cy + 9, f.e, "g-cat" + (esDest ? " fuerte" : ""), "end");
      if (ancho(t) > nombre) t.setAttribute("textLength", nombre), t.setAttribute("lengthAdjust", "spacingAndGlyphs");
      if (lado && f.b) {
        const clip = nodo("clipPath", { id: `${id}-b${i}` }, defs);
        nodo("rect", { x: izq - 24 - lado, y: cy - lado / 2, width: lado, height: lado, rx: lado * 0.24 }, clip);
        nodo("image", { href: f.b, x: izq - 24 - lado, y: cy - lado / 2, width: lado, height: lado,
          preserveAspectRatio: "xMidYMid slice", "clip-path": `url(#${id}-b${i})` }, svg);
      }
      if (f.v == null) return;
      const k = cuenta(f.v), total = Math.ceil(k - 1e-9), lineas = Math.max(1, Math.ceil(total / porLinea));
      const color = dest.size ? (esDest ? c.s1 : c.gris) : c.s1;
      const y0 = cy - (lineas * h + (lineas - 1) * h * 0.16) / 2;
      for (let j = 0; j < total; j++) {
        const x = izq + (j % porLinea) * paso, y = y0 + Math.floor(j / porLinea) * h * 1.16;
        const resto = k - j;
        let padre = svg;
        if (resto < 1 - 1e-9) { // el último ícono, cortado si sobra una fracción
          const clip = nodo("clipPath", { id: `${id}-p${i}` }, defs);
          nodo("rect", { x, y, width: w * resto, height: h }, clip);
          padre = nodo("g", { "clip-path": `url(#${id}-p${i})` }, svg);
        }
        nodo("use", { href: `#${id}-ic`, x, y, width: w, height: h, fill: color }, padre);
      }
      const xv = izq + (total ? (Math.min(total, porLinea) - 1) * paso + w + 16 : 0);
      texto(svg, xv, cy + 9, fmt(g, f.v), "g-valor" + (esDest || !dest.size ? " fuerte" : ""));
    });
    punteada(alto * n - 1);

    if (pie) {
      nodo("use", { href: `#${id}-ic`, x: izq, y: H - 40, width: (30 * forma.w) / forma.h, height: 30, fill: c.s1 }, svg);
      texto(svg, izq + (30 * forma.w) / forma.h + 12, H - 16, `= ${nf(0).format(unidad)}`, "g-eje");
    }
  }

  const DIBUJAR = { barras, barras_h: barrasH, lineas, proporcion, comparacion, intervalos, iconos };

  // ── ajuste de texto ───────────────────────────────────────────
  function ajustar(lam) {
    const cuerpo = lam.querySelector(".cuerpo");
    const graf = cuerpo.querySelector(".grafico");
    if (graf) graf.style.minHeight = Math.round(cuerpo.clientHeight * 0.5) + "px";
    // En las láminas alineadas abajo (portada, cierre, cifra) el texto que sobra se sale por arriba,
    // y eso scrollHeight no lo ve: por eso también se compara el borde superior del contenido.
    const tope = () => cuerpo.getBoundingClientRect().top + parseFloat(getComputedStyle(cuerpo).paddingTop);
    const desborda = () =>
      cuerpo.scrollHeight > cuerpo.clientHeight + 1 ||
      (cuerpo.firstElementChild && cuerpo.firstElementChild.getBoundingClientRect().top < tope() - 1) ||
      [...cuerpo.querySelectorAll(".titulo")].some((h) => h.scrollWidth > h.clientWidth + 1);
    let k = 1;
    while (desborda() && k > 0.6) {
      k = +(k - 0.02).toFixed(2);
      lam.style.setProperty("--k", k);
    }
    if (desborda()) avisos.push(`Lámina ${lam.dataset.n}: el texto no cabe ni achicándolo; acórtalo.`);
    else if (k < 0.8) avisos.push(`Lámina ${lam.dataset.n}: hay mucho texto (se achicó a ${Math.round(k * 100)} %).`);
  }

  // ── contraste (WCAG 2.1) ──────────────────────────────────────
  // Mide cada texto contra el color que tiene detrás. Mínimo 4,5:1; 3:1 si la letra es grande.
  const rgba = (s) => {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r, g, b, a = 1] = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return [r, g, b, a];
  };
  const sobre = (c, f) => c.slice(0, 3).map((v, i) => v * c[3] + f[i] * (1 - c[3]));
  const luz = (c) => {
    const [r, g, b] = c.map((v) => (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  function fondoDe(el) {
    const capas = [];
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage !== "none") return null; // degradado o imagen: no se puede medir
      const c = rgba(cs.backgroundColor);
      if (c && c[3] > 0) { capas.push(c); if (c[3] >= 1) break; }
    }
    return capas.reduceRight((f, c) => sobre(c, f), [255, 255, 255]);
  }
  const NOMBRE = { titulo: "el título", bajada: "la bajada", rotulo: "el rótulo", etiqueta: "la etiqueta",
                   nota: "la nota", destacado: "el destacado", fuente: "la fuente" };
  function contraste() {
    const bajos = new Map();
    const sel = ".titulo, .bajada, .rotulo, .cuerpo p, .lista li, .etiqueta, .nota, .fuente, strong, mark, em";
    for (const lam of document.querySelectorAll(".lamina"))
      for (const el of lam.querySelectorAll(sel)) {
        if (!el.textContent.trim() || el.closest("svg")) continue;
        const cs = getComputedStyle(el);
        const f = fondoDe(el), c = rgba(cs.color);
        if (!f || !c) continue;
        const [a, b] = [luz(sobre(c, f)), luz(f)].sort((x, y) => y - x);
        const ratio = (a + 0.05) / (b + 0.05);
        const px = parseFloat(cs.fontSize), grande = px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700);
        if (ratio >= (grande ? 3 : 4.5)) continue;
        const parte = el.closest(".titulo, .bajada, .rotulo, .etiqueta, .nota, .destacado, .fuente");
        const clave = `${parte ? NOMBRE[[...parte.classList].find((k) => NOMBRE[k])] : "el texto"} (${nf(1).format(ratio)}:1, mínimo ${grande ? 3 : "4,5"}:1)`;
        if (!bajos.has(clave)) bajos.set(clave, new Set());
        bajos.get(clave).add(lam.dataset.n);
      }
    for (const [clave, ns] of bajos)
      avisos.push(`Lámina${ns.size > 1 ? "s" : ""} ${[...ns].join(", ")}: contraste bajo en ${clave}.`);
  }

  // ── texto alternativo ─────────────────────────────────────────
  // Lo que dice cada lámina en texto plano, con los datos de sus gráficos, para pegarlo en Instagram.
  function describir(g) {
    const nombre = { barras: "Gráfico de barras", barras_h: "Gráfico de barras", lineas: "Gráfico de líneas",
                     proporcion: "Gráfico de proporción", comparacion: "Gráfico de comparación",
                     intervalos: "Gráfico de estimaciones con intervalos de confianza",
                     iconos: g._unidad > 1 ? `Gráfico de íconos (cada ícono = ${nf(0).format(g._unidad)})` : "Gráfico de íconos" }[g.tipo];
    const pares = (s) => g.etiquetas.map((e, i) => `${e}: ${fmt(g, s.valores[i])}`).filter((x) => !x.endsWith(": "));
    if (g.tipo === "proporcion")
      return `${nombre}: ` + g.etiquetas.map((e, i) => `${fmt(g, g.series.length > 1 ? g.series[i]?.valores[0] : g.series[0].valores[i])} ${e}`).join("; ") + ".";
    if (g.tipo === "intervalos")
      return `${nombre}. ` + g.series.map((s) => (s.nombre ? `${s.nombre}: ` : "") + g.etiquetas.map((e, i) =>
        `${e}: ${fmt(g, s.valores[i])} (entre ${fmt(g, s.inf[i])} y ${fmt(g, s.sup[i])})`).join("; ")).join(". ") + ".";
    if (g.series.length === 1) return `${nombre}. ${pares(g.series[0]).join("; ")}.`;
    return `${nombre}. ` + g.series.map((s) => `${s.nombre}: ${pares(s).join("; ")}`).join(". ") + ".";
  }
  function textoAlternativo() {
    const plano = (el) => el.innerText.replace(/\s*\n+\s*/g, " ").replace(/\s{2,}/g, " ").trim();
    const punto = (s) => (/[.!?…:»”)]$/.test(s) ? s : s + ".");
    window.__alt = [...document.querySelectorAll(".lamina")].map((lam) => {
      const partes = [];
      for (const el of lam.querySelector(".cuerpo").children) {
        if (el.classList.contains("grafico")) partes.push(describir(window.GRAFICOS[+el.dataset.i]));
        else if (el.matches("ol, ul"))
          partes.push([...el.children].map((li, i) => (el.tagName === "OL" ? `${i + 1}. ` : "") + punto(plano(li))).join(" "));
        else if (el.innerText.trim()) partes.push(punto(plano(el)));
      }
      const fuente = lam.querySelector(".fuente");
      if (fuente) partes.push(punto(plano(fuente)));
      return partes.join(" ");
    });
  }

  async function principal() {
    await document.fonts.ready;
    for (const lam of document.querySelectorAll(".lamina")) ajustar(lam);
    for (const caja of document.querySelectorAll(".grafico")) {
      const g = window.GRAFICOS[+caja.dataset.i];
      const lam = caja.closest(".lamina");
      try {
        DIBUJAR[g.tipo](caja, g, colores(lam));
      } catch (e) {
        avisos.push(`Lámina ${lam.dataset.n}: no pude dibujar el gráfico (${e.message})`);
      }
    }
    contraste();
    textoAlternativo();
    window.__listo = true;
  }
  principal();
})();
