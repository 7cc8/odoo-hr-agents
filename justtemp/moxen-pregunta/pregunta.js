/* =====================================================================
   Pregunta · Moxen
   La caja de pedido de un asistente, hecha como una pieza de papel. En
   reposo hay un saludo, una caja grande con foco terracota, un selector
   de modelo con descripciones (Rápido, Equilibrado, Profundo), adjuntos
   que entran como chips con miniatura y tres sugerencias. Al enviar, la
   caja baja a su sitio con FLIP (la medida antes y después, y un resorte
   entre las dos), el saludo y las sugerencias se desvanecen en su lugar,
   el texto sale de la caja hacia su burbuja y la respuesta se escribe a
   bloques —un párrafo, una lista, un bloque de código con resaltado— con
   un cursor que destella. El botón de enviar se vuelve «detener» (también
   Esc). Al terminar aparecen copiar (que se convierte en ✓) y regenerar;
   unos segundos después, o con «Nueva consulta», la conversación se
   recoge y todo vuelve al principio.

   Intro envía, Mayús+Intro salta de línea, Esc cierra el desplegable (o
   detiene la respuesta). El desplegable es un listbox: flechas, Inicio,
   Fin, Intro y Esc. Todo se simula en el cliente; para conectarlo a algo real:

     const p = Pregunta(document.querySelector('[data-pregunta]'), {
       responder: (texto, { modelo, adjuntos, tema, variante }) =>
         fetch('/api').then(r => r.json()),          // → [ { t: 'p', s: '…' }, { t: 'ul', items: ['…'] }, { t: 'code', lang: 'js', s: '…' } ]
       modelos: [ { id, nombre, desc, nivel: 1–3, vel: 1, espera: .5 } ],   // vel multiplica la velocidad; espera (s) es el «pensando»
       velocidad: 230,                // caracteres por segundo
       recoge: 5200,                  // ms hasta que la conversación se recoge sola (0 = nunca)
     });
     p.envia('Hola');  p.nueva();  p.modelo('rapido');

   Qué cambia qué: --pr-papel es el fondo, --pr-caja la caja, --pr-tinta el
   texto, --pr-terra el único acento (y --pr-terra-texto su versión para
   texto pequeño); --pr-cod-* los colores del bloque de código. Solo se
   anima transform y opacity (y la altura de la fila de adjuntos). En
   movimiento reducido no hay FLIP ni escritura: la respuesta llega entera.
   Sin dependencias.
   ===================================================================== */
(function () {
  'use strict';

  /* ── resortes: se convierten en curvas CSS linear() para la Web Animations API ── */
  function muelle(k, c) {
    const pts = [0];
    let x = 0, v = 0, t = 0;
    while (t < 3) {
      v += (k * (1 - x) - c * v) / 240; x += v / 240; t += 1 / 240;
      pts.push(x);
      if (t > .15 && Math.abs(1 - x) < .001 && Math.abs(v) < .01) break;
    }
    const out = [];
    for (let i = 0; i <= 48; i++) out.push(pts[Math.round(i / 48 * (pts.length - 1))].toFixed(4));
    out[48] = '1';
    return { easing: 'linear(' + out.join(', ') + ')', duration: Math.round(t * 1000) };
  }
  const esc = s => String(s).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

  /* ── los datos de la demostración ───────────────────────────────────
     nivel dibuja las barritas del desplegable; vel multiplica la velocidad
     de escritura y espera es el tiempo de «pensando» antes de empezar. */
  const MODELOS = [
    { id: 'rapido', nombre: 'Rápido', desc: 'Respuestas ágiles para el día a día', nivel: 1, vel: 1.55, espera: .22 },
    { id: 'equilibrado', nombre: 'Equilibrado', desc: 'El punto medio entre velocidad y detalle', nivel: 2, vel: 1, espera: .55 },
    { id: 'profundo', nombre: 'Profundo', desc: 'Razona con calma los temas difíciles', nivel: 3, vel: .72, espera: 1.15 },
  ];
  const ARCHIVOS = [
    { nombre: 'app.js', tam: '4 KB', tipo: 'codigo' },
    { nombre: 'resumen.pdf', tam: '1,2 MB', tipo: 'pdf' },
    { nombre: 'gastos.csv', tam: '18 KB', tipo: 'tabla' },
    { nombre: 'paisaje.jpg', tam: '2,4 MB', tipo: 'imagen' },
  ];
  const IC = {
    codigo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 8-4 4 4 4M15 8l4 4-4 4M13.2 6.5l-2.4 11"/></svg>',
    resumen: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3.5" width="14" height="17" rx="3"/><path d="M8.5 8.5h7M8.5 12h7M8.5 15.5h4"/></svg>',
    semana: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14.5" rx="3.2"/><path d="M4 10h16M8.5 3.8v3.4M15.5 3.8v3.4M8.5 14h2M13.5 14h2M8.5 17h2"/></svg>',
  };
  const SUGERENCIAS = [
    { id: 'codigo', titulo: 'Explica un código', sub: 'Qué hace una función, paso a paso', texto: 'Explícame qué hace esta función, paso a paso.' },
    { id: 'resumen', titulo: 'Resume un documento', sub: 'Las ideas centrales en pocas líneas', texto: 'Resume en tres ideas el documento adjunto.', adjunto: 1 },
    { id: 'semana', titulo: 'Planifica mi semana', sub: 'Un horario de estudio realista', texto: 'Ayúdame a planificar una semana de estudio.' },
  ];
  // cada tema tiene dos versiones (regenerar pasa a la otra); t: p (párrafo), ul (lista), code (bloque de código)
  const CODIGO = 'function total(precios) {\n  const suma = precios.reduce((a, p) => a + p, 0);\n  const final = suma > 100 ? suma * 0.9 : suma;\n  return Number(final.toFixed(2));\n}';
  const RESPUESTAS = {
    codigo: [[
      { t: 'p', s: 'Esa función suma los precios y aplica un descuento. Lo hace en tres pasos:' },
      { t: 'ul', items: ['Suma todos los precios con reduce.', 'Si la suma pasa de 100, rebaja un 10 %.', 'Redondea a dos decimales.'] },
      { t: 'code', lang: 'js', s: CODIGO },
    ], [
      { t: 'p', s: 'Dicho en corto: suma los precios y, si el total es alto, le quita un diez por ciento.' },
      { t: 'code', lang: 'js', s: '// con descuento solo si se pasa de 100\nconst conDescuento = suma > 100;\nreturn conDescuento ? suma * 0.9 : suma;' },
      { t: 'p', s: 'Si quieres, la reescribo con nombres más claros.' },
    ]],
    resumen: [[
      { t: 'p', s: 'Estas son las tres ideas centrales del documento:' },
      { t: 'ul', items: ['El proyecto necesita un plazo más realista.', 'Dos tareas bloquean al resto: conviene empezar por ellas.', 'El presupuesto alcanza si se recorta la fase de pruebas.'] },
      { t: 'p', s: 'Si quieres, lo convierto en una lista de tareas con fechas.' },
    ], [
      { t: 'p', s: 'En una línea: hay que mover la fecha, atacar primero lo que bloquea y ahorrar en pruebas.' },
      { t: 'ul', items: ['Plazo: sumar dos semanas de margen.', 'Prioridad: las dos tareas que bloquean.'] },
    ]],
    semana: [[
      { t: 'p', s: 'Una semana de estudio funciona mejor con bloques cortos y un día libre:' },
      { t: 'ul', items: ['Lunes y martes: lectura y apuntes, dos bloques de 50 minutos.', 'Miércoles y jueves: ejercicios y repaso de errores.', 'Viernes: un resumen de una página y autoevaluación.'] },
      { t: 'p', s: 'El fin de semana descansa; el domingo por la noche, revisa el plan.' },
    ], [
      { t: 'p', s: 'Otra opción: estudiar menos horas pero cada día.' },
      { t: 'ul', items: ['Cada mañana, un bloque de 40 minutos.', 'Cada tarde, repaso rápido de 15.'] },
    ]],
  };

  // el resaltado del bloque de código: comentarios, cadenas, números, palabras clave y nombres de función
  function resalta(src) {
    const re = /(\/\/[^\n]*)|("(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?|`(?:[^`\\]|\\.)*`?)|(\b\d+(?:\.\d+)?\b)|(\b(?:function|const|let|var|return|if|else|for|while|of|in|new|class|async|await|import|from|export|true|false|null)\b)|(\b[A-Za-z_$][\w$]*(?=\())/g;
    let out = '', i = 0, m;
    while ((m = re.exec(src))) {
      out += esc(src.slice(i, m.index));
      out += '<span class="c-' + (m[1] ? 'c' : m[2] ? 's' : m[3] ? 'n' : m[4] ? 'k' : 'f') + '">' + esc(m[0]) + '</span>';
      i = m.index + m[0].length;
    }
    return out + esc(src.slice(i));
  }

  const SVG_COPIA = '<svg class="pr-i-copia" viewBox="0 0 24 24" aria-hidden="true"><rect x="8.5" y="8.5" width="11" height="11" rx="3"/><path d="M15.5 8.5V7a2.5 2.5 0 0 0-2.5-2.5H7A2.5 2.5 0 0 0 4.5 7v6A2.5 2.5 0 0 0 7 15.5h1.5"/></svg><svg class="pr-i-ok" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.6 4.6L19 7.6" pathLength="1"/></svg>';
  const SVG_QUITA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  const SVG_OK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.6 4.6L19 7.6"/></svg>';

  function Pregunta(raiz, opciones) {
    const o = Object.assign({ modelos: MODELOS, sugerencias: SUGERENCIAS, respuestas: RESPUESTAS, responder: null, velocidad: 230, recoge: 5200 }, opciones);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const $ = s => raiz.querySelector(s);
    const SALTO = muelle(170, 19), PUNTO = muelle(260, 21);
    raiz.style.setProperty('--pr-muelle', muelle(210, 15).easing);

    const caja = $('[data-caja]'), campo = $('[data-campo]'), zonaAdj = $('[data-adjuntos]'), fila = $('[data-adjuntos-fila]');
    const enviarBtn = $('[data-enviar]'), adjBtn = $('[data-adjuntar]'), modeloBtn = $('[data-modelo]'), modeloTxt = $('[data-modelo-txt]'), menu = $('[data-menu]');
    const hilo = $('[data-hilo]'), nuevaBtn = $('[data-nueva]'), inicio = $('[data-inicio]'), sugEl = $('[data-sug]'), vivo = $('[data-vivo]');
    const avisa = s => { vivo.textContent = ''; vivo.textContent = s; };

    // los relojes: nueva() y detiene() los cancelan
    const relojes = new Set();
    const luego = (fn, ms) => { const id = setTimeout(() => { relojes.delete(id); fn(); }, ms); relojes.add(id); return id; };
    const cancela = id => { clearTimeout(id); relojes.delete(id); };

    let modeloIdx = 1, adjuntos = [], flujo = null, turnos = 0, variante = 0, sugActiva = null, ultima = null, recogeId = 0, abierto = false, activo = 1, ultimaIA = null, pegado = true;

    /* ── el desplegable de modelo ───────────────────────────────────── */
    o.modelos.forEach((m, i) => {
      const op = document.createElement('div');
      op.className = 'pr-op'; op.id = 'pr-op-' + m.id; op.dataset.op = m.id; op.setAttribute('role', 'option'); op.setAttribute('aria-selected', String(i === modeloIdx)); op.style.setProperty('--k', i);
      op.innerHTML = '<span class="pr-op-ico" aria-hidden="true"><i class="' + (m.nivel >= 1 ? 'on' : '') + '"></i><i class="' + (m.nivel >= 2 ? 'on' : '') + '"></i><i class="' + (m.nivel >= 3 ? 'on' : '') + '"></i></span>' +
        '<span class="pr-op-txt"><b>' + esc(m.nombre) + '</b><small>' + esc(m.desc) + '</small></span>' + SVG_OK;
      op.addEventListener('click', () => { elige(i); cierraMenu(true); });
      op.addEventListener('pointermove', () => { if (activo !== i) { activo = i; marcaActivo(); } });
      menu.appendChild(op);
    });
    const ops = Array.from(menu.children);
    function marcaActivo() {
      ops.forEach((op, i) => op.classList.toggle('is-activo', i === activo));
      menu.setAttribute('aria-activedescendant', ops[activo].id);
    }
    function elige(i) {
      if (i === modeloIdx && modeloTxt.textContent === o.modelos[i].nombre) return;
      modeloIdx = i;
      ops.forEach((op, k) => op.setAttribute('aria-selected', String(k === i)));
      modeloTxt.textContent = o.modelos[i].nombre;
      if (!reduce) {
        modeloTxt.animate([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: 380, easing: 'cubic-bezier(.22, 1, .36, 1)' });
        $('.pr-punto').animate([{ transform: 'scale(.4)' }, { transform: 'none' }], { duration: PUNTO.duration, easing: PUNTO.easing });
      }
      avisa('Modelo ' + o.modelos[i].nombre + '. ' + o.modelos[i].desc);
    }
    function abreMenu() {
      if (abierto) return;
      abierto = true;
      const r = modeloBtn.getBoundingClientRect(), h = menu.offsetHeight + 16;
      menu.classList.toggle('is-arriba', innerHeight - r.bottom < h && r.top > h);
      modeloBtn.setAttribute('aria-expanded', 'true');
      activo = modeloIdx; marcaActivo();
      void menu.offsetWidth;
      menu.classList.add('is-abierto');
      menu.focus({ preventScroll: true });
    }
    function cierraMenu(devuelve) {
      if (!abierto) return;
      abierto = false;
      menu.classList.remove('is-abierto');
      modeloBtn.setAttribute('aria-expanded', 'false');
      if (devuelve) modeloBtn.focus({ preventScroll: true });
    }
    modeloBtn.addEventListener('click', () => abierto ? cierraMenu(true) : abreMenu());
    modeloBtn.addEventListener('keydown', e => { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); abreMenu(); } });
    menu.addEventListener('keydown', e => {
      const n = ops.length;
      if (e.key === 'ArrowDown') activo = (activo + 1) % n;
      else if (e.key === 'ArrowUp') activo = (activo - 1 + n) % n;
      else if (e.key === 'Home') activo = 0;
      else if (e.key === 'End') activo = n - 1;
      else if (e.key === 'Enter' || e.key === ' ') { elige(activo); cierraMenu(true); }
      else if (e.key === 'Tab') cierraMenu(false);
      else return;
      e.preventDefault(); marcaActivo();
    });
    document.addEventListener('pointerdown', e => { if (abierto && !menu.contains(e.target) && !modeloBtn.contains(e.target)) cierraMenu(false); });

    /* ── la caja: crece con el texto, Intro envía ───────────────────── */
    function ajusta() { campo.style.height = 'auto'; campo.style.height = Math.min(campo.scrollHeight, 168) + 'px'; }
    function actualizaEnviar() {
      enviarBtn.disabled = !flujo && !campo.value.trim() && !adjuntos.length;
      enviarBtn.setAttribute('aria-label', flujo ? 'Detener la respuesta' : 'Enviar');
    }
    campo.addEventListener('input', () => { sugActiva = null; ajusta(); actualizaEnviar(); });
    campo.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); enviar(); }
    });
    caja.addEventListener('submit', e => { e.preventDefault(); if (flujo) detiene(); else enviar(); });
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      if (abierto) { cierraMenu(true); e.preventDefault(); } else if (flujo) { detiene(); e.preventDefault(); }
    });
    // las sugerencias escriben su texto en la caja, rápido, y dejan el foco listo para enviar
    function rellena(texto) {
      campo.value = ''; campo.focus({ preventScroll: true });
      let i = 0;
      const paso = () => {
        i = reduce ? texto.length : Math.min(texto.length, i + 2);
        campo.value = texto.slice(0, i); ajusta(); actualizaEnviar();
        if (i < texto.length) luego(paso, 16);
      };
      paso();
    }
    o.sugerencias.forEach((s, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pr-tarjeta'; b.dataset.sug = s.id; b.style.setProperty('--k', i);
      b.innerHTML = '<span class="pr-t-ico">' + (IC[s.id] || IC.resumen) + '</span><b>' + esc(s.titulo) + '</b><small>' + esc(s.sub) + '</small>';
      b.addEventListener('click', () => {
        cierraMenu(false);
        if (s.adjunto != null && !adjuntos.length) anade(ARCHIVOS[s.adjunto]);
        rellena(s.texto); sugActiva = s.id;
      });
      sugEl.appendChild(b);
    });

    /* ── los adjuntos ───────────────────────────────────────────────── */
    let siguiente = 0;
    function chip(a, mini) {
      const el = document.createElement('div');
      el.className = 'pr-chip';
      el.innerHTML = '<span class="pr-mini" data-tipo="' + a.tipo + '"></span><span class="pr-chip-txt"><b>' + esc(a.nombre) + '</b><small>' + esc(a.tam) + '</small></span>' + (mini ? '' : '<button type="button" aria-label="Quitar ' + esc(a.nombre) + '">' + SVG_QUITA + '</button>');
      return el;
    }
    function anade(a) {
      if (adjuntos.length >= 3) {
        if (!reduce) adjBtn.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-5px)' }, { transform: 'translateX(5px)' }, { transform: 'translateX(0)' }], { duration: 300 });
        avisa('Máximo tres archivos');
        return;
      }
      const item = Object.assign({}, a), el = chip(a, false);
      item.el = el; adjuntos.push(item);
      fila.appendChild(el); zonaAdj.classList.add('is-con');
      if (!reduce) el.animate([{ transform: 'translateY(16px) scale(.55)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: SALTO.duration, easing: SALTO.easing });
      el.querySelector('button').addEventListener('click', () => quita(item));
      actualizaEnviar(); avisa('Adjunto ' + a.nombre);
    }
    function quita(item) {
      const i = adjuntos.indexOf(item); if (i < 0) return;
      adjuntos.splice(i, 1);
      const fin = () => { item.el.remove(); };
      if (reduce) fin(); else item.el.animate([{ transform: 'none', opacity: 1 }, { transform: 'scale(.6) translateY(8px)', opacity: 0 }], { duration: 220, easing: 'cubic-bezier(.5, 0, .9, .5)', fill: 'forwards' }).onfinish = fin;
      if (!adjuntos.length) zonaAdj.classList.remove('is-con');
      actualizaEnviar(); avisa('Adjunto quitado'); campo.focus({ preventScroll: true });
    }
    adjBtn.addEventListener('click', () => { anade(ARCHIVOS[siguiente % ARCHIVOS.length]); siguiente++; });
    // arrastrar archivos de verdad sobre la caja: solo se muestran como chips (no se sube nada)
    const tipoDe = f => /^image\//.test(f.type) ? 'imagen' : /pdf/.test(f.type) ? 'pdf' : /csv|sheet|excel/.test(f.type) ? 'tabla' : 'codigo';
    const tam = n => n < 1024 * 1024 ? Math.max(1, Math.round(n / 1024)) + ' KB' : (n / 1048576).toFixed(1).replace('.', ',') + ' MB';
    ['dragenter', 'dragover'].forEach(t => caja.addEventListener(t, e => { e.preventDefault(); caja.classList.add('is-suelta'); }));
    ['dragleave', 'drop'].forEach(t => caja.addEventListener(t, e => { e.preventDefault(); caja.classList.remove('is-suelta'); }));
    caja.addEventListener('drop', e => { Array.from(e.dataTransfer.files || []).forEach(f => anade({ nombre: f.name, tam: tam(f.size), tipo: tipoDe(f) })); });

    /* ── FLIP y fantasmas ───────────────────────────────────────────── */
    // mide dónde estaba, deja que cambie el diseño y anima desde el sitio anterior con un resorte
    function flip(el, antes, anim) {
      if (reduce) return;
      const a = anim || SALTO, ahora = el.getBoundingClientRect(), dx = antes.left - ahora.left, dy = antes.top - ahora.top;
      if (Math.abs(dx) < .5 && Math.abs(dy) < .5) return;
      el.animate([{ transform: 'translate(' + dx + 'px, ' + dy + 'px)' }, { transform: 'none' }], { duration: a.duration, easing: a.easing });
    }
    // una copia que se queda donde estaba el elemento y se desvanece, para que el cambio de fase no la corte
    function fantasma(el) {
      const r = el.getBoundingClientRect(), g = el.cloneNode(true);
      g.removeAttribute('id'); g.querySelectorAll('[id]').forEach(n => n.removeAttribute('id'));
      g.classList.add('pr-fantasma'); g.setAttribute('aria-hidden', 'true'); g.inert = true;
      g.style.cssText = 'position:fixed;left:' + r.left + 'px;top:' + r.top + 'px;width:' + r.width + 'px;height:' + r.height + 'px;margin:0;z-index:1;pointer-events:none;';
      raiz.appendChild(g);
      g.animate([{ opacity: 1, transform: 'none', filter: 'blur(0)' }, { opacity: 0, transform: 'translateY(-24px) scale(.97)', filter: 'blur(6px)' }], { duration: 340, easing: 'cubic-bezier(.5, 0, .9, .5)', fill: 'forwards' }).onfinish = () => g.remove();
    }
    // entradas escalonadas del estado inicial
    function entradas() {
      if (reduce) return;
      const pila = [inicio.firstElementChild, inicio.querySelector('h1'), caja].concat(Array.from(sugEl.children));
      pila.forEach((el, i) => el.animate([{ opacity: 0, transform: 'translateY(18px)', filter: 'blur(4px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }], { duration: 700, delay: 60 + i * 70, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'backwards' }));
    }

    /* ── enviar ─────────────────────────────────────────────────────── */
    const turnoIA = () => {
      const t = document.createElement('article');
      t.className = 'pr-turno pr-ia';
      t.innerHTML = '<span class="pr-avatar" aria-hidden="true"><svg class="pr-sol"><use href="#pr-sol"/></svg></span><div class="pr-cuerpo"><span class="pr-pensando" role="img" aria-label="Pensando"><i></i><i></i><i></i></span></div>';
      return t;
    };
    function enviar() {
      if (flujo) return;
      const texto = campo.value.trim();
      if (!texto && !adjuntos.length) return;
      cierraMenu(false); cancela(recogeId);
      const primera = raiz.dataset.fase === 'inicio', antes = caja.getBoundingClientRect(), campoR = campo.getBoundingClientRect();
      const adj = adjuntos.map(a => ({ nombre: a.nombre, tam: a.tam, tipo: a.tipo }));
      if (primera) { fantasma(inicio); fantasma(sugEl); raiz.dataset.fase = 'chat'; }
      // la burbuja del usuario
      const yo = document.createElement('article'), burb = document.createElement('div');
      yo.className = 'pr-turno pr-yo'; burb.className = 'pr-burbuja';
      if (adj.length) {
        const cs = document.createElement('div'); cs.className = 'pr-chips-mini';
        adj.forEach(a => cs.appendChild(chip(a, true)));
        burb.appendChild(cs);
      }
      const p = document.createElement('p'); p.textContent = texto; burb.appendChild(p);
      yo.appendChild(burb); hilo.appendChild(yo);
      // la caja se vacía
      campo.value = ''; ajusta();
      adjuntos.forEach(a => a.el.remove()); adjuntos = []; zonaAdj.classList.remove('is-con');
      pegado = true; hilo.scrollTop = hilo.scrollHeight;
      if (primera) flip(caja, antes);
      // el texto sale de la caja hacia su burbuja
      if (!reduce) {
        const b = burb.getBoundingClientRect();
        burb.animate([{ transform: 'translate(' + (campoR.left - b.left + 8) + 'px, ' + (campoR.top - b.top) + 'px) scale(.96)', opacity: .2 }, { transform: 'none', opacity: 1 }], { duration: SALTO.duration, easing: SALTO.easing });
      }
      ultima = { texto, adj, tema: elegirTema(texto) };
      sugActiva = null; turnos++; variante = 0;
      responde();
    }
    function elegirTema(texto) {
      if (sugActiva) return sugActiva;
      const t = texto.toLowerCase(), claves = Object.keys(o.respuestas);
      if (/c[oó]digo|funci[oó]n|error|script|javascript|programa/.test(t) && o.respuestas.codigo) return 'codigo';
      if (/resum|document|texto|idea|pdf/.test(t) && o.respuestas.resumen) return 'resumen';
      if (/semana|plan|estudi|horario|agenda/.test(t) && o.respuestas.semana) return 'semana';
      return claves[(turnos) % claves.length];
    }

    /* ── la respuesta: «pensando», y luego se escribe a bloques ─────── */
    function responde() {
      const modelo = o.modelos[modeloIdx], t = turnoIA();
      hilo.appendChild(t); ultimaIA = t;
      const cuerpo = t.querySelector('.pr-cuerpo');
      flujo = { cuerpo, t, bloques: null, i: 0, acum: 0, pausa: 0, tiempo: 0, listo: false, modelo, parado: false, cursor: null, raf: 0, previo: 0 };
      raiz.classList.add('is-flujo'); hilo.setAttribute('aria-busy', 'true'); actualizaEnviar(); avisa('Pensando');
      if (!reduce) t.animate([{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], { duration: 520, easing: 'cubic-bezier(.22, 1, .36, 1)' });
      if (pegado) hilo.scrollTop = hilo.scrollHeight;
      const f = flujo;
      const datos = o.responder ? Promise.resolve(o.responder(ultima.texto, { modelo: modelo.id, adjuntos: ultima.adj, tema: ultima.tema, variante })) : Promise.resolve((o.respuestas[ultima.tema] || o.respuestas[Object.keys(o.respuestas)[0]])[variante % 2 < (o.respuestas[ultima.tema] || [0, 0]).length ? variante % 2 : 0]);
      const espera = new Promise(res => luego(res, reduce ? 0 : modelo.espera * 1000));
      Promise.all([datos, espera]).then(([bloques]) => { if (flujo === f && !f.parado) empieza(bloques); }, () => { if (flujo === f) termina(true); });
    }
    function empieza(bloques) {
      const f = flujo;
      f.bloques = bloques.map(b => Object.assign({}, b)); f.cuerpo.textContent = '';
      f.cursor = document.createElement('i'); f.cursor.className = 'pr-cursor'; f.cursor.setAttribute('aria-hidden', 'true');
      avisa('Escribiendo la respuesta');
      if (reduce) { while (!f.listo) { f.acum = 1; emite(); } termina(false); return; }
      f.previo = 0; f.raf = requestAnimationFrame(cuadro);
    }
    function creaBloque(b) {
      const c = flujo.cuerpo;
      if (b.t === 'p') { b.el = document.createElement('p'); b.el.className = 'pr-p'; c.appendChild(b.el); }
      else if (b.t === 'ul') { b.el = document.createElement('ul'); b.el.className = 'pr-ul'; c.appendChild(b.el); b.k = 0; b.li = null; }
      else {
        b.el = document.createElement('div'); b.el.className = 'pr-bloque';
        b.el.innerHTML = '<div class="pr-bloque-cab"><span>' + esc(b.lang || 'código') + '</span><button type="button" class="pr-copia" aria-label="Copiar el código" data-aviso="Copiado">' + SVG_COPIA + '</button></div><pre><code></code></pre>';
        b.cod = b.el.querySelector('code'); c.appendChild(b.el);
        const btn = b.el.querySelector('.pr-copia'); btn.addEventListener('click', () => copia(b.s, btn));
      }
      b.n = 0;
    }
    // escribe un carácter; devuelve false si hay que esperar (pausa) y marca listo al terminar
    function emite() {
      const f = flujo, b = f.bloques[f.i];
      if (!b) { f.listo = true; return false; }
      if (!b.el) creaBloque(b);
      let ch = '', fin = false;
      if (b.t === 'p') {
        ch = b.s[b.n++]; b.el.textContent = b.s.slice(0, b.n); b.el.appendChild(f.cursor); fin = b.n >= b.s.length;
      } else if (b.t === 'ul') {
        const txt = b.items[b.k];
        if (!b.li) { b.li = document.createElement('li'); b.el.appendChild(b.li); b.n = 0; }
        ch = txt[b.n++]; b.li.textContent = txt.slice(0, b.n); b.li.appendChild(f.cursor);
        if (b.n >= txt.length) { b.k++; b.li = null; fin = b.k >= b.items.length; if (!fin) f.pausa += .07; }
      } else {
        ch = b.s[b.n++]; b.cod.innerHTML = resalta(b.s.slice(0, b.n)); b.cod.appendChild(f.cursor); fin = b.n >= b.s.length;
      }
      // las pausas de la lectura: más largas tras un punto, cortas tras una coma; en el código, solo al saltar de línea
      f.pausa += b.t === 'code' ? (ch === '\n' ? .05 : 0) : /[.:?!]/.test(ch) ? .07 : /[,;]/.test(ch) ? .035 : 0;
      if (fin) { f.i++; f.pausa += .1; if (f.i >= f.bloques.length) f.listo = true; }
      return f.pausa <= 0 && !f.listo;
    }
    function cuadro(ms) {
      const f = flujo; if (!f) return;
      f.raf = 0;
      const dt = f.previo ? Math.min(.05, (ms - f.previo) / 1000) : 1 / 60; f.previo = ms; f.tiempo += dt;
      if (f.pausa > 0) f.pausa -= dt;
      else {
        f.acum += dt * o.velocidad * f.modelo.vel;
        while (f.acum >= 1 && !f.listo) { f.acum -= 1; if (!emite()) break; }
      }
      if (pegado) hilo.scrollTop = hilo.scrollHeight;
      if (f.listo) termina(false); else f.raf = requestAnimationFrame(cuadro);
    }
    hilo.addEventListener('scroll', () => { pegado = hilo.scrollHeight - hilo.scrollTop - hilo.clientHeight < 24; });

    function detiene() {
      if (!flujo) return;
      const f = flujo; f.parado = true;
      if (f.raf) cancelAnimationFrame(f.raf);
      termina(true);
    }
    function textoPlano(f) {
      return f.bloques.filter(b => b.el).map(b => b.t === 'p' ? b.s : b.t === 'ul' ? b.items.slice(0, b.k + (b.li ? 1 : 0)).map(i => '• ' + i).join('\n') : '```' + (b.lang || '') + '\n' + b.s.slice(0, b.n) + '\n```').join('\n\n');
    }
    function termina(parado) {
      const f = flujo; if (!f) return;
      if (f.raf) cancelAnimationFrame(f.raf);
      if (f.cursor) f.cursor.remove();
      if (!f.bloques) f.cuerpo.textContent = '';
      f.cuerpo.querySelectorAll('.pr-pensando').forEach(n => n.remove());
      const plano = f.bloques ? textoPlano(f) : '';
      if (parado) { const p = document.createElement('p'); p.className = 'pr-parada'; p.textContent = 'Respuesta detenida.'; f.cuerpo.appendChild(p); }
      const acc = document.createElement('div');
      acc.className = 'pr-acciones';
      acc.innerHTML = '<button type="button" class="pr-copia" data-copiar aria-label="Copiar la respuesta" data-aviso="Copiado">' + SVG_COPIA + '</button>' +
        '<button type="button" class="pr-acc" data-regenerar aria-label="Regenerar la respuesta"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12a7.5 7.5 0 1 1-2.4-5.5M19.5 4.5v4.2h-4.2"/></svg></button>' +
        '<span class="pr-meta">' + esc(f.modelo.nombre) + ' · ' + (Math.max(.4, f.tiempo)).toFixed(1).replace('.', ',') + ' s</span>';
      f.cuerpo.appendChild(acc);
      const cbtn = acc.querySelector('[data-copiar]'), rbtn = acc.querySelector('[data-regenerar]');
      cbtn.addEventListener('click', () => copia(plano, cbtn));
      rbtn.addEventListener('click', () => regenera(rbtn));
      raiz.classList.remove('is-flujo'); hilo.removeAttribute('aria-busy');
      flujo = null; actualizaEnviar();
      if (pegado) hilo.scrollTop = hilo.scrollHeight;
      avisa(parado ? 'Respuesta detenida' : 'Respuesta lista');
      if (!parado) armaRecogida();
    }
    // copiar: el botón se vuelve ✓ (el trazo se dibuja) y vuelve solo
    function copia(texto, btn) {
      try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(texto).catch(() => {}); } catch (e) { /* sin permiso: el ✓ se muestra igual */ }
      btn.classList.add('is-ok'); avisa('Copiado al portapapeles');
      if (btn._id) cancela(btn._id);
      btn._id = luego(() => btn.classList.remove('is-ok'), 1900);
    }
    function regenera(btn) {
      if (flujo || !ultima) return;
      cancela(recogeId);
      if (!reduce) btn.querySelector('svg').animate([{ transform: 'rotate(0)' }, { transform: 'rotate(360deg)' }], { duration: 600, easing: 'cubic-bezier(.22, 1, .36, 1)' });
      if (ultimaIA) ultimaIA.remove();
      variante++; responde();
    }

    /* ── recoger y volver al principio ──────────────────────────────── */
    function armaRecogida() {
      cancela(recogeId);
      if (o.recoge > 0) recogeId = luego(() => nueva(false), o.recoge);
    }
    ['pointerdown', 'keydown', 'focusin'].forEach(t => raiz.addEventListener(t, () => cancela(recogeId)));
    [hilo, caja].forEach(el => el.addEventListener('pointermove', () => cancela(recogeId)));
    function nueva(desdeTeclado) {
      if (raiz.dataset.fase === 'inicio' && !hilo.children.length) { campo.value = ''; ajusta(); actualizaEnviar(); return; }
      if (flujo) { flujo.parado = true; if (flujo.raf) cancelAnimationFrame(flujo.raf); flujo.cursor && flujo.cursor.remove(); raiz.classList.remove('is-flujo'); flujo = null; }
      cancela(recogeId); cierraMenu(false);
      const hecho = () => {
        const antes = caja.getBoundingClientRect();
        hilo.textContent = ''; ultima = null; ultimaIA = null; turnos = turnos; variante = 0;
        raiz.dataset.fase = 'inicio';
        adjuntos.forEach(a => a.el.remove()); adjuntos = []; zonaAdj.classList.remove('is-con');
        campo.value = ''; ajusta(); actualizaEnviar();
        flip(caja, antes);
        entradas2();
        avisa('Nueva consulta');
        if (desdeTeclado) campo.focus({ preventScroll: true });
      };
      if (reduce) hecho();
      else {
        hilo.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(14px)' }], { duration: 260, easing: 'cubic-bezier(.5, 0, .9, .5)', fill: 'forwards' });
        luego(() => { hecho(); hilo.getAnimations().forEach(a => a.cancel()); }, 250);
      }
    }
    // la vuelta del saludo y las sugerencias: llegan escalonadas (sin repetir la caja, que ya se mueve con FLIP)
    function entradas2() {
      if (reduce) return;
      const pila = [inicio.firstElementChild, inicio.querySelector('h1')].concat(Array.from(sugEl.children));
      pila.forEach((el, i) => el.animate([{ opacity: 0, transform: 'translateY(16px)', filter: 'blur(4px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }], { duration: 700, delay: 140 + i * 70, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'backwards' }));
      const svg = inicio.querySelector('h1 em svg'); if (svg) svg.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 900, delay: 500, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'backwards' });
    }
    nuevaBtn.addEventListener('click', e => nueva(e.detail === 0));

    // todo listo (la mono del código se pide ya, para que no aparezca tarde en el primer bloque)
    if (document.fonts && document.fonts.load) document.fonts.load('400 14px "Azeret Mono"');
    ajusta(); actualizaEnviar(); entradas();
    return {
      envia: t => { campo.value = t; ajusta(); actualizaEnviar(); enviar(); },
      nueva: () => nueva(false),
      modelo: id => { const i = o.modelos.findIndex(m => m.id === id); if (i > -1) elige(i); },
    };
  }

  window.Pregunta = Pregunta;
})();
