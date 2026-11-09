/* =====================================================================
   Venia · Moxen
   Una tarjeta propia que pide el permiso del navegador (avisos, ubicación,
   cámara) ANTES de lanzar el cuadro del sistema, y que guía la recuperación
   si se deniega. Cada permiso es una tarjeta con un anillo de estado: por
   pedir (anillo punteado), preguntando (el arco empieza a cerrarse mientras
   el ícono respira), concedido (el anillo se cierra en verde, una medalla
   con ✓ salta y la tarjeta demuestra el permiso: una notificación que cae,
   un punto de ubicación que late sobre un mapa abstracto, un visor de
   cámara que se abre como un diafragma) o denegado (ámbar, una guía de
   tres pasos y el candado de la barra de direcciones que pulsa y se
   señala con un hilo). El cuadro nativo es una vista previa dibujada que cae
   desde el candado con un resorte; el candado también abre los «Permisos
   del sitio», donde cada interruptor recupera (o revoca) lo decidido.

   Por qué existe: el navegador solo deja pedir cada permiso una vez; si el
   usuario lo rechaza a ciegas, ya no se puede volver a preguntar. Explicar
   primero para qué se pide y mostrar cómo volver atrás evita perderlo.

   Teclado: Tab recorre candado, reinicio y tarjetas; Intro o Espacio activa;
   con el cuadro abierto el foco se queda dentro, ← → ↑ ↓ eligen entre
   «Permitir» y «No permitir», Intro confirma y Esc lo cierra sin decidir.

   Montaje (se inicia solo sobre [data-venia]; el HTML de la demo es la plantilla):
     const v = Venia(document.querySelector('[data-venia]'), {
       alPedir: id => {},                 // el cuadro se abre (id: 'avisos' | 'ubicacion' | 'camara')
       alResponder: (id, estado) => {},   // estado: 'concedido' | 'denegado' | 'pendiente'
       pedirAlNavegador: id => {},        // opcional: aquí iría Notification.requestPermission() & co.
     });
     v.pide('ubicacion');   // abre el cuadro de una tarjeta
     v.responde(true);      // lo permite (false: lo deniega)
     v.reinicia();          // todo vuelve a «por pedir»
   Qué se personaliza: cada tarjeta es un <article data-permiso="id"> con su
   texto, su ícono y su vista previa (.ve-z-ok); el texto del cuadro sale de
   PERMISOS más abajo; los colores (verde, ámbar, tinta) están al principio de
   venia.css. Sin dependencias; el tiempo sale de timers y transiciones CSS
   (nada de Date), así que la página y el vídeo coinciden.
   ===================================================================== */
(function () {
  'use strict';

  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  const quieto = () => mq.matches;
  // un resorte convertido en curva CSS linear(): el cuadro, el interruptor y la medalla lo usan
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
  const MUELLE = { k: 330, c: 21 };          // el cuadro nativo al caer: un rebote corto
  const ESTADO_TX = { pendiente: 'Por pedir', pidiendo: 'Preguntando…', concedido: 'Concedido', denegado: 'Denegado' };
  const SITIO_TX = { pendiente: 'Preguntar', pidiendo: 'Preguntar', concedido: 'Permitido', denegado: 'Bloqueado' };

  // lo que dice el cuadro nativo de cada permiso
  const PERMISOS = {
    avisos: { titulo: 'Mostrar notificaciones', desc: 'Para avisarte cuando un envío termine.', nombre: 'Notificaciones', frase: 'las notificaciones' },
    ubicacion: { titulo: 'Conocer tu ubicación', desc: 'Para mostrar los puntos de entrega cercanos.', nombre: 'Ubicación', frase: 'la ubicación' },
    camara: { titulo: 'Usar tu cámara', desc: 'Para escanear un código desde la página.', nombre: 'Cámara', frase: 'la cámara' },
  };

  function Venia(raiz, opc) {
    opc = Object.assign({ alPedir: null, alResponder: null, pedirAlNavegador: null }, opc || {});
    const q = (s, c) => (c || raiz).querySelector(s);
    const qa = (s, c) => Array.from((c || raiz).querySelectorAll(s));
    const ventana = q('[data-ventana]'), pagina = q('[data-pagina]'), barra = q('.ve-barra');
    const velo = q('[data-velo]'), dialogo = q('[data-dialogo]'), sitio = q('[data-sitio]');
    const candado = q('[data-candado]'), conector = q('[data-conector]'), vivo = q('[data-vivo]');
    const dTit = q('[data-d-tit]'), dDesc = q('[data-d-desc]'), dIcono = q('[data-d-icono]');
    const botones = qa('[data-responde]');
    raiz.style.setProperty('--ve-muelle', muelle(MUELLE.k, MUELLE.c));

    const tarjetas = {};
    qa('[data-permiso]').forEach(el => {
      const id = el.dataset.permiso;
      tarjetas[id] = { id, el, boton: q('[data-activar]', el), tx: q('[data-estado-tx]', el), ok: q('.ve-z-ok', el),
        fila: q('[data-sitio-fila="' + id + '"]', sitio), sw: q('[data-sw="' + id + '"]', sitio), estado: 'pendiente' };
    });
    const ids = Object.keys(tarjetas);

    let abierto = null, opener = null, cierraT = 0, conectaT = 0, ultimoDenegado = null;
    const dice = t => { vivo.textContent = ''; setTimeout(() => { vivo.textContent = t; }, 30); };

    /* ── el estado de una tarjeta ───────────────────────────────────── */
    function ponEstado(id, estado, o) {
      o = o || {};
      const t = tarjetas[id], antes = t.estado;
      t.estado = estado;
      t.el.dataset.estado = estado;
      t.tx.textContent = ESTADO_TX[estado];
      t.boton.disabled = false;
      t.boton.setAttribute('aria-disabled', estado === 'pidiendo' ? 'true' : 'false');
      t.boton.setAttribute('aria-label', {
        pendiente: 'Activar ' + PERMISOS[id].frase, pidiendo: 'Esperando tu respuesta',
        concedido: PERMISOS[id].nombre + ' concedido: probar de nuevo', denegado: PERMISOS[id].nombre + ' denegado: abrir los ajustes del sitio',
      }[estado]);
      if (t.fila) {
        t.fila.dataset.estado = estado;
        q('[data-sitio-tx]', t.fila).textContent = SITIO_TX[estado];
        t.sw.setAttribute('aria-checked', estado === 'concedido' ? 'true' : 'false');
      }
      if (estado === 'concedido') reproduce(t);
      raiz.toggleAttribute('data-hay-denegado', ids.some(i => tarjetas[i].estado === 'denegado'));
      if (estado === 'denegado') { ultimoDenegado = id; if (!o.silencioso) señala(id); }
      else if (antes === 'denegado' && ultimoDenegado === id) { ultimoDenegado = null; ocultaConector(); }
      actualizaLlama();
    }
    // vuelve a reproducir la vista previa (la notificación, el punto, el visor)
    function reproduce(t) {
      t.ok.classList.remove('is-juega'); t.el.classList.remove('is-suena');
      void t.ok.offsetWidth;
      t.ok.classList.add('is-juega'); t.el.classList.add('is-suena');
    }

    /* ── el cuadro nativo ───────────────────────────────────────────── */
    function setInerte(si) {
      [pagina, barra].forEach(e => { if (si) e.setAttribute('inert', ''); else e.removeAttribute('inert'); });
    }
    function pide(id) {
      const t = tarjetas[id];
      if (!t || abierto || t.estado !== 'pendiente') return;
      cierraSitio(true);
      abierto = id; opener = t.boton;
      ponEstado(id, 'pidiendo');
      const p = PERMISOS[id];
      dTit.textContent = p.titulo; dDesc.textContent = p.desc;
      dIcono.innerHTML = q('.ve-icono', t.el).innerHTML;
      ocultaConector();
      clearTimeout(cierraT);
      dialogo.hidden = false;
      dialogo.classList.remove('is-cierra');
      void dialogo.offsetWidth;
      dialogo.classList.add('is-abierto');
      velo.classList.add('is-abierto');
      setInerte(true);
      foco(botones[0]);
      dice(p.nombre + ': el navegador pregunta si permites ' + p.frase + '.');
      if (opc.alPedir) opc.alPedir(id);
    }
    function cierraDialogo(devuelveFoco) {
      dialogo.classList.remove('is-abierto');
      dialogo.classList.add('is-cierra');
      velo.classList.remove('is-abierto');
      setInerte(false);
      cierraT = setTimeout(() => { if (!abierto) { dialogo.hidden = true; dialogo.classList.remove('is-cierra'); } }, quieto() ? 20 : 340);
      if (devuelveFoco && opener) opener.focus({ preventScroll: true });
    }
    function responde(si) {
      if (!abierto) return;
      const id = abierto;
      abierto = null;
      cierraDialogo(true);
      // el cuadro tarda un instante en irse: la tarjeta responde justo después, para que se vea qué pasó
      setTimeout(() => {
        ponEstado(id, si ? 'concedido' : 'denegado');
        dice(si ? 'Permiso de ' + PERMISOS[id].nombre.toLowerCase() + ' concedido.' : 'Permiso de ' + PERMISOS[id].nombre.toLowerCase() + ' denegado. Te mostramos cómo recuperarlo desde el candado.');
        if (opc.alResponder) opc.alResponder(id, si ? 'concedido' : 'denegado');
        if (si && opc.pedirAlNavegador) opc.pedirAlNavegador(id);
      }, quieto() ? 0 : 160);
    }
    function cancela() {
      if (!abierto) return;
      const id = abierto;
      abierto = null;
      cierraDialogo(true);
      ponEstado(id, 'pendiente');
      dice(PERMISOS[id].nombre + ': cerraste el cuadro sin decidir.');
      if (opc.alResponder) opc.alResponder(id, 'pendiente');
    }
    function foco(b) {
      botones.forEach(x => x.classList.toggle('is-foco', x === b));
      b.focus({ preventScroll: true });
    }
    botones.forEach(b => {
      b.addEventListener('click', () => responde(b.dataset.responde === 'si'));
      b.addEventListener('focus', () => botones.forEach(x => x.classList.toggle('is-foco', x === b)));
      b.addEventListener('blur', () => b.classList.remove('is-foco'));
    });
    dialogo.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); cancela(); return; }
      if (/^Arrow(Left|Right|Up|Down)$/.test(e.key)) {
        e.preventDefault();
        const i = botones.indexOf(document.activeElement);
        foco(botones[(i + (e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1) + botones.length) % botones.length]);
        return;
      }
      if (e.key === 'Tab') {                       // el foco se queda dentro del cuadro
        e.preventDefault();
        const i = botones.indexOf(document.activeElement);
        foco(botones[(i + (e.shiftKey ? -1 : 1) + botones.length) % botones.length]);
      }
    });

    /* ── el panel del candado ───────────────────────────────────────── */
    let sitioAbierto = false;
    function abreSitio(id) {
      if (abierto) return;
      sitioAbierto = true;
      ocultaConector();
      clearTimeout(cierraT);
      sitio.hidden = false; sitio.classList.remove('is-cierra');
      void sitio.offsetWidth;
      sitio.classList.add('is-abierto');
      candado.setAttribute('aria-expanded', 'true');
      ids.forEach(i => tarjetas[i].fila.classList.toggle('is-llama', i === id));
      actualizaLlama();
      const sw = id ? tarjetas[id].sw : tarjetas[ids[0]].sw;
      sw.focus({ preventScroll: true });
    }
    function cierraSitio(silencioso) {
      if (!sitioAbierto) return;
      sitioAbierto = false;
      sitio.classList.remove('is-abierto'); sitio.classList.add('is-cierra');
      candado.setAttribute('aria-expanded', 'false');
      ids.forEach(i => tarjetas[i].fila.classList.remove('is-llama'));
      setTimeout(() => { if (!sitioAbierto) { sitio.hidden = true; sitio.classList.remove('is-cierra'); } }, quieto() ? 20 : 320);
      actualizaLlama();
      if (!silencioso) candado.focus({ preventScroll: true });
    }
    candado.addEventListener('click', () => { if (sitioAbierto) cierraSitio(); else abreSitio(); });
    sitio.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); cierraSitio(); } });
    document.addEventListener('pointerdown', e => {
      if (sitioAbierto && !sitio.contains(e.target) && !candado.contains(e.target)) cierraSitio(true);
    });
    // un interruptor del panel: permitir lo bloqueado (la recuperación) o revocar lo concedido
    ids.forEach(id => tarjetas[id].sw.addEventListener('click', () => {
      const t = tarjetas[id];
      const nuevo = t.estado === 'concedido' ? 'pendiente' : 'concedido';
      ponEstado(id, nuevo, { silencioso: true });
      t.fila.classList.remove('is-llama');
      dice('Permiso de ' + PERMISOS[id].nombre.toLowerCase() + (nuevo === 'concedido' ? ' permitido desde los ajustes del sitio.' : ': vuelve a preguntar.'));
      if (opc.alResponder) opc.alResponder(id, nuevo);
    }));
    // el candado «llama» mientras haya algo bloqueado y el panel esté cerrado
    function actualizaLlama() {
      raiz.toggleAttribute('data-llama', ids.some(i => tarjetas[i].estado === 'denegado') && !sitioAbierto && !abierto);
    }

    /* ── el hilo de la guía al candado ──────────────────────────────── */
    function señala(id) {
      if (quieto() || getComputedStyle(conector).display === 'none') return;
      const t = tarjetas[id], chip = q('.ve-guia b', t.el);
      if (!chip) return;
      clearTimeout(conectaT);
      // el hilo sale de la guía, baja por la calle entre tarjetas, sube por el pasillo bajo la barra y entra al candado por abajo:
      // así no cruza ningún texto
      const o = ventana.getBoundingClientRect(), a = chip.getBoundingClientRect(), c = candado.getBoundingClientRect(), k = t.el.getBoundingClientRect();
      const sx = a.left + a.width / 2 - o.left, sy = a.top + a.height / 2 - o.top;
      const ex = c.left + c.width / 2 - o.left, ey = c.bottom - o.top + 6;
      const gx = k.left - o.left - (k.left - o.left > 60 ? 10 : 20);               // el centro de la calle a la izquierda de la tarjeta
      const py = barra.offsetHeight + 15;                                          // el pasillo bajo la barra de direcciones
      const R = 10, dir = ex > gx ? 1 : -1;
      const d = 'M' + sx.toFixed(1) + ',' + sy.toFixed(1) +
        ' H' + (gx + R).toFixed(1) + ' Q' + gx.toFixed(1) + ',' + sy.toFixed(1) + ' ' + gx.toFixed(1) + ',' + (sy - R).toFixed(1) +
        ' V' + (py + R).toFixed(1) + ' Q' + gx.toFixed(1) + ',' + py.toFixed(1) + ' ' + (gx + dir * R).toFixed(1) + ',' + py.toFixed(1) +
        ' H' + (ex - dir * R).toFixed(1) + ' Q' + ex.toFixed(1) + ',' + py.toFixed(1) + ' ' + ex.toFixed(1) + ',' + (py - R).toFixed(1) +
        ' V' + ey.toFixed(1);
      const p = conector.querySelector('path'), pt = conector.querySelector('circle');
      p.setAttribute('d', d);
      pt.setAttribute('cx', ex.toFixed(1)); pt.setAttribute('cy', ey.toFixed(1));
      conector.classList.remove('is-visible');
      void conector.getBoundingClientRect();
      // sale cuando la guía ya empezó a entrar: el hilo y los pasos se cuentan juntos
      conectaT = setTimeout(() => {
        conector.classList.add('is-visible');
        conectaT = setTimeout(ocultaConector, 3000);
      }, 450);
    }
    function ocultaConector() {
      clearTimeout(conectaT);
      conector.classList.remove('is-visible');
    }

    /* ── botones de las tarjetas y reinicio ─────────────────────────── */
    ids.forEach(id => tarjetas[id].boton.addEventListener('click', () => {
      const t = tarjetas[id];
      if (t.estado === 'pendiente') pide(id);
      else if (t.estado === 'concedido') reproduce(t);
      else if (t.estado === 'denegado') abreSitio(id);
    }));
    function reinicia() {
      if (abierto) { const id = abierto; abierto = null; cierraDialogo(false); ponEstado(id, 'pendiente'); }
      cierraSitio(true);
      ocultaConector();
      ids.forEach(id => { if (tarjetas[id].estado !== 'pendiente') ponEstado(id, 'pendiente', { silencioso: true }); });
      dice('Demo reiniciada: los tres permisos vuelven a estar por pedir.');
    }
    q('[data-reinicia]').addEventListener('click', reinicia);

    // los hijos del panel del candado nacen con su estado
    ids.forEach(id => ponEstado(id, 'pendiente', { silencioso: true }));

    return { pide, responde, reinicia, estado: id => tarjetas[id] && tarjetas[id].estado };
  }

  window.Venia = Venia;
  document.querySelectorAll('[data-venia]').forEach(r => { r.venia = Venia(r); });
})();
