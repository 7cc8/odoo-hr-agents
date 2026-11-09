/* =====================================================================
   Cavila · Moxen
   El momento en que una IA piensa y responde, bien resuelto. Al mandar la
   pregunta, la burbuja sube desde la caja de escribir; el asistente
   muestra «Pensando…» con una franja de luz inclinada que cruza la
   etiqueta y una chispa que late. Al terminar de pensar, la etiqueta se
   pliega en «Pensó n s ▸» (el tiempo real que tardó) y la respuesta entra
   palabra por palabra: cada una de borrosa a nítida, subiendo 4 px, con
   un cursor de bloque al final. Las palabras llegan en ráfagas (como por
   la red) a un búfer, y salen de él a un ritmo parejo que se apura si el
   búfer se llena: productor y consumidor. Al abrir ▸ se despliegan los
   pasos del razonamiento. Sin dependencias.

     Cavila(document.querySelector('[data-cavila]'), {
       responde: pregunta => ({ pasos: [['Leer la pregunta', '0,4 s']], texto: 'Hola, `código` y más.' }),
       piensa: 1300,                // ms que piensa la demo (con un servidor, resuelve cuando llegue)
     });

   En el texto, lo que va entre `comillas invertidas` se escribe como código.
   El tiempo sale de requestAnimationFrame y las ráfagas, de una semilla.
   ===================================================================== */
(function () {
  'use strict';

  function semilla(a) {
    return function () {
      a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  const CHISPA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5c.6 4.6 2.9 6.9 7.5 7.5-4.6.6-6.9 2.9-7.5 7.5-.6-4.6-2.9-6.9-7.5-7.5 4.6-.6 6.9-2.9 7.5-7.5z"/><path d="M19 15.5c.25 1.9 1.1 2.75 3 3-1.9.25-2.75 1.1-3 3-.25-1.9-1.1-2.75-3-3 1.9-.25 2.75-1.1 3-3z"/></svg>';
  const FLECHA = '<svg class="cv-flecha" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3.5 10.5 8 6 12.5"/></svg>';

  // la respuesta de ejemplo
  const EJEMPLO = {
    pasos: [
      ['Entender qué se quiere animar', '0,4 s'],
      ['Comparar una curva CSS con física de verdad', '0,9 s'],
      ['Elegir el ejemplo más corto', '0,3 s'],
    ],
    texto: 'Usa una transición con `cubic-bezier(.34, 1.56, .64, 1)`: esa curva se pasa del final y vuelve, como un resorte. ' +
      'Si quieres física de verdad, mueve el valor con `requestAnimationFrame` y frena la velocidad en cada cuadro.',
  };

  const escapa = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  // las fichas: palabras sueltas, o un trozo de `código` con su puntuación pegada
  const fichas = texto => (texto.match(/`[^`]+`[^\s`]*|[^\s`]+/g) || []).map(f => {
    const m = f.match(/^`([^`]+)`(.*)$/);
    return m ? '<code>' + escapa(m[1]) + '</code>' + escapa(m[2]) : escapa(f);
  });

  function Cavila(panel, opciones) {
    const o = Object.assign({ responde: () => EJEMPLO, piensa: 1300 }, opciones);
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hilo = panel.querySelector('[data-hilo]');
    const caja = panel.querySelector('[data-caja]');
    const campo = caja.querySelector('input');
    const enviar = caja.querySelector('.cv-enviar');
    let turno = null, raf = 0, antes = 0, azar = semilla(42);

    campo.addEventListener('input', () => { enviar.disabled = !campo.value.trim() || !!(turno && turno.ocupado); });
    caja.addEventListener('submit', e => { e.preventDefault(); pregunta(campo.value); });
    panel.querySelectorAll('[data-sugerencia]').forEach(b => b.addEventListener('click', () => pregunta(b.textContent)));
    panel.querySelector('[data-nueva]').addEventListener('click', nueva);

    /* ── preguntar ──────────────────────────────────────────────────── */
    function pregunta(texto) {
      texto = texto.trim();
      if (!texto || (turno && turno.ocupado)) return;
      const r = o.responde(texto);
      const origen = enviar.getBoundingClientRect();
      campo.value = '';
      enviar.disabled = true;
      panel.classList.add('is-charla');

      const el = document.createElement('div');
      el.className = 'cv-turno is-pensando';
      el.innerHTML =
        '<p class="cv-pregunta"></p>' +
        '<div class="cv-asistente"><span class="cv-avatar">' + CHISPA + '</span><div class="cv-cuerpo">' +
        '<button class="cv-etiqueta" type="button" aria-expanded="false" disabled>' +
        '<span class="cv-pensando">Pensando…</span>' +
        '<span class="cv-penso" aria-hidden="true"><span>Pensó</span><small></small>' + FLECHA + '</span></button>' +
        '<div class="cv-pasos"><ol>' + r.pasos.map((p, i) => '<li style="--i:' + i + '"><span>' + escapa(p[0]) + '</span><small>' + escapa(p[1]) + '</small></li>').join('') + '</ol></div>' +
        '<p class="cv-respuesta" aria-busy="true"><span class="cv-cursor" aria-hidden="true"></span></p>' +
        '</div></div>';
      el.querySelector('.cv-pregunta').textContent = texto;
      // un turno a la vez en la demo: el anterior se va
      hilo.querySelectorAll('.cv-turno').forEach(t => t.remove());
      hilo.appendChild(el);

      // la burbuja sube desde el botón de enviar (FLIP: de allá a su sitio)
      const burbuja = el.querySelector('.cv-pregunta');
      if (!reduce) {
        const b = burbuja.getBoundingClientRect();
        burbuja.animate([
          { transform: 'translate(' + (origen.left - b.right + 8).toFixed(1) + 'px, ' + (origen.top - b.top).toFixed(1) + 'px) scale(.92)', opacity: 0 },
          { opacity: 1, offset: .35 },
          { transform: 'none', opacity: 1 },
        ], { duration: 620, easing: 'cubic-bezier(.22, 1, .36, 1)' });
      }

      const etiqueta = el.querySelector('.cv-etiqueta');
      etiqueta.addEventListener('click', () => despliega(etiqueta.getAttribute('aria-expanded') !== 'true'));
      turno = {
        el, etiqueta, pasos: el.querySelector('.cv-pasos'), respuesta: el.querySelector('.cv-respuesta'), cursor: el.querySelector('.cv-cursor'),
        fichas: fichas(r.texto), llegadas: [], bufer: [], salidas: 0, reloj: 0, ultima: 0, pensado: false, ocupado: true,
      };
      // el productor: ráfagas de 1 a 4 fichas, separadas por pausas desiguales
      let t = 0, i = 0;
      while (i < turno.fichas.length) {
        t += 70 + azar() * 150;
        const n = 1 + Math.floor(azar() * 4);
        turno.llegadas.push({ t, desde: i, hasta: Math.min(turno.fichas.length, i + n) });
        i += n;
      }
      antes = 0;
      if (!raf) raf = requestAnimationFrame(cuadro);
    }

    /* ── pensar y escribir ──────────────────────────────────────────── */
    function cuadro(ts) {
      raf = 0;
      const tu = turno;
      if (!tu || !tu.ocupado) return;
      const h = antes ? Math.min(ts - antes, 50) : 16.7;
      antes = ts;
      tu.reloj += h;
      if (!tu.pensado) {
        if (tu.reloj >= o.piensa) termina(tu);
      } else {
        const t = tu.reloj - o.piensa;
        // llegan las ráfagas al búfer…
        while (tu.llegadas.length && tu.llegadas[0].t <= t) {
          const r = tu.llegadas.shift();
          for (let k = r.desde; k < r.hasta; k++) tu.bufer.push(tu.fichas[k]);
        }
        // …y salen de a una, a un ritmo parejo que se apura si se acumulan
        const ritmo = tu.bufer.length > 6 ? 28 : tu.bufer.length > 3 ? 42 : 56;
        if (tu.bufer.length && t - tu.ultima >= ritmo) { tu.ultima = t; escribe(tu, tu.bufer.shift()); }
        if (!tu.llegadas.length && !tu.bufer.length) {
          tu.ocupado = false;
          tu.el.classList.add('is-listo');
          tu.respuesta.setAttribute('aria-busy', 'false');
          enviar.disabled = !campo.value.trim();
          return;
        }
      }
      raf = requestAnimationFrame(cuadro);
    }

    // de «Pensando…» a «Pensó n s ▸»: el tiempo que de verdad pasó
    function termina(tu) {
      tu.pensado = true;
      tu.el.classList.replace('is-pensando', 'is-pensado');
      const s = Math.max(1, Math.round(tu.reloj / 1000));
      tu.el.querySelector('.cv-penso small').textContent = s + ' s';
      tu.etiqueta.disabled = false;
      tu.etiqueta.setAttribute('aria-label', 'Pensó ' + s + ' segundos. Ver los pasos');
      tu.el.querySelector('.cv-pensando').setAttribute('aria-hidden', 'true');
      // sin movimiento, la respuesta entera de una vez
      if (reduce) { tu.llegadas = []; tu.fichas.forEach(f => escribe(tu, f)); }
    }

    function escribe(tu, html) {
      const s = document.createElement('span');
      s.className = 'cv-palabra';
      s.innerHTML = html;
      tu.respuesta.insertBefore(s, tu.cursor);
      tu.respuesta.insertBefore(document.createTextNode(' '), tu.cursor);
      // si la respuesta ya no cabe, el hilo baja con ella
      if (hilo.scrollHeight > hilo.clientHeight) hilo.scrollTop = hilo.scrollHeight;
    }

    // los pasos: la caja crece hasta el alto real de la lista
    function despliega(abre) {
      const tu = turno;
      if (!tu || !tu.pensado) return;
      tu.etiqueta.setAttribute('aria-expanded', abre ? 'true' : 'false');
      tu.pasos.style.height = abre ? tu.pasos.firstElementChild.scrollHeight + 'px' : '0px';
      tu.pasos.classList.toggle('is-abierto', abre);
    }

    /* ── empezar de nuevo ───────────────────────────────────────────── */
    function nueva() {
      if (!turno) return;
      const el = turno.el;
      turno.ocupado = false;
      turno = null;
      azar = semilla(42);
      el.classList.add('is-ida');
      setTimeout(() => el.remove(), reduce ? 0 : 420);
      panel.classList.remove('is-charla');
      enviar.disabled = !campo.value.trim();
    }

    return { pregunta, nueva, despliega };
  }

  window.Cavila = Cavila;
})();
