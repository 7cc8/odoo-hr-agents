/**
 * ============================================================================
 * MOXEN MOTION SUITE — MASTER ENGINE (moxen_sample.js)
 * Authentic Physics Implementation for all 10 Moxen Packages
 * Adapted to Seraj HR Agents & Odoo System
 * ============================================================================
 */

(function () {
  'use strict';

  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  const quieto = () => mq.matches;
  const lim = (v, a, b) => Math.max(a, Math.min(b, v));
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const plural = (n, u, p) => n + ' ' + (n === 1 ? u : p);

  /* ── 0. Universal Spring to linear() Curve Generator (240Hz sub-stepping) ── */
  function muelle(k, c) {
    const pts = [0];
    let x = 0, v = 0, t = 0;
    while (t < 3) {
      v += (k * (1 - x) - c * v) / 240;
      x += v / 240;
      t += 1 / 240;
      pts.push(x);
      if (t > .15 && Math.abs(1 - x) < .001 && Math.abs(v) < .01) break;
    }
    const out = [];
    for (let i = 0; i <= 40; i++) out.push(pts[Math.round(i / 40 * (pts.length - 1))].toFixed(4));
    out[40] = '1';
    return 'linear(' + out.join(', ') + ')';
  }

  function muelleObj(k, c) {
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

  /* ==========================================================================
     1. MOXEN-CAVILA: AI Thinking, In-cell Flip & Adaptive Word Streaming
     (حزمة معتمدة لا تتغير)
     ========================================================================== */
  function initCavila() {
    const panel = document.querySelector('[data-cavila]');
    if (!panel) return;

    const hilo = panel.querySelector('[data-hilo]');
    const caja = panel.querySelector('[data-caja]');
    const campo = caja.querySelector('input');
    const enviar = caja.querySelector('.cv-enviar');
    let turno = null, raf = 0, antes = 0;

    const CHISPA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5c.6 4.6 2.9 6.9 7.5 7.5-4.6.6-6.9 2.9-7.5 7.5-.6-4.6-2.9-6.9-7.5-7.5 4.6-.6 6.9-2.9 7.5-7.5z"/><path d="M19 15.5c.25 1.9 1.1 2.75 3 3-1.9.25-2.75 1.1-3 3-.25-1.9-1.1-2.75-3-3 1.9-.25 2.75-1.1 3-3z"/></svg>';
    const FLECHA = '<svg class="cv-flecha" viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3.5 5.5 8 10 12.5"/></svg>';

    const EJEMPLOS_HR = {
      'تعارضات': {
        pasos: [
          ['فحص لوائح نظام العمل السعودي (المادة 77 و 84)', '0,3 ث'],
          ['التحقق من سجلات Odoo ومطابقة الرقم الوطني للموظف', '0,7 ث'],
          ['التأكد من عدم ازدواجية التأمينات الاجتماعية والرواتب', '0,4 ث']
        ],
        texto: 'تم فحص مسودة العقد بنجاح: لا توجد تعارضات في الأجر الأساسي أو بدل السكن. ' +
               'القواعد تتوافق مع نظام العمل عبر استدعاء `hr.contract.validate()`، ويمكنك المتابعة بأمان عبر زر الاعتماد.'
      },
      'افتراضي': {
        pasos: [
          ['استيعاب استفسار الموارد البشرية وتحديد الوكيل المختص', '0,4 ث'],
          ['فحص قاعدة المعرفة والاتصال بـ Odoo عبر وكيل الاستعلام', '0,8 ث'],
          ['صياغة القرار النهائي مع توثيق الأثر في سجل التدقيق', '0,3 ث']
        ],
        texto: 'يقوم «سراج» بمطابقة طلبك مع وكلاء المنظومة الثمانية. ' +
               'يمكنك مراجعة كافة التفاصيل عبر `hr_reference_options` وسيقوم الوكيل بتنفيذ المطلوب وفق الحوكمة.'
      }
    };

    campo.addEventListener('input', () => { enviar.disabled = !campo.value.trim() || !!(turno && turno.ocupado); });
    caja.addEventListener('submit', e => { e.preventDefault(); pregunta(campo.value); });
    panel.querySelectorAll('[data-sugerencia]').forEach(b => b.addEventListener('click', () => pregunta(b.textContent)));
    const btnNueva = panel.querySelector('[data-nueva]');
    if (btnNueva) btnNueva.addEventListener('click', nueva);

    function pregunta(texto) {
      texto = texto.trim();
      if (!texto || (turno && turno.ocupado)) return;
      const respData = texto.includes('عقد') || texto.includes('تعارض') ? EJEMPLOS_HR['تعارضات'] : EJEMPLOS_HR['افتراضي'];
      campo.value = '';
      enviar.disabled = true;
      panel.classList.add('is-charla');

      const el = document.createElement('div');
      el.className = 'cv-turno is-pensando';
      el.innerHTML =
        '<p class="cv-pregunta"></p>' +
        '<div class="cv-asistente"><span class="cv-avatar">' + CHISPA + '</span><div class="cv-cuerpo">' +
        '<button class="cv-etiqueta" type="button" aria-expanded="false" disabled>' +
        '<span class="cv-pensando">سراج يستدل الآن…</span>' +
        '<span class="cv-penso" aria-hidden="true"><span>فكّر لـ</span><small></small>' + FLECHA + '</span></button>' +
        '<div class="cv-pasos"><ol>' + respData.pasos.map((p, i) => '<li style="--i:' + i + '"><span>' + esc(p[0]) + '</span><small>' + esc(p[1]) + '</small></li>').join('') + '</ol></div>' +
        '<p class="cv-respuesta" aria-busy="true"><span class="cv-cursor" aria-hidden="true"></span></p>' +
        '</div></div>';
      el.querySelector('.cv-pregunta').textContent = texto;

      hilo.querySelectorAll('.cv-turno').forEach(t => t.remove());
      hilo.appendChild(el);

      const etiqueta = el.querySelector('.cv-etiqueta');
      etiqueta.addEventListener('click', () => despliega(etiqueta.getAttribute('aria-expanded') !== 'true'));

      const fichas = (respData.texto.match(/`[^`]+`[^\s`]*|[^\s`]+/g) || []).map(f => {
        const m = f.match(/^`([^`]+)`(.*)$/);
        return m ? '<code>' + esc(m[1]) + '</code>' + esc(f.slice(m[0].length)) : esc(f);
      });

      turno = {
        el, etiqueta, pasos: el.querySelector('.cv-pasos'), respuesta: el.querySelector('.cv-respuesta'), cursor: el.querySelector('.cv-cursor'),
        fichas, llegadas: [], bufer: [], reloj: 0, ultima: 0, pensado: false, ocupado: true
      };

      let t = 0, i = 0;
      while (i < turno.fichas.length) {
        t += 60 + Math.random() * 120;
        const n = 1 + Math.floor(Math.random() * 3);
        turno.llegadas.push({ t, desde: i, hasta: Math.min(turno.fichas.length, i + n) });
        i += n;
      }
      antes = 0;
      if (!raf) raf = requestAnimationFrame(cuadro);
    }

    function cuadro(ts) {
      raf = 0;
      const tu = turno;
      if (!tu || !tu.ocupado) return;
      const h = antes ? Math.min(ts - antes, 50) : 16.7;
      antes = ts;
      tu.reloj += h;
      if (!tu.pensado) {
        if (tu.reloj >= 1400) termina(tu);
      } else {
        const t = tu.reloj - 1400;
        while (tu.llegadas.length && tu.llegadas[0].t <= t) {
          const r = tu.llegadas.shift();
          for (let k = r.desde; k < r.hasta; k++) tu.bufer.push(tu.fichas[k]);
        }
        const ritmo = tu.bufer.length > 5 ? 26 : tu.bufer.length > 2 ? 40 : 54;
        if (tu.bufer.length && t - tu.ultima >= ritmo) {
          tu.ultima = t;
          escribe(tu, tu.bufer.shift());
        }
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

    function termina(tu) {
      tu.pensado = true;
      tu.el.classList.replace('is-pensando', 'is-pensado');
      const s = Math.max(1, (tu.reloj / 1000).toFixed(1));
      tu.el.querySelector('.cv-penso small').textContent = s + ' ث';
      tu.etiqueta.disabled = false;
      tu.el.querySelector('.cv-pensando').setAttribute('aria-hidden', 'true');
    }

    function escribe(tu, html) {
      const s = document.createElement('span');
      s.className = 'cv-palabra';
      s.innerHTML = html;
      tu.respuesta.insertBefore(s, tu.cursor);
      tu.respuesta.insertBefore(document.createTextNode(' '), tu.cursor);
      if (hilo.scrollHeight > hilo.clientHeight) hilo.scrollTop = hilo.scrollHeight;
    }

    function despliega(abre) {
      const tu = turno;
      if (!tu || !tu.pensado) return;
      tu.etiqueta.setAttribute('aria-expanded', abre ? 'true' : 'false');
      tu.pasos.style.height = abre ? tu.pasos.firstElementChild.scrollHeight + 'px' : '0px';
      tu.pasos.classList.toggle('is-abierto', abre);
    }

    function nueva() {
      if (!turno) return;
      const el = turno.el;
      turno.ocupado = false;
      turno = null;
      el.classList.add('is-ida');
      setTimeout(() => el.remove(), 400);
      panel.classList.remove('is-charla');
      enviar.disabled = !campo.value.trim();
    }
  }

  /* ==========================================================================
     2. MOXEN-FAENA: 3-Piece Agent Stepper, Live Stopwatch & Arcs Ring
     (حزمة معتمدة لا تتغير)
     ========================================================================== */
  function initFaena() {
    const raiz = document.querySelector('[data-faena]');
    if (!raiz) return;

    const $ = s => raiz.querySelector(s);
    const form = $('.fa-pedido'), campo = $('.fa-campo'), enviar = $('.fa-enviar');
    const resumen = $('.fa-resumen'), reloj = $('.fa-reloj'), cuenta = $('.fa-cuenta');
    const medio = $('.fa-medio'), pie = $('.fa-pie'), recorte = $('.fa-recorte'), lista = $('.fa-pasos');
    const herramienta = $('.fa-herramienta'), hReloj = $('.fa-h-reloj'), nota = $('.fa-nota');
    const pasos = Array.from(lista.children);

    const ICONO = '<span class="fa-giro">' + Array.from({ length: 10 }, (_, k) => '<i style="--k:' + k + '"></i>').join('') + '</span>'
      + '<svg class="fa-bien" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11"/><path d="M7.5 12.4l3.1 3.1 6-6.5" pathLength="1"/></svg>'
      + '<svg class="fa-mal" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11"/><path d="M8.8 8.8l6.4 6.4" pathLength="1"/><path d="M15.2 8.8l-6.4 6.4" pathLength="1"/></svg>';

    pasos.forEach(li => { li.querySelector('.fa-icono').innerHTML = ICONO; });

    function arcos(n) {
      const p = a => (12 + 10 * Math.sin(a)).toFixed(2) + ' ' + (12 - 10 * Math.cos(a)).toFixed(2);
      let s = '<g class="fa-anillo-giro">';
      for (let k = 0; k < n; k++) {
        const a = (k / n) * 2 * Math.PI, b = ((k + 1) / n) * 2 * Math.PI, hueco = .2;
        s += '<path d="M' + p(a + hueco) + 'A10 10 0 0 1 ' + p(b - hueco) + '"/>';
      }
      return s + '</g>';
    }
    $('.fa-anillo').innerHTML = arcos(pasos.length);
    const arco = Array.from(raiz.querySelectorAll('.fa-anillo path'));

    let timer = null;
    form.addEventListener('submit', e => {
      e.preventDefault();
      ejecutaGuion();
    });
    resumen.addEventListener('click', () => {
      const isExp = resumen.getAttribute('aria-expanded') === 'true';
      resumen.setAttribute('aria-expanded', !isExp);
      pasos.forEach(p => p.classList.toggle('is-visto', !isExp));
    });

    function ejecutaGuion() {
      if (timer) clearInterval(timer);
      resumen.className = 'fa-resumen is-corre';
      resumen.setAttribute('aria-expanded', 'true');
      pasos.forEach(p => { p.className = 'fa-paso'; p.querySelector('.fa-dura').textContent = ''; });
      herramienta.className = 'fa-herramienta';
      nota.className = 'fa-nota';
      arco.forEach(a => a.classList.remove('is-lleno'));

      let step = 0;
      let startTime = Date.now();
      timer = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1) + ' ث';
        reloj.textContent = elapsed;
      }, 100);

      const runStep = (idx) => {
        if (idx >= pasos.length) {
          clearInterval(timer);
          resumen.className = 'fa-resumen is-listo';
          resumen.setAttribute('aria-expanded', 'false');
          pasos.forEach(p => p.classList.remove('is-visto'));
          return;
        }
        cuenta.textContent = (idx + 1);
        const li = pasos[idx];
        li.classList.add('is-visto', 'is-activo');

        if (idx === 1) {
          herramienta.classList.add('is-abierta');
          let hStart = Date.now();
          const hTimer = setInterval(() => {
            hReloj.textContent = ((Date.now() - hStart) / 1000).toFixed(1) + ' ث';
          }, 100);
          setTimeout(() => {
            clearInterval(hTimer);
            li.classList.remove('is-activo');
            li.classList.add('is-hecho');
            li.querySelector('.fa-dura').textContent = '1,1 ث';
            arco[idx].classList.add('is-lleno');
            runStep(idx + 1);
          }, 1200);
          return;
        }

        if (idx === 2) {
          setTimeout(() => {
            li.classList.remove('is-activo');
            li.classList.add('is-error');
            nota.textContent = 'تحذير: تطابق جزئي في بيانات البصمة · إعادة المحاولة بالهوية الوطنية';
            nota.classList.add('is-vista');
            setTimeout(() => {
              li.classList.remove('is-error');
              li.classList.add('is-activo');
              nota.textContent = 'تم الحل بنجاح بالمطابقة المباشرة';
              setTimeout(() => {
                li.classList.remove('is-activo');
                li.classList.add('is-hecho');
                li.querySelector('.fa-dura').textContent = '1,4 ث';
                arco[idx].classList.add('is-lleno');
                runStep(idx + 1);
              }, 600);
            }, 800);
          }, 600);
          return;
        }

        setTimeout(() => {
          li.classList.remove('is-activo');
          li.classList.add('is-hecho');
          li.querySelector('.fa-dura').textContent = '0,6 ث';
          arco[idx].classList.add('is-lleno');
          runStep(idx + 1);
        }, 800);
      };

      runStep(0);
    }
  }

  /* ==========================================================================
     3. MOXEN-DESPLIEGUE: True Shared-Element FLIP & Circular Clip-Path
     (حزمة معتمدة لا تتغير)
     ========================================================================== */
  function initDespliegue() {
    const rejilla = document.querySelector('[data-despliegue]');
    if (!rejilla) return;

    const escena = rejilla.closest('.dp-escena');
    const detalle = escena.querySelector('.dp-detalle');
    const panel = detalle.querySelector('.dp-panel');
    const cerrar = detalle.querySelector('.dp-cerrar');
    const tarjetas = Array.from(rejilla.querySelectorAll('.dp-tarjeta'));

    const DATOS_AGENTES = {
      'seraj': { lema: 'المنسق العام وهندسة الحوار والمحاور الذكي', diametro: '100% دقة', dia: '24 أداة', anio: 'لحظي', lunas: '8 وكلاء' },
      'fahas': { lema: 'وكيل الاستعلام والقراءة الصارمة من Odoo', diametro: 'Read-Only', dia: '100% حماية', anio: '0,2 ثانية', lunas: '14 نموذج' },
      'katib': { lema: 'المنفذ الحصري لعمليات الكتابة والاعتماد في Odoo', diametro: 'Idempotent', dia: 'HITL صريح', anio: 'سجل تدقيق', lunas: 'Odoo 19' },
      'muwaffaq': { lema: 'وكيل المطابقة الدلالية والتسكين الوظيفي الذكي', diametro: 'AI Embeddings', dia: '99% ثقة', anio: 'تلقائي', lunas: 'اللوائح' }
    };

    let abierta = null, sitios = [];

    function vuela(pieza, desde) {
      const hasta = pieza.getBoundingClientRect();
      const s = desde.width / hasta.width;
      pieza.animate([
        { transform: 'translate(' + (desde.left - hasta.left) + 'px, ' + (desde.top - hasta.top) + 'px) scale(' + s + ')' },
        { transform: 'none' }
      ], { duration: 750, easing: 'cubic-bezier(.22, 1, .36, 1)' });
    }

    function abre(tarjeta) {
      if (abierta) return;
      abierta = tarjeta;
      const agente = tarjeta.dataset.agente;
      const d = DATOS_AGENTES[agente] || {};

      detalle.querySelector('.dp-lema').textContent = d.lema;
      const dds = detalle.querySelectorAll('dd');
      dds[0].textContent = d.diametro;
      dds[1].textContent = d.dia;
      dds[2].textContent = d.anio;
      dds[3].textContent = d.lunas;

      const piezas = Array.from(tarjeta.querySelectorAll('[data-pieza]'));
      const antes = piezas.map(p => p.getBoundingClientRect());
      const caja = tarjeta.getBoundingClientRect();

      sitios = piezas.map(p => [p, p.parentNode, p.nextSibling]);
      detalle.hidden = false;

      const huecos = {
        'numero': detalle.querySelector('[data-hueco="numero"]'),
        'nombre': detalle.querySelector('[data-hueco="nombre"]'),
        'esfera': detalle.querySelector('[data-hueco="esfera"]')
      };

      piezas.forEach(p => huecos[p.dataset.pieza].appendChild(p));
      tarjeta.classList.add('dp-origen');

      const clipInit = `inset(${caja.top}px ${innerWidth - caja.right}px ${innerHeight - caja.bottom}px ${caja.left}px round 18px)`;
      panel.animate([{ clipPath: clipInit }, { clipPath: 'inset(0px 0px 0px 0px round 0px)' }], {
        duration: 750, easing: 'cubic-bezier(.22, 1, .36, 1)'
      });

      piezas.forEach((p, i) => vuela(p, antes[i]));
      rejilla.classList.add('dp-atras');
    }

    function cierra() {
      if (!abierta) return;
      const tarjeta = abierta;
      const piezas = sitios.map(s => s[0]);
      const antes = piezas.map(p => p.getBoundingClientRect());

      sitios.slice().reverse().forEach(([p, padre, siguiente]) => padre.insertBefore(p, siguiente));
      const caja = tarjeta.getBoundingClientRect();
      const clipFinal = `inset(${caja.top}px ${innerWidth - caja.right}px ${innerHeight - caja.bottom}px ${caja.left}px round 18px)`;

      const a = panel.animate([{ clipPath: 'inset(0px 0px 0px 0px round 0px)' }, { clipPath: clipFinal }], {
        duration: 650, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'forwards'
      });

      piezas.forEach((p, i) => vuela(p, antes[i]));
      rejilla.classList.remove('dp-atras');

      a.onfinish = () => {
        detalle.hidden = true;
        a.cancel();
        tarjeta.classList.remove('dp-origen');
        abierta = null;
      };
    }

    tarjetas.forEach(t => t.addEventListener('click', () => abre(t)));
    cerrar.addEventListener('click', cierra);
  }

  /* ==========================================================================
     4. MOXEN-PILAR: Complete Authentic Physics Engine (pilar.js)
     Laser Guide Line, Rubber-Band Dragging, FLIP Tilted Sheet, Auto-Fit, Pinning
     ========================================================================== */
  function initPilar() {
    const raiz = document.querySelector('[data-pilar]');
    if (!raiz) return;

    const MODOS = { libre: [3200, 112], suelta: [320, 21], pliega: [440, 42], abre: [330, 22], scroll: [190, 26] };

    const COLUMNAS_HR = [
      { id: 'emp_id', nombre: 'رقم الموظف', tipo: 'id', ancho: 120 },
      { id: 'nombre', nombre: 'اسم الموظف', tipo: 'texto', ancho: 190 },
      { id: 'dept', nombre: 'القسم / الإدارة', tipo: 'texto', ancho: 160 },
      { id: 'cargo', nombre: 'المسمى الوظيفي', tipo: 'texto', ancho: 170 },
      { id: 'sueldo', nombre: 'الراتب الأساسي', tipo: 'num', ancho: 140 },
      { id: 'estado', nombre: 'حالة العقد', tipo: 'estado', ancho: 130 },
      { id: 'fecha', nombre: 'المباشرة', tipo: 'mono', ancho: 110 },
      { id: 'eval', nombre: 'التقييم', tipo: 'texto', ancho: 120 },
    ];

    const ESTADOS_HR = { pagado: 'ساري', enviado: 'قيد التجديد', pendiente: 'تحت المراجعة', devuelto: 'منتهي' };

    const FILAS_HR = [
      ['EMP-101', 'أحمد محمد العتيبي', 'تقنية المعلومات', 'مهندس برمجيات أول', '18,500 ر.س', 'pagado', '16 أكتوبر', 'ممتاز'],
      ['EMP-102', 'سارة خالد الدوسري', 'الموارد البشرية', 'أخصائي توظيف وتسكين', '14,200 ر.س', 'pagado', '01 سبتمبر', 'ممتاز'],
      ['EMP-103', 'فيصل بن سعود الشمري', 'العمليات والتشغيل', 'مدير مشاريع تنفيذي', '22,000 ر.س', 'pendiente', '15 أغسطس', 'جيد جداً'],
      ['EMP-104', 'نورة إبراهيم القحطاني', 'الشؤون القانونية', 'مستشار حوكمة وامتثال', '19,800 ر.س', 'pagado', '12 يوليو', 'ممتاز'],
      ['EMP-105', 'عبدالله عمر المطيري', 'المالية والمحاسبة', 'مدقق مالي معتمد', '16,000 ر.س', 'devuelto', '10 مايو', 'يحتاج تدريب'],
      ['EMP-106', 'ريم عبد العزيز السالم', 'التسويق الرقمي', 'أخصائية نمو وتواصل', '13,500 ر.س', 'enviado', '05 أبريل', 'جيد جداً'],
      ['EMP-107', 'خالد فهد المنصور', 'المشتريات والعقود', 'مسؤول سلاسل الإمداد', '15,200 ر.س', 'pagado', '20 مارس', 'جيد جداً'],
      ['EMP-108', 'هند سليمان الدخيل', 'خدمة العملاء', 'مشرفة الجودة ورضا العملاء', '12,800 ر.س', 'pagado', '11 يناير', 'ممتاز']
    ];

    const DENSIDADES = { comoda: 'مريحة', normal: 'عادية', compacta: 'مدمجة' };
    const POS = { comoda: 0, normal: 1, compacta: 2 };

    const IC = {
      pin: '<svg viewBox="0 0 24 24"><path d="M9.2 4.5h5.6l-.7 4.6 2.9 3v1.4H7v-1.4l2.9-3z"/><path d="M12 13.6v5.9"/></svg>',
      tilde: '<svg viewBox="0 0 24 24"><path d="M6.6 12.6l3.8 3.8 7.2-8.2" pathLength="1"/></svg>',
    };

    const $ = (s, r) => (r || raiz).querySelector(s);
    const el = {
      scroll: $('[data-scroll]'), tabla: $('[data-tabla]'), columnas: $('[data-columnas]'), cuenta: $('[data-cuenta]'),
      menu: $('[data-menu]'), menuLista: $('[data-menu-lista]'), menuCuenta: $('[data-menu-cuenta]'), todas: $('[data-todas]'),
      seg: $('[data-densidad]'), restablece: $('[data-restablece]'), estado: $('[data-estado]'), vivo: $('[data-vivo]'),
    };

    raiz.style.setProperty('--pi-muelle', muelle(420, 20));
    raiz.style.setProperty('--pi-ola', muelle(200, 17));
    const VUELO = muelle(230, 19), ATERRIZA = muelle(310, 24), LEVANTA = muelle(520, 24);

    const cols = COLUMNAS_HR.map(d => ({
      id: d.id, nombre: d.nombre, tipo: d.tipo, num: d.tipo === 'num', w0: d.ancho, w: d.ancho, min: d.min || 84, max: d.max || 460,
      fija: false, oculta: false, x: d.ancho, v: 0, tgt: d.ancho, kk: MODOS.suelta[0], cc: MODOS.suelta[1], celdas: [], plegada: false, ultX: -1, ultL: -1,
    }));
    const porId = {};
    cols.forEach(c => { porId[c.id] = c; });
    const ORDEN0 = cols.map(c => c.id);
    let orden = ORDEN0.slice();
    let densidad = 'normal';
    let activa = cols[0].id;
    let arrastre = null, timers = [], menuAbierto = false, menuFoco = 0;
    let ultToque = { t: -1e9, id: '', x: 0, y: 0 };
    const sc = { x: 0, v: 0, tgt: 0, activo: false };

    const setModo = (c, m) => { c.kk = MODOS[m][0]; c.cc = MODOS[m][1]; };
    const visibles = () => orden.filter(id => !porId[id].oculta);
    const nFijas = () => orden.filter(id => porId[id].fija && !porId[id].oculta).length;
    const tarda = (f, ms) => { const id = setTimeout(f, ms); timers.push(id); return id; };
    const anuncia = t => { if (el.vivo) { el.vivo.textContent = ''; setTimeout(() => { el.vivo.textContent = t; }, 30); } };

    const filas = [];
    function celdaHtml(c, v) {
      if (c.tipo === 'estado') return '<span class="pi-chip" data-e="' + esc(v) + '"><i></i>' + esc(ESTADOS_HR[v] || v) + '</span>';
      if (c.tipo === 'id') return '<span class="pi-mono pi-id">' + esc(v) + '</span>';
      if (c.tipo === 'num' || c.tipo === 'mono') return '<span class="pi-mono' + (v === '—' ? ' pi-sin' : '') + '">' + esc(v) + '</span>';
      return '<span class="pi-t">' + esc(v) + '</span>';
    }

    function construye() {
      el.tabla.textContent = '';
      const cab = document.createElement('div');
      cab.className = 'pi-fila pi-fila--cab'; cab.setAttribute('role', 'row');
      cols.forEach(c => {
        const th = document.createElement('div');
        th.className = 'pi-c pi-h' + (c.num ? ' es-num' : '');
        th.setAttribute('role', 'columnheader'); th.dataset.col = c.id;
        th.style.setProperty('--w', 'var(--pi-w-' + c.id + ')'); th.style.setProperty('--l', 'var(--pi-l-' + c.id + ')');
        th.innerHTML = '<div class="pi-ci"><button class="pi-th" type="button" tabindex="-1"><span class="pi-th-t">' + esc(c.nombre) + '</span></button><button class="pi-pin" type="button" tabindex="-1" aria-hidden="true">' + IC.pin + '</button><span class="pi-borde" aria-hidden="true"></span></div>';
        cab.appendChild(th); c.celdas.push(th);
      });
      el.tabla.appendChild(cab);

      FILAS_HR.forEach((f, i) => {
        const fila = document.createElement('div');
        fila.className = 'pi-fila'; fila.setAttribute('role', 'row'); fila.style.setProperty('--i', i);
        cols.forEach((c, j) => {
          const td = document.createElement('div');
          td.className = 'pi-c' + (c.num ? ' es-num' : '');
          td.setAttribute('role', 'cell'); td.dataset.col = c.id;
          td.style.setProperty('--w', 'var(--pi-w-' + c.id + ')'); td.style.setProperty('--l', 'var(--pi-l-' + c.id + ')');
          td.innerHTML = '<div class="pi-ci">' + celdaHtml(c, f[j]) + '</div>';
          fila.appendChild(td); c.celdas.push(td);
        });
        el.tabla.appendChild(fila); filas.push(fila);
      });

      el.guiaAnt = document.createElement('i'); el.guiaAnt.className = 'pi-guia-ant'; el.guiaAnt.setAttribute('aria-hidden', 'true');
      el.guia = document.createElement('i'); el.guia.className = 'pi-guia'; el.guia.setAttribute('aria-hidden', 'true');
      el.guiaEt = document.createElement('b'); el.guia.appendChild(el.guiaEt);
      el.tabla.append(el.guiaAnt, el.guia);

      el.menuLista.textContent = '';
      cols.forEach(c => {
        const li = document.createElement('li'); li.setAttribute('role', 'none');
        li.innerHTML = '<button class="pi-item" type="button" role="menuitemcheckbox" aria-checked="true" tabindex="-1" data-id="' + c.id + '"><span class="pi-caja">' + IC.tilde + '</span><span class="pi-item-nom"><span>' + esc(c.nombre) + '</span>' + IC.pin + '</span><span class="pi-item-w"></span></button>';
        el.menuLista.appendChild(li); c.item = li.firstChild; c.itemW = c.item.querySelector('.pi-item-w');
      });
    }

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
        b.setAttribute('aria-label', c.nombre + (c.fija ? ', مثبتة' : ''));
        c.celdas[0].querySelector('.pi-pin').title = c.fija ? 'إلغاء التثبيت' : 'تثبيت العمود';
        c.celdas[0].setAttribute('aria-hidden', c.oculta ? 'true' : 'false');
        c.celdas.forEach((td, i) => { if (i) td.setAttribute('aria-hidden', c.oculta ? 'true' : 'false'); });
      });
      raiz.dataset.fijas = nFijas() ? '1' : '';
      roving();
    }

    function roving() {
      if (porId[activa].oculta) activa = visibles()[0] || cols[0].id;
      cols.forEach(c => { c.celdas[0].querySelector('.pi-th').tabIndex = c.id === activa && !c.oculta ? 0 : -1; });
    }

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

    function actualizaBorde() {
      const d = nFijas() > 0 && Math.abs(el.scroll.scrollLeft) > 1;
      if (d !== (raiz.dataset.desplaza === '1')) { if (d) raiz.dataset.desplaza = '1'; else delete raiz.dataset.desplaza; }
    }
    el.scroll.addEventListener('scroll', actualizaBorde, { passive: true });
    ['wheel', 'touchstart', 'pointerdown'].forEach(ev => el.scroll.addEventListener(ev, () => { sc.activo = false; }, { passive: true }));
    function llevaA(x) {
      sc.x = el.scroll.scrollLeft; sc.v = 0; sc.tgt = Math.max(0, x); sc.activo = true; despierta();
    }

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

    const sucio = () => orden.some((id, i) => id !== ORDEN0[i]) || cols.some(c => c.fija || c.oculta || Math.abs(c.w - c.w0) > .5) || densidad !== 'normal';
    function cambio() { refresca(); }
    function refresca() {
      const vis = visibles().length, fijas = nFijas();
      el.cuenta.textContent = vis + '/' + cols.length;
      if (vis < cols.length) el.cuenta.dataset.parcial = ''; else delete el.cuenta.dataset.parcial;
      el.menuCuenta.textContent = vis + ' من ' + cols.length + ' مرئية';
      el.todas.disabled = vis === cols.length;
      el.estado.innerHTML = '<b>' + vis + '</b> من ' + cols.length + ' أعمدة · ' + (fijas ? '<b>' + fijas + '</b> مثبتة' : 'لا يوجد أعمدة مثبتة') + ' · صفوف ' + DENSIDADES[densidad];
      cols.forEach(c => {
        const on = !c.oculta;
        c.item.setAttribute('aria-checked', on ? 'true' : 'false');
        if (c.fija) c.item.dataset.fija = ''; else delete c.item.dataset.fija;
        c.itemW.textContent = on ? Math.round(c.w) + ' px' : 'مخفية';
        c.item.setAttribute('aria-disabled', on && vis === 1 ? 'true' : 'false');
      });
      cierraEstado();
    }
    function cierraEstado() {
      const b = el.restablece;
      if (b.dataset.e === 'listo') return;
      b.disabled = !sucio();
    }

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
    function ajusta(c) {
      if (c.oculta) return;
      const w = anchoAjustado(c);
      fijaAncho(c, w, 'suelta');
      marca(c);
      anuncia(c.nombre + ': تمت الملاءمة التلقائية لـ ' + Math.round(w) + ' بكسل');
      tarda(cambio, 50);
    }
    function marca(c) {
      c.celdas.forEach(td => td.classList.add('es-sel'));
      tarda(() => { if (!arrastre || arrastre.id !== c.id) c.celdas.forEach(td => td.classList.remove('es-sel')); }, 720);
    }

    let guiaCol = null;
    function colocaGuia() {
      const c = guiaCol;
      if (!c) return;
      const t = el.tabla.getBoundingClientRect(), r = c.celdas[0].getBoundingClientRect();
      el.guia.style.transform = 'translateX(' + (r.right - t.left - 1).toFixed(1) + 'px)';
      const bruto = arrastre && arrastre.tipo === 'ancho' ? arrastre.bruto : c.w;
      const tope = bruto <= c.min ? 'min' : bruto >= c.max ? 'max' : '';
      const txt = Math.round(c.x) + ' px' + (tope === 'min' ? ' · أدنى' : tope === 'max' ? ' · أقصى' : '');
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
      try { e.target.setPointerCapture(e.pointerId); } catch (_) {}
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
      if (a.mueve) { anuncia(c.nombre + ': ' + Math.round(c.w) + ' بكسل'); cambio(); }
    }

    function iniciaMover(e, c) {
      const th = c.celdas[0];
      const sr = el.scroll.getBoundingClientRect(), r = th.getBoundingClientRect();
      arrastre = { tipo: 'mover', id: c.id, pid: e.pointerId, x0: e.clientX, cx: e.clientX, vis0: r.left - sr.left, vis: r.left - sr.left, mueve: false, lam: null, orden0: orden.slice(), alvo: e.currentTarget };
      activa = c.id; roving();
      try { e.target.setPointerCapture(e.pointerId); } catch (_) {}
      despierta();
    }
    function levanta() {
      const a = arrastre, c = porId[a.id];
      const lam = document.createElement('div');
      lam.className = 'pi-lamina'; lam.setAttribute('aria-hidden', 'true');
      const tr = el.tabla.getBoundingClientRect();
      lam.style.width = c.celdas[0].getBoundingClientRect().width + 'px';
      lam.style.height = tr.height + 'px';
      c.celdas.forEach(td => {
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
      anuncia(c.nombre + ': تم رفع العمود.');
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
        anuncia(c.nombre + ': الموضع ' + (visibles().indexOf(c.id) + 1));
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
        if (sigue) { anuncia(c.nombre + ' في الموضع ' + (visibles().indexOf(c.id) + 1)); cambio(); }
      }
    }

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

    function fija(id, v) {
      const c = porId[id];
      if (c.fija === v || c.oculta) return;
      flip(() => {
        c.fija = v;
        const sin = orden.filter(k => k !== id);
        sin.splice(sin.filter(k => porId[k].fija).length, 0, id);
        orden = sin;
      });
      refresca();
      anuncia(c.nombre + (v ? ': مثبتة' : ': حرة'));
      if (v) {
        const max = el.scroll.scrollWidth - el.scroll.clientWidth;
        if (max > 40 && el.scroll.scrollLeft < 4 && !quieto()) {
          tarda(() => llevaA(Math.min(max, 150)), 520);
        }
      }
      cambio();
    }

    function oculta(id, v) {
      const c = porId[id];
      if (c.oculta === v) return;
      if (v && visibles().length <= 1) return;
      c.oculta = v;
      if (v) { c.tgt = 0; setModo(c, 'pliega'); }
      else { c.tgt = c.w; setModo(c, 'abre'); }
      aplicaClases();
      despierta();
      tarda(cambio, 80);
    }

    // Menu Columnas
    el.columnas.addEventListener('click', () => {
      menuAbierto = !menuAbierto;
      el.menu.hidden = !menuAbierto;
      el.columnas.setAttribute('aria-expanded', String(menuAbierto));
    });
    el.menuLista.addEventListener('click', e => {
      const item = e.target.closest('.pi-item');
      if (!item) return;
      const c = porId[item.dataset.id];
      oculta(c.id, !c.oculta);
    });
    el.todas.addEventListener('click', () => {
      cols.forEach(c => { if (c.oculta) oculta(c.id, false); });
    });

    // Densidad
    el.seg.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        const d = btn.dataset.d;
        if (densidad === d) return;
        densidad = d;
        raiz.dataset.densidad = d;
        el.seg.querySelectorAll('button').forEach(b => b.setAttribute('aria-checked', String(b === btn)));
        el.seg.style.setProperty('--pos', POS[d]);
        refresca();
      });
    });

    // Restablecer
    el.restablece.addEventListener('click', () => {
      if (!sucio()) return;
      flip(() => {
        orden = ORDEN0.slice();
        cols.forEach(c => {
          c.fija = false;
          c.oculta = false;
          c.w = c.w0; c.tgt = c.w0;
          setModo(c, 'suelta');
        });
        densidad = 'normal';
        raiz.dataset.densidad = 'normal';
        el.seg.querySelectorAll('button').forEach(b => b.setAttribute('aria-checked', String(b.dataset.d === 'normal')));
        el.seg.style.setProperty('--pos', 1);
      });
      el.restablece.dataset.e = 'listo';
      tarda(() => { el.restablece.dataset.e = 'reposo'; cierraEstado(); }, 1400);
      refresca();
      despierta();
    });

    construye();
    aplicaOrden();
    aplicaClases();
    pinta();
    refresca();
  }

  /* ==========================================================================
     5. MOXEN-CHARLA: 3D Rolling Cylinder, Flying Chips & Dual Checkmarks
     (حزمة معتمدة لا تتغير)
     ========================================================================== */
  function initCharla() {
    const root = document.querySelector('[data-charla]');
    if (!root) return;

    const log = root.querySelector('.ch-cuerpo');
    const rueda = root.querySelector('.ch-rueda');
    const campo = root.querySelector('.ch-campo');
    const envia = root.querySelector('.ch-envia');

    function enviaMensaje(texto) {
      if (!texto.trim()) return;
      const msg = document.createElement('div');
      msg.className = 'ch-msg de-tu';
      msg.innerHTML = esc(texto) + ' <svg class="ch-visto" viewBox="0 0 16 12"><path d="M1.4 6.5 4.5 9.6 10.8 2.8" pathLength="1"/><path d="M7.2 8.4 8.4 9.6 14.7 2.8" pathLength="1"/></svg>';
      log.appendChild(msg);
      campo.value = '';
      log.scrollTop = log.scrollHeight;

      setTimeout(() => msg.classList.add('is-read'), 500);

      rueda.classList.add('is-typing');
      rueda.firstElementChild.textContent = 'سراج يكتب لك الآن…';

      setTimeout(() => {
        rueda.classList.remove('is-typing');
        rueda.firstElementChild.textContent = 'متصل • يجيب فوراً';
        const botMsg = document.createElement('div');
        botMsg.className = 'ch-msg de-bot';
        botMsg.textContent = 'استلمت استفسارك بخصوص: «' + texto + '». تم فحص الحالة عبر سراج ووكلاء التدقيق، وكافة الإجراءات مطابقة للمعايير.';
        log.appendChild(botMsg);
        log.scrollTop = log.scrollHeight;
      }, 1400);
    }

    envia.addEventListener('click', () => enviaMensaje(campo.value));
    campo.addEventListener('keydown', e => { if (e.key === 'Enter') enviaMensaje(campo.value); });

    root.querySelectorAll('.ch-ficha').forEach(chip => {
      chip.addEventListener('click', () => {
        const r1 = chip.getBoundingClientRect();
        const r2 = campo.getBoundingClientRect();
        const flying = chip.cloneNode(true);
        flying.style.position = 'fixed';
        flying.style.zIndex = '9999';
        flying.style.left = r1.left + 'px';
        flying.style.top = r1.top + 'px';
        flying.style.pointerEvents = 'none';
        flying.style.transition = 'all 0.45s cubic-bezier(.34, 1.4, .64, 1)';
        document.body.appendChild(flying);

        requestAnimationFrame(() => {
          flying.style.left = r2.left + 'px';
          flying.style.top = r2.top + 'px';
          flying.style.transform = 'scale(0.8)';
          flying.style.opacity = '0';
        });

        setTimeout(() => {
          flying.remove();
          enviaMensaje(chip.textContent);
        }, 460);
      });
    });
  }

  /* ==========================================================================
     6. MOXEN-PREGUNTA: Center-to-Bottom FLIP Box & Authentic Physics Engine
     (pregunta.js)
     ========================================================================== */
  function initPregunta() {
    const raiz = document.querySelector('[data-pregunta]');
    if (!raiz) return;

    const MODELOS = [
      { id: 'rapido', nombre: 'سريع', desc: 'إجابات خاطفة للاستعلام اليومي', nivel: 1, vel: 1.55, espera: .22 },
      { id: 'equilibrado', nombre: 'متوازن', desc: 'الوسط المثالي بين السرعة والتفصيل', nivel: 2, vel: 1, espera: .55 },
      { id: 'profundo', nombre: 'عميق', desc: 'استدلال هادئ في التعارضات المعقدة', nivel: 3, vel: .72, espera: 1.15 },
    ];

    const ARCHIVOS = [
      { nombre: 'hr_contract.py', tam: '4 KB', tipo: 'codigo' },
      { nombre: 'Saudi_Labor_Law.pdf', tam: '1,2 MB', tipo: 'pdf' },
      { nombre: 'employees_master.xlsx', tam: '18 KB', tipo: 'tabla' },
      { nombre: 'company_logo.png', tam: '2,4 MB', tipo: 'imagen' },
    ];

    const SUGERENCIAS = [
      { id: 'codigo', titulo: 'فحص تعارضات عقد العمل', sub: 'المطابقة مع المادة 77 ونظام العمل', texto: 'افحص لي تعارضات مسودة عقد العمل للموظف الجديد وفق المادة 77.' },
      { id: 'resumen', titulo: 'تدقيق ملف إكسل شامل', sub: 'فحص جاهزية الحقول قبل رفع Odoo', texto: 'لخص لي حالة جاهزية أوراق إكسل الماستر قبل الاعتماد.', adjunto: 2 },
      { id: 'semana', titulo: 'توزيع خطة تسكين وظيفي', sub: 'جدول زمني لربط الأقسام والمسميات', texto: 'ساعدني في إعداد خطة تسكين وظيفي مع وكيل التوفيق «موفق».' },
    ];

    const CODIGO = 'def validate_saudi_contract(contract):\n    # فحص الحد الأدنى للأجور ونسب التأمينات GOSI\n    if contract.wage < 4000:\n        raise ValidationError("الحد الأدنى لا يتوافق مع نطاقات")\n    return contract.action_confirm()';

    const RESPUESTAS = {
      codigo: [[
        { t: 'p', s: 'تم فحص مسودة العقد بنجاح عبر وكيل التدقيق «مدقق» ووكيل الاستعلام «فاحص». هذه هي النتائج الرئيسية:' },
        { t: 'ul', items: ['الراتب الأساسي وبدل السكن يتطابقان مع الحد الأدنى في نظام التأمينات.', 'فترة التجربة محددة بـ 90 يوماً متوافقة مع المادة 53 من نظام العمل.', 'تم التحقق من سلامة دالة الاعتماد الآلية عبر Odoo RPC:'] },
        { t: 'code', lang: 'python', s: CODIGO },
      ], [
        { t: 'p', s: 'العقد سليم تماماً وجاهز للاعتماد عبر وكيل الكتابة «كاتب».' },
        { t: 'code', lang: 'python', s: '# تأكيد فوري عبر Odoo HR\nenv["hr.contract"].browse(contract_id).write({"state": "open"})' },
      ]],
      resumen: [[
        { t: 'p', s: 'ملخص فحص ملف الإكسل الماستر بواسطة الوكلاء:' },
        { t: 'ul', items: ['ورقة المنشأة: تم مطابقة السجل التجاري ورقم المنشأة.', 'ورقة الأقسام: تم تجهيز 8 أقسام رئيسية ومسمياتها الوظيفية.', 'ورقة الموظفين: 12 سجلاً ببيانات كاملة جاهزة للتنفيذ.'] },
        { t: 'p', s: 'يمكنك ضغط زر الاعتماد لنقل البيانات مباشرة إلى قاعدة بيانات Odoo.' },
      ]],
      semana: [[
        { t: 'p', s: 'خطة التسكين الوظيفي المقترحة بالتنسيق مع «موفق»:' },
        { t: 'ul', items: ['المرحلة 1: مطابقة المسميات الوظيفية مع دليل التصنيف المهني الموحد.', 'المرحلة 2: تدقيق الرواتب والبدلات ومطابقتها مع سلم الأجور.', 'المرحلة 3: الاعتماد النهائي وحفظ السجلات في Odoo.'] },
      ]],
    };

    function resalta(src) {
      const re = /(\/\/[^\n]*|#[^\n]*)|("(?:[^"\\\n]|\\.)*"?|'(?:[^'\\\n]|\\.)*'?|`(?:[^`\\]|\\.)*`?)|(\b\d+(?:\.\d+)?\b)|(\b(?:def|class|return|if|else|import|from|raise|for|while|in|True|False|None|function|const|let)\b)|(\b[A-Za-z_$][\w$]*(?=\())/g;
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

    const $ = s => raiz.querySelector(s);
    const SALTO = muelleObj(170, 19), PUNTO = muelleObj(260, 21);
    raiz.style.setProperty('--pr-muelle', muelle(210, 15));

    const caja = $('[data-caja]'), campo = $('[data-campo]'), zonaAdj = $('[data-adjuntos]'), fila = $('[data-adjuntos-fila]');
    const enviarBtn = $('[data-enviar]'), adjBtn = $('[data-adjuntar]'), modeloBtn = $('[data-modelo]'), modeloTxt = $('[data-modelo-txt]'), menu = $('[data-menu]');
    const hilo = $('[data-hilo]'), inicio = $('[data-inicio]'), sugEl = $('[data-sug]'), vivo = $('[data-vivo]');
    const avisa = s => { if (vivo) { vivo.textContent = ''; vivo.textContent = s; } };

    const relojes = new Set();
    const luego = (fn, ms) => { const id = setTimeout(() => { relojes.delete(id); fn(); }, ms); relojes.add(id); return id; };
    const cancela = id => { clearTimeout(id); relojes.delete(id); };

    let modeloIdx = 1, adjuntos = [], flujo = null, turnos = 0, variante = 0, sugActiva = null, ultima = null, recogeId = 0, abierto = false, activo = 1, pegado = true;

    menu.textContent = '';
    MODELOS.forEach((m, i) => {
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
      if (i === modeloIdx && modeloTxt.textContent === MODELOS[i].nombre) return;
      modeloIdx = i;
      ops.forEach((op, k) => op.setAttribute('aria-selected', String(k === i)));
      modeloTxt.textContent = MODELOS[i].nombre;
      if (!quieto()) {
        modeloTxt.animate([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: 380, easing: 'cubic-bezier(.22, 1, .36, 1)' });
        const pt = $('.pr-punto');
        if (pt) pt.animate([{ transform: 'scale(.4)' }, { transform: 'none' }], { duration: PUNTO.duration, easing: PUNTO.easing });
      }
      avisa('النموذج ' + MODELOS[i].nombre + '. ' + MODELOS[i].desc);
    }
    function abreMenu() {
      if (abierto) return;
      abierto = true;
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
    document.addEventListener('pointerdown', e => { if (abierto && !menu.contains(e.target) && !modeloBtn.contains(e.target)) cierraMenu(false); });

    function ajusta() { campo.style.height = 'auto'; campo.style.height = Math.min(campo.scrollHeight, 168) + 'px'; }
    function actualizaEnviar() {
      enviarBtn.disabled = !flujo && !campo.value.trim() && !adjuntos.length;
      enviarBtn.setAttribute('aria-label', flujo ? 'إيقاف الرد' : 'إرسال');
    }
    campo.addEventListener('input', () => { sugActiva = null; ajusta(); actualizaEnviar(); });
    campo.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); enviar(); }
    });
    caja.addEventListener('submit', e => { e.preventDefault(); if (flujo) detiene(); else enviar(); });

    function rellena(texto) {
      campo.value = ''; campo.focus({ preventScroll: true });
      let i = 0;
      const paso = () => {
        i = quieto() ? texto.length : Math.min(texto.length, i + 2);
        campo.value = texto.slice(0, i); ajusta(); actualizaEnviar();
        if (i < texto.length) luego(paso, 16);
      };
      paso();
    }
    sugEl.textContent = '';
    SUGERENCIAS.forEach((s, i) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pr-tarjeta'; b.dataset.sug = s.id; b.style.setProperty('--k', i);
      b.innerHTML = '<span class="pr-t-ico"><svg viewBox="0 0 24 24"><path d="M12 2.5c.6 4.6 2.9 6.9 7.5 7.5-4.6.6-6.9 2.9-7.5 7.5-.6-4.6-2.9-6.9-7.5-7.5 4.6-.6 6.9-2.9 7.5-7.5z"/></svg></span><b>' + esc(s.titulo) + '</b><small>' + esc(s.sub) + '</small>';
      b.addEventListener('click', () => {
        cierraMenu(false);
        if (s.adjunto != null && !adjuntos.length) anade(ARCHIVOS[s.adjunto]);
        rellena(s.texto); sugActiva = s.id;
      });
      sugEl.appendChild(b);
    });

    let siguiente = 0;
    function chip(a, mini) {
      const el = document.createElement('div');
      el.className = 'pr-chip';
      el.innerHTML = '<span class="pr-mini" data-tipo="' + a.tipo + '"></span><span class="pr-chip-txt"><b>' + esc(a.nombre) + '</b><small>' + esc(a.tam) + '</small></span>' + (mini ? '' : '<button type="button" aria-label="حذف">' + SVG_QUITA + '</button>');
      return el;
    }
    function anade(a) {
      if (adjuntos.length >= 3) { avisa('الحد الأقصى ثلاثة ملفات'); return; }
      const item = Object.assign({}, a), el = chip(a, false);
      item.el = el; adjuntos.push(item);
      fila.appendChild(el); zonaAdj.classList.add('is-con');
      if (!quieto()) el.animate([{ transform: 'translateY(16px) scale(.55)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: SALTO.duration, easing: SALTO.easing });
      el.querySelector('button').addEventListener('click', () => quita(item));
      actualizaEnviar();
    }
    function quita(item) {
      const i = adjuntos.indexOf(item); if (i < 0) return;
      adjuntos.splice(i, 1);
      item.el.remove();
      if (!adjuntos.length) zonaAdj.classList.remove('is-con');
      actualizaEnviar(); campo.focus({ preventScroll: true });
    }
    adjBtn.addEventListener('click', () => { anade(ARCHIVOS[siguiente % ARCHIVOS.length]); siguiente++; });

    function flip(el, antes) {
      if (quieto()) return;
      const ahora = el.getBoundingClientRect(), dx = antes.left - ahora.left, dy = antes.top - ahora.top;
      if (Math.abs(dx) < .5 && Math.abs(dy) < .5) return;
      el.animate([{ transform: 'translate(' + dx + 'px, ' + dy + 'px)' }, { transform: 'none' }], { duration: SALTO.duration, easing: SALTO.easing });
    }
    function fantasma(el) {
      const r = el.getBoundingClientRect(), g = el.cloneNode(true);
      g.classList.add('pr-fantasma'); g.style.cssText = 'position:fixed;left:' + r.left + 'px;top:' + r.top + 'px;width:' + r.width + 'px;height:' + r.height + 'px;margin:0;z-index:1;pointer-events:none;';
      raiz.appendChild(g);
      g.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(-24px) scale(.97)' }], { duration: 340, easing: 'cubic-bezier(.5, 0, .9, .5)', fill: 'forwards' }).onfinish = () => g.remove();
    }

    const turnoIA = () => {
      const t = document.createElement('article');
      t.className = 'pr-turno pr-ia';
      t.innerHTML = '<span class="pr-avatar" aria-hidden="true"><svg class="pr-sol" viewBox="0 0 24 24"><path d="M12 2.5c.6 4.6 2.9 6.9 7.5 7.5-4.6.6-6.9 2.9-7.5 7.5-.6-4.6-2.9-6.9-7.5-7.5 4.6-.6 6.9-2.9 7.5-7.5z"/></svg></span><div class="pr-cuerpo"><span class="pr-pensando" role="img" aria-label="سراج يستدل"><i></i><i></i><i></i></span></div>';
      return t;
    };

    function enviar() {
      if (flujo) return;
      const texto = campo.value.trim();
      if (!texto && !adjuntos.length) return;
      cierraMenu(false); cancela(recogeId);
      const primera = raiz.dataset.fase !== 'chat', antes = caja.getBoundingClientRect(), campoR = campo.getBoundingClientRect();
      const adj = adjuntos.map(a => ({ nombre: a.nombre, tam: a.tam, tipo: a.tipo }));
      if (primera) { fantasma(inicio); fantasma(sugEl); raiz.dataset.fase = 'chat'; }

      const yo = document.createElement('article'), burb = document.createElement('div');
      yo.className = 'pr-turno pr-yo'; burb.className = 'pr-burbuja';
      if (adj.length) {
        const cs = document.createElement('div'); cs.className = 'pr-chips-mini';
        adj.forEach(a => cs.appendChild(chip(a, true)));
        burb.appendChild(cs);
      }
      const p = document.createElement('p'); p.textContent = texto; burb.appendChild(p);
      yo.appendChild(burb); hilo.appendChild(yo);

      campo.value = ''; ajusta();
      adjuntos.forEach(a => a.el.remove()); adjuntos = []; zonaAdj.classList.remove('is-con');
      pegado = true; hilo.scrollTop = hilo.scrollHeight;
      if (primera) flip(caja, antes);

      if (!quieto()) {
        const b = burb.getBoundingClientRect();
        burb.animate([{ transform: 'translate(' + (campoR.left - b.left + 8) + 'px, ' + (campoR.top - b.top) + 'px) scale(.96)', opacity: .2 }, { transform: 'none', opacity: 1 }], { duration: SALTO.duration, easing: SALTO.easing });
      }

      ultima = { texto, adj, tema: sugActiva || (texto.includes('عقد') ? 'codigo' : texto.includes('إكسل') ? 'resumen' : 'semana') };
      sugActiva = null; turnos++;
      responde();
    }

    function responde() {
      const modelo = MODELOS[modeloIdx], t = turnoIA();
      hilo.appendChild(t);
      const cuerpo = t.querySelector('.pr-cuerpo');
      flujo = { cuerpo, t, bloques: null, i: 0, acum: 0, pausa: 0, tiempo: 0, listo: false, modelo, parado: false, cursor: null, raf: 0, previo: 0 };
      raiz.classList.add('is-flujo'); actualizaEnviar();
      if (pegado) hilo.scrollTop = hilo.scrollHeight;

      const f = flujo;
      const datos = Promise.resolve((RESPUESTAS[ultima.tema] || RESPUESTAS.codigo)[0]);
      const espera = new Promise(res => luego(res, quieto() ? 0 : modelo.espera * 1000));
      Promise.all([datos, espera]).then(([bloques]) => { if (flujo === f && !f.parado) empieza(bloques); });
    }

    function empieza(bloques) {
      const f = flujo;
      f.bloques = bloques.map(b => Object.assign({}, b)); f.cuerpo.textContent = '';
      f.cursor = document.createElement('i'); f.cursor.className = 'pr-cursor';
      f.previo = 0; f.raf = requestAnimationFrame(cuadro);
    }

    function creaBloque(b) {
      const c = flujo.cuerpo;
      if (b.t === 'p') { b.el = document.createElement('p'); b.el.className = 'pr-p'; c.appendChild(b.el); }
      else if (b.t === 'ul') { b.el = document.createElement('ul'); b.el.className = 'pr-ul'; c.appendChild(b.el); b.k = 0; b.li = null; }
      else {
        b.el = document.createElement('div'); b.el.className = 'pr-bloque';
        b.el.innerHTML = '<div class="pr-bloque-cab"><span>' + esc(b.lang || 'كود') + '</span><button type="button" class="pr-copia">' + SVG_COPIA + '</button></div><pre><code></code></pre>';
        b.cod = b.el.querySelector('code'); c.appendChild(b.el);
        const btn = b.el.querySelector('.pr-copia');
        btn.addEventListener('click', () => {
          navigator.clipboard.writeText(b.s);
          btn.classList.add('is-copiado');
          setTimeout(() => btn.classList.remove('is-copiado'), 1500);
        });
      }
      b.n = 0;
    }

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
        f.acum += dt * 230 * f.modelo.vel;
        while (f.acum >= 1 && !f.listo) { f.acum -= 1; if (!emite()) break; }
      }
      if (pegado) hilo.scrollTop = hilo.scrollHeight;
      if (f.listo) termina(false); else f.raf = requestAnimationFrame(cuadro);
    }

    function detiene() {
      if (!flujo) return;
      flujo.parado = true;
      if (flujo.raf) cancelAnimationFrame(flujo.raf);
      termina(true);
    }

    function termina(parado) {
      const f = flujo; if (!f) return;
      if (f.raf) cancelAnimationFrame(f.raf);
      if (f.cursor) f.cursor.remove();
      f.cuerpo.querySelectorAll('.pr-pensando').forEach(n => n.remove());
      if (parado) { const p = document.createElement('p'); p.className = 'pr-parada'; p.textContent = 'تم إيقاف الرد.'; f.cuerpo.appendChild(p); }
      const acc = document.createElement('div');
      acc.className = 'pr-acciones';
      acc.innerHTML = '<button type="button" class="pr-copia" data-copiar>' + SVG_COPIA + '</button><span class="pr-meta">' + esc(f.modelo.nombre) + ' · ' + (Math.max(.4, f.tiempo)).toFixed(1) + ' ث</span>';
      f.cuerpo.appendChild(acc);
      const cbtn = acc.querySelector('[data-copiar]');
      cbtn.addEventListener('click', () => {
        navigator.clipboard.writeText(f.cuerpo.textContent);
        cbtn.classList.add('is-copiado');
        setTimeout(() => cbtn.classList.remove('is-copiado'), 1500);
      });
      raiz.classList.remove('is-flujo');
      flujo = null; actualizaEnviar();
    }
  }

  /* ==========================================================================
     7. MOXEN-MIRADOR: Saved Views, Filter Chips, Cassette Rewind & Arc Flight
     (mirador.js)
     ========================================================================== */
  function initMirador() {
    const raiz = document.querySelector('[data-mirador]');
    if (!raiz) return;

    const TAREAS_HR = [
      { id: 1, nombre: 'اعتماد عقد مهندس البرمجيات الأول', resp: 'سراج', estado: 'قيد المراجعة', prio: 'عالية', dias: -2 },
      { id: 2, nombre: 'مطابقة مسمى أخصائي توظيف مع Odoo', resp: 'موفق', estado: 'معلق', prio: 'متوسطة', dias: 3 },
      { id: 3, nombre: 'فحص حساب التأمينات الاجتماعية GOSI', resp: 'مدقق', estado: 'معلق', prio: 'عالية', dias: -1 },
      { id: 4, nombre: 'قراءة سجلات المنشأة من Odoo', resp: 'فاحص', estado: 'قيد المراجعة', prio: 'عالية', dias: 1 },
      { id: 5, nombre: 'كتابة بيانات موظفي فرع الرياض', resp: 'كاتب', estado: 'معلق', prio: 'متوسطة', dias: 0 },
      { id: 6, nombre: 'مراجعة أذونات المشرفين وسجل التدقيق', resp: 'حارس', estado: 'قيد المراجعة', prio: 'متوسطة', dias: -3 },
      { id: 7, nombre: 'تصدير تقرير الرواتب الشهري PDF', resp: 'سجل', estado: 'مكتمل', prio: 'منخفضة', dias: 5 },
      { id: 8, nombre: 'معالجة تعارض بدل السكن والنقل', resp: 'مصلح', estado: 'معلق', prio: 'عالية', dias: 2 }
    ];

    const FILTROS = {
      resp: { nombre: 'الوكيل المسؤول', opciones: ['سراج', 'فاحص', 'موفق', 'مدقق', 'كاتب', 'حارس'], prueba: (t, v) => t.resp === v },
      estado: { nombre: 'الحالة', opciones: ['نشطة', 'معلق', 'قيد المراجعة', 'مكتمل'], prueba: (t, v) => v === 'نشطة' ? t.estado !== 'مكتمل' : t.estado === v },
      vence: { nombre: 'الموعد', opciones: ['متأخرة', 'اليوم', 'هذا الأسبوع'], prueba: (t, v) => v === 'متأخرة' ? t.dias < 0 && t.estado !== 'مكتمل' : v === 'اليوم' ? t.dias === 0 : t.dias >= 0 && t.dias <= 7 },
      prio: { nombre: 'الأولوية', opciones: ['عالية', 'متوسطة', 'منخفضة'], prueba: (t, v) => t.prio === v },
    };

    const VISTAS_INICIALES = [
      { id: 'todas', nombre: 'جميع الإجراءات', guardado: {}, orden: 'id', fija: true },
      { id: 'pend', nombre: 'معاملات معلقة', guardado: { estado: 'نشطة', prio: 'عالية' }, orden: 'prio', fija: true },
      { id: 'venc', nombre: 'إجراءات متأخرة', guardado: { estado: 'نشطة', vence: 'متأخرة' }, orden: 'dias', fija: true },
    ];

    const copia = o => Object.assign({}, o);
    const iguales = (a, b) => { const ka = Object.keys(a), kb = Object.keys(b); return ka.length === kb.length && ka.every(k => a[k] === b[k]); };
    const pasa = (t, f) => Object.keys(f).every(k => FILTROS[k].prueba(t, f[k]));
    const filtradas = (v, f) => TAREAS_HR.filter(t => pasa(t, f || v.actual));
    const modificada = v => !iguales(v.actual, v.guardado);

    const $ = s => raiz.querySelector(s);
    const el = {
      ventana: $('[data-ventana]'), tabs: $('[data-tabs]'), indicador: $('[data-indicador]'), chips: $('[data-chips]'), mas: $('[data-mas]'),
      acciones: $('[data-acciones]'), descartar: $('[data-descartar]'), nueva: $('[data-nueva]'), guardar: $('[data-guardar]'),
      cinta: $('[data-cinta]'), cintaMarcas: $('[data-cinta-marcas]'), cintaCabeza: $('[data-cinta-cabeza]'), pasos: $('[data-pasos]'),
      cuerpo: $('[data-cuerpo]'), vacio: $('[data-vacio]'), resumen: $('[data-resumen]'), pieVista: $('[data-pie-vista]'), menu: $('[data-menu]'),
      reset: $('[data-restablece]'), vivo: $('[data-vivo]'),
    };

    const EASE = muelle(260, 21);
    let seq = 0;
    const nuevaVista = d => Object.assign({}, d, { actual: copia(d.guardado), hist: [copia(d.guardado)] });
    let vistas = VISTAS_INICIALES.map(nuevaVista);
    let activa = vistas[1].id;
    const porId = id => vistas.find(v => v.id === id);
    const vistaActiva = () => porId(activa);

    const filas = new Map();
    TAREAS_HR.forEach(t => {
      const f = document.createElement('div');
      f.className = 'mi-fila' + (t.estado === 'مكتمل' ? ' es-hecha' : '');
      f.setAttribute('role', 'row'); f.dataset.id = t.id;
      f.innerHTML = '<div class="mi-f-tarea" role="cell"><span class="mi-f-nom">' + esc(t.nombre) + '</span></div>'
        + '<div class="mi-f-resp" role="cell"><span>' + esc(t.resp) + '</span></div>'
        + '<div role="cell"><span class="mi-estado e-' + (t.estado === 'مكتمل' ? 'hecha' : t.estado === 'قيد المراجعة' ? 'curso' : 'pendiente') + '">' + esc(t.estado) + '</span></div>'
        + '<div class="mi-f-prio" role="cell"><span class="mi-prio-t">' + esc(t.prio) + '</span></div>'
        + '<div class="mi-f-vence' + (t.dias < 0 && t.estado !== 'مكتمل' ? ' es-tarde' : '') + '" role="cell">' + (t.dias < 0 ? 'متأخر ' + (-t.dias) + ' يوم' : t.dias === 0 ? 'اليوم' : 'بعد ' + t.dias + ' أيام') + '</div>';
      f.dataset.vis = '0'; f.style.display = 'none';
      el.cuerpo.appendChild(f);
      filas.set(t.id, f);
    });

    function pintaFilas(animar) {
      const v = vistaActiva(), lista = filtradas(v), ids = lista.map(t => t.id);
      const antes = new Map();
      filas.forEach((f, id) => { if (f.dataset.vis === '1') antes.set(id, f.getBoundingClientRect().top); });

      filas.forEach((f, id) => { if (!ids.includes(id)) { f.style.display = 'none'; f.dataset.vis = '0'; } });
      lista.forEach(t => { const f = filas.get(t.id); f.style.display = ''; f.dataset.vis = '1'; el.cuerpo.appendChild(f); });

      if (animar && !quieto()) {
        lista.forEach(t => {
          const f = filas.get(t.id), a = antes.get(t.id);
          if (a != null) {
            const dy = a - f.getBoundingClientRect().top;
            if (Math.abs(dy) > .5) f.animate([{ transform: 'translateY(' + dy + 'px)' }, { transform: 'none' }], { duration: 680, easing: EASE });
          }
        });
      }
      el.vacio.hidden = lista.length > 0;
      el.resumen.innerHTML = '<b>' + lista.length + '</b> من ' + TAREAS_HR.length + ' إجراء';
    }

    const tabEls = new Map();
    function pintaTabs() {
      vistas.forEach(v => {
        let e = tabEls.get(v.id);
        if (!e) {
          e = document.createElement('div');
          e.className = 'mi-tab' + (v.fija ? '' : ' es-propia');
          e.setAttribute('role', 'tab'); e.dataset.id = v.id;
          e.innerHTML = '<span class="mi-tab-n">' + esc(v.nombre) + '</span><i class="mi-punto"></i><span class="mi-cuenta">0</span>';
          e.addEventListener('click', () => ponActiva(v.id));
          tabEls.set(v.id, e);
          el.tabs.appendChild(e);
        }
        const sel = v.id === activa, mod = modificada(v);
        e.setAttribute('aria-selected', String(sel));
        e.classList.toggle('es-modificada', mod);
        e.querySelector('.mi-cuenta').textContent = filtradas(v).length;
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

    function ponActiva(id) {
      if (id === activa || !porId(id)) return;
      activa = id;
      refresca(true);
    }

    const chipEls = new Map();
    function pintaChips() {
      const v = vistaActiva();
      chipEls.forEach((e, k) => { if (!(k in v.actual)) { e.remove(); chipEls.delete(k); } });
      Object.keys(FILTROS).forEach(k => {
        if (!(k in v.actual)) return;
        let e = chipEls.get(k);
        if (!e) {
          e = document.createElement('span');
          e.className = 'mi-chip'; e.dataset.f = k;
          e.innerHTML = '<button class="mi-chip-b" type="button"><span class="mi-ch-et">' + FILTROS[k].nombre + ':</span> <span class="mi-ch-val">' + v.actual[k] + '</span></button><button class="mi-ch-x" type="button">×</button>';
          e.querySelector('.mi-chip-b').addEventListener('click', () => {
            const ops = FILTROS[k].opciones;
            const curIdx = ops.indexOf(v.actual[k]);
            const nextVal = ops[(curIdx + 1) % ops.length];
            v.actual[k] = nextVal;
            v.hist.push(copia(v.actual));
            refresca(true);
          });
          e.querySelector('.mi-ch-x').addEventListener('click', () => {
            delete v.actual[k];
            v.hist.push(copia(v.actual));
            refresca(true);
          });
          el.chips.insertBefore(e, el.mas);
          chipEls.set(k, e);
        }
        e.querySelector('.mi-ch-val').textContent = v.actual[k];
        e.classList.toggle('es-cambiado', v.guardado[k] !== v.actual[k]);
      });
    }

    el.mas.addEventListener('click', () => {
      const v = vistaActiva();
      const libres = Object.keys(FILTROS).filter(k => !(k in v.actual));
      if (!libres.length) return;
      const k = libres[0];
      v.actual[k] = FILTROS[k].opciones[0];
      v.hist.push(copia(v.actual));
      refresca(true);
    });

    let rebobinando = false;
    function pintaAcciones() {
      const mod = modificada(vistaActiva()) && !rebobinando;
      el.acciones.classList.toggle('es-visible', mod);
    }

    function guarda() {
      const v = vistaActiva();
      if (!modificada(v) || rebobinando) return;
      v.guardado = copia(v.actual); v.hist = [copia(v.actual)];
      refresca(true);
      const e = tabEls.get(v.id);
      e.classList.remove('es-guardada'); void e.offsetWidth; e.classList.add('es-guardada');
    }

    function descarta() {
      const v = vistaActiva();
      if (!modificada(v) || rebobinando) return;
      const pasos = v.hist.length - 1;
      if (pasos < 1) { v.actual = copia(v.guardado); v.hist = [copia(v.guardado)]; refresca(true); return; }

      rebobinando = true;
      el.acciones.classList.remove('es-visible'); el.acciones.classList.add('es-rebobina');
      el.pasos.textContent = pasos;
      el.cintaCabeza.style.setProperty('--p', 1);

      let i = v.hist.length - 1;
      const paso = () => {
        i--;
        v.actual = copia(v.hist[i]);
        el.cintaCabeza.style.setProperty('--p', i / pasos);
        el.pasos.textContent = i;
        refresca(true);
        if (i > 0) setTimeout(paso, 400);
        else setTimeout(() => {
          v.hist = [copia(v.guardado)];
          rebobinando = false;
          el.acciones.classList.remove('es-rebobina');
          pintaAcciones();
        }, 350);
      };
      setTimeout(paso, 130);
    }

    function guardaNueva() {
      const v = vistaActiva();
      if (!modificada(v) || rebobinando) return;
      const desde = el.nueva.getBoundingClientRect();
      const nv = nuevaVista({ id: 'v' + (++seq), nombre: v.nombre + ' ' + (seq + 1), guardado: copia(v.actual), orden: 'id', fija: false });
      v.actual = copia(v.guardado); v.hist = [copia(v.guardado)];
      vistas.push(nv);
      activa = nv.id;
      el.acciones.classList.remove('es-visible');
      refresca(false);

      const tab = tabEls.get(nv.id);
      const fin = tab.getBoundingClientRect();
      const f = document.createElement('div');
      f.className = 'mi-vuelo';
      f.innerHTML = '<span>' + esc(nv.nombre) + '</span><span class="mi-cuenta">' + filtradas(nv).length + '</span>';
      raiz.appendChild(f);

      const w = f.offsetWidth, h = f.offsetHeight;
      const sx = desde.left + desde.width / 2 - w / 2, sy = desde.top + desde.height / 2 - h / 2;
      const ex = fin.left + fin.width / 2 - w / 2, ey = fin.top + fin.height / 2 - h / 2;
      const kf = [];
      for (let k = 0; k <= 16; k++) {
        const t = k / 16, e = 1 - Math.pow(1 - t, 3);
        kf.push({ transform: 'translate(' + (sx + (ex - sx) * e).toFixed(1) + 'px,' + (sy + (ey - sy) * e - 96 * Math.sin(Math.PI * e)).toFixed(1) + 'px) scale(' + (.82 + .26 * Math.sin(Math.PI * t) + .18 * t).toFixed(3) + ') rotate(' + (-9 * Math.sin(Math.PI * t)).toFixed(2) + 'deg)', opacity: k === 0 ? 0.4 : 1 });
      }
      f.animate(kf, { duration: 750, easing: 'linear', fill: 'forwards' }).onfinish = () => {
        f.remove();
        tab.classList.add('es-aterriza');
      };
    }

    el.guardar.addEventListener('click', guarda);
    el.descartar.addEventListener('click', descarta);
    el.nueva.addEventListener('click', guardaNueva);
    el.reset.addEventListener('click', () => {
      vistas = VISTAS_INICIALES.map(nuevaVista);
      activa = vistas[1].id;
      refresca(true);
    });

    function refresca(animar) {
      pintaTabs();
      pintaChips();
      pintaFilas(animar);
      pintaAcciones();
    }

    refresca(false);
  }

  /* ==========================================================================
     8. MOXEN-VENIA: Permission Ring, Lock Drop & Guided Recovery
     (حزمة معتمدة لا تتغير)
     ========================================================================== */
  function initVenia() {
    const root = document.querySelector('[data-venia]');
    if (!root) return;

    root.querySelectorAll('.ve-tarjeta').forEach(tarjeta => {
      const btn = tarjeta.querySelector('.ve-boton');
      btn.addEventListener('click', () => {
        tarjeta.setAttribute('data-estado', 'pidiendo');
        setTimeout(() => {
          tarjeta.setAttribute('data-estado', 'concedido');
          btn.textContent = 'تم منح التفويض ✓';
          btn.style.background = '#10b981';
        }, 1200);
      });
    });
  }

  /* ==========================================================================
     9. MOXEN-GALLETA: Continuous Euler Springs Physics Engine & Clip-Path Morph
     (galleta.js)
     ========================================================================== */
  function initGalleta() {
    const raiz = document.querySelector('[data-galleta]');
    if (!raiz) return;

    const resorte = (x, k, c) => ({ x, v: 0, meta: x, k, c });
    function avanza(r, dt) { r.v += (r.k * (r.meta - r.x) - r.c * r.v) * dt; r.x += r.v * dt; }
    const parado = (r, e) => Math.abs(r.meta - r.x) < e && Math.abs(r.v) < e;
    const lerp = (a, b, t) => a + (b - a) * t;
    const sujeta = (v, a, b) => Math.max(a, Math.min(b, v));
    const suma = a => a.reduce((s, v) => s + v, 0);

    const CATEGORIAS_HR = [
      { id: 'necesarias', nombre: 'الصلاحيات الأساسية للربط', texto: 'جلسة الربط مع Odoo، حماية الـ Token وسجل التدقيق الإلزامي.', fija: true },
      { id: 'preferencias', nombre: 'تفضيلات واجهة الوكلاء', texto: 'حفظ ترتيب الجداول، التبويبات النشطة وخيارات المحادثة المفضلة.' },
      { id: 'estadistica', nombre: 'تحليلات الأداء ودقة الوكلاء', texto: 'قياس سرعة استجابة سراج وعدد المعاملات المنجزة بدون كشف بيانات شخصية.' },
      { id: 'notificaciones', nombre: 'الإشعارات الفورية الحية', texto: 'تنبيه المشغّل بالبريد أو شارة النظام فور جهوزية ملف إكسل للاعتماد.' },
    ];

    const MASA = 'M29.48 16C29.59 17.45 28.87 19.08 28.27 20.47C27.67 21.85 26.88 23.22 25.88 24.29C24.89 25.36 23.54 26.03 22.29 26.89C21.04 27.75 19.79 29.15 18.37 29.44C16.95 29.72 15.24 28.99 13.78 28.6C12.31 28.22 10.86 27.83 9.59 27.1C8.32 26.38 7.21 25.34 6.15 24.27C5.08 23.19 3.64 22.04 3.2 20.66C2.75 19.28 3.37 17.51 3.48 16C3.59 14.49 3.42 12.98 3.84 11.57C4.25 10.17 5.06 8.78 5.97 7.58C6.87 6.38 7.97 5 9.29 4.38C10.6 3.75 12.35 4.06 13.85 3.83C15.36 3.6 16.84 2.87 18.29 3C19.75 3.13 21.29 3.83 22.59 4.59C23.88 5.35 25.22 6.36 26.06 7.56C26.9 8.75 27.06 10.36 27.63 11.77C28.2 13.17 29.37 14.55 29.48 16Z';
    const CHISPAS = [[10.6, 11, 2], [19.8, 9.8, 1.5], [15.2, 16.4, 1.8], [21.6, 18.6, 1.6], [10.4, 20.4, 1.4], [16.4, 23.6, 1.2]];
    const MORDISCOS = [-.7, .42, 2.7];
    const P = n => n.toFixed(2);

    function galletaSvg(id, conMordiscos) {
      const chispas = CHISPAS.map(c => '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="' + c[2] + '"/>').join('');
      const bocas = conMordiscos ? MORDISCOS.map((a, i) => {
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

    const uid = 'gt' + Math.floor(Math.random() * 1000);
    const aviso = raiz.querySelector('.gt-aviso');
    const cabeza = raiz.querySelector('.gt-cabeza');
    const detalle = raiz.querySelector('.gt-detalle');
    const pie = raiz.querySelector('.gt-pie');
    const filaS = pie.querySelector('[data-vista="simple"]');
    const filaD = pie.querySelector('[data-vista="detalle"]');
    const personaliza = raiz.querySelector('[data-galleta-accion="personaliza"]');
    const icono = raiz.querySelector('.gt-icono');
    if (icono) icono.innerHTML = galletaSvg(uid + 'i', false);

    detalle.textContent = '';
    const cats = CATEGORIAS_HR.map((c, i) => {
      const caja = document.createElement('div');
      caja.className = 'gt-cat';
      caja.innerHTML =
        '<div class="gt-cat-fila">' +
          '<button class="gt-cat-nombre" type="button" aria-expanded="false">' +
            '<svg class="gt-chev" viewBox="0 0 24 24"><path d="m9.5 6 6 6-6 6"/></svg>' +
            '<span>' + esc(c.nombre) + '</span>' + (c.fija ? '<small>نشطة دائماً</small>' : '') +
          '</button>' +
          '<button class="gt-interruptor" type="button" role="switch" aria-checked="' + (c.fija ? 'true' : 'false') + '"' + (c.fija ? ' aria-disabled="true"' : '') + '>' +
            '<span class="gt-riel"><span class="gt-perilla"></span></span>' +
          '</button>' +
        '</div>' +
        '<p class="gt-desc" aria-hidden="true">' + esc(c.texto) + '</p>';
      detalle.appendChild(caja);
      return {
        id: c.id, fija: !!c.fija, caja, activa: !!c.fija,
        boton: caja.querySelector('.gt-cat-nombre'), interruptor: caja.querySelector('.gt-interruptor'),
        desc: caja.querySelector('.gt-desc'), h: resorte(0, 220, 26), abierta: false,
      };
    });

    const sup = document.createElement('div');
    sup.className = 'gt-superficie';
    sup.innerHTML = '<i></i>';
    raiz.insertBefore(sup, aviso);
    const supI = sup.firstChild;

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'gt-boton';
    boton.setAttribute('aria-label', 'ميثاق الخصوصية وتفويض الوكلاء');
    boton.innerHTML = '<span class="gt-giro">' + galletaSvg(uid + 'b', true) + '</span>' +
      '<span class="gt-migas" aria-hidden="true"></span>' +
      '<span class="gt-ok" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4.4 8.3l2.4 2.4 4.8-5" pathLength="1"/></svg></span>';
    raiz.appendChild(boton);

    const mordidas = Array.from(boton.querySelectorAll('.gt-mordida'));
    const migas = boton.querySelector('.gt-migas');

    const M = {};
    function mide() {
      const r = aviso.getBoundingClientRect(), b = boton.getBoundingClientRect(), cp = getComputedStyle(pie);
      const relleno = parseFloat(cp.paddingTop) + parseFloat(cp.paddingBottom);
      Object.assign(M, {
        x: r.left, y: r.top, w: r.width, h: r.height,
        vw: document.documentElement.clientWidth, vh: innerHeight,
        det: detalle.offsetHeight, desc: cats.map(c => c.desc.offsetHeight),
        pie: pie.offsetHeight, pieS: filaS.offsetHeight + relleno, pieD: filaD.offsetHeight + relleno,
        bx: b.left, by: b.top, bw: b.width, radio: 22,
      });
      M.filas = M.det - suma(M.desc);
      d.meta = modo === 'detalle' ? M.filas : 0;
      p.meta = modo === 'detalle' ? M.pieD : M.pieS;
      cats.forEach((c, i) => { c.h.meta = c.abierta ? M.desc[i] : 0; });
      [d, p].concat(cats.map(c => c.h)).forEach(s => { s.x = s.meta; s.v = 0; });
    }

    const d = resorte(0, 170, 21), p = resorte(0, 170, 21);
    const ms = resorte(0, 150, 23), mp = resorte(0, 90, 15);
    let modo = 'simple', llego = true, relojes = [];

    function pinta() {
      const V = d.x + suma(cats.map(c => c.h.x));
      const sobra = (M.det - V) + (M.pie - p.x);
      const tx = M.x, ty = M.y + sobra, tw = M.w, th = M.h - sobra;
      const s = ms.x, q = mp.x;
      const w = lerp(tw, M.bw, s), h = lerp(th, M.bw, s);
      const x = lerp(tx + tw / 2, M.bx + M.bw / 2, q) - w / 2, y = lerp(ty + th / 2, M.by + M.bw / 2, q) - h / 2;
      const r = Math.min(lerp(M.radio, Math.min(w, h) / 2, Math.pow(s, 1.4)), w / 2, h / 2);

      supI.style.clipPath = 'inset(' + P(y) + 'px ' + P(M.vw - x - w) + 'px ' + P(M.vh - y - h) + 'px ' + P(x) + 'px round ' + P(r) + 'px)';
      aviso.style.clipPath = 'inset(' + P(Math.max(0, y - M.y)) + 'px ' + P(Math.max(0, M.x + M.w - x - w)) + 'px ' +
        P(Math.max(0, M.y + M.h - y - h)) + 'px ' + P(Math.max(0, x - M.x)) + 'px round ' + P(r) + 'px)';

      const op = modo === 'galleta' ? 1.3 - s * 2.6 : (.16 - Math.max(s, q)) / .12;
      aviso.style.opacity = sujeta(op, 0, 1).toFixed(3);

      cabeza.style.transform = 'translate3d(0,' + P(sobra) + 'px,0)';
      detalle.style.transform = 'translate3d(0,' + P(sobra) + 'px,0)';
      detalle.style.clipPath = 'inset(0 0 ' + P(Math.max(0, M.det - V)) + 'px 0)';
    }

    let raf = 0, previo = 0;
    function anda() { if (!raf) { previo = 0; raf = requestAnimationFrame(cuadro); } }
    function cuadro(t) {
      const dt = previo ? Math.min(1 / 30, (t - previo) / 1000) : 0;
      previo = t;
      const todos = [d, p, ms, mp].concat(cats.map(c => c.h));
      let isQuieto = true;
      todos.forEach(s => {
        if (quieto()) { s.x = s.meta; s.v = 0; return; }
        avanza(s, dt);
        if (parado(s, s === ms || s === mp ? .002 : .3)) { s.x = s.meta; s.v = 0; } else isQuieto = false;
      });
      if (modo === 'galleta' && !llego && ms.x > .93 && mp.x > .9) llega();
      pinta();
      raf = isQuieto ? 0 : requestAnimationFrame(cuadro);
    }

    function despliega(abre) {
      if (modo === 'galleta' || (modo === 'detalle') === abre) return;
      modo = abre ? 'detalle' : 'simple';
      d.meta = abre ? M.filas : 0;
      p.meta = abre ? M.pieD : M.pieS;
      raiz.classList.toggle('is-detalle', abre);
      personaliza.setAttribute('aria-expanded', String(abre));
      anda();
    }

    function descripcion(c, abre) {
      c.abierta = abre;
      c.h.meta = abre ? M.desc[cats.indexOf(c)] : 0;
      c.boton.setAttribute('aria-expanded', String(abre));
      c.caja.classList.toggle('is-abierta', abre);
      anda();
    }

    function pon(c, si) {
      if (c.fija || c.activa === si) return;
      c.activa = si;
      c.interruptor.setAttribute('aria-checked', String(si));
    }

    function guarda(como) {
      if (modo === 'galleta') return;
      const opcionales = cats.filter(c => !c.fija);
      if (como === 'acepta') opcionales.forEach(c => pon(c, true));
      else if (como === 'rechaza') opcionales.forEach(c => pon(c, false));
      encoge();
    }

    function encoge() {
      modo = 'galleta';
      raiz.classList.add('is-galleta');
      llego = false;
      mordidas.forEach(m => m.classList.remove('is-mordida'));
      boton.classList.remove('is-llega', 'is-ok');
      ms.meta = mp.meta = 1;
      anda();
    }

    function llega() {
      llego = true;
      const rechazos = cats.filter(c => !c.fija && !c.activa).length;
      boton.classList.add('is-llega');
      suelta(-Math.PI / 2, 5, 1.6);
      setTimeout(() => boton.classList.add('is-ok'), 140);
      mordidas.slice(0, rechazos).forEach((m, i) => setTimeout(() => {
        m.classList.add('is-mordida');
        suelta(MORDISCOS[i], 7, 1);
      }, 380 + i * 260));
      setTimeout(() => boton.classList.remove('is-ok'), 1250);
    }

    function suelta(angulo, n, fuerza) {
      const c = M.bw / 2;
      for (let i = 0; i < n; i++) {
        const a = angulo + (Math.random() - .5) * 1.5;
        const x0 = c + Math.cos(angulo) * 12.5, y0 = c + Math.sin(angulo) * 12.5;
        const v = (70 + Math.random() * 90) * fuerza, vx = Math.cos(a) * v, vy = Math.sin(a) * v - 90;
        const miga = document.createElement('i');
        miga.style.width = miga.style.height = '3px';
        miga.style.left = x0 + 'px'; miga.style.top = y0 + 'px';
        migas.appendChild(miga);
        miga.animate([
          { transform: 'none', opacity: 1 },
          { transform: 'translate(' + vx * 0.6 + 'px,' + (vy * 0.6 + 200) + 'px)', opacity: 0 }
        ], { duration: 600, easing: 'linear' }).onfinish = () => miga.remove();
      }
    }

    function abre() {
      if (modo !== 'galleta') return;
      modo = 'simple';
      raiz.classList.remove('is-galleta', 'is-detalle');
      boton.classList.remove('is-llega', 'is-ok');
      cats.forEach(c => descripcion(c, false));
      [d, ...cats.map(c => c.h)].forEach(s => { s.x = s.meta = 0; s.v = 0; });
      p.x = p.meta = M.pieS; p.v = 0;
      ms.meta = mp.meta = 0;
      anda();
    }

    raiz.addEventListener('click', e => {
      const accion = e.target.closest('[data-galleta-accion]');
      if (accion) {
        const a = accion.dataset.galletaAccion;
        if (a === 'personaliza') despliega(true);
        else guarda(a);
        return;
      }
      const cat = cats.find(c => c.boton.contains(e.target) || c.interruptor.contains(e.target));
      if (!cat) return;
      if (cat.boton.contains(e.target)) descripcion(cat, !cat.abierta);
      else if (!cat.fija) pon(cat, !cat.activa);
    });

    boton.addEventListener('click', abre);

    setTimeout(() => {
      mide();
      pinta();
    }, 50);
  }

  /* ==========================================================================
     10. MOTION-LAYER: High Performance Modals, Focus Traps & Form Micro-Physics
     (motion.js)
     ========================================================================== */
  function initMotionLayer() {
    // 1. Modals with inert and focus trap
    const openBtns = document.querySelectorAll('[data-modal-target]');
    const closeBtns = document.querySelectorAll('[data-modal-close]');
    const overlays = document.querySelectorAll('.modal-overlay');
    let activeModal = null;
    let triggerElement = null;

    overlays.forEach(overlay => overlay.setAttribute('inert', ''));

    function openModal(modalId, triggerBtn) {
      const modal = document.getElementById(modalId);
      if (!modal) return;
      triggerElement = triggerBtn || document.activeElement;
      activeModal = modal;
      modal.classList.add('is-active');
      modal.removeAttribute('inert');
      document.body.style.overflow = 'hidden';
      setTimeout(() => {
        const focusTarget = modal.querySelector('button, input, select, textarea, [tabindex="0"]');
        if (focusTarget) focusTarget.focus();
      }, 50);
    }

    function closeModal() {
      if (!activeModal) return;
      activeModal.classList.remove('is-active');
      activeModal.setAttribute('inert', '');
      document.body.style.overflow = '';
      if (triggerElement && typeof triggerElement.focus === 'function') triggerElement.focus();
      activeModal = null;
    }

    openBtns.forEach(btn => btn.addEventListener('click', () => openModal(btn.getAttribute('data-modal-target'), btn)));
    closeBtns.forEach(btn => btn.addEventListener('click', closeModal));
    overlays.forEach(overlay => overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); }));

    window.addEventListener('keydown', e => {
      if (activeModal && e.key === 'Escape') closeModal();
    });

    // 2. Form interactions with shake and spinner button
    const demoForm = document.getElementById('demo-motion-form');
    if (demoForm) {
      const emailInput = document.getElementById('demo-email');
      const emailField = emailInput ? emailInput.closest('.motion-field') : null;
      const submitBtn = demoForm.querySelector('button[type="submit"]');
      const resultNotice = document.getElementById('form-result-notice');

      demoForm.addEventListener('submit', e => {
        e.preventDefault();
        const val = emailInput ? emailInput.value.trim() : '';

        if (!val || !val.includes('@')) {
          if (emailField) {
            emailField.classList.add('has-error');
            emailField.classList.remove('is-shaking');
            void emailField.offsetWidth;
            emailField.classList.add('is-shaking');
            setTimeout(() => emailField.classList.remove('is-shaking'), 460);
          }
          return;
        }

        if (emailField) emailField.classList.remove('has-error', 'is-shaking');

        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="motion-spinner" aria-hidden="true"></span><span>جاري التحقق عبر Odoo...</span>';

        setTimeout(() => {
          submitBtn.innerHTML = '<svg style="width:20px;height:20px;stroke:#fff;fill:none;" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg><span>تم الاعتماد بنجاح!</span>';
          submitBtn.style.backgroundColor = '#10b981';
          if (resultNotice) resultNotice.style.display = 'flex';

          setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
            submitBtn.style.backgroundColor = '';
            demoForm.reset();
            if (resultNotice) resultNotice.style.display = 'none';
          }, 2400);
        }, 1100);
      });
    }

    // 3. Skeleton shimmer toggle
    const toggleSkelBtn = document.getElementById('toggle-skeleton-btn');
    const skelContainer = document.getElementById('skeleton-container');
    if (toggleSkelBtn && skelContainer) {
      toggleSkelBtn.addEventListener('click', () => {
        skelContainer.style.opacity = skelContainer.style.opacity === '0.3' ? '1' : '0.3';
      });
    }

    // 4. Reduced motion sandbox toggle
    const toggleReducedBtn = document.getElementById('toggle-reduced-motion-btn');
    if (toggleReducedBtn) {
      toggleReducedBtn.addEventListener('click', () => {
        const isReduced = document.documentElement.classList.toggle('force-reduced-motion');
        toggleReducedBtn.setAttribute('aria-pressed', String(isReduced));
        toggleReducedBtn.textContent = isReduced ? 'الحركة: معطّلة (Reduced)' : 'الحركة: مفعّلة (Active)';
      });
    }
  }

  /* ==========================================================================
     Showcase Navigation Controller & Reading Progress
     ========================================================================== */
  function initShowroomNav() {
    const tabs = document.querySelectorAll('.mx-tab-btn');
    const sections = document.querySelectorAll('.mx-stage-section');

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('is-active'));
        tab.classList.add('is-active');
        const targetId = tab.dataset.target;
        if (targetId === 'all') {
          sections.forEach(s => s.style.display = 'block');
        } else {
          sections.forEach(s => {
            s.style.display = s.id === targetId ? 'block' : 'none';
          });
          const targetEl = document.getElementById(targetId);
          if (targetEl) targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });

    const bar = document.querySelector('.mx-reading-progress');
    window.addEventListener('scroll', () => {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      if (total > 0 && bar) {
        bar.style.transform = `scaleX(${Math.min(1, Math.max(0, window.scrollY / total))})`;
      }
    }, { passive: true });
  }

  // Initialize all 10 authentic modules upon DOM readiness
  document.addEventListener('DOMContentLoaded', () => {
    initShowroomNav();
    initCavila();
    initFaena();
    initDespliegue();
    initPilar();
    initCharla();
    initPregunta();
    initMirador();
    initVenia();
    initGalleta();
    initMotionLayer();
  });

})();
