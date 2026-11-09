/* =====================================================================
   Faena · Moxen
   El panel de un agente de IA haciendo su trabajo. Al enviar la
   petición, los pasos aparecen uno a uno con un spinner de segmentos
   que termina en un ✓ dibujado; una herramienta se despliega con su
   llamada y un cronómetro; un paso falla, tiembla, se reintenta y
   pasa; y al final todo se pliega con un resorte en una sola línea,
   «Listo en 12 s · 5 pasos», que se vuelve a desplegar con un clic.
   Si nadie lo toca, se luce solo cada tanto. Sin dependencias.

     Faena(document.querySelector('[data-faena]'), {
       primera: 6500,    // ms hasta la primera vuelta sola, si nadie llega
       tras_gesto: 2500, // ms tras el primer movimiento, por si no envía
       pausa: 3200,      // ms entre una vuelta y la siguiente
     });

   Los pasos son de ejemplo: el guion de abajo es lo que cambiarías por
   los eventos de tu agente (paso que empieza, termina o falla).
   ===================================================================== */
(function () {
  'use strict';

  /* El guion de una tarea, en segundos reales desde que se envía. */
  const GUION = [
    [0, 'envia'],
    [.12, 'corre'],
    [.18, 'aparece', 0], [.66, 'hecho', 0],
    [.78, 'aparece', 1], [1.0, 'abre'], [2.08, 'resuelve'], [2.18, 'hecho', 1],
    [2.32, 'aparece', 2], [2.8, 'falla', 2], [3.42, 'reintenta', 2], [3.86, 'hecho', 2],
    [3.96, 'aparece', 3], [4.34, 'hecho', 3],
    [4.46, 'aparece', 4], [4.78, 'hecho', 4],
    [5.02, 'listo'],
    [5.42, 'pliega'],
    [6.1, 'fin'],
  ];
  const cuando = (que, i) => GUION.find(g => g[1] === que && (i === undefined || g[2] === i))[0];
  /* El cronómetro va más rápido que el reloj: los 4,9 s de la animación
     se cuentan como los 12 s de una tarea de verdad (lo dice el resumen). */
  const RITMO = 12 / (cuando('listo') - cuando('corre'));
  const DURA = [0, 1, 2, 3, 4].map(i => (cuando('hecho', i) - cuando('aparece', i)) * RITMO);
  const T_HERR = (cuando('resuelve') - cuando('abre')) * RITMO;
  const NOTA = { falla: 'Se agotó el tiempo de espera', reintenta: 'Reintentando · intento 2 de 3', hecho: 'Resuelto al segundo intento' };
  const seg = x => Math.max(0, x).toFixed(1).replace('.', ',') + ' s';

  // el ícono de cada paso: diez trazos en anillo, el ✓ y el ✕, superpuestos
  const ICONO = '<span class="fa-giro">' + Array.from({ length: 10 }, (_, k) => '<i style="--k:' + k + '"></i>').join('') + '</span>'
    + '<svg class="fa-bien" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11"/><path d="M7.5 12.4l3.1 3.1 6-6.5" pathLength="1"/></svg>'
    + '<svg class="fa-mal" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11"/><path d="M8.8 8.8l6.4 6.4" pathLength="1"/><path d="M15.2 8.8l-6.4 6.4" pathLength="1"/></svg>';

  // el anillo del resumen: un arco por paso, con un hueco entre cada uno
  function arcos(n) {
    const p = a => (12 + 10 * Math.sin(a)).toFixed(2) + ' ' + (12 - 10 * Math.cos(a)).toFixed(2);
    let s = '<g class="fa-anillo-giro">';
    for (let k = 0; k < n; k++) {
      const a = (k / n) * 2 * Math.PI, b = ((k + 1) / n) * 2 * Math.PI, hueco = .2;
      s += '<path d="M' + p(a + hueco) + 'A10 10 0 0 1 ' + p(b - hueco) + '"/>';
    }
    return s + '</g>';
  }

  function Faena(raiz, opciones) {
    const o = Object.assign({ primera: 6500, tras_gesto: 2500, pausa: 3200 }, opciones);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const $ = s => raiz.querySelector(s);
    const form = $('.fa-pedido'), campo = $('.fa-campo'), enviar = $('.fa-enviar');
    const resumen = $('.fa-resumen'), reloj = $('.fa-reloj'), cuenta = $('.fa-cuenta'), voz = $('.fa-voz');
    const medio = $('.fa-medio'), pie = $('.fa-pie'), recorte = $('.fa-recorte'), lista = $('.fa-pasos');
    const herramienta = $('.fa-herramienta'), hReloj = $('.fa-h-reloj'), nota = $('.fa-nota');
    const pasos = Array.from(lista.children);
    pasos.forEach(li => { li.querySelector('.fa-icono').innerHTML = ICONO; });
    $('.fa-anillo').innerHTML = arcos(pasos.length);
    const arco = Array.from(raiz.querySelectorAll('.fa-anillo path'));

    const texto = (el, s) => { if (el.textContent !== s) el.textContent = s; };
    const pon = (el, ...c) => el.classList.add(...c);
    const quita = (el, ...c) => el.classList.remove(...c);

    /* ── los estados ───────────────────────────────────────────────── */
    // una tarea nueva: todo en blanco (no se ve: el panel está plegado)
    function limpia() {
      pasos.forEach(li => { li.className = 'fa-paso'; li.style.transitionDelay = ''; texto(li.querySelector('.fa-dura'), ''); });
      herramienta.className = 'fa-herramienta';
      nota.className = 'fa-nota'; texto(nota, '');
      arco.forEach(a => quita(a, 'is-lleno'));
    }
    // lo que deja una tarea terminada, que el resumen despliega
    function completa() {
      pasos.forEach((li, i) => {
        pon(li, 'is-hecho');
        li.classList.toggle('is-sigue', i < pasos.length - 1);
        texto(li.querySelector('.fa-dura'), seg(DURA[i]));
      });
      pon(herramienta, 'is-abierta', 'is-resuelta'); texto(hReloj, seg(T_HERR));
      nota.className = 'fa-nota is-vista'; texto(nota, NOTA.hecho);
    }
    // desplegar y plegar: los pasos entran de arriba abajo y se van al revés
    function despliega() {
      pasos.forEach((li, i) => { li.style.transitionDelay = (i * 45) + 'ms'; pon(li, 'is-visto'); });
      tope = lista; resumen.setAttribute('aria-expanded', 'true');
    }
    function pliega() {
      pasos.forEach((li, i) => { li.style.transitionDelay = ((pasos.length - 1 - i) * 40) + 'ms'; quita(li, 'is-visto'); });
      tope = null; resumen.setAttribute('aria-expanded', 'false');
    }

    /* Cada entrada del guion. `tope` es el elemento donde termina lo que
       se ve: el panel lleva su borde de abajo hasta ahí con el resorte. */
    function haz([, que, i]) {
      const li = pasos[i];
      switch (que) {
        case 'envia': limpia(); tope = null; break;
        case 'corre':
          quita(resumen, 'is-listo'); pon(resumen, 'is-corre');
          resumen.setAttribute('aria-expanded', 'true');
          texto(voz, 'Trabajando…');
          break;
        case 'aparece':
          li.style.transitionDelay = '';
          pon(li, 'is-visto', 'is-activo');
          if (i) pon(pasos[i - 1], 'is-sigue');
          texto(cuenta, String(i + 1));
          tope = li.firstElementChild;
          break;
        case 'abre': pon(herramienta, 'is-abierta'); tope = herramienta; break;
        case 'resuelve': pon(herramienta, 'is-resuelta'); texto(hReloj, seg(T_HERR)); break;
        case 'falla':
          quita(li, 'is-activo'); pon(li, 'is-error');
          texto(nota, NOTA.falla); pon(nota, 'is-vista', 'is-mal');
          tope = nota;
          break;
        case 'reintenta':
          quita(li, 'is-error'); pon(li, 'is-activo');
          texto(nota, NOTA.reintenta); quita(nota, 'is-mal');
          break;
        case 'hecho':
          quita(li, 'is-activo', 'is-error'); pon(li, 'is-hecho');
          texto(li.querySelector('.fa-dura'), seg(DURA[i]));
          if (li.contains(nota)) texto(nota, NOTA.hecho);
          pon(arco[i], 'is-lleno');
          break;
        case 'listo':
          quita(resumen, 'is-corre'); pon(resumen, 'is-listo');
          campo.readOnly = false; enviar.removeAttribute('aria-disabled'); resumen.removeAttribute('aria-disabled');
          texto(voz, 'Listo en 12 s, 5 pasos');
          break;
        // con movimiento reducido no se pliega: los pasos se quedan a la vista
        case 'pliega': if (!reduce) pliega(); break;
        case 'fin': corriendo = false; abierto = reduce; proxima = reduce ? Infinity : ahora + o.pausa; break;
      }
    }

    /* ── el panel ──────────────────────────────────────────────────── */
    /* La altura de lo visible (h) sigue a la meta con un resorte de
       masa, muelle y amortiguador, a pasos fijos de 1/240 s: al abrirse
       se pasa un poco y vuelve; al cerrarse, más amortiguado, no rebota
       contra el resumen. Con h se mueven las tres piezas del fondo, el
       recorte de los pasos (que sube lo que su contenido baja) y, en
       pantallas anchas, el panel entero, que sube la mitad para seguir
       centrado. */
    let h = 0, v = 0, objetivo = 0, alto = 0, holgura = 0, tope = null, centra = 0;
    const metas = new Map();
    function resorte(dt) {
      if (reduce) { h = objetivo; v = 0; return; }
      const k = 210, c = objetivo < h ? 27 : 17.5;
      for (let n = Math.round(Math.min(dt, .05) * 240); n > 0; n--) {
        v += (k * (objetivo - h) - c * v) / 240;
        h += v / 240;
      }
      if (Math.abs(objetivo - h) + Math.abs(v) < .05) { h = objetivo; v = 0; }
    }
    let pintado = -1;
    function pinta() {
      const y = Math.max(0, h);
      if (y === pintado) return;
      pintado = y;
      const d = alto + holgura - y;
      // centrado: el panel sube la mitad de lo que crece, y crece hacia los dos lados
      if (centra) raiz.style.transform = 'translateY(' + (-y * centra / 2).toFixed(2) + 'px)';
      medio.style.transform = 'scaleY(' + (y / 100).toFixed(4) + ')';
      pie.style.transform = 'translateY(' + y.toFixed(2) + 'px)';
      recorte.style.transform = 'translateY(' + (-d).toFixed(2) + 'px)';
      lista.style.transform = 'translateY(' + d.toFixed(2) + 'px)';
    }
    /* Las medidas se toman aquí (al cargar las fuentes y al cambiar el
       ancho), nunca en el cuadro que anima: el borde de abajo de cada
       elemento que puede ser el tope, medido sin las transformaciones. */
    const fondo = el => { let y = el.offsetHeight; for (let n = el; n && n !== lista; n = n.offsetParent) y += n.offsetTop; return y; };
    function mide() {
      const h0 = resumen.offsetTop + resumen.offsetHeight;
      alto = lista.offsetHeight;
      holgura = Math.round(alto * .15) + 24;   // sitio para que el resorte se pase
      raiz.style.setProperty('--fa-h0', h0 + 'px');
      raiz.style.setProperty('--fa-alto-recorte', (alto + holgura) + 'px');
      // con --fa-centra la caja mide lo plegado (y el panel se centra al crecer); sin él, reserva lo desplegado
      centra = parseFloat(getComputedStyle(raiz).getPropertyValue('--fa-centra')) || 0;
      raiz.style.setProperty('--fa-reserva', (centra ? 0 : alto) + pie.offsetHeight + 'px');
      if (!centra) raiz.style.transform = '';
      metas.clear();
      [herramienta, nota, ...pasos.map(li => li.firstElementChild)].forEach(el => metas.set(el, fondo(el) + 7));
      metas.set(lista, alto);
      pintado = -1;
    }

    /* ── el reloj ──────────────────────────────────────────────────── */
    /* Un solo bucle de requestAnimationFrame. La tarea es función del
       tiempo desde que se envió (r), así cada vuelta sale idéntica. */
    let corriendo = false, abierto = false, inicio = 0, paso = 0, pedido = -1;
    let ahora = 0, antes = 0, proxima = Infinity, gesto = false;

    function cuadro(sello) {
      requestAnimationFrame(cuadro);
      const dt = antes ? (sello - antes) / 1000 : 0;
      // la primera vuelta sola, para quien solo mira
      if (!antes && !reduce) proxima = sello + o.primera;
      antes = ahora = sello;
      // alguien llegó: se le da un momento para que envíe él
      if (gesto === true) { gesto = sello; if (!corriendo && !abierto && document.activeElement !== campo && !reduce) proxima = sello + o.tras_gesto; }
      if (!corriendo && sello >= proxima) envia(true);
      if (pedido >= 0) { inicio = sello + pedido; pedido = -1; paso = 0; corriendo = true; }
      if (corriendo) {
        const r = (sello - inicio) / 1000;
        while (corriendo && paso < GUION.length && GUION[paso][0] <= r) haz(GUION[paso++]);
        if (resumen.classList.contains('is-corre')) texto(reloj, seg((r - cuando('corre')) * RITMO));
        if (herramienta.classList.contains('is-abierta') && !herramienta.classList.contains('is-resuelta')) texto(hReloj, seg((r - cuando('abre')) * RITMO));
      }
      objetivo = tope ? metas.get(tope) : 0;
      resorte(dt);
      pinta();
    }

    // enviar: el botón se hunde y la flecha sale disparada y vuelve por abajo
    function envia(sola) {
      if (corriendo || enviar.hasAttribute('aria-disabled')) return;
      proxima = Infinity;
      if (!reduce) {
        enviar.animate([{ transform: 'scale(1)' }, { transform: 'scale(.84)', offset: .3 }, { transform: 'scale(1.05)', offset: .7 }, { transform: 'scale(1)' }],
          { duration: 420, easing: 'ease-out' });
        enviar.firstElementChild.animate([
          { transform: 'none', opacity: 1 }, { transform: 'translateY(-16px)', opacity: 0, offset: .4 },
          { transform: 'translateY(14px)', opacity: 0, offset: .41 }, { transform: 'none', opacity: 1 },
        ], { duration: 700, easing: 'cubic-bezier(.22, 1, .36, 1)' });
      }
      campo.readOnly = true;
      enviar.setAttribute('aria-disabled', 'true');
      resumen.setAttribute('aria-disabled', 'true');
      // si los pasos estaban a la vista, primero se pliegan
      pedido = abierto && !reduce ? 420 : 0;
      if (abierto && !reduce) pliega();
      abierto = false;
      if (sola) campo.blur();
    }
    form.addEventListener('submit', e => { e.preventDefault(); envia(false); });

    // el resumen plegado se despliega con un clic (y se vuelve a plegar)
    resumen.addEventListener('click', () => {
      if (corriendo || resumen.hasAttribute('aria-disabled')) return;
      abierto = !abierto;
      abierto ? despliega() : pliega();
      proxima = abierto ? Infinity : ahora + o.pausa;
    });
    // mientras se escribe la petición, no se envía sola
    campo.addEventListener('focus', () => { if (!corriendo) proxima = Infinity; });
    campo.addEventListener('blur', () => { if (!corriendo && !abierto && !reduce) proxima = ahora + o.pausa; });
    ['pointermove', 'pointerdown', 'keydown'].forEach(ev => addEventListener(ev, () => { if (gesto === false) gesto = true; }, { once: true }));

    completa();
    if (reduce) { abierto = true; despliega(); }
    (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => {
      mide();
      addEventListener('resize', mide);
      requestAnimationFrame(cuadro);
    });
    return { envia: () => envia(true) };
  }

  window.Faena = Faena;
})();
