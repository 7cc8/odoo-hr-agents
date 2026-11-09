/* =====================================================================
   Pilar · Moxen
   El manejo de las columnas de una tabla de datos, como en una hoja de cálculo o en el panel de un producto: ancho,
   orden, fijar a la izquierda, ocultar y densidad. Solo trata de las columnas (no busca, filtra ni pagina).

   · Ancho. Arrastrar el borde de un encabezado cambia el ancho de esa columna; una guía azul cruza la tabla entera y
     lleva su medida («184 px», y «mín.» o «máx.» cuando topa), con una marca punteada donde estaba el borde. Doble clic
     (o doble toque) sobre el borde la ajusta al contenido con un resorte: mide la celda más larga y el encabezado.
   · Orden. Arrastrar el encabezado levanta la columna entera como una lámina (sombra, un grado de inclinación) que
     sigue al cursor, y las demás se apartan con un resorte (FLIP: cada una viaja de su sitio viejo al nuevo). Deja un
     hueco azul donde caerá; al soltar, la lámina vuela al hueco. Cerca del borde de la tabla se desplaza sola. Lo fijo y
     lo móvil son dos grupos: se ordena dentro de cada uno.
   · Fijar. La chincheta del encabezado lleva la columna al grupo de la izquierda con un vuelo; al desplazar en
     horizontal, lo fijo se queda (position: sticky) y una sombra lo separa de lo que pasa por debajo. Al fijar, la tabla
     se asoma un poco a la derecha y vuelve, para que se vea que lo fijo se queda (empujaAlFijar: false lo apaga).
   · Ocultar. El menú «Columnas» tiene una casilla por columna: al quitarla, la columna se pliega hasta 0 px y las demás
     ocupan su sitio; al ponerla, se despliega. Siempre queda al menos una visible.
   · Densidad. Cómoda, normal o compacta cambian el alto de las filas en ola: cada fila arranca un poco después que la
     anterior (el retardo sale de su índice, --i).
   · Restablecer. Devuelve cada columna a su sitio, ancho y visibilidad (lo que estaba oculto se despliega, lo fijado se
     suelta, la tabla vuelve a la izquierda) con un vuelo, y el botón se vuelve «Restablecido» con su ✓ azul. Está
     apagado mientras no haya nada que deshacer y muestra un punto azul cuando sí.
   · Teclado. Un solo tope de tabulación en los encabezados (roving): ← → recorren; Alt+← → mueven la columna;
     Mayús+← → cambian el ancho de 16 en 16 px; P fija o suelta; H oculta; Intro ajusta al contenido; Inicio y Fin
     saltan a los extremos. El menú de columnas se abre con Intro, Espacio o ↓ y se recorre con ↑ ↓; Esc cierra. Mientras
     se arrastra, Esc cancela. Todo lo que cambia se anuncia en una región aria-live.

   Montaje (se inicia con la llamada de index.html; el HTML de esta demo es la plantilla):
     const p = Pilar(document.querySelector('[data-pilar]'), {
       columnas: COLUMNAS,               // [{ id, nombre, tipo: 'id'|'estado'|'texto'|'num'|'mono', ancho, min?, max? }]
       filas: FILAS,                     // una fila por array, con un valor por columna en el mismo orden
       densidad: 'normal',               // 'comoda' | 'normal' | 'compacta': la de fábrica a la que vuelve «Restablecer»
       empujaAlFijar: true,
       alCambiar: ({ orden, anchos, fijas, ocultas, densidad }) => {},   // cuando algo se asienta: guárdalo donde quieras
     });
     p.mueve('importe', 1);  p.ancho('producto', 220);  p.fija('pedido', true);  p.oculta('descuento', true);
     p.densidad('compacta');  p.ajusta('producto');  p.restablece();  p.estado();

   Qué cambia qué: COLUMNAS y FILAS (los datos de ejemplo), MODOS (los resortes de cada situación) y los colores, al
   principio de pilar.css (--pi-azul es todo lo que agarras y lo que se completa; --pi-alto, el alto de fila de cada
   densidad al final). Sin dependencias; el tiempo viene de requestAnimationFrame, timers, Web Animations y transiciones
   CSS (nada de Date): la página y el vídeo coinciden.
   ===================================================================== */
(function () {
  'use strict';

  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  const quieto = () => mq.matches;
  const lim = (v, a, b) => Math.max(a, Math.min(b, v));
  const h = (tag, clase, texto) => { const e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const plural = (n, u, p) => n + ' ' + (n === 1 ? u : p);

  /* Un resorte convertido en curva `linear()`: sirve para CSS y para Web Animations. */
  function muelle(k, c) {
    const pts = [0];
    let x = 0, v = 0, t = 0;
    while (t < 3) {
      v += (k * (1 - x) - c * v) / 240; x += v / 240; t += 1 / 240;
      pts.push(x);
      if (t > .15 && Math.abs(1 - x) < .001 && Math.abs(v) < .01) break;
    }
    const out = [];
    for (let i = 0; i <= 40; i++) out.push(pts[Math.round(i / 40 * (pts.length - 1))].toFixed(4));
    out[40] = '1';
    return 'linear(' + out.join(', ') + ')';
  }

  /* resortes (rigidez, amortiguación): libre sigue al puntero casi sin retraso; suelta da un pequeño rebote al ajustar;
     pliega cierra sin rebote (un ancho negativo no existe); abre sí rebota; scroll lleva la tabla a un lado y a otro */
  const MODOS = { libre: [3200, 112], suelta: [320, 21], pliega: [440, 42], abre: [330, 22], scroll: [190, 26] };

  /* ── los datos de ejemplo: pedidos de una tienda, sin personas ni marcas ─ */
  const COLUMNAS = [
    { id: 'pedido', nombre: 'Pedido', tipo: 'id', ancho: 132 },
    { id: 'estado', nombre: 'Estado', tipo: 'estado', ancho: 140 },
    { id: 'canal', nombre: 'Canal', tipo: 'texto', ancho: 124 },
    { id: 'region', nombre: 'Región', tipo: 'texto', ancho: 130 },
    { id: 'producto', nombre: 'Producto', tipo: 'texto', ancho: 156 },
    { id: 'unidades', nombre: 'Unidades', tipo: 'num', ancho: 116 },
    { id: 'importe', nombre: 'Importe', tipo: 'num', ancho: 132 },
    { id: 'descuento', nombre: 'Descuento', tipo: 'num', ancho: 126 },
    { id: 'fecha', nombre: 'Fecha', tipo: 'mono', ancho: 112 },
    { id: 'entrega', nombre: 'Entrega', tipo: 'texto', ancho: 132 },
  ];
  const ESTADOS = { pagado: 'Pagado', enviado: 'Enviado', pendiente: 'Pendiente', devuelto: 'Devuelto' };
  const FILAS = [
    ['PD-4821', 'pagado', 'Web', 'Norte', 'Escritorio regulable en altura', '2', '1.240,50', '10 %', '16 oct', 'Mañana'],
    ['PD-4820', 'enviado', 'Tienda', 'Centro', 'Lámpara articulada de mesa', '4', '318,00', '—', '16 oct', 'En 2 días'],
    ['PD-4819', 'pendiente', 'Mayorista', 'Costa', 'Silla ergonómica de oficina', '12', '4.860,00', '15 %', '15 oct', 'En 5 días'],
    ['PD-4818', 'pagado', 'App', 'Sur', 'Estantería modular de pared', '1', '189,90', '—', '15 oct', 'Hoy'],
    ['PD-4817', 'devuelto', 'Web', 'Oriente', 'Mesa plegable de roble', '2', '540,00', '5 %', '14 oct', 'Devuelto'],
    ['PD-4816', 'enviado', 'Tienda', 'Norte', 'Banco de trabajo con cajones', '1', '772,40', '—', '14 oct', 'En 3 días'],
    ['PD-4815', 'pagado', 'Web', 'Costa', 'Soporte para monitor doble', '6', '612,00', '8 %', '13 oct', 'Entregado'],
    ['PD-4814', 'pendiente', 'App', 'Centro', 'Organizador de cables adhesivo', '24', '216,00', '—', '13 oct', 'En 4 días'],
    ['PD-4813', 'pagado', 'Mayorista', 'Sur', 'Cajonera rodante de oficina', '8', '2.304,00', '12 %', '12 oct', 'Entregado'],
    ['PD-4812', 'enviado', 'Web', 'Oriente', 'Perchero de pared en nogal', '3', '267,30', '—', '12 oct', 'Mañana'],
    ['PD-4811', 'pagado', 'Tienda', 'Norte', 'Taburete regulable de taller', '5', '495,00', '5 %', '11 oct', 'Entregado'],
    ['PD-4810', 'pendiente', 'Web', 'Costa', 'Alfombra técnica para silla', '2', '134,80', '—', '11 oct', 'En 6 días'],
  ];
  const DENSIDADES = { comoda: 'cómodas', normal: 'normales', compacta: 'compactas' };
  const POS = { comoda: 0, normal: 1, compacta: 2 };

  const IC = {
    pin: '<svg viewBox="0 0 24 24"><path d="M9.2 4.5h5.6l-.7 4.6 2.9 3v1.4H7v-1.4l2.9-3z"/><path d="M12 13.6v5.9"/></svg>',
    tilde: '<svg viewBox="0 0 24 24"><path d="M6.6 12.6l3.8 3.8 7.2-8.2" pathLength="1"/></svg>',
  };

  function Pilar(raiz, opciones) {
    const op = Object.assign({ columnas: COLUMNAS, filas: FILAS, densidad: 'normal', empujaAlFijar: true, alCambiar: null }, opciones);
    const $ = (s, r) => (r || raiz).querySelector(s);
    const el = {
      scroll: $('[data-scroll]'), tabla: $('[data-tabla]'), columnas: $('[data-columnas]'), cuenta: $('[data-cuenta]'),
      menu: $('[data-menu]'), menuLista: $('[data-menu-lista]'), menuCuenta: $('[data-menu-cuenta]'), todas: $('[data-todas]'),
      seg: $('[data-densidad]'), restablece: $('[data-restablece]'), estado: $('[data-estado]'), vivo: $('[data-vivo]'),
    };
    raiz.style.setProperty('--pi-muelle', muelle(420, 20));
    raiz.style.setProperty('--pi-ola', muelle(200, 17));
    const VUELO = muelle(230, 19), ATERRIZA = muelle(310, 24), LEVANTA = muelle(520, 24);

    /* ── el estado ────────────────────────────────────────────────── */
    const cols = op.columnas.map(d => ({
      id: d.id, nombre: d.nombre, tipo: d.tipo, num: d.tipo === 'num', w0: d.ancho, w: d.ancho, min: d.min || 76, max: d.max || 460,
      fija: false, oculta: false, x: d.ancho, v: 0, tgt: d.ancho, kk: MODOS.suelta[0], cc: MODOS.suelta[1], celdas: [], plegada: false, ultX: -1, ultL: -1,
    }));
    const porId = {};
    cols.forEach(c => { porId[c.id] = c; });
    const ORDEN0 = cols.map(c => c.id);
    let orden = ORDEN0.slice();
    let densidad = op.densidad;
    let activa = cols[0].id;                    // el encabezado que lleva el tope de tabulación
    let arrastre = null, timers = [], menuAbierto = false, menuFoco = 0, cierraId = 0, listoId = 0;
    let ultToque = { t: -1e9, id: '', x: 0, y: 0 };
    const sc = { x: 0, v: 0, tgt: 0, activo: false };
    const setModo = (c, m) => { c.kk = MODOS[m][0]; c.cc = MODOS[m][1]; };
    const visibles = () => orden.filter(id => !porId[id].oculta);
    const nFijas = () => orden.filter(id => porId[id].fija && !porId[id].oculta).length;
    const tarda = (f, ms) => { const id = setTimeout(f, ms); timers.push(id); return id; };
    const anuncia = t => { el.vivo.textContent = ''; setTimeout(() => { el.vivo.textContent = t; }, 30); };

    /* ── la construcción ──────────────────────────────────────────── */
    const filas = [];
    function celdaHtml(c, v) {
      if (c.tipo === 'estado') return '<span class="pi-chip" data-e="' + esc(v) + '"><i></i>' + esc(ESTADOS[v] || v) + '</span>';
      if (c.tipo === 'id') return '<span class="pi-mono pi-id">' + esc(v) + '</span>';
      if (c.tipo === 'num' || c.tipo === 'mono') return '<span class="pi-mono' + (v === '—' ? ' pi-sin' : '') + '">' + esc(v) + '</span>';
      return '<span class="pi-t">' + esc(v) + '</span>';
    }
    function construye() {
      el.tabla.textContent = '';
      const cab = h('div', 'pi-fila pi-fila--cab'); cab.setAttribute('role', 'row');
      cols.forEach(c => {
        const th = h('div', 'pi-c pi-h' + (c.num ? ' es-num' : ''));
        th.setAttribute('role', 'columnheader'); th.dataset.col = c.id;
        th.style.setProperty('--w', 'var(--pi-w-' + c.id + ')'); th.style.setProperty('--l', 'var(--pi-l-' + c.id + ')');
        th.innerHTML = '<div class="pi-ci"><button class="pi-th" type="button" tabindex="-1" aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight Shift+ArrowLeft Shift+ArrowRight P H Enter"><span class="pi-th-t">' + esc(c.nombre) + '</span></button><button class="pi-pin" type="button" tabindex="-1" aria-hidden="true">' + IC.pin + '</button><span class="pi-borde" aria-hidden="true"></span></div>';
        cab.appendChild(th); c.celdas.push(th);
      });
      el.tabla.appendChild(cab);
      op.filas.forEach((f, i) => {
        const fila = h('div', 'pi-fila'); fila.setAttribute('role', 'row'); fila.style.setProperty('--i', i);
        cols.forEach((c, j) => {
          const td = h('div', 'pi-c' + (c.num ? ' es-num' : ''));
          td.setAttribute('role', 'cell'); td.dataset.col = c.id;
          td.style.setProperty('--w', 'var(--pi-w-' + c.id + ')'); td.style.setProperty('--l', 'var(--pi-l-' + c.id + ')');
          td.innerHTML = '<div class="pi-ci">' + celdaHtml(c, f[j]) + '</div>';
          fila.appendChild(td); c.celdas.push(td);
        });
        el.tabla.appendChild(fila); filas.push(fila);
      });
      el.guiaAnt = h('i', 'pi-guia-ant'); el.guiaAnt.setAttribute('aria-hidden', 'true');
      el.guia = h('i', 'pi-guia'); el.guia.setAttribute('aria-hidden', 'true');
      el.guiaEt = h('b'); el.guia.appendChild(el.guiaEt);
      el.tabla.append(el.guiaAnt, el.guia);

      // el menú de columnas: una casilla por columna, en el orden de fábrica
      el.menuLista.textContent = '';
      cols.forEach(c => {
        const li = h('li'); li.setAttribute('role', 'none');
        li.innerHTML = '<button class="pi-item" type="button" role="menuitemcheckbox" aria-checked="true" tabindex="-1" data-id="' + c.id + '"><span class="pi-caja">' + IC.tilde + '</span><span class="pi-item-nom"><span>' + esc(c.nombre) + '</span>' + IC.pin + '</span><span class="pi-item-w"></span></button>';
        el.menuLista.appendChild(li); c.item = li.firstChild; c.itemW = c.item.querySelector('.pi-item-w');
      });
    }

    /* ── el orden, lo fijo y las variables ─────────────────────────── */
    function aplicaOrden() {
      orden.forEach((id, i) => { porId[id].celdas.forEach(td => { td.style.order = i; }); });
    }
    function aplicaClases() {
      const ultima = orden.slice().reverse().find(id => porId[id].fija && !porId[id].oculta);
      cols.forEach(c => {
        c.celdas.forEach(td => {
          td.classList.toggle('es-fija', c.fija);
          td.classList.toggle('es-borde', c.id === ultima);
        });
        const b = c.celdas[0].querySelector('.pi-th');
        b.setAttribute('aria-label', c.nombre + (c.fija ? ', fijada a la izquierda' : ''));
        c.celdas[0].querySelector('.pi-pin').title = c.fija ? 'Soltar' : 'Fijar a la izquierda';
        c.celdas[0].setAttribute('aria-hidden', c.oculta ? 'true' : 'false');
        c.celdas.forEach((td, i) => { if (i) td.setAttribute('aria-hidden', c.oculta ? 'true' : 'false'); });
      });
      raiz.dataset.fijas = nFijas() ? '1' : '';
      roving();
    }
    function roving() {
      if (porId[activa].oculta) activa = visibles()[0];
      cols.forEach(c => { c.celdas[0].querySelector('.pi-th').tabIndex = c.id === activa && !c.oculta ? 0 : -1; });
    }

    /* escribe en el DOM los anchos y los pegados de este cuadro; solo toca lo que cambió */
    function pinta() {
      let total = 0, l = 0;
      orden.forEach(id => {
        const c = porId[id];
        if (Math.abs(c.x - c.ultX) > .01) { el.tabla.style.setProperty('--pi-w-' + id, c.x.toFixed(2) + 'px'); c.ultX = c.x; }
        total += c.x;
        if (c.fija) {
          if (Math.abs(l - c.ultL) > .01) { el.tabla.style.setProperty('--pi-l-' + id, l.toFixed(2) + 'px'); c.ultL = l; }
          l += c.x;
        }
        const plegada = c.oculta && c.x < .6;
        if (plegada !== c.plegada) {
          c.plegada = plegada;
          c.celdas.forEach(td => td.classList.toggle('es-plegada', plegada));
        }
      });
      el.tabla.style.setProperty('--pi-total', total.toFixed(2) + 'px');
      if (arrastre && arrastre.tipo === 'mover' && arrastre.lam) colocaLamina();
      if (guiaCol) colocaGuia();
    }

    /* ── el bucle de resortes ──────────────────────────────────────── */
    let raf = 0, tPrev = 0;
    function despierta() { if (!raf) { tPrev = 0; raf = requestAnimationFrame(bucle); } }
    function bucle(t) {
      raf = 0;
      const dt = tPrev ? lim((t - tPrev) / 1000, .001, .034) : 1 / 60;
      tPrev = t;
      let mueve = false;
      cols.forEach(c => {
        if (quieto()) { c.x = c.tgt; c.v = 0; return; }
        if (Math.abs(c.tgt - c.x) > .2 || Math.abs(c.v) > 2) {
          const n = Math.ceil(dt * 240), hh = dt / n;
          for (let i = 0; i < n; i++) { c.v += (c.kk * (c.tgt - c.x) - c.cc * c.v) * hh; c.x += c.v * hh; }
          if (c.x < 0) { c.x = 0; if (c.v < 0) c.v = 0; }
          mueve = true;
        } else { c.x = c.tgt; c.v = 0; }
      });
      // el desplazamiento a un lado y a otro (la asomada tras fijar, el regreso de «Restablecer»)
      if (sc.activo) {
        if (quieto()) { sc.x = sc.tgt; sc.v = 0; }
        else {
          const n = Math.ceil(dt * 240), hh = dt / n;
          for (let i = 0; i < n; i++) { sc.v += (MODOS.scroll[0] * (sc.tgt - sc.x) - MODOS.scroll[1] * sc.v) * hh; sc.x += sc.v * hh; }
        }
        el.scroll.scrollLeft = sc.x;
        if (Math.abs(sc.tgt - sc.x) < .4 && Math.abs(sc.v) < 3) { sc.x = sc.tgt; el.scroll.scrollLeft = sc.x; sc.activo = false; sc.v = 0; } else mueve = true;
      }
      if (arrastre && arrastre.tipo === 'mover' && arrastre.lam) { autodesplaza(dt); evaluaMover(); }
      pinta();
      actualizaBorde();
      if (mueve || arrastre) raf = requestAnimationFrame(bucle); else { tPrev = 0; reposo(); }
    }
    function reposo() { cierraEstado(); }

    /* la sombra de lo fijo solo aparece cuando algo pasa por debajo */
    function actualizaBorde() {
      const d = nFijas() > 0 && el.scroll.scrollLeft > 1;
      if (d !== (raiz.dataset.desplaza === '1')) { if (d) raiz.dataset.desplaza = '1'; else delete raiz.dataset.desplaza; }
    }
    el.scroll.addEventListener('scroll', actualizaBorde, { passive: true });
    ['wheel', 'touchstart', 'pointerdown'].forEach(ev => el.scroll.addEventListener(ev, () => { sc.activo = false; }, { passive: true }));
    function llevaA(x) {
      sc.x = el.scroll.scrollLeft; sc.v = 0; sc.tgt = Math.max(0, x); sc.activo = true; despierta();
    }

    /* ── FLIP: cada columna viaja de su sitio viejo al nuevo ───────── */
    function izquierdas() {
      const m = {};
      cols.forEach(c => { if (c.x > 1) m[c.id] = c.celdas[0].getBoundingClientRect().left; });
      return m;
    }
    function flip(cambia) {
      const antes = izquierdas();
      cols.forEach(c => c.celdas.forEach(td => td.getAnimations().forEach(a => a.cancel())));
      cambia();
      aplicaOrden(); aplicaClases(); pinta();
      if (quieto()) return;
      const despues = izquierdas();
      cols.forEach(c => {
        if (!(c.id in antes) || !(c.id in despues)) return;
        const d = antes[c.id] - despues[c.id];
        if (Math.abs(d) < .5) return;
        c.celdas.forEach(td => {
          td.classList.add('es-vuela');
          const a = td.animate([{ transform: 'translateX(' + d.toFixed(1) + 'px)' }, { transform: 'translateX(0)' }], { duration: 760, easing: VUELO });
          a.onfinish = a.oncancel = () => td.classList.remove('es-vuela');
        });
      });
    }

    /* ── lo que cambia el estado ───────────────────────────────────── */
    const estadoPublico = () => ({
      orden: orden.slice(), anchos: Object.fromEntries(cols.map(c => [c.id, Math.round(c.w)])),
      fijas: orden.filter(id => porId[id].fija), ocultas: orden.filter(id => porId[id].oculta), densidad,
    });
    const sucio = () => orden.some((id, i) => id !== ORDEN0[i]) || cols.some(c => c.fija || c.oculta || Math.abs(c.w - c.w0) > .5) || densidad !== op.densidad;
    function cambio() {
      refresca();
      if (typeof op.alCambiar === 'function') op.alCambiar(estadoPublico());
    }
    function refresca() {
      const vis = visibles().length, fijas = nFijas();
      el.cuenta.textContent = vis + '/' + cols.length;
      if (vis < cols.length) el.cuenta.dataset.parcial = ''; else delete el.cuenta.dataset.parcial;
      el.menuCuenta.textContent = vis + ' de ' + cols.length + ' visibles';
      el.todas.disabled = vis === cols.length;
      el.estado.innerHTML = '<b>' + vis + '</b> de ' + cols.length + ' columnas · ' + (fijas ? '<b>' + fijas + '</b> ' + (fijas === 1 ? 'fija' : 'fijas') : 'ninguna fija') + ' · filas ' + DENSIDADES[densidad];
      cols.forEach(c => {
        const on = !c.oculta;
        c.item.setAttribute('aria-checked', on ? 'true' : 'false');
        if (c.fija) c.item.dataset.fija = ''; else delete c.item.dataset.fija;
        c.itemW.textContent = on ? Math.round(c.w) + ' px' : 'oculta';
        c.item.setAttribute('aria-disabled', on && vis === 1 ? 'true' : 'false');
      });
      cierraEstado();
    }
    function cierraEstado() {
      const b = el.restablece;
      if (b.dataset.e === 'listo') return;
      b.disabled = !sucio();
    }

    /* ── ancho ─────────────────────────────────────────────────────── */
    function fijaAncho(c, w, modo) {
      c.w = lim(w, c.min, c.max);
      if (!c.oculta) { c.tgt = c.w; setModo(c, modo || 'suelta'); despierta(); }
    }
    function anchoAjustado(c) {
      let m = 0;
      c.celdas.forEach((td, i) => {
        if (!i) { const t = td.querySelector('.pi-th-t'); m = Math.max(m, t.scrollWidth + 14 + 4 + 24 + 6 + 2); return; }
        const hijo = td.firstElementChild && td.firstElementChild.firstElementChild;
        if (hijo) m = Math.max(m, Math.max(hijo.scrollWidth, hijo.offsetWidth) + 28 + 2);
      });
      return lim(Math.ceil(m), c.min, c.max);
    }
    function ajusta(c, teclado) {
      if (c.oculta) return;
      const w = anchoAjustado(c);
      fijaAncho(c, w, 'suelta');
      marca(c);
      anuncia(c.nombre + ': ajustada al contenido, ' + Math.round(w) + ' píxeles');
      tarda(cambio, 50);
    }
    /* un destello azul en la columna: confirma qué se midió */
    function marca(c) {
      c.celdas.forEach(td => td.classList.add('es-sel'));
      tarda(() => { if (!arrastre || arrastre.id !== c.id) c.celdas.forEach(td => td.classList.remove('es-sel')); }, 720);
    }

    /* la guía sigue a la columna cuadro a cuadro (pinta() la reposiciona) mientras esté encendida */
    let guiaCol = null;
    function colocaGuia() {
      const c = guiaCol;
      if (!c) return;
      const t = el.tabla.getBoundingClientRect(), r = c.celdas[0].getBoundingClientRect();
      el.guia.style.transform = 'translateX(' + (r.right - t.left - 1).toFixed(1) + 'px)';
      const bruto = arrastre && arrastre.tipo === 'ancho' ? arrastre.bruto : c.w;
      const tope = bruto <= c.min ? 'min' : bruto >= c.max ? 'max' : '';
      const txt = Math.round(c.x) + ' px' + (tope === 'min' ? ' · mín.' : tope === 'max' ? ' · máx.' : '');
      if (el.guiaEt.textContent !== txt) el.guiaEt.textContent = txt;
      if (tope) el.guia.dataset.tope = ''; else delete el.guia.dataset.tope;
    }
    function enciendeGuia(c) {
      const yaOn = guiaCol === c && 'on' in el.guia.dataset;
      if (guiaCol && guiaCol !== c) apagaGuia(guiaCol);
      guiaCol = c;
      if (!yaOn) {
        const t = el.tabla.getBoundingClientRect(), r = c.celdas[0].getBoundingClientRect();
        el.guiaAnt.style.transform = 'translateX(' + (r.right - t.left - 1).toFixed(1) + 'px)';
      }
      colocaGuia();
      el.guia.dataset.on = ''; el.guiaAnt.dataset.on = '';
      c.celdas.forEach(td => td.classList.add('es-sel'));
      c.celdas[0].classList.add('es-agarra');
      despierta();
    }
    function apagaGuia(c) {
      if (guiaCol === c) guiaCol = null;
      delete el.guia.dataset.on; delete el.guiaAnt.dataset.on; delete el.guia.dataset.tope;
      c.celdas.forEach(td => td.classList.remove('es-sel'));
      c.celdas[0].classList.remove('es-agarra');
    }

    function iniciaAncho(e, c) {
      e.preventDefault();
      const ahora = performance.now();
      if (ultToque.id === c.id && ahora - ultToque.t < 380 && Math.hypot(e.clientX - ultToque.x, e.clientY - ultToque.y) < 10) {
        ultToque.t = -1e9; ajusta(c); return;
      }
      ultToque = { t: ahora, id: c.id, x: e.clientX, y: e.clientY };
      arrastre = { tipo: 'ancho', id: c.id, pid: e.pointerId, x0: e.clientX, w0: c.w, bruto: c.w, mueve: false, alvo: e.target };
      try { e.target.setPointerCapture(e.pointerId); } catch (_) { /* sin captura también funciona */ }
      raiz.dataset.arrastra = 'ancho';
      activa = c.id; roving();
      enciendeGuia(c);
      despierta();
    }
    function mueveAncho(e) {
      const a = arrastre, c = porId[a.id];
      const dx = e.clientX - a.x0;
      if (Math.abs(dx) > 1) a.mueve = true;
      a.bruto = a.w0 + dx;
      fijaAncho(c, a.bruto, 'libre');
    }
    function terminaAncho() {
      const a = arrastre, c = porId[a.id];
      arrastre = null;
      delete raiz.dataset.arrastra;
      apagaGuia(c);
      if (a.mueve) { anuncia(c.nombre + ': ' + Math.round(c.w) + ' píxeles'); cambio(); }
    }

    /* ── orden: la lámina ──────────────────────────────────────────── */
    function iniciaMover(e, c) {
      const th = c.celdas[0];
      const sr = el.scroll.getBoundingClientRect(), r = th.getBoundingClientRect();
      arrastre = { tipo: 'mover', id: c.id, pid: e.pointerId, x0: e.clientX, cx: e.clientX, vis0: r.left - sr.left, vis: r.left - sr.left, mueve: false, lam: null, orden0: orden.slice(), alvo: e.currentTarget };
      activa = c.id; roving();
      try { e.target.setPointerCapture(e.pointerId); } catch (_) { /* sin captura también funciona */ }
      despierta();
    }
    function levanta() {
      const a = arrastre, c = porId[a.id];
      const lam = h('div', 'pi-lamina'); lam.setAttribute('aria-hidden', 'true');
      const tr = el.tabla.getBoundingClientRect();
      lam.style.width = c.celdas[0].getBoundingClientRect().width + 'px';
      lam.style.height = tr.height + 'px';
      c.celdas.forEach((td, i) => {
        const k = td.cloneNode(true);
        k.removeAttribute('role'); k.removeAttribute('aria-hidden'); k.classList.remove('es-fija', 'es-borde', 'es-sel', 'es-vuela'); k.style.order = '';
        k.querySelectorAll('button').forEach(b => { b.tabIndex = -1; });
        k.style.height = td.getBoundingClientRect().height + 'px';
        lam.appendChild(k);
      });
      el.tabla.insertBefore(lam, el.guiaAnt);
      a.lam = lam; a.w = c.x;
      c.celdas.forEach(td => td.classList.add('es-hueco'));
      raiz.dataset.arrastra = 'mover';
      colocaLamina();
      if (!quieto()) lam.animate([
        { scale: 1, rotate: '0deg', boxShadow: '0 0 0 1.5px rgba(var(--pi-azul-rgb), 0), 0 0 0 0 rgba(var(--pi-sombra), 0)' },
        { scale: 1.014, rotate: '.45deg', boxShadow: getComputedStyle(lam).boxShadow },
      ], { duration: 520, easing: LEVANTA, fill: 'both' });
      else { lam.style.scale = '1.014'; lam.style.rotate = '.45deg'; }
      anuncia(c.nombre + ' levantada. Mueve el cursor para cambiar su sitio.');
    }
    function colocaLamina() {
      const a = arrastre, c = porId[a.id];
      const max = Math.max(0, el.scroll.clientWidth - c.x);
      a.vis = lim(a.vis0 + (a.cx - a.x0), 0, max);
      a.lam.style.translate = (a.vis + el.scroll.scrollLeft).toFixed(1) + 'px 0';
    }
    function autodesplaza(dt) {
      const a = arrastre, c = porId[a.id];
      if (c.fija) return;
      const r = el.scroll.getBoundingClientRect(), borde = 64;
      const pegado = orden.reduce((s, id) => s + (porId[id].fija ? porId[id].x : 0), 0);
      let v = 0;
      if (a.cx > r.right - borde) v = (a.cx - (r.right - borde)) / borde;
      else if (a.cx < r.left + pegado + borde) v = -((r.left + pegado + borde) - a.cx) / borde;
      if (v) el.scroll.scrollLeft += lim(v, -1, 1) * 15 * dt * 60;
      colocaLamina();
    }
    /* a qué hueco corresponde la lámina: cuántas de las otras columnas tienen su centro a la izquierda del suyo.
       Se cuenta con el diseño sin la columna levantada, así que no hay zona muerta al cambiar de sitio. */
    function evaluaMover() {
      const a = arrastre, c = porId[a.id];
      const otras = orden.filter(id => id !== c.id && porId[id].fija === c.fija && !porId[id].oculta);
      let acc = c.fija ? 0 : orden.reduce((s, id) => s + (porId[id].fija && !porId[id].oculta ? porId[id].x : 0), 0);
      const centro = (c.fija ? a.vis : a.vis + el.scroll.scrollLeft) + c.x / 2;
      let n = 0;
      otras.forEach(id => { const w = porId[id].x; if (centro > acc + w / 2) n++; acc += w; });
      const sin = orden.filter(id => id !== c.id);
      let pos;
      if (!otras.length) return;
      if (n < otras.length) pos = sin.indexOf(otras[n]); else pos = sin.indexOf(otras[otras.length - 1]) + 1;
      const nuevo = sin.slice(); nuevo.splice(pos, 0, c.id);
      if (nuevo.some((id, i) => id !== orden[i])) {
        flip(() => { orden = nuevo; });
        anuncia(c.nombre + ': posición ' + (visibles().indexOf(c.id) + 1) + ' de ' + visibles().length);
      }
    }
    function mueveMover(e) {
      const a = arrastre;
      a.cx = e.clientX;
      if (!a.mueve) {
        if (Math.abs(e.clientX - a.x0) < 5) return;
        a.mueve = true; levanta();
      }
      colocaLamina(); evaluaMover();
    }
    function terminaMover(cancela) {
      const a = arrastre, c = porId[a.id];
      arrastre = null;
      delete raiz.dataset.arrastra;
      if (!a.lam) return;
      if (cancela && a.orden0.some((id, i) => id !== orden[i])) flip(() => { orden = a.orden0.slice(); });
      pinta();
      const tr = el.tabla.getBoundingClientRect(), r = c.celdas[0].getBoundingClientRect();
      const destino = r.left - tr.left;
      const lam = a.lam;
      const fin = () => { lam.remove(); c.celdas.forEach(td => td.classList.remove('es-hueco')); };
      if (quieto()) { fin(); } else {
        const desde = getComputedStyle(lam);
        const an = lam.animate([
          { translate: desde.translate, scale: desde.scale, rotate: desde.rotate, boxShadow: desde.boxShadow },
          { translate: destino.toFixed(1) + 'px 0', scale: 1, rotate: '0deg', boxShadow: '0 0 0 1.5px rgba(var(--pi-azul-rgb), .25), 0 10px 18px -10px rgba(var(--pi-sombra), .18)' },
        ], { duration: 640, easing: ATERRIZA, fill: 'forwards' });
        an.onfinish = fin; an.oncancel = fin;
      }
      if (!cancela) {
        const sigue = orden.some((id, i) => id !== a.orden0[i]);
        if (sigue) { anuncia(c.nombre + ' en la posición ' + (visibles().indexOf(c.id) + 1) + ' de ' + visibles().length); cambio(); }
      } else anuncia('Movimiento cancelado');
    }

    /* ── los eventos del puntero ──────────────────────────────────── */
    el.tabla.addEventListener('pointerdown', e => {
      if (arrastre || (e.pointerType === 'mouse' && e.button !== 0)) return;
      const borde = e.target.closest('.pi-borde');
      if (borde) { iniciaAncho(e, porId[borde.closest('.pi-c').dataset.col]); return; }
      if (e.target.closest('.pi-pin')) return;
      const th = e.target.closest('.pi-th');
      if (th) iniciaMover(e, porId[th.closest('.pi-c').dataset.col]);
    });
    el.tabla.addEventListener('pointermove', e => {
      if (!arrastre || e.pointerId !== arrastre.pid) return;
      if (arrastre.tipo === 'ancho') mueveAncho(e); else mueveMover(e);
    });
    const suelta = e => {
      if (!arrastre || e.pointerId !== arrastre.pid) return;
      if (arrastre.tipo === 'ancho') terminaAncho(); else terminaMover(false);
    };
    el.tabla.addEventListener('pointerup', suelta);
    el.tabla.addEventListener('pointercancel', e => {
      if (!arrastre || e.pointerId !== arrastre.pid) return;
      if (arrastre.tipo === 'ancho') terminaAncho(); else terminaMover(true);
    });
    el.tabla.addEventListener('click', e => {
      const pin = e.target.closest('.pi-pin');
      if (pin) { const c = porId[pin.closest('.pi-c').dataset.col]; fija(c.id, !c.fija); }
    });
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape' || !arrastre) return;
      if (arrastre.tipo === 'ancho') { const c = porId[arrastre.id]; fijaAncho(c, arrastre.w0, 'suelta'); terminaAncho(); } else terminaMover(true);
    });

    /* ── fijar, ocultar, mover con teclado ─────────────────────────── */
    function fija(id, v) {
      const c = porId[id];
      if (c.fija === v || c.oculta) return;
      flip(() => {
        c.fija = v;
        const sin = orden.filter(k => k !== id);
        sin.splice(sin.filter(k => porId[k].fija).length, 0, id);   // al final de lo fijo, o al principio de lo móvil
        orden = sin;
      });
      refresca();
      if (v && !quieto()) {
        const pb = c.celdas[0].querySelector('.pi-pin');
        pb.classList.remove('es-clava'); void pb.offsetWidth; pb.classList.add('es-clava');
        tarda(() => pb.classList.remove('es-clava'), 900);
      }
      anuncia(c.nombre + (v ? ': fijada a la izquierda' : ': suelta'));
      if (v && op.empujaAlFijar) {
        const max = el.scroll.scrollWidth - el.scroll.clientWidth;
        if (max > 40 && el.scroll.scrollLeft < 4 && !quieto()) {
          tarda(() => llevaA(Math.min(max, 150)), 520);
          tarda(() => llevaA(0), 1500);
        }
      }
      if (typeof op.alCambiar === 'function') op.alCambiar(estadoPublico());
    }
    function oculta(id, v) {
      const c = porId[id];
      if (c.oculta === v) return false;
      if (v && visibles().length <= 1) return false;
      c.oculta = v;
      c.tgt = v ? 0 : c.w; setModo(c, v ? 'pliega' : 'abre');
      aplicaClases(); despierta();
      refresca();
      anuncia(c.nombre + (v ? ': oculta' : ': visible'));
      if (typeof op.alCambiar === 'function') op.alCambiar(estadoPublico());
      return true;
    }
    function mueve(id, pos) {
      const c = porId[id];
      const grupo = orden.filter(k => porId[k].fija === c.fija && k !== id);
      const i = lim(pos, 0, grupo.length);
      const sin = orden.filter(k => k !== id);
      const idx = i < grupo.length ? sin.indexOf(grupo[i]) : sin.indexOf(grupo[grupo.length - 1]) + 1;
      const nuevo = sin.slice(); nuevo.splice(idx, 0, id);
      if (!nuevo.some((k, j) => k !== orden[j])) return;
      flip(() => { orden = nuevo; });
      refresca();
      anuncia(c.nombre + ': posición ' + (visibles().indexOf(id) + 1) + ' de ' + visibles().length);
      if (typeof op.alCambiar === 'function') op.alCambiar(estadoPublico());
    }
    function mueveVecina(c, dir) {
      const grupo = orden.filter(k => porId[k].fija === c.fija && !porId[k].oculta);
      const i = grupo.indexOf(c.id), j = i + dir;
      if (j < 0 || j >= grupo.length) { anuncia(c.nombre + ': ya está en el extremo' + (c.fija ? ' de lo fijo' : '')); return; }
      mueve(c.id, orden.filter(k => porId[k].fija === c.fija && k !== c.id).indexOf(grupo[j]) + (dir > 0 ? 1 : 0));
    }

    el.tabla.addEventListener('focusin', e => {
      const th = e.target.closest && e.target.closest('.pi-th');
      if (th) { activa = th.closest('.pi-c').dataset.col; roving(); }
    });
    el.tabla.addEventListener('keydown', e => {
      const th = e.target.closest && e.target.closest('.pi-th');
      if (!th) return;
      const c = porId[th.closest('.pi-c').dataset.col];
      const vis = visibles();
      const i = vis.indexOf(c.id);
      const enfoca = id => { porId[id].celdas[0].querySelector('.pi-th').focus(); };
      let usada = true;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const dir = e.key === 'ArrowRight' ? 1 : -1;
        if (e.altKey) mueveVecina(c, dir);
        else if (e.shiftKey) {
          const w = lim(c.w + dir * 16, c.min, c.max);
          fijaAncho(c, w, 'suelta');
          enciendeGuia(c);
          clearTimeout(c.apagaId);
          c.apagaId = tarda(() => { if (!arrastre) apagaGuia(c); }, 1300);
          anuncia(c.nombre + ': ' + Math.round(w) + ' píxeles');
          clearTimeout(c.cambioId); c.cambioId = tarda(cambio, 300);
        } else if (vis[i + dir]) enfoca(vis[i + dir]);
      } else if (e.key === 'Home' && !e.shiftKey) enfoca(vis[0]);
      else if (e.key === 'End' && !e.shiftKey) enfoca(vis[vis.length - 1]);
      else if (e.key === 'p' || e.key === 'P') fija(c.id, !c.fija);
      else if (e.key === 'h' || e.key === 'H') {
        if (vis.length > 1) { const sig = vis[i + 1] || vis[i - 1]; oculta(c.id, true); enfoca(sig); } else anuncia('Tiene que quedar al menos una columna visible');
      } else if (e.key === 'Enter' || e.key === ' ') ajusta(c, true);
      else usada = false;
      if (usada) e.preventDefault();
    });
    // al pulsar la chincheta con el teclado nunca pasa (tabindex -1): la tecla P hace lo mismo desde el encabezado

    /* ── densidad ──────────────────────────────────────────────────── */
    function poneDensidad(d, silencio) {
      if (!(d in POS)) return;
      densidad = d;
      raiz.dataset.densidadAct = d;
      el.seg.style.setProperty('--pos', POS[d]);
      el.seg.querySelectorAll('[role="radio"]').forEach(b => {
        const on = b.dataset.d === d;
        b.setAttribute('aria-checked', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1;
      });
      if (!silencio) { refresca(); anuncia('Filas ' + DENSIDADES[d]); if (typeof op.alCambiar === 'function') op.alCambiar(estadoPublico()); }
    }
    el.seg.addEventListener('click', e => { const b = e.target.closest('[role="radio"]'); if (b) poneDensidad(b.dataset.d); });
    el.seg.addEventListener('keydown', e => {
      const radios = Array.from(el.seg.querySelectorAll('[role="radio"]'));
      const i = radios.findIndex(b => b.getAttribute('aria-checked') === 'true');
      let j = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') j = (i + 1) % radios.length;
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') j = (i + radios.length - 1) % radios.length;
      if (j < 0) return;
      e.preventDefault(); poneDensidad(radios[j].dataset.d); radios[j].focus();
    });

    /* ── restablecer ───────────────────────────────────────────────── */
    function restablece() {
      if (arrastre) return;
      flip(() => {
        orden = ORDEN0.slice();
        cols.forEach(c => {
          c.fija = false; c.w = c.w0;
          const estabaOculta = c.oculta; c.oculta = false;
          c.tgt = c.w0; setModo(c, estabaOculta ? 'abre' : 'suelta');
        });
      });
      poneDensidad(op.densidad, true);
      llevaA(0);
      despierta();
      activa = cols[0].id; roving();
      refresca();
      const b = el.restablece;
      b.dataset.e = 'listo'; b.disabled = false;
      b.classList.remove('is-bota'); void b.offsetWidth; b.classList.add('is-bota');
      anuncia('Tabla restablecida: cada columna en su sitio');
      clearTimeout(listoId);
      listoId = tarda(() => { b.dataset.e = 'reposo'; cierraEstado(); }, 1900);
      if (typeof op.alCambiar === 'function') op.alCambiar(estadoPublico());
    }
    el.restablece.addEventListener('click', () => {
      if (el.restablece.dataset.e === 'listo') return;
      restablece();
    });
    // si algo cambia mientras se muestra el ✓, vuelve a su estado normal
    const vuelveReposo = () => { if (el.restablece.dataset.e === 'listo') { clearTimeout(listoId); el.restablece.dataset.e = 'reposo'; cierraEstado(); } };

    /* ── el menú de columnas ──────────────────────────────────────── */
    const items = () => cols.map(c => c.item);
    function abreMenu(foco) {
      if (menuAbierto) return;
      clearTimeout(cierraId);
      menuAbierto = true;
      el.menu.hidden = false;
      el.columnas.setAttribute('aria-expanded', 'true');
      void el.menu.offsetWidth;
      el.menu.dataset.abierto = '';
      menuFoco = foco === 'ultimo' ? cols.length - 1 : 0;
      items().forEach((b, i) => { b.tabIndex = i === menuFoco ? 0 : -1; });
      if (foco) items()[menuFoco].focus({ preventScroll: true });
    }
    function cierraMenu(devuelve) {
      if (!menuAbierto) return;
      menuAbierto = false;
      delete el.menu.dataset.abierto;
      el.columnas.setAttribute('aria-expanded', 'false');
      cierraId = setTimeout(() => { if (!menuAbierto) el.menu.hidden = true; }, quieto() ? 0 : 520);
      if (devuelve) el.columnas.focus();
    }
    el.columnas.addEventListener('click', e => { if (menuAbierto) cierraMenu(false); else abreMenu(e.detail === 0 ? 'primero' : false); });
    el.columnas.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { e.preventDefault(); abreMenu('primero'); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); abreMenu('ultimo'); }
      else if (e.key === 'Escape' && menuAbierto) { e.stopPropagation(); cierraMenu(false); }
    });
    el.menuLista.addEventListener('click', e => {
      const b = e.target.closest('.pi-item'); if (!b) return;
      const c = porId[b.dataset.id];
      vuelveReposo();
      if (!oculta(c.id, !c.oculta)) {
        if (c.item.getAttribute('aria-disabled') === 'true') {
          b.classList.remove('is-no'); void b.offsetWidth; b.classList.add('is-no');
          anuncia('Tiene que quedar al menos una columna visible');
        }
      }
      menuFoco = cols.indexOf(c); items().forEach((x, i) => { x.tabIndex = i === menuFoco ? 0 : -1; });
    });
    el.menuLista.addEventListener('keydown', e => {
      const lista = items(); let i = lista.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') i = (i + 1) % lista.length;
      else if (e.key === 'ArrowUp') i = (i + lista.length - 1) % lista.length;
      else if (e.key === 'Home') i = 0; else if (e.key === 'End') i = lista.length - 1;
      else return;
      e.preventDefault(); menuFoco = i; lista.forEach((b, k) => { b.tabIndex = k === i ? 0 : -1; }); lista[i].focus();
    });
    el.menu.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.stopPropagation(); cierraMenu(true); }
      else if (e.key === 'Tab') cierraMenu(false);
    });
    el.todas.addEventListener('click', () => {
      vuelveReposo();
      cols.forEach(c => { if (c.oculta) oculta(c.id, false); });
    });
    document.addEventListener('pointerdown', e => { if (menuAbierto && !e.target.closest('.pi-menu-env')) cierraMenu(false); });

    /* ── la puesta en marcha ──────────────────────────────────────── */
    // cualquier cambio que no sea «Restablecer» apaga el ✓ de «Restablecido»
    el.tabla.addEventListener('pointerdown', vuelveReposo);
    el.tabla.addEventListener('keydown', vuelveReposo);
    el.seg.addEventListener('click', vuelveReposo);

    construye();
    aplicaOrden();
    aplicaClases();
    poneDensidad(densidad, true);
    cols.forEach(c => { c.ultX = -1; });
    pinta();
    refresca();
    actualizaBorde();

    return {
      mueve, oculta, fija, restablece, estado: estadoPublico,
      ancho: (id, px) => { const c = porId[id]; if (!c) return; fijaAncho(c, px, 'suelta'); marca(c); cambio(); },
      densidad: d => poneDensidad(d),
      ajusta: id => { const c = porId[id]; if (c) ajusta(c); },
    };
  }

  window.Pilar = Pilar;
})();
