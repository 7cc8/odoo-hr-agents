/* =====================================================================
   Mirador · Moxen
   Vistas guardadas de una tabla: pestañas con los filtros que cada una
   recuerda, filtros que se pueden tocar y tres destinos para lo que cambies:
   guardarlo, guardarlo como vista nueva o descartarlo.

   · Cambiar de vista: las filas se REORDENAN con FLIP (cada una viaja con un
     resorte hasta su sitio nuevo; las que sobran se desvanecen y las que llegan
     entran escalonadas), los chips de filtro entran y salen con resorte y la
     barra de debajo de las pestañas se desliza hasta la nueva.
   · Tocar un filtro: cada chip abre un menú de valores («+ Filtro» ofrece los que
     faltan); al cambiar uno, el chip se tiñe de ámbar, la pestaña muestra un
     PUNTO de «modificada» y, con un resorte escalonado, aparecen Descartar,
     Guardar como nueva y Guardar. Cada pestaña recuerda cuántas tareas muestra.
   · Descartar REBOBINA: la vista no vuelve de golpe; deshace tus cambios paso
     a paso como una cinta (una cabeza ámbar retrocede por la pista, los valores
     de los chips ruedan hacia atrás y las filas siguen a cada paso).
   · Guardar como nueva: una pestaña SALE del botón, vuela en arco y cae al final
     de la fila con un pequeño rebote, con el nombre editable al instante
     (Intro lo fija, Esc deja el que propone). La vista de origen vuelve a lo guardado.
   · Guardar fija los filtros (el punto se apaga y el contador da un destello);
     las pestañas se reordenan arrastrándolas (las vecinas se apartan con resorte) y
     las propias se quitan con su ×. «Restablecer vistas» devuelve el ejemplo al inicio.

   Teclado: pestañas con ← → Inicio Fin; chips y menús con Intro, ↑ ↓ y Esc; todo lo
   demás son botones. Con movimiento reducido no hay resortes, vuelos ni cinta
   animada: los cambios son directos y se anuncian igual.

   Montaje (se inicia con la llamada de index.html; el HTML de esta demo es la plantilla):
     const m = Mirador(document.querySelector('[data-mirador]'), {
       vista: 'pend',                                     // la vista con la que empieza
       alCambiar: ({ vistas, activa }) => {},             // al guardar, crear, borrar o reordenar
     });
     m.activa('venc');  m.vistas();  m.restablece();

   Qué cambia qué: las TAREAS y los FILTROS (con su función de prueba) están justo abajo; las vistas
   iniciales, en VISTAS_INICIALES; los colores, al principio de mirador.css (--mi-petroleo es el único
   acento y --mi-ambar solo marca lo modificado o vencido). Sin dependencias; el tiempo viene de
   requestAnimationFrame, timers y Web Animations (nada de Date): la página y el vídeo coinciden.
   ===================================================================== */
(function () {
  'use strict';

  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  const quieto = () => mq.matches;
  const lim = (v, a, b) => Math.max(a, Math.min(b, v));
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

  /* ── los datos de ejemplo ─────────────────────────────────────────── */
  const T = (id, nombre, resp, estado, prio, dias) => ({ id, nombre, resp, estado, prio, dias });
  const TAREAS = [
    T(1, 'Revisar permisos de acceso', 'Yo', 'En curso', 'Alta', -2),
    T(2, 'Actualizar la guía de estilos', 'Diseño', 'Pendiente', 'Media', 3),
    T(3, 'Corregir el redondeo de totales', 'Yo', 'Pendiente', 'Alta', -1),
    T(4, 'Preparar la demo para el cliente', 'Desarrollo', 'En curso', 'Alta', 1),
    T(5, 'Responder consultas de facturación', 'Soporte', 'Pendiente', 'Media', 0),
    T(6, 'Auditar la accesibilidad de formularios', 'Diseño', 'En curso', 'Media', -3),
    T(7, 'Migrar imágenes a un formato moderno', 'Desarrollo', 'Pendiente', 'Baja', 5),
    T(8, 'Escribir las notas de la versión', 'Yo', 'Pendiente', 'Media', 2),
    T(9, 'Probar el flujo de registro', 'Yo', 'Hecha', 'Media', -4),
    T(10, 'Optimizar consultas del panel', 'Desarrollo', 'En curso', 'Alta', -1),
    T(11, 'Rediseñar la página de precios', 'Diseño', 'Pendiente', 'Alta', 4),
    T(12, 'Cerrar tickets antiguos', 'Soporte', 'Hecha', 'Baja', -5),
    T(13, 'Revisar textos del correo de bienvenida', 'Yo', 'En curso', 'Baja', 3),
    T(14, 'Configurar alertas de errores', 'Desarrollo', 'Pendiente', 'Alta', -2),
    T(15, 'Documentar la API de pagos', 'Desarrollo', 'Pendiente', 'Media', 6),
    T(16, 'Elegir los iconos de la nueva sección', 'Diseño', 'En curso', 'Baja', 2),
    T(17, 'Planificar la capacitación del equipo', 'Yo', 'Pendiente', 'Alta', 7),
    T(18, 'Revisar las métricas de la semana', 'Soporte', 'En curso', 'Media', 0),
  ];
  const FILTROS = {
    resp: { nombre: 'Responsable', opciones: ['Yo', 'Diseño', 'Desarrollo', 'Soporte'], prueba: (t, v) => t.resp === v },
    estado: { nombre: 'Estado', opciones: ['Abiertas', 'Pendiente', 'En curso', 'Hecha'], prueba: (t, v) => v === 'Abiertas' ? t.estado !== 'Hecha' : t.estado === v },
    vence: { nombre: 'Vence', opciones: ['Vencidas', 'Hoy', 'Esta semana'], prueba: (t, v) => v === 'Vencidas' ? t.dias < 0 && t.estado !== 'Hecha' : v === 'Hoy' ? t.dias === 0 : t.dias >= 0 && t.dias <= 7 },
    prio: { nombre: 'Prioridad', opciones: ['Alta', 'Media', 'Baja'], prueba: (t, v) => t.prio === v },
  };
  const ORDEN_F = ['resp', 'estado', 'vence', 'prio'];
  const RANGO = { Alta: 0, Media: 1, Baja: 2 };
  const ORDENES = {
    id: { nombre: 'número', f: (a, b) => a.id - b.id },
    dias: { nombre: 'vencimiento', f: (a, b) => a.dias - b.dias || a.id - b.id },
    prio: { nombre: 'prioridad', f: (a, b) => RANGO[a.prio] - RANGO[b.prio] || a.dias - b.dias },
  };
  const VISTAS_INICIALES = [
    { id: 'todas', nombre: 'Todas', guardado: {}, orden: 'id', fija: true },
    { id: 'pend', nombre: 'Mis pendientes', guardado: { resp: 'Yo', estado: 'Abiertas' }, orden: 'prio', fija: true },
    { id: 'venc', nombre: 'Vencidas', guardado: { estado: 'Abiertas', vence: 'Vencidas' }, orden: 'dias', fija: true },
  ];
  const copia = o => Object.assign({}, o);
  const iguales = (a, b) => { const ka = Object.keys(a), kb = Object.keys(b); return ka.length === kb.length && ka.every(k => a[k] === b[k]); };
  const pasa = (t, f) => Object.keys(f).every(k => FILTROS[k].prueba(t, f[k]));
  const filtradas = (v, f) => TAREAS.filter(t => pasa(t, f || v.actual)).sort(ORDENES[v.orden].f);
  const modificada = v => !iguales(v.actual, v.guardado);
  const plural = (n, u, p) => n + ' ' + (n === 1 ? u : p);

  const IC = {
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 12.6 4 4 8-9"/></svg>',
    x: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/></svg>',
    abajo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6.5 9.5 5.5 5.5 5.5-5.5"/></svg>',
    Yo: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="9" r="3.4"/><path d="M5.4 19c.9-3.4 3.5-5 6.6-5s5.7 1.6 6.6 5"/></svg>',
    Diseño: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19l.9-3.9L15.8 5.2a2 2 0 0 1 2.8 0l.2.2a2 2 0 0 1 0 2.8L8.9 18.1z"/><path d="m14 7 3 3"/></svg>',
    Desarrollo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8.6 8.2-4 3.8 4 3.8M15.4 8.2l4 3.8-4 3.8M13.2 6.4l-2.4 11.2"/></svg>',
    Soporte: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7.6"/><circle cx="12" cy="12" r="3"/><path d="m6.7 6.7 3.2 3.2M14.1 14.1l3.2 3.2M17.3 6.7l-3.2 3.2M9.9 14.1l-3.2 3.2"/></svg>',
  };

  function Mirador(raiz, opciones) {
    const op = Object.assign({ vista: 'pend', alCambiar: null }, opciones);
    const $ = (s, r) => (r || raiz).querySelector(s);
    const el = {
      ventana: $('[data-ventana]'), tabs: $('[data-tabs]'), indicador: $('[data-indicador]'), chips: $('[data-chips]'), mas: $('[data-mas]'),
      acciones: $('[data-acciones]'), descartar: $('[data-descartar]'), nueva: $('[data-nueva]'), guardar: $('[data-guardar]'),
      cinta: $('[data-cinta]'), cintaMarcas: $('[data-cinta-marcas]'), cintaCabeza: $('[data-cinta-cabeza]'), pasos: $('[data-pasos]'),
      cuerpo: $('[data-cuerpo]'), vacio: $('[data-vacio]'), resumen: $('[data-resumen]'), pieVista: $('[data-pie-vista]'), menu: $('[data-menu]'),
      reset: $('[data-restablece]'), vivo: $('[data-vivo]'),
    };
    const EASE = muelle(260, 21);
    raiz.style.setProperty('--mi-muelle', muelle(300, 21));
    const anuncia = t => { el.vivo.textContent = t; };
    const anima = (e, kf, o) => (quieto() || !e.animate) ? null : e.animate(kf, o);

    /* ── las vistas ───────────────────────────────────────────────── */
    let seq = 0;
    const nueva = d => Object.assign({}, d, { actual: copia(d.guardado), hist: [copia(d.guardado)] });
    let vistas = VISTAS_INICIALES.map(nueva);
    let activa = vistas.some(v => v.id === op.vista) ? op.vista : vistas[0].id;
    const porId = id => vistas.find(v => v.id === id);
    const vistaActiva = () => porId(activa);
    function notifica() { if (op.alCambiar) op.alCambiar({ vistas: vistas.map(v => ({ id: v.id, nombre: v.nombre, filtros: copia(v.guardado) })), activa }); }

    /* ── las filas (una por tarea, siempre las mismas) ──────────────── */
    const filas = new Map();
    const diaTxt = d => d === 0 ? 'hoy' : d === 1 ? 'mañana' : d > 0 ? 'en ' + d + ' d' : 'hace ' + (-d) + ' d';
    TAREAS.forEach(t => {
      const f = document.createElement('div');
      f.className = 'mi-fila' + (t.estado === 'Hecha' ? ' es-hecha' : '');
      f.setAttribute('role', 'row'); f.dataset.id = t.id;
      const clase = { Pendiente: 'e-pendiente', 'En curso': 'e-curso', Hecha: 'e-hecha' }[t.estado], p = { Alta: 3, Media: 2, Baja: 1 }[t.prio];
      f.innerHTML = '<div class="mi-f-tarea" role="cell"><span class="mi-ck">' + IC.check + '</span><span class="mi-f-nom"></span></div>'
        + '<div class="mi-f-resp" role="cell"><span class="mi-glifo' + (t.resp === 'Yo' ? ' es-yo' : '') + '">' + IC[t.resp] + '</span><span></span></div>'
        + '<div role="cell"><span class="mi-estado ' + clase + '"></span></div>'
        + '<div class="mi-f-prio" role="cell"><span class="mi-prio p' + p + '"><i></i><i></i><i></i></span><span class="mi-prio-t"></span></div>'
        + '<div class="mi-f-vence' + (t.dias < 0 && t.estado !== 'Hecha' ? ' es-tarde' : '') + '" role="cell"></div>';
      f.querySelector('.mi-f-nom').textContent = t.nombre;
      f.querySelector('.mi-f-resp span:last-child').textContent = t.resp;
      f.querySelector('.mi-estado').textContent = t.estado;
      f.querySelector('.mi-prio-t').textContent = t.prio;
      f.querySelector('.mi-f-vence').textContent = diaTxt(t.dias);
      f.dataset.vis = '0'; f.style.display = 'none';
      el.cuerpo.appendChild(f);
      filas.set(t.id, f);
    });

    function pintaFilas(animar, cambioDeVista) {
      const v = vistaActiva(), lista = filtradas(v), ids = lista.map(t => t.id);
      const base = el.cuerpo.getBoundingClientRect();
      const antes = new Map();
      filas.forEach((f, id) => { if (f.dataset.vis === '1') antes.set(id, f.getBoundingClientRect().top); });
      const fantasmas = [];
      if (animar && !quieto()) antes.forEach((top, id) => {
        if (ids.includes(id)) return;
        const g = filas.get(id).cloneNode(true);
        g.classList.add('mi-fantasma'); g.removeAttribute('data-id'); g.style.display = ''; g.style.top = (top - base.top + el.cuerpo.scrollTop) + 'px';
        fantasmas.push(g);
      });
      if (cambioDeVista) el.cuerpo.scrollTop = 0;
      filas.forEach((f, id) => { if (!ids.includes(id)) { f.style.display = 'none'; f.dataset.vis = '0'; } });
      lista.forEach(t => { const f = filas.get(t.id); f.style.display = ''; f.dataset.vis = '1'; el.cuerpo.appendChild(f); });
      fantasmas.forEach(g => {
        el.cuerpo.appendChild(g);
        const a = g.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(-14px) scale(.985)', offset: .6 }, { opacity: 0, transform: 'translateX(-14px) scale(.985)' }], { duration: 240, easing: 'ease-in', fill: 'forwards' });
        a.onfinish = () => g.remove();
      });
      if (animar && !quieto()) {
        let entra = 0;
        lista.forEach(t => {
          const f = filas.get(t.id), a = antes.get(t.id);
          if (a == null) f.animate([{ opacity: 0, transform: 'translateY(12px) scale(.97)' }, { opacity: 1, transform: 'none' }], { duration: 560, delay: 120 + Math.min(entra++, 8) * 34, easing: EASE, fill: 'backwards' });
          else { const dy = a - f.getBoundingClientRect().top; if (Math.abs(dy) > .5) f.animate([{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }], { duration: 680, easing: EASE }); }
        });
      }
      el.vacio.hidden = lista.length > 0;
      el.resumen.innerHTML = '<b>' + lista.length + '</b> de ' + TAREAS.length + ' tareas';
      el.pieVista.textContent = 'Orden: ' + ORDENES[v.orden].nombre;
    }

    /* ── las pestañas ─────────────────────────────────────────────── */
    const tabEls = new Map();
    function creaTab(v) {
      const e = document.createElement('div');
      e.className = 'mi-tab' + (v.fija ? '' : ' es-propia');
      e.setAttribute('role', 'tab'); e.dataset.id = v.id;
      e.innerHTML = '<span class="mi-tab-n"></span><i class="mi-punto" aria-hidden="true"></i><span class="mi-cuenta" aria-hidden="true">0</span><button class="mi-tab-x" type="button" tabindex="-1">' + IC.x + '</button>';
      e.querySelector('.mi-tab-x').setAttribute('aria-label', 'Eliminar la vista');
      e.addEventListener('click', ev => { if (tabArrastro) { tabArrastro = false; return; } if (ev.target.closest('.mi-tab-x') || ev.target.closest('.mi-tab-in')) return; ponActiva(v.id); });
      e.querySelector('.mi-tab-x').addEventListener('click', ev => { ev.stopPropagation(); eliminaVista(v.id); });
      e.addEventListener('keydown', ev => {
        if (ev.target.closest('.mi-tab-in')) return;
        const i = vistas.indexOf(porId(v.id));
        let n = -1;
        if (ev.key === 'ArrowRight') n = (i + 1) % vistas.length; else if (ev.key === 'ArrowLeft') n = (i - 1 + vistas.length) % vistas.length;
        else if (ev.key === 'Home') n = 0; else if (ev.key === 'End') n = vistas.length - 1;
        else if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ponActiva(v.id); return; }
        else if ((ev.key === 'Delete' || ev.key === 'Backspace') && !v.fija) { ev.preventDefault(); eliminaVista(v.id); return; }
        if (n < 0) return;
        ev.preventDefault();
        ponActiva(vistas[n].id); tabEls.get(vistas[n].id).focus();
      });
      e.addEventListener('pointerdown', ev => iniciaArrastre(ev, e, v.id));
      return e;
    }
    function pintaTabs() {
      vistas.forEach(v => {
        let e = tabEls.get(v.id);
        if (!e) { e = creaTab(v); tabEls.set(v.id, e); }
        el.tabs.appendChild(e);
        const sel = v.id === activa, mod = modificada(v);
        e.setAttribute('aria-selected', sel); e.tabIndex = sel ? 0 : -1;
        e.classList.toggle('es-modificada', mod);
        const nom = e.querySelector('.mi-tab-n');
        if (!e.querySelector('.mi-tab-in')) nom.textContent = v.nombre;
        const n = String(filtradas(v).length), c = e.querySelector('.mi-cuenta');
        if (c.textContent !== n) { c.textContent = n; anima(c, [{ transform: 'scale(1.3)' }, { transform: 'none' }], { duration: 420, easing: EASE }); }
        e.setAttribute('aria-label', v.nombre + ', ' + plural(+n, 'tarea', 'tareas') + (mod ? ', modificada' : ''));
      });
      tabEls.forEach((e, id) => { if (!porId(id)) { e.remove(); tabEls.delete(id); } });
      posIndicador();
    }
    function posIndicador() {
      const e = tabEls.get(activa);
      if (!e) return;
      el.indicador.style.setProperty('--x', (e.offsetLeft - el.tabs.scrollLeft) + 'px');
      el.indicador.style.width = e.offsetWidth + 'px';
    }
    function ponActiva(id, silencioso) {
      if (id === activa || !porId(id)) return;
      cierraMenu(false);
      activa = id;
      refresca(true, { vista: true });
      if (!silencioso) anuncia('Vista ' + porId(id).nombre + ', ' + plural(filtradas(porId(id)).length, 'tarea', 'tareas'));
    }

    /* ── los chips ────────────────────────────────────────────────── */
    const chipEls = new Map();
    function creaChip(k) {
      const e = document.createElement('span');
      e.className = 'mi-chip'; e.dataset.f = k;
      e.innerHTML = '<button class="mi-chip-b" type="button" aria-haspopup="menu" aria-expanded="false"><span class="mi-ch-et"></span><span class="mi-ch-val"><span></span></span>' + IC.abajo + '</button><button class="mi-ch-x" type="button">' + IC.x + '</button>';
      e.querySelector('.mi-ch-et').textContent = FILTROS[k].nombre;
      e.querySelector('.mi-ch-x').setAttribute('aria-label', 'Quitar el filtro ' + FILTROS[k].nombre);
      const b = e.querySelector('.mi-chip-b');
      b.addEventListener('click', () => {
        if (el.menu._ancla === b) { cierraMenu(true); return; }
        const v = vistaActiva();
        abreMenu(b, FILTROS[k].nombre, FILTROS[k].opciones.map(o => ({ texto: o, actual: o === v.actual[k] })), it => ponFiltro(k, it.texto));
      });
      e.querySelector('.mi-ch-x').addEventListener('click', () => quitaFiltro(k));
      return e;
    }
    function pintaChips(animar, sentido) {
      const v = vistaActiva();
      // los que sobran se encogen y salen
      chipEls.forEach((e, k) => {
        if (k in v.actual) return;
        chipEls.delete(k);
        if (animar && !quieto()) {
          const r = e.getBoundingClientRect(), c = el.chips.getBoundingClientRect();
          Object.assign(e.style, { position: 'absolute', left: (r.left - c.left) + 'px', top: (r.top - c.top) + 'px', pointerEvents: 'none' });
          const a = e.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(.8) translateY(-6px)' }], { duration: 240, easing: 'ease-in', fill: 'forwards' });
          a.onfinish = () => e.remove();
        } else e.remove();
      });
      const nuevos = [];
      ORDEN_F.forEach(k => {
        if (!(k in v.actual)) return;
        let e = chipEls.get(k);
        if (!e) { e = creaChip(k); chipEls.set(k, e); nuevos.push(e); }
        el.chips.insertBefore(e, el.mas);
        const val = e.querySelector('.mi-ch-val'), actual = val.lastElementChild;
        if (actual.textContent !== v.actual[k]) {
          if (animar && !quieto() && actual.textContent && !nuevos.includes(e)) {
            const n = document.createElement('span'); n.textContent = v.actual[k]; val.appendChild(n);
            const dir = sentido && sentido.atras ? -1 : 1;
            actual.animate([{ transform: 'translateY(0)', opacity: 1 }, { transform: 'translateY(' + (-18 * dir) + 'px)', opacity: 0 }], { duration: 380, easing: EASE, fill: 'forwards' }).onfinish = () => actual.remove();
            n.animate([{ transform: 'translateY(' + (18 * dir) + 'px)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 440, easing: EASE });
            val.style.width = '';
          } else actual.textContent = v.actual[k];
        }
        e.classList.toggle('es-cambiado', v.guardado[k] !== v.actual[k]);
        e.querySelector('.mi-chip-b').setAttribute('aria-label', FILTROS[k].nombre + ': ' + v.actual[k] + (v.guardado[k] !== v.actual[k] ? ' (cambiado)' : ''));
      });
      if (animar && !quieto()) nuevos.forEach((e, i) => e.animate([{ opacity: 0, transform: 'scale(.7) translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 560, delay: 100 + i * 70, easing: EASE, fill: 'backwards' }));
      const libres = ORDEN_F.filter(k => !(k in v.actual));
      el.mas.hidden = !libres.length;
    }
    function cambia(nuevoActual, frase) {
      const v = vistaActiva();
      v.actual = nuevoActual; v.hist.push(copia(nuevoActual));
      refresca(true);
      anuncia(frase + '. Vista modificada, ' + plural(filtradas(v).length, 'tarea', 'tareas'));
    }
    function ponFiltro(k, valor) {
      const v = vistaActiva();
      if (v.actual[k] === valor) return;
      const n = copia(v.actual); n[k] = valor;
      cambia(n, FILTROS[k].nombre + ': ' + valor);
    }
    function quitaFiltro(k) {
      const v = vistaActiva();
      const n = copia(v.actual); delete n[k];
      cambia(n, 'Filtro ' + FILTROS[k].nombre + ' quitado');
    }
    el.mas.addEventListener('click', () => {
      if (el.menu._ancla === el.mas) { cierraMenu(true); return; }
      const v = vistaActiva();
      abreMenu(el.mas, 'Añadir filtro', ORDEN_F.filter(k => !(k in v.actual)).map(k => ({ texto: FILTROS[k].nombre, k })), it => ponFiltro(it.k, FILTROS[it.k].opciones[0]));
    });

    /* ── el menú de valores ───────────────────────────────────────── */
    let tMenu = 0;
    function abreMenu(ancla, titulo, items, alElegir) {
      cierraMenu(false);
      clearTimeout(tMenu);
      el.menu.textContent = '';
      const t = document.createElement('p'); t.className = 'mi-m-tit'; t.textContent = titulo; el.menu.appendChild(t);
      items.forEach((it, i) => {
        const b = document.createElement('button'); b.type = 'button'; b.className = 'mi-m-item' + (it.actual ? ' es-actual' : '');
        b.setAttribute('role', 'menuitem'); b.tabIndex = -1; b.style.setProperty('--i', i);
        b.innerHTML = IC.check + '<span></span>'; b.lastChild.textContent = it.texto;
        b.addEventListener('click', () => { cierraMenu(false); alElegir(it); });
        el.menu.appendChild(b);
      });
      el.menu.hidden = false; el.menu._ancla = ancla;
      ancla.setAttribute('aria-expanded', 'true');
      const v = el.ventana.getBoundingClientRect(), r = ancla.getBoundingClientRect(), w = el.menu.offsetWidth;
      const izq = Math.max(12, Math.min(r.left - v.left, v.width - w - 12));
      el.menu.style.left = izq + 'px'; el.menu.style.top = (r.bottom - v.top + 8) + 'px';
      el.menu.style.transformOrigin = Math.min(w - 20, Math.max(20, r.left + 28 - v.left - izq)) + 'px 0';
      void el.menu.offsetWidth;
      el.menu.classList.add('es-visible');
      (el.menu.querySelector('.es-actual') || el.menu.querySelector('.mi-m-item')).focus({ preventScroll: true });
    }
    function cierraMenu(devuelveFoco) {
      if (el.menu.hidden) return;
      const ancla = el.menu._ancla;
      el.menu.classList.remove('es-visible');
      if (ancla) ancla.setAttribute('aria-expanded', 'false');
      el.menu._ancla = null;
      const fin = () => { if (!el.menu._ancla) el.menu.hidden = true; };
      if (quieto()) fin(); else tMenu = setTimeout(fin, 200);
      if (devuelveFoco && ancla) ancla.focus({ preventScroll: true });
    }
    el.menu.addEventListener('keydown', e => {
      const items = Array.from(el.menu.querySelectorAll('.mi-m-item')), i = items.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length].focus(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
      else if (e.key === 'Home') { e.preventDefault(); items[0].focus(); }
      else if (e.key === 'End') { e.preventDefault(); items[items.length - 1].focus(); }
      else if (e.key === 'Escape') { e.preventDefault(); cierraMenu(true); }
      else if (e.key === 'Tab') cierraMenu(false);
    });
    document.addEventListener('pointerdown', e => { if (!el.menu.hidden && !el.menu.contains(e.target) && !(el.menu._ancla && el.menu._ancla.contains(e.target))) cierraMenu(false); });

    /* ── lo que aparece al modificar ──────────────────────────────── */
    let rebobinando = false;
    function pintaAcciones() {
      const mod = modificada(vistaActiva()) && !rebobinando;
      el.acciones.classList.toggle('es-visible', mod);
      el.acciones.setAttribute('aria-hidden', !mod);
      [el.descartar, el.nueva, el.guardar].forEach(b => { b.tabIndex = mod ? 0 : -1; });
    }
    function guarda() {
      const v = vistaActiva();
      if (!modificada(v) || rebobinando) return;
      v.guardado = copia(v.actual); v.hist = [copia(v.actual)];
      refresca(true);
      const e = tabEls.get(v.id);
      e.classList.remove('es-guardada'); void e.offsetWidth; e.classList.add('es-guardada');
      anuncia('Vista ' + v.nombre + ' guardada');
      notifica();
    }
    let tRebobina = 0;
    function descarta() {
      const v = vistaActiva();
      if (!modificada(v) || rebobinando) return;
      const pasos = v.hist.length - 1;
      if (quieto() || pasos < 1) { v.actual = copia(v.guardado); v.hist = [copia(v.guardado)]; refresca(true, { atras: true }); anuncia('Cambios descartados'); return; }
      rebobinando = true; cierraMenu(false);
      el.acciones.classList.remove('es-visible'); el.acciones.classList.add('es-rebobina');
      el.pasos.textContent = pasos;
      el.cinta.style.setProperty('--p', 1);
      el.cintaMarcas.style.background = 'repeating-linear-gradient(90deg, transparent 0 ' + (120 / pasos - 2) + 'px, color-mix(in srgb, var(--mi-ambar) 70%, transparent) ' + (120 / pasos - 2) + 'px ' + (120 / pasos) + 'px)';
      el.cintaCabeza.style.setProperty('--p', 1);
      let i = v.hist.length - 1;
      const paso = () => {
        i--;
        v.actual = copia(v.hist[i]);
        el.cintaCabeza.style.setProperty('--p', i / pasos);
        el.pasos.textContent = i;
        refresca(true, { atras: true });
        if (i > 0) tRebobina = setTimeout(paso, 560);
        else tRebobina = setTimeout(() => {
          v.hist = [copia(v.guardado)];
          rebobinando = false;
          el.acciones.classList.remove('es-rebobina');
          pintaAcciones();
          anuncia('Cambios descartados: la vista vuelve a lo guardado');
        }, 520);
      };
      tRebobina = setTimeout(paso, 160);
    }
    el.guardar.addEventListener('click', guarda);
    el.descartar.addEventListener('click', descarta);

    /* ── guardar como nueva: la pestaña sale del botón y vuela ─────── */
    function nombreUnico(base) {
      const raizN = base.replace(/\s\d+$/, '');
      let n = 2;
      while (vistas.some(v => v.nombre === raizN + ' ' + n)) n++;
      return raizN + ' ' + n;
    }
    function guardaNueva() {
      const v = vistaActiva();
      if (!modificada(v) || rebobinando) return;
      const desde = el.nueva.getBoundingClientRect();
      const nv = nueva({ id: 'v' + (++seq), nombre: nombreUnico(v.nombre), guardado: copia(v.actual), orden: v.orden, fija: false });
      v.actual = copia(v.guardado); v.hist = [copia(v.guardado)];
      vistas.push(nv);
      activa = nv.id;
      el.acciones.classList.remove('es-visible');
      cierraMenu(false);
      refresca(false);
      const tab = tabEls.get(nv.id);
      el.tabs.scrollLeft = el.tabs.scrollWidth;
      const llega = () => { tab.style.visibility = ''; tab.classList.remove('es-aterriza'); void tab.offsetWidth; tab.classList.add('es-aterriza'); editaNombre(tab, nv); posIndicador(); };
      if (quieto()) { llega(); return; }
      tab.style.visibility = 'hidden';
      posIndicador();
      const fin = tab.getBoundingClientRect();
      const f = document.createElement('div');
      f.className = 'mi-vuelo';
      f.innerHTML = '<span></span><span class="mi-cuenta">' + filtradas(nv).length + '</span>';
      f.firstChild.textContent = nv.nombre;
      raiz.appendChild(f);
      const w = f.offsetWidth, h = f.offsetHeight;
      const sx = desde.left + desde.width / 2 - w / 2, sy = desde.top + desde.height / 2 - h / 2;
      const ex = fin.left + fin.width / 2 - w / 2, ey = fin.top + fin.height / 2 - h / 2;
      const kf = [];
      for (let k = 0; k <= 16; k++) {
        const t = k / 16, e = 1 - Math.pow(1 - t, 3);
        kf.push({ transform: 'translate(' + (sx + (ex - sx) * e).toFixed(1) + 'px,' + (sy + (ey - sy) * e - 96 * Math.sin(Math.PI * e)).toFixed(1) + 'px) scale(' + (.82 + .26 * Math.sin(Math.PI * t) + .18 * t).toFixed(3) + ') rotate(' + (-9 * Math.sin(Math.PI * t)).toFixed(2) + 'deg)', opacity: k === 0 ? 0.4 : 1 });
      }
      const a = f.animate(kf, { duration: 820, easing: 'linear', fill: 'forwards' });
      a.onfinish = () => { f.remove(); llega(); };
      anuncia('Vista nueva ' + nv.nombre + ' creada');
      notifica();
    }
    el.nueva.addEventListener('click', guardaNueva);

    /* el nombre de una vista nueva se edita al aterrizar */
    function editaNombre(tab, v) {
      const nom = tab.querySelector('.mi-tab-n');
      if (tab.querySelector('.mi-tab-in')) return;
      const inp = document.createElement('input');
      inp.className = 'mi-tab-in'; inp.type = 'text'; inp.value = v.nombre; inp.maxLength = 24; inp.spellcheck = false; inp.autocomplete = 'off';
      inp.setAttribute('aria-label', 'Nombre de la vista nueva');
      nom.replaceWith(inp);
      let hecho = false;
      const fin = guarda => {
        if (hecho) return; hecho = true;
        if (guarda && inp.value.trim()) v.nombre = inp.value.trim();
        const n = document.createElement('span'); n.className = 'mi-tab-n'; n.textContent = v.nombre;
        inp.replaceWith(n);
        pintaTabs(); notifica();
        anuncia('Vista ' + v.nombre);
      };
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); fin(true); tab.focus(); } else if (e.key === 'Escape') { e.preventDefault(); fin(false); tab.focus(); } e.stopPropagation(); });
      inp.addEventListener('blur', () => fin(true));
      inp.addEventListener('pointerdown', e => e.stopPropagation());
      posIndicador();
      inp.focus({ preventScroll: true }); inp.select();
    }

    /* ── arrastrar pestañas para reordenarlas ───────────────────────── */
    let arr = null, tabArrastro = false;
    function iniciaArrastre(ev, tab, id) {
      if (ev.button !== 0 || ev.target.closest('.mi-tab-x') || ev.target.closest('.mi-tab-in')) return;
      arr = { tab, id, x0: ev.clientX, activo: false, pid: ev.pointerId };
    }
    el.tabs.addEventListener('pointermove', ev => {
      if (!arr || ev.pointerId !== arr.pid) return;
      const dx = ev.clientX - arr.x0;
      if (!arr.activo) {
        if (Math.abs(dx) < 6) return;
        arr.activo = true; tabArrastro = true;
        try { arr.tab.setPointerCapture(ev.pointerId); } catch (e) {}
        arr.rects = vistas.map(v => { const e = tabEls.get(v.id); return { id: v.id, e, l: e.offsetLeft, w: e.offsetWidth }; });
        arr.i0 = vistas.findIndex(v => v.id === arr.id);
        arr.tab.classList.add('es-arrastra');
        el.indicador.style.opacity = '0';
        arr.rects.forEach(r => { if (r.id !== arr.id) r.e.style.transition = 'transform .6s ' + muelle(300, 21); });
      }
      const yo = arr.rects[arr.i0];
      const dxc = lim(dx, -yo.l, arr.rects[arr.rects.length - 1].l + arr.rects[arr.rects.length - 1].w - yo.l - yo.w);
      arr.tab.style.transform = 'translateX(' + dxc + 'px)';
      const centro = yo.l + yo.w / 2 + dxc;
      let n = 0; arr.rects.forEach((r, i) => { if (i !== arr.i0 && r.l + r.w / 2 < centro) n++; });
      arr.n = n;
      arr.rects.forEach((r, i) => {
        if (i === arr.i0) return;
        let s = 0;
        if (arr.i0 < n && i > arr.i0 && i <= n) s = -yo.w - 2;
        else if (arr.i0 > n && i < arr.i0 && i >= n) s = yo.w + 2;
        r.e.style.transform = s ? 'translateX(' + s + 'px)' : '';
      });
    });
    const suelta = ev => {
      if (!arr || ev.pointerId !== arr.pid) return;
      const a = arr; arr = null;
      if (!a.activo) return;
      el.indicador.style.opacity = '';
      const antes = new Map(a.rects.map(r => [r.id, r.e.getBoundingClientRect().left]));
      a.rects.forEach(r => { r.e.style.transition = 'none'; r.e.style.transform = ''; });
      a.tab.classList.remove('es-arrastra');
      const [mov] = vistas.splice(a.i0, 1); vistas.splice(a.n, 0, mov);
      pintaTabs();
      a.rects.forEach(r => {
        const dx = antes.get(r.id) - r.e.getBoundingClientRect().left;
        r.e.style.transition = '';
        if (Math.abs(dx) > .5) anima(r.e, [{ transform: 'translateX(' + dx + 'px)' }, { transform: 'none' }], { duration: 620, easing: EASE });
      });
      setTimeout(() => { tabArrastro = false; }, 0);
      anuncia('Vista ' + mov.nombre + ' en la posición ' + (a.n + 1));
      notifica();
    };
    el.tabs.addEventListener('pointerup', suelta);
    el.tabs.addEventListener('pointercancel', suelta);

    /* ── quitar una vista propia ──────────────────────────────────── */
    function eliminaVista(id) {
      const v = porId(id);
      if (!v || v.fija) return;
      cierraMenu(false);
      const i = vistas.indexOf(v), e = tabEls.get(id);
      const sigue = () => {
        vistas.splice(i, 1);
        if (activa === id) { activa = vistas[Math.max(0, i - 1)].id; refresca(true, { vista: true }); } else pintaTabs();
        notifica();
      };
      anuncia('Vista ' + v.nombre + ' eliminada');
      if (quieto() || !e) { sigue(); return; }
      e.style.pointerEvents = 'none';
      const a = e.animate([{ opacity: 1, transform: 'none', maxWidth: e.offsetWidth + 'px' }, { opacity: 0, transform: 'scale(.85) translateY(6px)', maxWidth: '0px', paddingLeft: '0px', paddingRight: '0px' }], { duration: 320, easing: 'cubic-bezier(.4, 0, .2, 1)', fill: 'forwards' });
      a.onfinish = sigue;
    }

    /* ── todo junto ───────────────────────────────────────────────── */
    function refresca(animar, info) {
      const cambioVista = !!(info && info.vista);
      pintaChips(animar, info);
      pintaFilas(animar, cambioVista);
      pintaTabs();
      pintaAcciones();
    }
    function restablece() {
      clearTimeout(tRebobina); rebobinando = false;
      el.acciones.classList.remove('es-rebobina');
      cierraMenu(false);
      vistas.filter(v => !v.fija).forEach(v => { const e = tabEls.get(v.id); if (e) { e.style.pointerEvents = 'none'; anima(e, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(.8)' }], { duration: 260, fill: 'forwards' }); } });
      const setTab = e => e;
      void setTab;
      vistas = vistas.filter(v => v.fija);
      vistas.forEach(v => { v.actual = copia(v.guardado); v.hist = [copia(v.guardado)]; });
      activa = op.vista;
      if (quieto()) tabEls.forEach((e, id) => { if (!porId(id)) { e.remove(); tabEls.delete(id); } });
      refresca(true, { vista: true });
      anuncia('Vistas restablecidas');
      notifica();
    }
    el.reset.addEventListener('click', restablece);
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !el.menu.hidden) cierraMenu(true); });
    if (window.ResizeObserver) new ResizeObserver(posIndicador).observe(el.tabs); else window.addEventListener('resize', posIndicador);
    el.tabs.addEventListener('scroll', posIndicador);

    /* ── arranque ─────────────────────────────────────────────────── */
    refresca(false);
    el.indicador.style.transition = 'none';
    posIndicador();
    void el.indicador.offsetWidth;
    el.indicador.style.transition = '';
    (document.fonts && document.fonts.ready || Promise.resolve()).then(() => { el.indicador.style.transition = 'none'; posIndicador(); void el.indicador.offsetWidth; el.indicador.style.transition = ''; });

    return {
      activa: id => ponActiva(id),
      vistas: () => vistas.map(v => ({ id: v.id, nombre: v.nombre, filtros: copia(v.guardado) })),
      restablece,
    };
  }

  window.Mirador = Mirador;
})();
