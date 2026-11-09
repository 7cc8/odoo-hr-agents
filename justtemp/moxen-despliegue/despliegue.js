/* =====================================================================
   Despliegue · Moxen
   Una tarjeta que se despliega en una vista completa. Es la técnica
   FLIP (First, Last, Invert, Play): se mide dónde está cada pieza
   (el número, el planeta, el nombre), se mueve de verdad a su hueco en
   la vista completa, se mide otra vez y se anima solo la diferencia con
   transform. Así la pieza es la misma —el planeta sigue girando— y el
   navegador no recalcula nada mientras se mueve. El panel de fondo
   crece desde la tarjeta con un recorte que se abre, y todo va con un
   resorte de verdad. Cerrar es lo mismo al revés. Sin dependencias.

     const d = Despliegue(document.querySelector('[data-despliegue]'), { datos });
     d.abre(tarjeta);      d.cierra();
   ===================================================================== */
(function () {
  'use strict';

  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Un resorte como curva de animación: se simula un oscilador amortiguado
     y su recorrido se entrega como linear(), que el navegador sigue tal
     cual. Sale una animación de CSS normal, con el rebote de la física.
     Donde linear() no existe, una curva parecida sin rebote. */
  function resorte(rigidez, roce) {
    if (!(window.CSS && CSS.supports('transition-timing-function', 'linear(0, 1)'))) {
      return { easing: 'cubic-bezier(.22, 1, .36, 1)', ms: 800 };
    }
    let x = 0, v = 0, t = 0;
    const dt = 1 / 120, puntos = [0];
    for (let n = 1; n < 600; n++) {
      v += (rigidez * (1 - x) - roce * v) * dt;
      x += v * dt; t += dt;
      if (n % 2 === 0) puntos.push(+x.toFixed(4));
      if (Math.abs(1 - x) < .0015 && Math.abs(v) < .02 && n % 2 === 0) break;
    }
    puntos[puntos.length - 1] = 1;
    return { easing: 'linear(' + puntos.join(', ') + ')', ms: Math.round(t * 1000) };
  }

  function Despliegue(rejilla, opciones) {
    const o = Object.assign({
      datos: {},          // los textos de cada vista, por data-planeta
      rigidez: 140,       // el resorte: más rigidez, más rápido
      roce: 18,           // menos roce, más rebote
    }, opciones);
    const escena = rejilla.parentElement;
    const detalle = escena.querySelector('.dp-detalle');
    const panel = detalle.querySelector('.dp-panel');
    const cerrar = detalle.querySelector('.dp-cerrar');
    const huecos = {};
    detalle.querySelectorAll('[data-hueco]').forEach(h => { huecos[h.dataset.hueco] = h; });
    detalle.querySelectorAll('[data-aparece]').forEach((e, i) => e.style.setProperty('--i', i));
    const tarjetas = Array.from(rejilla.querySelectorAll('.dp-tarjeta'));
    const curva = resorte(o.rigidez, o.roce);

    let abierta = null, ocupado = false, sitios = [];

    // el rectángulo de la tarjeta como recorte del panel, que ocupa la pantalla
    function recorte(r, radio) {
      return 'inset(' + r.top + 'px ' + (innerWidth - r.right) + 'px ' + (innerHeight - r.bottom) + 'px ' + r.left + 'px round ' + radio + 'px)';
    }
    const entero = 'inset(0px 0px 0px 0px round 0px)';

    /* Invertir y reproducir: la pieza ya está en su sitio nuevo; se la
       devuelve con transform a donde estaba y se la suelta. La escala sale
       del ancho: número y nombre tienen el mismo interlineado y espaciado en
       los dos tamaños, así que crecen en proporción, sin deformarse. */
    function vuela(pieza, desde) {
      const hasta = pieza.getBoundingClientRect();
      const s = desde.width / hasta.width;
      pieza.classList.add('dp-viaja');
      const a = pieza.animate([
        { transform: 'translate(' + (desde.left - hasta.left) + 'px, ' + (desde.top - hasta.top) + 'px) scale(' + s + ')' },
        { transform: 'none' },
      ], { duration: reduce ? 0 : curva.ms, easing: curva.easing });
      a.onfinish = () => pieza.classList.remove('dp-viaja');
    }

    function rellena(planeta) {
      const d = o.datos[planeta] || {};
      detalle.dataset.planeta = planeta;
      detalle.querySelector('.dp-lema').textContent = d.lema || '';
      detalle.querySelectorAll('[data-dato]').forEach(e => { e.textContent = d[e.dataset.dato] || '—'; });
    }

    function abre(tarjeta) {
      if (abierta || ocupado) return;
      ocupado = true; abierta = tarjeta;
      rellena(tarjeta.dataset.planeta);

      // First: dónde están ahora las piezas y la tarjeta
      const piezas = Array.from(tarjeta.querySelectorAll('[data-pieza]'));
      const antes = piezas.map(p => p.getBoundingClientRect());
      const caja = tarjeta.getBoundingClientRect();
      const radio = parseFloat(getComputedStyle(tarjeta).borderTopLeftRadius) || 0;

      // Last: se mudan de verdad a la vista completa
      sitios = piezas.map(p => [p, p.parentNode, p.nextSibling]);
      detalle.hidden = false;
      piezas.forEach(p => huecos[p.dataset.pieza].appendChild(p));
      tarjeta.classList.add('dp-origen');
      tarjeta.setAttribute('aria-expanded', 'true');

      // Invert y Play: el panel crece desde la tarjeta y cada pieza vuela
      panel.animate([{ clipPath: recorte(caja, radio) }, { clipPath: entero }], { duration: reduce ? 0 : curva.ms, easing: curva.easing });
      piezas.forEach((p, i) => vuela(p, antes[i]));

      /* Las demás se hunden un poco, primero las más cercanas: se nota que
         la tarjeta sale de entre ellas y no que todo se apaga a la vez. */
      const cx = caja.left + caja.width / 2;
      tarjetas.forEach(t => {
        const r = t.getBoundingClientRect();
        t.style.setProperty('--d', Math.round(Math.abs(r.left + r.width / 2 - cx) / r.width));
      });
      rejilla.classList.add('dp-atras');
      detalle.classList.add('dp-abierto');

      setTimeout(() => { ocupado = false; cerrar.focus({ preventScroll: true }); }, reduce ? 0 : curva.ms * .6);
    }

    function cierra() {
      if (!abierta || ocupado) return;
      ocupado = true;
      const tarjeta = abierta;
      const piezas = sitios.map(s => s[0]);
      const antes = piezas.map(p => p.getBoundingClientRect());

      // lo que no viaja se va primero y rápido, para no estorbar al regreso
      detalle.classList.remove('dp-abierto');
      detalle.classList.add('dp-cierra');
      rejilla.classList.remove('dp-atras');

      /* De vuelta a la tarjeta, cada una en su sitio (al revés, para que el
         «hermano siguiente» de cada pieza ya esté en su lugar). La tarjeta
         sigue oculta y por encima del panel mientras sus piezas vuelan. */
      sitios.slice().reverse().forEach(([p, padre, siguiente]) => padre.insertBefore(p, siguiente));
      tarjeta.classList.add('dp-vuelve');
      const caja = tarjeta.getBoundingClientRect();
      const radio = parseFloat(getComputedStyle(tarjeta).borderTopLeftRadius) || 0;
      const a = panel.animate([{ clipPath: entero }, { clipPath: recorte(caja, radio) }], { duration: reduce ? 0 : curva.ms, easing: curva.easing, fill: 'forwards' });
      piezas.forEach((p, i) => vuela(p, antes[i]));

      a.onfinish = () => {
        detalle.hidden = true;
        detalle.classList.remove('dp-cierra');
        a.cancel();
        tarjeta.classList.remove('dp-origen', 'dp-vuelve');
        tarjeta.setAttribute('aria-expanded', 'false');
        abierta = null; ocupado = false;
        tarjeta.focus({ preventScroll: true });
      };
    }

    tarjetas.forEach(t => {
      t.setAttribute('aria-expanded', 'false');
      t.addEventListener('click', () => abre(t));
    });
    cerrar.addEventListener('click', cierra);
    addEventListener('keydown', e => { if (e.key === 'Escape') cierra(); });

    return { abre, cierra };
  }

  window.Despliegue = Despliegue;
})();
