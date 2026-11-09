/* =====================================================================
   Charla · Moxen
   Un chat de soporte para tu sitio o tu panel: los mensajes se agrupan
   por remitente (la cola de la burbuja, el avatar y la hora solo en el
   último del grupo), «escribiendo…» con tres puntos en ola, respuestas
   rápidas en fichas que, al tocarlas, vuelan al campo y de ahí suben
   convertidas en tu burbuja, ✓ enviado y ✓✓ leído que se dibujan,
   reacciones al pasar el cursor (o al mantener el dedo), adjuntos con
   su avance y tarjetas ricas (un pedido, un horario) en las respuestas.

     const c = Charla(document.querySelector('[data-charla]'), {
       bienvenida: [{ texto: '¡Hola! ¿En qué te ayudo?' }],
       fichas: ['¿Dónde está mi pedido?', 'Hablar con una persona'],
       hora: () => '14:03',                          // la hora que se muestra (la pones tú)
       responde: async (texto, { archivo, historial }) => {
         const r = await fetch('/api/soporte', { method: 'POST', body: texto });
         return r.json();   // { texto, tarjeta, fichas } o una lista de ellos, o un texto
       },
       sube: (archivo, avance, senal) => …,          // tu subida: llama avance(0…1)
     });
     c.recibe({ de: 'agente', texto: 'Hola, soy del equipo de atención' });   // lo que llega de tu servidor
     c.reinicia();   c.envia('Hola');   c.escribiendo(true);

   Intro envía y Mayús + Intro salta de línea. En el hilo, ↑ ↓ pasan de
   un mensaje a otro e Intro abre las reacciones (← → para elegir, Esc
   las cierra). Lo que se mueve es transform y opacity, y el hilo nunca
   salta: antes de cada cambio se mide dónde estaba cada fila y se la
   lleva a su sitio nuevo con un resorte (FLIP). Sin dependencias.
   ===================================================================== */
(function () {
  'use strict';

  /* Un resorte convertido en curva: linear() para CSS y Web Animations,
     y una tabla para lo que se mueve desde JS (los vuelos). */
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
    const n = pts.length - 1;
    const f = p => { if (p >= 1) return 1; const i = Math.max(0, p) * n, a = Math.floor(i); return pts[a] + (pts[a + 1] - pts[a]) * (i - a); };
    return { easing: 'linear(' + out.join(', ') + ')', duration: Math.round(t * 1000), f };
  }
  const ACOMODA = muelle(230, 23);      // las filas que se corren
  const BROTA = muelle(320, 19);        // una burbuja que llega: crece y se pasa un poco
  const POSA = muelle(260, 24);         // el trayecto de lo que vuela
  const SALTA = muelle(440, 15);        // la píldora de la reacción

  const espera = ms => new Promise(r => setTimeout(r, ms));
  const entre = (v, a, b) => Math.max(a, Math.min(b, v));
  const suave = p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const svg = (d, clase) => '<svg viewBox="0 0 24 24" aria-hidden="true"' + (clase ? ' class="' + clase + '"' : '') + '>' + d + '</svg>';

  const ICONOS = {
    soporte: '<path d="M4.5 13.5V12a7.5 7.5 0 0 1 15 0v1.5"/><rect x="3.5" y="12.5" width="4" height="6" rx="2"/><rect x="16.5" y="12.5" width="4" height="6" rx="2"/><path d="M18.5 18.5c0 1.4-1.6 2.5-4 2.5h-1.5"/>',
    flecha: '<path d="M5 12h13.5m0 0-5.5-5.5m5.5 5.5-5.5 5.5"/>',
    doc: '<path d="M7 3.5h7l4.5 4.5v11a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5z"/><path d="M14 3.5V8h4.5M9 13h6M9 16.5h4"/>',
    equis: '<path d="m8.5 8.5 7 7m0-7-7 7"/>',
    sube: '<path d="M12 15.5V4.5m0 0L7.5 9m4.5-4.5L16.5 9"/><path d="M4.5 14.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/>',
  };
  const REACCIONES = [
    { clave: 'gusta', nombre: 'Me gusta', d: '<path d="M7.5 10.5v9h-3v-9z"/><path d="m7.5 10.5 3.6-6.2a1.9 1.9 0 0 1 3.4 1.4l-.8 3.3h4.6a2 2 0 0 1 2 2.4l-1.3 6.4a2 2 0 0 1-2 1.7H7.5"/>' },
    { clave: 'encanta', nombre: 'Me encanta', d: '<path class="ch-lleno" d="M12 19.8 5.2 13.1a4.3 4.3 0 0 1 6.1-6.1l.7.7.7-.7a4.3 4.3 0 0 1 6.1 6.1z"/>' },
    { clave: 'risa', nombre: 'Me da risa', d: '<circle cx="12" cy="12" r="8.5"/><path d="M8 13.3c.8 2 2.2 3 4 3s3.2-1 4-3z"/><path d="m8.4 8.9 1.9 1-1.9 1M15.6 8.9l-1.9 1 1.9 1"/>' },
    { clave: 'asombro', nombre: 'Me asombra', d: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="15.2" r="1.9"/><path d="M9.2 9.4v1M14.8 9.4v1"/>' },
    { clave: 'listo', nombre: 'Resuelto', d: '<circle cx="12" cy="12" r="8.5"/><path d="m8.3 12.3 2.6 2.6 5-5.4"/>' },
  ];
  // ✓ enviado y ✓✓ leído: dos ganchos que se dibujan (pathLength = 1)
  const VISTO = '<svg class="ch-visto" viewBox="0 0 16 12" role="img" aria-label="Enviando"><path d="M1.4 6.5 4.5 9.6 10.8 2.8" pathLength="1"/><path d="M7.2 8.4 8.4 9.6 14.7 2.8" pathLength="1"/></svg>';
  let cuenta = 0;

  function Charla(raiz, opciones) {
    const o = Object.assign({
      responde: null, bienvenida: [], fichas: [], hora: () => '', horaBienvenida: null, dia: 'Hoy',
      remitentes: {}, sube: null, maxMB: 10, escribeMin: 650, leeEn: 320,
      alEnviar: null, alReaccionar: null, alReiniciar: null,
      error: 'No pude responderte. Inténtalo de nuevo en un momento.',
      escribiendoTexto: 'Escribiendo…',
    }, opciones);
    const quienes = Object.assign({ bot: { nombre: 'Soporte', icono: ICONOS.soporte }, tu: { nombre: 'Tú' } }, o.remitentes);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const id = 'ch' + (++cuenta);
    const $ = s => raiz.querySelector(s);
    const hilo = $('.ch-hilo'), log = $('.ch-log'), intro = $('.ch-intro'), escribe = $('.ch-escribe'), fichasEl = $('.ch-fichas');
    const form = $('.ch-redacta'), cajaCampo = $('.ch-campo'), campo = $('.ch-campo textarea'), boton = $('.ch-envia'), clip = $('.ch-adjunta'), elige = $('.ch-archivos');
    const rueda = $('.ch-rueda'), nueva = $('.ch-nueva'), abajo = $('.ch-abajo');
    const enLinea = rueda.textContent.trim();
    raiz.style.setProperty('--ch-muelle', BROTA.easing);

    // lo que se anuncia al lector de pantalla (reacciones, adjuntos, reinicio)
    const anuncio = document.createElement('p');
    anuncio.className = 'ch-oculto'; anuncio.setAttribute('aria-live', 'polite');
    raiz.appendChild(anuncio);
    const anuncia = t => { anuncio.textContent = ''; setTimeout(() => { anuncio.textContent = t; }, 30); };
    // lo que vuela va en una capa fija, por encima de todo (fuera del recorte del hilo)
    const capa = document.createElement('div');
    capa.className = 'ch-vuelos'; capa.setAttribute('aria-hidden', 'true');
    document.body.appendChild(capa);
    // la barra de reacciones: una sola, que se coloca sobre el mensaje
    const barra = document.createElement('div');
    barra.className = 'ch-reacciones'; barra.setAttribute('role', 'toolbar'); barra.setAttribute('aria-label', 'Reaccionar al mensaje');
    barra.innerHTML = REACCIONES.map((r, i) => '<button type="button" tabindex="-1" style="--i:' + i + '" data-clave="' + r.clave + '" aria-label="' + r.nombre + '" aria-pressed="false" title="' + r.nombre + '">' + svg(r.d) + '</button>').join('');
    raiz.appendChild(barra);
    const suelta = document.createElement('div');
    suelta.className = 'ch-suelta'; suelta.setAttribute('aria-hidden', 'true');
    suelta.innerHTML = svg(ICONOS.sube) + 'Suelta el archivo para adjuntarlo';
    raiz.appendChild(suelta);
    escribe.innerHTML = '<span class="ch-av"></span><div class="ch-puntos"><i></i><i></i><i></i></div>';

    let historial = [], fijos = 0;
    const avatar = q => q.icono ? svg(q.icono) : esc(q.iniciales || String(q.nombre || '?').split(/\s+/).map(p => p[0]).join('').slice(0, 2).toUpperCase());

    /* ── el hilo no salta (FLIP) ──────────────────────────────────────
       Se mide dónde se ve cada fila, se hace el cambio (llega un
       mensaje, se van las fichas, aparece «escribiendo…»), se pega el
       hilo al fondo si estaba ahí, y cada fila arranca desde donde se
       veía y viaja a su sitio nuevo con un resorte. */
    const pegado = () => hilo.scrollHeight - hilo.scrollTop - hilo.clientHeight < 56;
    const vivos = () => [intro].concat(Array.from(log.children), [escribe, fichasEl]).filter(el => !el.hidden);
    function cambia(fn, como) {
      const c = como || {};
      const antes = new Map();
      if (!reduce) vivos().forEach(el => antes.set(el, el.getBoundingClientRect().top));
      const fondo = c.fondo || pegado();
      antes.forEach((_, el) => { if (el._flip) { el._flip.cancel(); el._flip = null; } });
      const r = fn();
      if (c.arriba) hilo.scrollTop = 0;
      else if (fondo) hilo.scrollTop = hilo.scrollHeight;
      /* Primero se lee todo, después se escribe (un solo cálculo de
         diseño). Lo nuevo viaja pegado a lo que tiene encima: entra desde
         abajo con el resto, como una cinta. */
      const saltos = [];
      let previo = 0;
      vivos().forEach(el => {
        const y = antes.get(el);
        const d = y === undefined ? (c.solo ? 0 : previo) : y - el.getBoundingClientRect().top;
        previo = d;
        if (c.excluye && c.excluye.includes(el)) return;
        if (Math.abs(d) > .5) saltos.push([el, d]);
      });
      saltos.forEach(([el, d]) => {
        el._flip = el.animate([{ transform: 'translateY(' + d.toFixed(1) + 'px)' }, { transform: 'none' }], { duration: ACOMODA.duration, easing: ACOMODA.easing });
      });
      return r;
    }

    /* ── una fila (un mensaje) ────────────────────────────────────── */
    function nuevaFila(de, m, hora) {
      const ultima = log.lastElementChild;
      const junta = ultima && ultima.classList.contains('ch-fila') && ultima.dataset.de === de;
      if (junta) ultima.classList.remove('is-ultimo');
      const q = quienes[de] || { nombre: de };
      const el = document.createElement('div');
      el.className = 'ch-fila is-ultimo' + (junta ? '' : ' is-primero');
      el.dataset.de = de;
      el.innerHTML = (de === 'tu' ? '' : '<p class="ch-nombre" aria-hidden="true">' + esc(q.nombre) + '</p><span class="ch-av" aria-hidden="true">' + avatar(q) + '</span>') +
        '<div class="ch-msj" tabindex="-1"><span class="ch-oculto">' + esc(de === 'tu' ? 'Tú' : q.nombre) + ': </span></div>' +
        '<p class="ch-meta"><time></time>' + (de === 'tu' ? VISTO : '') + '</p>';
      const msj = el.querySelector('.ch-msj');
      if (m.texto) {
        const b = document.createElement('div');
        b.className = 'ch-bloque ch-burbuja';
        b.innerHTML = '<span class="ch-t"></span>';
        b.firstChild.textContent = m.texto;
        msj.appendChild(b);
      }
      if (m.html) msj.insertAdjacentHTML('beforeend', '<div class="ch-bloque ch-burbuja"><span class="ch-t">' + m.html + '</span></div>');
      if (m.tarjeta) msj.insertAdjacentHTML('beforeend', tarjeta(m.tarjeta));
      if (m.archivo) msj.insertAdjacentHTML('beforeend', adjuntoHTML(m.archivo));
      el.querySelector('time').textContent = hora != null ? hora : (m.hora || o.hora() || '');
      log.appendChild(el);
      historial.push({ de, texto: m.texto || '', tarjeta: m.tarjeta || null, archivo: m.archivo || null });
      return el;
    }

    // una respuesta rica: un pedido con sus etapas, un horario, filas…
    function tarjeta(t) {
      let h = '<div class="ch-bloque ch-tarjeta">';
      if (t.etiqueta || t.estado) h += '<div class="ch-t-cabeza ch-t-parte"><span>' + esc(t.etiqueta || '') + '</span>' + (t.estado ? '<span class="ch-t-estado"><i></i>' + esc(t.estado) + '</span>' : '') + '</div>';
      if (t.titulo) h += '<p class="ch-t-titulo ch-t-parte">' + esc(t.titulo) + '</p>';
      if (t.detalle) h += '<p class="ch-t-detalle ch-t-parte">' + esc(t.detalle) + '</p>';
      if (t.pasos) {
        const n = t.pasos.length, a = entre(t.actual || 0, 0, n - 1);
        h += '<div class="ch-t-pasos ch-t-parte" style="--n:' + n + '" role="img" aria-label="' + esc('Etapa ' + (a + 1) + ' de ' + n + ': ' + t.pasos[a]) + '">' +
          t.pasos.map((_, i) => '<i><b class="' + (i < a ? 'is-hecho' : i === a ? 'is-actual' : '') + '"></b></i>').join('') + '</div>' +
          '<div class="ch-t-etapas ch-t-parte" style="--n:' + n + '" aria-hidden="true">' + t.pasos.map((p, i) => '<span' + (i === a ? ' class="is-actual"' : '') + '>' + esc(p) + '</span>').join('') + '</div>';
      }
      if (t.filas) h += '<dl class="ch-t-filas ch-t-parte">' + t.filas.map(f => '<div><dt>' + esc(f[0]) + '</dt><dd>' + esc(f[1]) + '</dd></div>').join('') + '</dl>';
      if (t.pie || (t.acciones && t.acciones.length)) {
        h += '<div class="ch-t-pie ch-t-parte"><span>' + esc(t.pie || '') + '</span>' + (t.acciones || []).map(a => a.href
          ? '<a class="ch-t-accion" href="' + esc(a.href) + '" target="_blank" rel="noopener">' + esc(a.texto) + svg(ICONOS.flecha) + '</a>'
          : '<button class="ch-t-accion" type="button" data-envia="' + esc(a.envia || a.texto) + '"><span>' + esc(a.texto) + '</span>' + svg(ICONOS.flecha) + '</button>').join('') + '</div>';
      }
      return h + '</div>';
    }

    function adjuntoHTML(a) {
      return '<div class="ch-bloque ch-archivo is-subiendo">' +
        '<button class="ch-arch-icono" type="button" aria-label="Cancelar la subida de ' + esc(a.nombre) + '">' +
          '<svg class="ch-arch-anillo" viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="20.5"/><circle cx="22" cy="22" r="20.5" pathLength="1"/></svg>' +
          svg(ICONOS.doc, 'ch-arch-doc') + svg(ICONOS.equis, 'ch-arch-cancela') +
        '</button>' +
        '<span class="ch-arch-textos"><b></b><small></small></span></div>';
    }

    /* La burbuja llega desde la esquina de su remitente: crece, se pasa
       un poco y vuelve (un resorte); el texto aparece un instante después,
       cuando la forma ya está. Las partes de una tarjeta suben en cascada
       y las barras de etapas se llenan una tras otra. */
    function brota(fila, retraso) {
      if (reduce) return;
      const tu = fila.dataset.de === 'tu', r0 = retraso || 0;
      fila.querySelectorAll('.ch-bloque').forEach((b, i) => {
        const r = r0 + i * 120;
        b.style.transformOrigin = tu ? '100% 100%' : '0 100%';
        b.animate([{ transform: 'translateY(12px) scale(.5)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: BROTA.duration, easing: BROTA.easing, delay: r, fill: 'backwards' });
        const t = b.querySelector(':scope > .ch-t');
        if (t) t.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, delay: r + 70, easing: 'ease-out', fill: 'backwards' });
        b.querySelectorAll('.ch-t-parte').forEach((p, k) => p.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 460, delay: r + 70 + k * 35, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'backwards' }));
        b.querySelectorAll('.ch-t-pasos b').forEach((p, k) => {
          const fin = p.classList.contains('is-hecho') ? 1 : p.classList.contains('is-actual') ? .55 : 0;
          if (fin) p.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(' + fin + ')' }], { duration: 340, delay: r + 150 + k * 70, easing: 'cubic-bezier(.65, 0, .35, 1)', fill: 'backwards' });
        });
      });
      const av = fila.querySelector('.ch-av');
      if (av) av.animate([{ transform: 'scale(.4)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: BROTA.duration, easing: BROTA.easing, delay: r0, fill: 'backwards' });
      const meta = fila.querySelector('.ch-meta');
      meta.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: r0 + 200, fill: 'backwards' });
      const nombre = fila.querySelector('.ch-nombre');
      if (nombre) nombre.animate([{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], { duration: 400, delay: r0 + 60, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'backwards' });
    }
    // al posarse, un pequeño aplastamiento: llega con peso
    const asienta = (el, origen) => {
      if (reduce) return;
      el.style.transformOrigin = origen;
      el.animate([{ transform: 'scale(1.05, .92)' }, { transform: 'none' }], { duration: SALTA.duration, easing: SALTA.easing });
    };
    function estado(fila, e) {
      const meta = fila.querySelector('.ch-meta'), v = meta.querySelector('.ch-visto');
      meta.classList.remove('is-enviado', 'is-leido');
      meta.classList.add('is-' + e);
      if (v) v.setAttribute('aria-label', e === 'leido' ? 'Leído' : 'Enviado');
    }

    /* ── «escribiendo…» y el subtítulo que gira ───────────────────── */
    function gira(caja, texto) {
      const viejo = caja.lastElementChild;
      if (viejo && viejo.textContent === texto) return;
      const nuevo = document.createElement('span');
      nuevo.textContent = texto;
      caja.appendChild(nuevo);
      if (!viejo) return;
      nuevo.classList.add('is-entra');
      viejo.classList.add('is-sale');
      setTimeout(() => viejo.remove(), 320);
    }
    function ponEscribiendo(si, de) {
      const q = quienes[de || 'bot'] || quienes.bot;
      if (si) {
        const ultima = log.lastElementChild;
        escribe.classList.toggle('is-junta', !!ultima && ultima.dataset.de === (de || 'bot'));
        escribe.firstChild.innerHTML = avatar(q);
      }
      gira(rueda, si ? o.escribiendoTexto : enLinea);
      log.setAttribute('aria-busy', String(!!si));
      if (si === !escribe.hidden) return;
      cambia(() => { escribe.hidden = !si; });
      if (si && !reduce) {
        escribe.querySelector('.ch-puntos').animate([{ transform: 'translateY(10px) scale(.4)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: BROTA.duration, easing: BROTA.easing });
        escribe.firstChild.animate([{ transform: 'scale(.4)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: BROTA.duration, easing: BROTA.easing });
      }
    }

    /* ── las respuestas rápidas ───────────────────────────────────── */
    function ponFichas(lista) {
      fichasEl.innerHTML = '';
      (lista || []).forEach(t => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'ch-ficha'; b.dataset.texto = t;
        b.innerHTML = '<span></span>';
        b.firstChild.textContent = t;
        fichasEl.appendChild(b);
      });
      fichasEl.hidden = !fichasEl.children.length;
    }
    function entranFichas(retraso) {
      if (reduce) return;
      Array.from(fichasEl.children).forEach((b, i) => b.animate(
        [{ transform: 'translateY(12px) scale(.82)', opacity: 0 }, { transform: 'none', opacity: 1 }],
        { duration: BROTA.duration, easing: BROTA.easing, delay: (retraso || 0) + i * 60, fill: 'backwards' }));
    }

    /* ── lo que vuela ─────────────────────────────────────────────────
       Un doble en la capa fija: viaja de un punto a otro con la curva de
       un resorte y un arco (sube por el medio). `hasta` puede ser una
       función: el destino se recalcula en cada cuadro. El paso de cada
       cuadro se limita: si la pestaña se oculta, al volver sigue donde iba. */
    function doble(forma, texto, w, h, tx, ty, ancho) {
      const el = document.createElement('div');
      el.className = 'ch-vuelo'; el.dataset.forma = forma;
      el.style.width = w + 'px'; el.style.height = h + 'px';
      el.innerHTML = '<i class="ch-vuelo-fondo"></i><span class="ch-vuelo-texto"></span>' + (forma === 'burbuja' ? '<span class="ch-vuelo-texto is-tinta"></span>' : '');
      el.querySelectorAll('.ch-vuelo-texto').forEach(s => {
        s.textContent = texto;
        s.style.transform = 'translate(' + tx + 'px,' + ty + 'px)';
        if (ancho) s.style.width = ancho + 'px';
      });
      capa.appendChild(el);
      return { el, fondo: el.firstChild, claro: el.children[1], tinta: el.children[2] };
    }
    function vuela(el, desde, hasta, op) {
      return new Promise(fin => {
        let t = 0, previo = 0;
        const pon = p => {
          const b = typeof hasta === 'function' ? hasta() : hasta, e = POSA.f(p);
          const x = desde[0] + (b[0] - desde[0]) * e, y = desde[1] + (b[1] - desde[1]) * e + (op.arco || 0) * Math.sin(Math.PI * p);
          el.style.transform = 'translate3d(' + x.toFixed(2) + 'px,' + y.toFixed(2) + 'px,0) scale(' + (op.escala ? op.escala(p) : 1).toFixed(4) + ')';
          if (op.paso) op.paso(p);
        };
        pon(0);
        const cuadro = ahora => {
          t += previo ? Math.min(50, ahora - previo) : 0;
          previo = ahora;
          const p = Math.min(1, t / op.dur);
          pon(p);
          if (p < 1) requestAnimationFrame(cuadro); else fin();
        };
        requestAnimationFrame(cuadro);
      });
    }
    // dónde empieza el texto dentro del campo (para que el doble calce letra con letra)
    function origenCampo() {
      const r = campo.getBoundingClientRect(), cs = getComputedStyle(campo);
      return { x: r.left + parseFloat(cs.paddingLeft), y: r.top + parseFloat(cs.paddingTop) - campo.scrollTop };
    }

    /* Tocar una ficha: la ficha vuela al campo (su borde se desvanece en
       el camino y su texto cae justo sobre el del campo), espera un
       instante y se envía como cualquier mensaje escrito. */
    let ocupado = false;
    async function eligeFicha(b) {
      if (ocupado || !b.isConnected) return;
      const texto = b.dataset.envia || b.dataset.texto;
      const teclado = b.matches(':focus-visible');
      if (reduce) { campo.value = texto; ajusta(); return enviaCampo(); }
      ocupado = true;
      const r = b.getBoundingClientRect(), rt = (b.querySelector('span') || b).getBoundingClientRect();
      const ox = rt.left - r.left, oy = rt.top - r.top;
      const ficha = b.classList.contains('ch-ficha');
      const v = doble('ficha', texto, r.width, r.height, ox, oy);
      if (ficha) {
        b.style.visibility = 'hidden';
        Array.from(fichasEl.children).filter(x => x !== b).forEach((x, i) => x.animate(
          [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(.86)' }], { duration: 220, delay: i * 35, easing: 'cubic-bezier(.5, 0, .75, 0)', fill: 'forwards' }));
      } else v.fondo.style.opacity = '0';
      campo.value = ''; ajusta();
      cajaCampo.classList.add('is-callado');
      await vuela(v.el, [r.left, r.top], () => { const d = origenCampo(); return [d.x - ox, d.y - oy]; }, {
        dur: 400, arco: -30,
        paso: p => { if (ficha) v.fondo.style.opacity = (1 - suave(entre(p / .75, 0, 1))).toFixed(3); },
      });
      campo.value = texto; ajusta();
      v.el.remove();
      if (teclado) campo.focus({ preventScroll: true });
      await espera(90);
      ocupado = false;
      enviaCampo();
    }

    /* ── enviar ───────────────────────────────────────────────────────
       El texto sale del campo y sube hasta su burbuja: el doble nace con
       la letra exactamente donde estaba en el campo, el fondo de la
       burbuja aparece en el camino (la tinta cambia de color con él) y
       al llegar se aplasta un poco. Mientras, el hilo le abre sitio. */
    function enviaCampo() {
      const texto = campo.value.trim();
      if (!texto || ocupado) return;
      const d = origenCampo();
      campo.value = ''; ajusta();
      cajaCampo.classList.add('is-callado');
      setTimeout(() => cajaCampo.classList.remove('is-callado'), reduce ? 0 : 260);
      boton.classList.remove('is-sale'); void boton.offsetWidth; boton.classList.add('is-sale');
      cierraBarra();
      let fila;
      cambia(() => { ponFichas([]); fila = nuevaFila('tu', { texto }); }, { fondo: true, excluye: [fichasEl] });
      const burbuja = fila.querySelector('.ch-burbuja'), meta = fila.querySelector('.ch-meta');
      rueda0();
      const listo = () => { estado(fila, 'enviado'); turno(texto, {}, fila); };
      if (o.alEnviar) o.alEnviar({ texto });
      if (reduce) return listo();
      const r = burbuja.getBoundingClientRect(), cs = getComputedStyle(burbuja);
      const pl = parseFloat(cs.paddingLeft), pt = parseFloat(cs.paddingTop);
      const v = doble('burbuja', texto, r.width, r.height, pl, pt, r.width - pl - parseFloat(cs.paddingRight));
      v.fondo.style.opacity = '0'; v.tinta.style.opacity = '0';
      burbuja.style.visibility = 'hidden';
      meta.style.opacity = '0';
      // el destino se sigue en cada cuadro: la fila sube con el hilo mientras el texto vuela hacia ella
      vuela(v.el, [d.x - pl, d.y - pt], () => { const b = burbuja.getBoundingClientRect(); return [b.left, b.top]; }, {
        dur: 540, arco: -38,
        escala: p => 1 + .05 * Math.sin(Math.PI * p),
        // el fondo aparece pronto y la tinta cambia de color en un tramo corto, cuando ya hay fondo detrás
        paso: p => {
          const f = suave(entre(p / .3, 0, 1)), t = suave(entre((p - .12) / .16, 0, 1));
          v.fondo.style.opacity = f.toFixed(3); v.tinta.style.opacity = t.toFixed(3); v.claro.style.opacity = (1 - t).toFixed(3);
        },
      }).then(() => {
        burbuja.style.visibility = '';
        v.el.remove();
        asienta(burbuja, '100% 100%');
        meta.style.opacity = '';
        meta.animate([{ opacity: 0, transform: 'translateY(-3px)' }, { opacity: 1, transform: 'none' }], { duration: 300, easing: 'ease-out' });
        listo();
      });
    }
    // el foco del hilo (un solo Tab para todos los mensajes): el último
    function rueda0() {
      const todos = log.querySelectorAll('.ch-msj');
      if (raiz.contains(document.activeElement) && document.activeElement.classList.contains('ch-msj')) return;
      todos.forEach((m, i) => { m.tabIndex = i === todos.length - 1 ? 0 : -1; });
    }

    /* ── la respuesta ─────────────────────────────────────────────────
       Una cola: cada turno espera al anterior. El mensaje se marca leído,
       aparece «escribiendo…» al menos `escribeMin` ms (aunque tu servidor
       conteste antes: que no parpadee) y llegan los mensajes uno a uno,
       con una pausa de escritura entre ellos según su largo. */
    let cola = Promise.resolve(), gen = 0;
    const pausa = m => entre(String(m.texto || '').length * 14, 420, 1100);
    function turno(texto, extra, fila) {
      const g = gen;
      cola = cola.then(async () => {
        if (g !== gen) return;
        await espera(o.leeEn);
        if (g !== gen) return;
        if (fila) estado(fila, 'leido');
        if (!o.responde) return;
        ponEscribiendo(true);
        let r;
        try {
          r = (await Promise.all([Promise.resolve().then(() => o.responde(texto, Object.assign({ historial: historial.slice() }, extra))), espera(o.escribeMin)]))[0];
        } catch (e) { r = { texto: o.error }; }
        if (g !== gen) return;
        const lista = (Array.isArray(r) ? r : r == null ? [] : [r]).map(m => typeof m === 'string' ? { texto: m } : m);
        for (let i = 0; i < lista.length; i++) {
          if (i > 0) {
            await espera(280);
            if (g !== gen) return;
            ponEscribiendo(true, lista[i].de);
            await espera(lista[i].espera != null ? lista[i].espera : pausa(lista[i]));
            if (g !== gen) return;
          }
          recibe(lista[i], i < lista.length - 1);
        }
        if (!lista.length) ponEscribiendo(false);
      }).catch(() => {});
      return cola;
    }

    // un mensaje que llega (del bot, de una persona o un aviso del sistema)
    function recibe(m, sigue) {
      m = typeof m === 'string' ? { texto: m } : (m || {});
      const fondo = pegado();
      let fila = null;
      const hay = m.texto || m.html || m.tarjeta || m.sistema;
      cambia(() => {
        escribe.hidden = true;
        if (m.sistema) {
          fila = document.createElement('div');
          fila.className = 'ch-sistema';
          fila.innerHTML = (m.de && quienes[m.de] ? '<span class="ch-av" aria-hidden="true">' + avatar(quienes[m.de]) + '</span>' : '') + '<span></span>';
          fila.lastChild.textContent = m.sistema;
          log.appendChild(fila);
        } else if (hay) fila = nuevaFila(m.de || 'bot', m);
        if (m.fichas) ponFichas(m.fichas);
      }, { excluye: m.fichas ? [fichasEl] : [] });
      // mientras quedan mensajes del mismo turno, la cabecera sigue en «Escribiendo…»
      if (!sigue) { gira(rueda, enLinea); log.setAttribute('aria-busy', 'false'); }
      if (fila && !reduce) {
        if (m.sistema) fila.animate([{ opacity: 0, transform: 'translateY(8px) scale(.96)' }, { opacity: 1, transform: 'none' }], { duration: 520, easing: 'cubic-bezier(.22, 1, .36, 1)' });
        else brota(fila);
      }
      if (m.fichas) entranFichas(fila ? 420 : 0);
      if (fila && !fondo) { abajo.classList.add('is-visible'); abajo.tabIndex = 0; }
      rueda0();
      return fila;
    }

    /* ── las reacciones ───────────────────────────────────────────────
       Al pasar el cursor por un mensaje (o al mantener el dedo, o con
       Intro), la barra crece desde su esquina y sus caritas suben en
       cascada. La elegida vuela hasta la burbuja y se posa en una
       píldora con un rebote y una onda. */
    let objetivo = null, relojAbre = 0, relojCierra = 0;
    function abreBarra(msj, foco) {
      clearTimeout(relojCierra); clearTimeout(relojAbre);
      if (!msj.isConnected || !msj.querySelector('.ch-bloque')) return;
      const fila = msj.closest('.ch-fila'), tu = fila.dataset.de === 'tu';
      const rr = raiz.getBoundingClientRect(), rm = msj.getBoundingClientRect(), rh = hilo.getBoundingClientRect();
      const W = barra.offsetWidth, H = barra.offsetHeight;
      const x = entre(tu ? rm.right - rr.left - W + 6 : rm.left - rr.left - 6, 8, rr.width - W - 8);
      const arriba = rm.top - H - 8 >= rh.top + 2;
      barra.style.left = x + 'px';
      barra.style.top = (arriba ? rm.top - rr.top - H - 8 : Math.min(rm.bottom, rh.bottom - H - 8) - rr.top + 8) + 'px';
      barra.style.setProperty('--ch-origen', (tu ? '90%' : '10%') + (arriba ? ' 100%' : ' 0'));
      barra.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.clave === fila.dataset.reac)));
      objetivo = msj;
      barra.classList.add('is-abierta');
      if (foco) barra.querySelector('button').focus();
    }
    function cierraBarra(devuelve) {
      clearTimeout(relojAbre);
      if (!barra.classList.contains('is-abierta')) return;
      barra.classList.remove('is-abierta');
      if (devuelve && objetivo) objetivo.focus({ preventScroll: true });
      objetivo = null;
    }
    function reacciona(msj, clave, b) {
      const fila = msj.closest('.ch-fila'), r = REACCIONES.find(x => x.clave === clave);
      if (!fila || !r) return;
      const quita = fila.dataset.reac === clave;
      const icono = b && b.querySelector('svg').getBoundingClientRect();
      const teclado = b && b.matches(':focus-visible');
      cierraBarra(teclado);
      let pila = msj.querySelector('.ch-reac');
      if (quita) {
        delete fila.dataset.reac;
        const fuera = () => cambia(() => { pila.remove(); fila.classList.remove('is-reac'); });
        if (reduce) fuera();
        else pila.animate([{ transform: 'none', opacity: 1 }, { transform: 'scale(0)', opacity: 0 }], { duration: 200, easing: 'cubic-bezier(.5, 0, .75, 0)', fill: 'forwards' }).onfinish = fuera;
        anuncia('Quitaste tu reacción.');
      } else {
        fila.dataset.reac = clave;
        if (!pila) cambia(() => {
          pila = document.createElement('span');
          pila.className = 'ch-reac'; pila.setAttribute('aria-hidden', 'true');
          msj.querySelector('.ch-bloque:last-of-type').appendChild(pila);
          fila.classList.add('is-reac');
        });
        pila.innerHTML = svg(r.d);
        const posa = () => {
          pila.style.visibility = '';
          if (reduce) return;
          pila.animate([{ transform: 'scale(0) rotate(-20deg)' }, { transform: 'none' }], { duration: SALTA.duration, easing: SALTA.easing });
          pila.classList.remove('is-posa'); void pila.offsetWidth; pila.classList.add('is-posa');
        };
        if (!reduce && icono) {
          pila.style.visibility = 'hidden';
          const rp = pila.querySelector('svg').getBoundingClientRect();
          const el = document.createElement('div');
          el.className = 'ch-vuelo-icono';
          el.innerHTML = svg(r.d);
          el.style.width = el.style.height = icono.width + 'px';
          capa.appendChild(el);
          const k = rp.width / icono.width;
          vuela(el, [icono.left, icono.top], [rp.left - (icono.width - rp.width) / 2, rp.top - (icono.height - rp.height) / 2], {
            dur: 460, arco: -46, escala: p => 1.25 + .35 * Math.sin(Math.PI * p) - (1.25 - k) * suave(p),
          }).then(() => { el.remove(); posa(); });
        } else posa();
        anuncia('Reaccionaste con «' + r.nombre + '».');
      }
      if (o.alReaccionar) o.alReaccionar({ indice: Array.from(log.querySelectorAll('.ch-msj')).indexOf(msj), reaccion: quita ? null : clave });
    }

    /* ── adjuntos ─────────────────────────────────────────────────────
       El archivo entra como tu burbuja con un anillo que se llena; el
       ícono hace de «cancelar» mientras sube. `sube` es tuya (fetch,
       XHR…): recibe el archivo, una función de avance y una señal para
       abortar. Sin `sube`, la demo simula el avance. */
    const peso = n => n < 1024 ? n + ' B' : n < 1048576 ? Math.round(n / 1024) + ' KB' : (n / 1048576).toFixed(1).replace('.', ',') + ' MB';
    function simula(avance, senal) {
      const pasos = [.06, .17, .29, .38, .52, .61, .74, .83, .92, 1];
      return new Promise((ok, mal) => {
        let i = 0;
        senal.addEventListener('abort', () => mal(new Error('cancelado')));
        const sigue = () => {
          if (senal.aborted) return;
          avance(pasos[i]);
          if (++i < pasos.length) setTimeout(sigue, 140 + (i % 3) * 45); else setTimeout(ok, 240);
        };
        setTimeout(sigue, 160);
      });
    }
    function adjunta(archivo) {
      const a = { nombre: archivo.name || 'archivo', tamano: archivo.size || 0, tipo: archivo.type || '' };
      const ext = (a.nombre.split('.').pop() || '').toUpperCase().slice(0, 4);
      if (a.tamano > o.maxMB * 1048576) { recibe({ sistema: '«' + a.nombre + '» pesa más de ' + o.maxMB + ' MB. Prueba con uno más liviano.' }); return; }
      cierraBarra();
      let fila;
      cambia(() => { ponFichas([]); fila = nuevaFila('tu', { archivo: a }); }, { fondo: true, excluye: [fichasEl] });
      const caja = fila.querySelector('.ch-archivo'), anillo = caja.querySelector('.ch-arch-anillo circle:last-child');
      const nota = caja.querySelector('small'), cancela = caja.querySelector('.ch-arch-icono');
      caja.querySelector('b').textContent = a.nombre;
      brota(fila);
      const ctl = new AbortController();
      const avance = p => { p = entre(+p || 0, 0, 1); anillo.style.strokeDashoffset = (1 - p).toFixed(3); nota.textContent = peso(a.tamano) + ' · Subiendo ' + Math.round(p * 100) + ' %'; };
      avance(0);
      cancela.addEventListener('click', () => { if (caja.classList.contains('is-subiendo')) ctl.abort(); });
      anuncia('Subiendo «' + a.nombre + '».');
      const subida = o.sube ? Promise.resolve().then(() => o.sube(archivo, avance, ctl.signal)) : simula(avance, ctl.signal);
      return subida.then(res => {
        if (ctl.signal.aborted) throw new Error('cancelado');
        avance(1);
        caja.classList.remove('is-subiendo');
        cancela.disabled = true; cancela.setAttribute('aria-label', 'Archivo enviado');
        nota.textContent = peso(a.tamano) + (ext ? ' · ' + ext : '');
        asienta(caja, '100% 100%');
        estado(fila, 'enviado');
        anuncia('«' + a.nombre + '» enviado.');
        turno('', { archivo: a, subida: res }, fila);
      }).catch(() => {
        if (ctl.signal.aborted) {
          const fuera = () => cambia(() => { fila.remove(); arreglaGrupos(); });
          if (reduce) fuera();
          else fila.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(.9)' }], { duration: 220, easing: 'ease-in', fill: 'forwards' }).onfinish = fuera;
          anuncia('Subida cancelada.');
        } else { nota.textContent = 'No se pudo subir'; caja.classList.add('is-error'); }
      });
    }
    // tras quitar una fila, cada grupo vuelve a tener su primera y su última
    function arreglaGrupos() {
      const filas = Array.from(log.children);
      filas.forEach((f, i) => {
        if (!f.classList.contains('ch-fila')) return;
        const a = filas[i - 1], b = filas[i + 1];
        f.classList.toggle('is-primero', !(a && a.classList.contains('ch-fila') && a.dataset.de === f.dataset.de));
        f.classList.toggle('is-ultimo', !(b && b.classList.contains('ch-fila') && b.dataset.de === f.dataset.de));
      });
    }

    /* ── nueva conversación ───────────────────────────────────────────
       Lo nuevo se va de abajo hacia arriba, en cascada; después el hilo
       vuelve arriba (las filas que quedan bajan con su resorte) y las
       fichas del principio entran otra vez. */
    async function reinicia() {
      gen++;
      cola = Promise.resolve();
      cierraBarra();
      ocupado = false;
      const fuera = Array.from(log.children).slice(fijos);
      const tambien = [escribe, fichasEl].filter(el => !el.hidden);
      if (!reduce && (fuera.length || tambien.length)) {
        const van = fuera.concat(tambien).reverse().filter(el => el.getBoundingClientRect().bottom > hilo.getBoundingClientRect().top);
        van.forEach((el, i) => el.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(14px) scale(.96)' }],
          { duration: 240, delay: Math.min(i, 7) * 40, easing: 'cubic-bezier(.5, 0, .75, 0)', fill: 'forwards' }));
        await espera(250 + Math.min(Math.max(van.length - 1, 0), 7) * 40);
      }
      cambia(() => {
        fuera.forEach(el => el.remove());
        tambien.forEach(el => el.getAnimations().forEach(a => a.cancel()));
        escribe.hidden = true;
        log.querySelectorAll('.ch-reac').forEach(p => p.remove());
        log.querySelectorAll('.is-reac').forEach(f => { f.classList.remove('is-reac'); delete f.dataset.reac; });
        arreglaGrupos();
        ponFichas(o.fichas);
      }, { arriba: true, excluye: [fichasEl] });
      historial = historial.slice(0, fijos - (o.dia ? 1 : 0));
      entranFichas(160);
      gira(rueda, enLinea);
      log.setAttribute('aria-busy', 'false');
      abajo.classList.remove('is-visible'); abajo.tabIndex = -1;
      campo.value = ''; ajusta();
      rueda0();
      anuncia('Nueva conversación.');
      if (o.alReiniciar) o.alReiniciar();
    }

    /* ── el campo ─────────────────────────────────────────────────── */
    const MAXIMO = parseFloat(getComputedStyle(campo).maxHeight) || 136;
    // crece con el texto (hasta unas cinco líneas) y el hilo sigue pegado al fondo
    function ajusta() {
      const fondo = pegado();
      campo.style.height = 'auto';
      const h = campo.scrollHeight;
      campo.style.height = Math.min(h, MAXIMO) + 'px';
      campo.style.overflowY = h > MAXIMO ? 'auto' : 'hidden';
      boton.disabled = !campo.value.trim();
      if (fondo) hilo.scrollTop = hilo.scrollHeight;
    }
    campo.addEventListener('input', ajusta);
    campo.addEventListener('keydown', e => {
      // Intro envía; Mayús + Intro, salto de línea (y nada mientras se compone un acento o un ideograma)
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); enviaCampo(); }
    });
    form.addEventListener('submit', e => { e.preventDefault(); enviaCampo(); });
    clip.addEventListener('click', () => elige.click());
    elige.addEventListener('change', () => { Array.from(elige.files || []).forEach(adjunta); elige.value = ''; });
    nueva.addEventListener('click', reinicia);
    abajo.addEventListener('click', () => {
      cambia(() => {}, { fondo: true });
      abajo.classList.remove('is-visible'); abajo.tabIndex = -1;
    });

    // las fichas, y los botones de las tarjetas que responden algo
    raiz.addEventListener('click', e => {
      const b = e.target.closest('.ch-ficha, .ch-t-accion[data-envia]');
      if (b && raiz.contains(b)) eligeFicha(b);
    });
    barra.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (b && objetivo) reacciona(objetivo, b.dataset.clave, b);
    });

    // reacciones: con el cursor (al pasar), con el dedo (manteniendo) y con el teclado
    log.addEventListener('pointerover', e => {
      if (e.pointerType !== 'mouse') return;
      const msj = e.target.closest('.ch-msj');
      if (!msj) return;
      clearTimeout(relojCierra);
      if (objetivo === msj) return;
      clearTimeout(relojAbre);
      relojAbre = setTimeout(() => abreBarra(msj), objetivo ? 80 : 240);
    });
    log.addEventListener('pointerout', e => {
      if (e.pointerType !== 'mouse') return;
      const msj = e.target.closest('.ch-msj');
      if (!msj || (e.relatedTarget && msj.contains(e.relatedTarget))) return;
      clearTimeout(relojAbre);
      clearTimeout(relojCierra);
      relojCierra = setTimeout(() => cierraBarra(), 340);
    });
    barra.addEventListener('pointerenter', () => clearTimeout(relojCierra));
    barra.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') relojCierra = setTimeout(() => cierraBarra(), 340); });
    let toque = null;
    log.addEventListener('pointerdown', e => {
      if (e.pointerType === 'mouse') return;
      const msj = e.target.closest('.ch-msj');
      if (!msj || e.target.closest('button, a')) return;
      toque = { x: e.clientX, y: e.clientY, reloj: setTimeout(() => { abreBarra(msj); if (navigator.vibrate) navigator.vibrate(8); }, 420) };
    });
    log.addEventListener('pointermove', e => { if (toque && Math.hypot(e.clientX - toque.x, e.clientY - toque.y) > 10) { clearTimeout(toque.reloj); toque = null; } });
    ['pointerup', 'pointercancel'].forEach(t => log.addEventListener(t, () => { if (toque) clearTimeout(toque.reloj); toque = null; }));
    log.addEventListener('contextmenu', e => { if (e.target.closest('.ch-msj') && matchMedia('(hover: none)').matches) e.preventDefault(); });
    document.addEventListener('pointerdown', e => { if (objetivo && !barra.contains(e.target) && !objetivo.contains(e.target)) cierraBarra(); });
    hilo.addEventListener('scroll', () => {
      if (pegado()) { abajo.classList.remove('is-visible'); abajo.tabIndex = -1; }
      if (objetivo && !barra.matches(':focus-within')) cierraBarra();
    }, { passive: true });

    log.addEventListener('keydown', e => {
      const msj = e.target.classList && e.target.classList.contains('ch-msj') ? e.target : null;
      if (!msj) return;
      const todos = Array.from(log.querySelectorAll('.ch-msj')), i = todos.indexOf(msj);
      const j = { ArrowUp: i - 1, ArrowDown: i + 1, Home: 0, End: todos.length - 1 }[e.key];
      if (j !== undefined) {
        e.preventDefault();
        const otro = todos[entre(j, 0, todos.length - 1)];
        todos.forEach(m => { m.tabIndex = m === otro ? 0 : -1; });
        otro.focus();
        otro.scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abreBarra(msj, true); }
    });
    barra.addEventListener('keydown', e => {
      const bs = Array.from(barra.querySelectorAll('button')), i = bs.indexOf(document.activeElement);
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); bs[(i + (e.key === 'ArrowRight' ? 1 : bs.length - 1)) % bs.length].focus(); }
      else if (e.key === 'Escape' || e.key === 'Tab') { e.preventDefault(); cierraBarra(true); }
    });

    // soltar archivos sobre la ventana
    let arrastres = 0;
    const conArchivos = e => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');
    raiz.addEventListener('dragenter', e => { if (!conArchivos(e)) return; e.preventDefault(); arrastres++; raiz.classList.add('is-arrastra'); });
    raiz.addEventListener('dragover', e => { if (conArchivos(e)) e.preventDefault(); });
    raiz.addEventListener('dragleave', e => { if (!conArchivos(e)) return; if (--arrastres <= 0) { arrastres = 0; raiz.classList.remove('is-arrastra'); } });
    raiz.addEventListener('drop', e => {
      if (!conArchivos(e)) return;
      e.preventDefault(); arrastres = 0; raiz.classList.remove('is-arrastra');
      Array.from(e.dataTransfer.files).forEach(adjunta);
    });

    /* ── al empezar ───────────────────────────────────────────────── */
    if (o.dia) {
      const d = document.createElement('div');
      d.className = 'ch-dia'; d.setAttribute('role', 'separator');
      d.innerHTML = '<span></span>'; d.firstChild.textContent = o.dia;
      log.appendChild(d);
    }
    o.bienvenida.forEach(m => nuevaFila(m.de || 'bot', typeof m === 'string' ? { texto: m } : m, o.horaBienvenida));
    fijos = log.children.length;
    ponFichas(o.fichas);
    log.setAttribute('aria-describedby', id + '-ayuda');
    const ayuda = document.createElement('p');
    ayuda.id = id + '-ayuda'; ayuda.className = 'ch-oculto';
    ayuda.textContent = 'Usa las flechas para recorrer los mensajes e Intro para reaccionar.';
    raiz.appendChild(ayuda);
    rueda0();
    ajusta();

    return {
      envia: texto => { campo.value = String(texto || ''); ajusta(); enviaCampo(); },
      recibe, adjunta, reinicia,
      escribiendo: (si, de) => ponEscribiendo(!!si, de),
      fichas: lista => { cambia(() => ponFichas(lista), { excluye: [fichasEl] }); entranFichas(); },
      historial: () => historial.slice(),
    };
  }

  window.Charla = Charla;
})();
