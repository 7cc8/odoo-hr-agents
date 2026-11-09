/* =====================================================================
   Galleta · Moxen
   Un aviso de cookies bien hecho y que cumple: tres botones con el
   mismo peso (Rechazar · Personalizar · Aceptar todas), las categorías
   opcionales apagadas de partida y las necesarias bloqueadas con su
   candado. «Personalizar» despliega la tarjeta con un resorte, sin
   saltos de alto, y cada categoría abre su descripción. Al guardar, la
   tarjeta se encoge y se vuelve un botón redondo abajo a la izquierda
   con una galleta que gira al llegar, suelta migas, muestra un ✓ y
   lleva un mordisco por cada categoría rechazada. Al pulsarla, el aviso
   vuelve a abrirse con la misma transformación al revés.

     const g = Galleta(document.querySelector('[data-galleta]'), {
       categorias: [{ id: 'estadistica', nombre: 'Estadística', texto: '…' }, …],
       recordar: true,          // guarda la elección y no vuelve a preguntar
       clave: 'mx-cookies',     // la clave en localStorage
       alGuardar: prefs => { if (prefs.estadistica) cargaAnalitica(); },
     });
     g.abre();      g.prefs();   // → { necesarias: true, estadistica: false, … }

   Teclado: el foco queda dentro del aviso desplegado, Esc vuelve a la
   vista simple y los interruptores son role="switch" con aria-checked.
   Todo lo que se mueve es transform, opacity o clip-path. Sin dependencias.
   ===================================================================== */
(function () {
  'use strict';

  /* Un resorte amortiguado por cada cosa que se mueve, con el paso real
     del cuadro (dt): así va igual a 60 que a 120 Hz. */
  const resorte = (x, k, c) => ({ x, v: 0, meta: x, k, c });
  function avanza(r, dt) { r.v += (r.k * (r.meta - r.x) - r.c * r.v) * dt; r.x += r.v * dt; }
  const parado = (r, e) => Math.abs(r.meta - r.x) < e && Math.abs(r.v) < e;
  const lerp = (a, b, t) => a + (b - a) * t;
  const sujeta = (v, a, b) => Math.max(a, Math.min(b, v));
  const suma = a => a.reduce((s, v) => s + v, 0);

  // azar con semilla: las migas caen igual cada vez
  function azar(a) {
    return function () {
      a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  const CATEGORIAS = [
    { id: 'necesarias', nombre: 'Necesarias', texto: 'Mantienen tu sesión, el carrito y la seguridad del sitio. Sin ellas, nada funciona.', fija: true },
    { id: 'preferencias', nombre: 'Preferencias', texto: 'Recuerdan lo que elegiste, como el idioma o el tema, para tu próxima visita.' },
    { id: 'estadistica', nombre: 'Estadística', texto: 'Cuentan visitas y clics de forma anónima para saber qué mejorar.' },
    { id: 'publicidad', nombre: 'Publicidad', texto: 'Muestran anuncios según lo que te interesa, aquí y en otros sitios.' },
  ];

  /* ── la galleta ─────────────────────────────────────────────────── */
  /* Un disco de borde irregular; las chispas de chocolate y los
     mordiscos son agujeros de la misma máscara, así dejan ver el fondo
     en los dos temas. Cada mordisco son tres círculos solapados (el
     borde festoneado de los dientes) que entran desde fuera. */
  const MASA = 'M29.48 16C29.59 17.45 28.87 19.08 28.27 20.47C27.67 21.85 26.88 23.22 25.88 24.29C24.89 25.36 23.54 26.03 22.29 26.89C21.04 27.75 19.79 29.15 18.37 29.44C16.95 29.72 15.24 28.99 13.78 28.6C12.31 28.22 10.86 27.83 9.59 27.1C8.32 26.38 7.21 25.34 6.15 24.27C5.08 23.19 3.64 22.04 3.2 20.66C2.75 19.28 3.37 17.51 3.48 16C3.59 14.49 3.42 12.98 3.84 11.57C4.25 10.17 5.06 8.78 5.97 7.58C6.87 6.38 7.97 5 9.29 4.38C10.6 3.75 12.35 4.06 13.85 3.83C15.36 3.6 16.84 2.87 18.29 3C19.75 3.13 21.29 3.83 22.59 4.59C23.88 5.35 25.22 6.36 26.06 7.56C26.9 8.75 27.06 10.36 27.63 11.77C28.2 13.17 29.37 14.55 29.48 16Z';
  const CHISPAS = [[10.6, 11, 2], [19.8, 9.8, 1.5], [15.2, 16.4, 1.8], [21.6, 18.6, 1.6], [10.4, 20.4, 1.4], [16.4, 23.6, 1.2], [24.4, 13.2, .7], [7.4, 15.6, .6], [13.4, 6.6, .6]];
  const MORDISCOS = [-.7, .42, 2.7];   // dónde muerde cada rechazo, en radianes desde el centro
  const P = n => n.toFixed(2);

  function galleta(id, mordiscos) {
    const chispas = CHISPAS.map(c => '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="' + c[2] + '"/>').join('');
    const bocas = mordiscos ? MORDISCOS.map((a, i) => {
      const uno = (d, da, r) => '<circle cx="' + P(16 + Math.cos(a + da) * d) + '" cy="' + P(16 + Math.sin(a + da) * d) + '" r="' + r + '"/>';
      return '<g class="gt-mordida" data-i="' + i + '" style="--dx:' + P(Math.cos(a) * 7) + 'px;--dy:' + P(Math.sin(a) * 7) + 'px">' +
        uno(12.6, -.27, 2.7) + uno(12.4, 0, 2.8) + uno(12.6, .27, 2.7) + '</g>';
    }).join('') : '';
    return '<svg class="gt-svg" viewBox="0 0 32 32" aria-hidden="true">' +
      '<defs><radialGradient id="' + id + '-g" cx=".42" cy=".38" r=".7"><stop offset="0" class="gt-masa-1"/><stop offset="1" class="gt-masa-2"/></radialGradient>' +
      '<mask id="' + id + '-m" maskUnits="userSpaceOnUse" x="-4" y="-4" width="40" height="40"><rect x="-4" y="-4" width="40" height="40" fill="#fff"/>' +
      '<g fill="#000">' + chispas + bocas + '</g></mask></defs>' +
      '<path class="gt-masa" d="' + MASA + '" fill="url(#' + id + '-g)" mask="url(#' + id + '-m)"/></svg>';
  }

  let instancias = 0;

  function Galleta(raiz, opciones) {
    const o = Object.assign({ categorias: CATEGORIAS, recordar: true, clave: 'mx-cookies', alGuardar: null }, opciones);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const uid = 'gt' + (++instancias);
    const aviso = raiz.querySelector('.gt-aviso');
    const cabeza = raiz.querySelector('.gt-cabeza');
    const detalle = raiz.querySelector('.gt-detalle');
    const pie = raiz.querySelector('.gt-pie');
    const filaS = pie.querySelector('[data-vista="simple"]');
    const filaD = pie.querySelector('[data-vista="detalle"]');
    const personaliza = raiz.querySelector('[data-galleta-accion="personaliza"]');
    const icono = raiz.querySelector('.gt-icono');
    if (icono && !icono.firstChild) icono.innerHTML = galleta(uid + 'i', false);
    detalle.id = detalle.id || uid + '-detalle';
    personaliza.setAttribute('aria-controls', detalle.id);

    /* ── las categorías ───────────────────────────────────────────── */
    const cats = o.categorias.map((c, i) => {
      const caja = document.createElement('div');
      caja.className = 'gt-cat';
      caja.innerHTML =
        '<div class="gt-cat-fila">' +
          '<button class="gt-cat-nombre" type="button" aria-expanded="false" aria-controls="' + uid + '-d' + i + '">' +
            '<svg class="gt-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>' +
            '<span id="' + uid + '-n' + i + '"></span>' + (c.fija ? '<small>Siempre activas</small>' : '') +
          '</button>' +
          '<button class="gt-interruptor" type="button" role="switch" aria-labelledby="' + uid + '-n' + i + '"' + (c.fija ? ' aria-disabled="true"' : '') + '>' +
            '<span class="gt-riel"><span class="gt-perilla">' +
              (c.fija ? '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="11" width="12" height="9" rx="2.2"/><path d="M8.8 11V8.6a3.2 3.2 0 0 1 6.4 0V11"/></svg>' : '') +
            '</span></span>' +
          '</button>' +
        '</div>' +
        '<p class="gt-desc" id="' + uid + '-d' + i + '" aria-hidden="true"></p>';
      caja.querySelector('span[id]').textContent = c.nombre;
      caja.querySelector('.gt-desc').textContent = c.texto || '';
      detalle.appendChild(caja);
      const cat = {
        id: c.id, fija: !!c.fija, caja, activa: !!c.fija || !!c.activa,
        boton: caja.querySelector('.gt-cat-nombre'), interruptor: caja.querySelector('.gt-interruptor'),
        desc: caja.querySelector('.gt-desc'), h: resorte(0, 220, 26), abierta: false,
      };
      cat.interruptor.setAttribute('aria-checked', String(cat.activa));
      return cat;
    });

    /* ── la superficie y el botón flotante ────────────────────────── */
    /* La superficie es una capa de pantalla completa recortada con
       clip-path: el mismo recorte es la tarjeta (de cualquier alto) y el
       botón redondo, así la transformación de una en otra es continua.
       La sombra va en un filtro del contenedor y sigue al recorte. */
    const sup = document.createElement('div');
    sup.className = 'gt-superficie';
    sup.setAttribute('aria-hidden', 'true');
    sup.innerHTML = '<i></i>';
    raiz.insertBefore(sup, aviso);
    const supI = sup.firstChild;
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'gt-boton';
    boton.setAttribute('aria-label', 'Preferencias de cookies');
    boton.innerHTML = '<span class="gt-giro">' + galleta(uid + 'b', true) + '</span>' +
      '<span class="gt-migas" aria-hidden="true"></span>' +
      '<span class="gt-ok" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4.4 8.3l2.4 2.4 4.8-5" pathLength="1"/></svg></span>';
    raiz.appendChild(boton);
    const mordidas = Array.from(boton.querySelectorAll('.gt-mordida'));
    const migas = boton.querySelector('.gt-migas');
    const anuncio = document.createElement('p');
    anuncio.className = 'gt-oculto';
    anuncio.setAttribute('aria-live', 'polite');
    raiz.appendChild(anuncio);

    /* ── medidas ──────────────────────────────────────────────────── */
    /* La tarjeta se maqueta siempre entera (todo desplegado) y anclada
       abajo; lo que falta se recorta y la cabeza baja con transform.
       Así el alto nunca cambia de verdad: solo se mide al empezar y al
       cambiar el tamaño de la ventana. */
    const M = {};
    function mide() {
      const r = aviso.getBoundingClientRect(), b = boton.getBoundingClientRect(), cp = getComputedStyle(pie);
      const relleno = parseFloat(cp.paddingTop) + parseFloat(cp.paddingBottom);
      Object.assign(M, {
        x: r.left, y: r.top, w: r.width, h: r.height,
        vw: document.documentElement.clientWidth, vh: innerHeight,
        det: detalle.offsetHeight, desc: cats.map(c => c.desc.offsetHeight),
        pie: pie.offsetHeight, pieS: filaS.offsetHeight + relleno, pieD: filaD.offsetHeight + relleno,
        bx: b.left, by: b.top, bw: b.width, radio: parseFloat(getComputedStyle(raiz).getPropertyValue('--gt-radio')) || 22,
      });
      M.filas = M.det - suma(M.desc);
      d.meta = modo === 'detalle' ? M.filas : 0;
      p.meta = modo === 'detalle' ? M.pieD : M.pieS;
      cats.forEach((c, i) => { c.h.meta = c.abierta ? M.desc[i] : 0; });
      // al cambiar de tamaño todo salta a su sitio, sin viajar
      [d, p].concat(cats.map(c => c.h)).forEach(s => { s.x = s.meta; s.v = 0; });
    }

    // lo visible del detalle (d), de cada descripción (h) y del pie (p)
    const d = resorte(0, 170, 21), p = resorte(0, 170, 21);
    // la transformación: el tamaño (ms) llega antes que la posición (mp)
    const ms = resorte(0, 150, 23), mp = resorte(0, 90, 15);
    let modo = 'simple', llego = true, relojes = [];

    /* ── el dibujo ────────────────────────────────────────────────── */
    function pinta() {
      const V = d.x + suma(cats.map(c => c.h.x));
      const sobra = (M.det - V) + (M.pie - p.x);           // lo que la cabeza baja
      const tx = M.x, ty = M.y + sobra, tw = M.w, th = M.h - sobra;
      // de la tarjeta al círculo: el tamaño con ms, el centro con mp
      const s = ms.x, q = mp.x;
      const w = lerp(tw, M.bw, s), h = lerp(th, M.bw, s);
      const x = lerp(tx + tw / 2, M.bx + M.bw / 2, q) - w / 2, y = lerp(ty + th / 2, M.by + M.bw / 2, q) - h / 2;
      // el radio crece antes que el tamaño: de tarjeta a píldora y de píldora a círculo
      const r = Math.min(lerp(M.radio, Math.min(w, h) / 2, Math.pow(s, 1.4)), w / 2, h / 2);
      supI.style.clipPath = 'inset(' + P(y) + 'px ' + P(M.vw - x - w) + 'px ' + P(M.vh - y - h) + 'px ' + P(x) + 'px round ' + P(r) + 'px)';
      // el contenido se recorta con la misma forma y se apaga antes de achicarse mucho
      aviso.style.clipPath = 'inset(' + P(Math.max(0, y - M.y)) + 'px ' + P(Math.max(0, M.x + M.w - x - w)) + 'px ' +
        P(Math.max(0, M.y + M.h - y - h)) + 'px ' + P(Math.max(0, x - M.x)) + 'px round ' + P(r) + 'px)';
      // al irse se apaga pronto; al volver aparece solo cuando la tarjeta ya casi está
      const op = modo === 'galleta' ? 1.3 - s * 2.6 : (.16 - Math.max(s, q)) / .12;
      aviso.style.opacity = sujeta(op, 0, 1).toFixed(3);

      cabeza.style.transform = 'translate3d(0,' + P(sobra) + 'px,0)';
      detalle.style.transform = 'translate3d(0,' + P(sobra) + 'px,0)';
      detalle.style.clipPath = 'inset(0 0 ' + P(Math.max(0, M.det - V)) + 'px 0)';
      // cada categoría sube lo que no se ve de las descripciones de arriba
      let arriba = 0;
      const u = M.filas ? d.x / M.filas : 0;
      cats.forEach((c, i) => {
        c.caja.style.transform = arriba ? 'translate3d(0,' + P(-arriba) + 'px,0)' : '';
        c.caja.style.opacity = sujeta(u * 1.6 - i * .14, 0, 1).toFixed(3);
        const falta = Math.max(0, M.desc[i] - c.h.x);
        c.desc.style.clipPath = 'inset(0 0 ' + P(falta) + 'px 0)';
        c.desc.style.opacity = M.desc[i] ? sujeta(c.h.x / M.desc[i] * 1.4 - .3, 0, 1).toFixed(3) : 0;
        c.desc.style.visibility = c.h.x < .5 && !c.abierta ? 'hidden' : '';
        arriba += falta;
      });
    }

    /* ── el bucle de los resortes ─────────────────────────────────── */
    let raf = 0, previo = 0;
    function anda() { if (!raf) { previo = 0; raf = requestAnimationFrame(cuadro); } }
    function cuadro(t) {
      const dt = previo ? Math.min(1 / 30, (t - previo) / 1000) : 0;
      previo = t;
      const todos = [d, p, ms, mp].concat(cats.map(c => c.h));
      let quieto = true;
      todos.forEach(s => {
        if (reduce) { s.x = s.meta; s.v = 0; return; }
        avanza(s, dt);
        if (parado(s, s === ms || s === mp ? .002 : .3)) { s.x = s.meta; s.v = 0; } else quieto = false;
      });
      // la galleta llega: el tamaño ya es el del botón y casi está en su sitio
      if (modo === 'galleta' && !llego && ms.x > .93 && mp.x > .9) llega();
      pinta();
      raf = quieto ? 0 : requestAnimationFrame(cuadro);
    }

    /* ── las vistas ───────────────────────────────────────────────── */
    function despliega(abre) {
      if (modo === 'galleta' || (modo === 'detalle') === abre) return;
      modo = abre ? 'detalle' : 'simple';
      d.meta = abre ? M.filas : 0;
      p.meta = abre ? M.pieD : M.pieS;
      if (!abre) cats.forEach(c => descripcion(c, false));
      raiz.classList.toggle('is-detalle', abre);
      detalle.inert = !abre; filaS.inert = abre; filaD.inert = !abre;
      personaliza.setAttribute('aria-expanded', String(abre));
      aviso.setAttribute('aria-modal', String(abre));
      anda();
    }

    function descripcion(c, abre) {
      c.abierta = abre;
      c.h.meta = abre ? M.desc[cats.indexOf(c)] : 0;
      c.boton.setAttribute('aria-expanded', String(abre));
      c.desc.setAttribute('aria-hidden', String(!abre));
      c.caja.classList.toggle('is-abierta', abre);
      anda();
    }

    function pon(c, si) {
      if (c.fija || c.activa === si) return;
      c.activa = si;
      c.interruptor.setAttribute('aria-checked', String(si));
    }

    const prefs = () => cats.reduce((r, c) => (r[c.id] = c.activa, r), {});

    /* Guardar: «acepta» y «rechaza» mueven antes los interruptores (si
       se ven, en cascada) y luego la tarjeta se vuelve galleta. */
    function guarda(como) {
      if (modo === 'galleta') return;
      const opcionales = cats.filter(c => !c.fija);
      let espera = 0;
      if (como === 'acepta' || como === 'rechaza') {
        const si = como === 'acepta';
        const cambian = opcionales.filter(c => c.activa !== si);
        if (modo === 'detalle' && !reduce && cambian.length) {
          cambian.forEach((c, i) => relojes.push(setTimeout(() => pon(c, si), i * 80)));
          espera = cambian.length * 80 + 260;
        } else cambian.forEach(c => pon(c, si));
      }
      relojes.push(setTimeout(() => {
        const r = prefs();
        try { if (o.recordar) localStorage.setItem(o.clave, JSON.stringify(r)); } catch (e) { /* sin almacenamiento: no se recuerda */ }
        if (o.alGuardar) o.alGuardar(r);
        encoge();
      }, espera));
    }

    function encoge(sinViaje) {
      const enAviso = aviso.contains(document.activeElement);
      modo = 'galleta';
      // la fila de botones no cambia mientras la tarjeta se va: se cambia al volver
      raiz.classList.add('is-galleta');
      aviso.inert = true;
      llego = false;
      // un mordisco por cada categoría rechazada (vuelven a su sitio, fuera de la galleta)
      mordidas.forEach(m => m.classList.remove('is-mordida'));
      boton.classList.remove('is-llega', 'is-ok');
      ms.meta = mp.meta = 1;
      const rechazadas = cats.filter(c => !c.fija && !c.activa).length;
      anuncio.textContent = 'Preferencias guardadas' + (rechazadas ? ': ' + rechazadas + (rechazadas === 1 ? ' categoría rechazada' : ' categorías rechazadas') : '') + '.';
      if (sinViaje) { ms.x = mp.x = 1; llega(true); pinta(); }
      else anda();
      if (enAviso) boton.focus({ preventScroll: true });
    }

    /* El momento: la galleta gira al llegar, el ✓ asoma un instante y
       cada categoría rechazada se lleva un mordisco, con sus migas. */
    function llega(quieta) {
      llego = true;
      const rechazos = cats.filter(c => !c.fija && !c.activa).length;
      boton.classList.toggle('is-quieta', !!quieta);
      boton.classList.add('is-llega');
      if (quieta) { mordidas.slice(0, rechazos).forEach(m => m.classList.add('is-mordida')); return; }
      if (!reduce) suelta(-Math.PI / 2, 5, 1.6);
      relojes.push(setTimeout(() => boton.classList.add('is-ok'), 140));
      mordidas.slice(0, rechazos).forEach((m, i) => relojes.push(setTimeout(() => {
        m.classList.add('is-mordida');
        if (!reduce) suelta(MORDISCOS[i], 7, 1);
      }, 380 + i * 260)));
      relojes.push(setTimeout(() => boton.classList.remove('is-ok'), 1250));
    }

    // las migas: saltan desde el borde y caen con gravedad (Web Animations)
    const azarMigas = azar(7);
    function suelta(angulo, n, fuerza) {
      const c = M.bw / 2, k = (M.bw - 24) / 32;   // la galleta: 12 px de aire por lado, 32 unidades
      for (let i = 0; i < n; i++) {
        const a = angulo + (azarMigas() - .5) * 1.5;
        const x0 = c + Math.cos(angulo) * 12.5 * k, y0 = c + Math.sin(angulo) * 12.5 * k;
        const v = (70 + azarMigas() * 90) * fuerza, vx = Math.cos(a) * v, vy = Math.sin(a) * v - 90;
        const giro = (azarMigas() - .5) * 540, dura = .62 + azarMigas() * .3, lado = 2 + azarMigas() * 2.6;
        const miga = document.createElement('i');
        miga.style.width = miga.style.height = P(lado) + 'px';
        miga.style.left = P(x0 - lado / 2) + 'px'; miga.style.top = P(y0 - lado / 2) + 'px';
        migas.appendChild(miga);
        const pasos = [];
        for (let j = 0; j <= 8; j++) {
          const t = dura * j / 8;
          pasos.push({ transform: 'translate(' + P(vx * t) + 'px,' + P(vy * t + 560 * t * t) + 'px) rotate(' + P(giro * t) + 'deg)', opacity: j < 5 ? 1 : 1 - (j - 4) / 4 });
        }
        miga.animate(pasos, { duration: dura * 1000, easing: 'linear', fill: 'forwards' }).onfinish = () => miga.remove();
      }
    }

    // abrir de nuevo: el botón vuelve a ser tarjeta, en su vista simple
    function abre() {
      if (modo !== 'galleta') return;
      relojes.forEach(clearTimeout); relojes = [];
      const enBoton = document.activeElement === boton;
      modo = 'simple';
      raiz.classList.remove('is-galleta', 'is-detalle');
      boton.classList.remove('is-llega', 'is-ok', 'is-quieta');
      cats.forEach(c => descripcion(c, false));
      [d, ...cats.map(c => c.h)].forEach(s => { s.x = s.meta = 0; s.v = 0; });
      p.x = p.meta = M.pieS; p.v = 0;
      detalle.inert = true; filaS.inert = false; filaD.inert = true; aviso.inert = false;
      personaliza.setAttribute('aria-expanded', 'false');
      aviso.setAttribute('aria-modal', 'false');
      ms.meta = mp.meta = 0;
      anuncio.textContent = '';
      anda();
      if (enBoton) filaS.querySelector('button').focus({ preventScroll: true });
    }

    /* ── ratón, dedo y teclado ────────────────────────────────────── */
    raiz.addEventListener('click', e => {
      const accion = e.target.closest('[data-galleta-accion]');
      if (accion) {
        const a = accion.dataset.galletaAccion;
        if (a === 'personaliza') {
          despliega(true);
          cats[0].boton.focus({ preventScroll: true });
        } else guarda(a);
        return;
      }
      const cat = cats.find(c => c.boton.contains(e.target) || c.interruptor.contains(e.target));
      if (!cat) return;
      if (cat.boton.contains(e.target)) descripcion(cat, !cat.abierta);
      else if (cat.fija) {
        // la bloqueada no se mueve: el candado se sacude
        cat.interruptor.classList.remove('is-no'); void cat.interruptor.offsetWidth; cat.interruptor.classList.add('is-no');
      } else pon(cat, !cat.activa);
    });
    boton.addEventListener('click', abre);

    aviso.addEventListener('keydown', e => {
      if (e.key === 'Escape' && modo === 'detalle') {
        e.preventDefault();
        despliega(false);
        personaliza.focus({ preventScroll: true });
      } else if (e.key === 'Tab' && modo === 'detalle') {
        // el foco da la vuelta dentro del aviso desplegado
        const lista = Array.from(aviso.querySelectorAll('a[href], button')).filter(b => !b.closest('[inert]'));
        const i = lista.indexOf(document.activeElement);
        if (e.shiftKey ? i <= 0 : i === lista.length - 1) {
          e.preventDefault();
          lista[e.shiftKey ? lista.length - 1 : 0].focus();
        }
      }
    });

    let cambio = 0;
    addEventListener('resize', () => { clearTimeout(cambio); cambio = setTimeout(() => { mide(); pinta(); }, 100); });

    /* ── al empezar ───────────────────────────────────────────────── */
    detalle.inert = true; filaD.inert = true;
    mide();
    pinta();
    // con la tipografía cargada cambian los altos: se mide otra vez
    if (document.fonts) document.fonts.ready.then(() => { mide(); pinta(); });
    // si ya eligió antes, no se pregunta de nuevo: queda la galleta
    let guardadas = null;
    try { if (o.recordar) guardadas = JSON.parse(localStorage.getItem(o.clave) || 'null'); } catch (e) { guardadas = null; }
    if (guardadas) { cats.forEach(c => { if (!c.fija && c.id in guardadas) pon(c, !!guardadas[c.id]); }); encoge(true); }

    return { abre, prefs };
  }

  window.Galleta = Galleta;
})();
