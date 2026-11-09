/**
 * ============================================================================
 * MOTION INTERACTION ENGINE (motion.js)
 * محرك التفاعل والحركة فائق الأداء — بدون مكتبات خارجية (Pure Vanilla JS)
 * Passive Listeners • RAF Optimized • IntersectionObserver
 * ============================================================================
 */

(function () {
  'use strict';

  // التحقق من تفضيل تقليل الحركة لدى المستخدم
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /**
   * 1) محرك الظهور عند التمرير (Scroll Reveal with Stagger)
   * يعتمد بالكامل على IntersectionObserver لتفادي مراقبة scroll المكلفة
   */
  function initScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal-item, .reveal-fade, .reveal-slide-start');
    if (!revealElements.length) return;

    // إذا كان المستخدم يفضل تقليل الحركة، نظهر المحتوى فوراً
    if (prefersReducedMotion) {
      revealElements.forEach(el => el.classList.add('is-visible'));
      return;
    }

    // إعداد التتابع (Stagger) التلقائي للعناصر الشقيقة داخل الحاويات
    const staggerContainers = document.querySelectorAll('[data-stagger]');
    staggerContainers.forEach(container => {
      const items = container.querySelectorAll('.reveal-item');
      items.forEach((item, index) => {
        const delay = index * 80; // 80ms بين كل عنصر وآخر
        item.style.setProperty('--reveal-delay', `${delay}ms`);
      });
    });

    const observerOptions = {
      root: null,
      rootMargin: '0px 0px -40px 0px', // يظهر العنصر قبل دخوله التام بـ 40px
      threshold: 0.12
    };

    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          // ظهور لمرة واحدة فقط كما هو مطلوب لتوفير موارد المتصفح
          observer.unobserve(entry.target);
        }
      });
    }, observerOptions);

    revealElements.forEach(el => revealObserver.observe(el));
  }

  /**
   * 2) الهيدر الذكي، شريط القراءة، وزر العودة للأعلى
   * محسّن بواسطة requestAnimationFrame وقراءة واحدة فقط للـ DOM
   */
  function initScrollEngine() {
    const header = document.querySelector('.site-header');
    const progressBar = document.querySelector('.reading-progress-bar');
    const scrollTopBtn = document.querySelector('.scroll-top-btn');

    let ticking = false;

    function onScrollUpdate() {
      const scrollY = window.scrollY || window.pageYOffset;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;

      // أ) تحديث شريط تقدم القراءة عبر scaleX (بدون إحداث layout shift)
      if (progressBar && docHeight > 0) {
        const progress = Math.min(Math.max(scrollY / docHeight, 0), 1);
        progressBar.style.transform = `scaleX(${progress})`;
      }

      // ب) تحديث حالة الهيدر عند التمرير
      if (header) {
        if (scrollY > 30) {
          header.classList.add('is-scrolled');
        } else {
          header.classList.remove('is-scrolled');
        }
      }

      // ج) إظهار أو إخفاء زر العودة للأعلى
      if (scrollTopBtn) {
        if (scrollY > 280) {
          scrollTopBtn.classList.add('is-visible');
        } else {
          scrollTopBtn.classList.remove('is-visible');
        }
      }

      ticking = false;
    }

    // تشغيل التحديث مرة واحدة عند التحميل لمزامنة شريط التقدم وحالة الهيدر
    onScrollUpdate();

    // مستمع تمرير سلبي (Passive listener) لا يعيق تمرير الصفحة
    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(onScrollUpdate);
        ticking = true;
      }
    }, { passive: true });

    // تفعيل زر العودة للأعلى بسلاسة
    if (scrollTopBtn) {
      scrollTopBtn.addEventListener('click', () => {
        window.scrollTo({
          top: 0,
          behavior: prefersReducedMotion ? 'auto' : 'smooth'
        });
      });
    }
  }

  /**
   * 3) القائمة المتنقلة وأيقونة الهامبرغر المتحولة
   */
  function initMobileMenu() {
    const toggleBtn = document.querySelector('.hamburger-toggle');
    const drawer = document.querySelector('.mobile-drawer');
    const backdrop = document.querySelector('.drawer-backdrop');
    const drawerLinks = document.querySelectorAll('.mobile-drawer a');

    if (!toggleBtn || !drawer || !backdrop) return;

    // جعل الدرج غير قابل للتركيز في البداية وهو مغلق لمنع وصول Tab إليه
    drawer.setAttribute('inert', '');

    function openMenu() {
      toggleBtn.classList.add('is-active');
      toggleBtn.setAttribute('aria-expanded', 'true');
      drawer.classList.add('is-open');
      backdrop.classList.add('is-open');
      drawer.removeAttribute('inert');
      document.body.style.overflow = 'hidden'; // منع التمرير الخلفي أثناء فتح القائمة

      // نقل التركيز لأول رابط عند الفتح بعد استقرار العرض
      setTimeout(() => {
        const firstLink = drawer.querySelector('a, button');
        if (firstLink) firstLink.focus();
      }, 50);
    }

    function closeMenu() {
      toggleBtn.classList.remove('is-active');
      toggleBtn.setAttribute('aria-expanded', 'false');
      drawer.classList.remove('is-open');
      backdrop.classList.remove('is-open');
      drawer.setAttribute('inert', '');
      document.body.style.overflow = '';

      // إعادة التركيز لزر الهامبرغر عند إغلاق الدرج
      if (toggleBtn && typeof toggleBtn.focus === 'function') {
        toggleBtn.focus();
      }
    }

    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = drawer.classList.contains('is-open');
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    backdrop.addEventListener('click', closeMenu);

    drawerLinks.forEach(link => {
      link.addEventListener('click', closeMenu);
    });

    // إغلاق بمفتاح الهروب Escape وحصر Tab داخل الدرج (Focus trap)
    window.addEventListener('keydown', (e) => {
      if (!drawer.classList.contains('is-open')) return;

      if (e.key === 'Escape') {
        closeMenu();
        return;
      }

      if (e.key === 'Tab') {
        const focusables = drawer.querySelectorAll('a, button, [tabindex="0"]');
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });
  }

  /**
   * 4) النوافذ المنبثقة (Modal Dialogs)
   */
  function initModal() {
    const openBtns = document.querySelectorAll('[data-modal-target]');
    const closeBtns = document.querySelectorAll('[data-modal-close]');
    const overlays = document.querySelectorAll('.modal-overlay');
    let activeModal = null;
    let triggerElement = null;

    // جعل النوافذ المنبثقة خاملة وهي مغلقة
    overlays.forEach(overlay => overlay.setAttribute('inert', ''));

    function openModal(modalId, triggerBtn) {
      const modal = document.getElementById(modalId);
      if (!modal) return;

      triggerElement = triggerBtn || document.activeElement;
      activeModal = modal;
      modal.classList.add('is-active');
      modal.removeAttribute('inert');
      document.body.style.overflow = 'hidden';

      // نقل التركيز لأول عنصر تفاعلي داخل النافذة بعد استقرار العرض
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

      // إعادة التركيز للزر الذي قام بفتح النافذة
      if (triggerElement && typeof triggerElement.focus === 'function') {
        triggerElement.focus();
      }
      activeModal = null;
      triggerElement = null;
    }

    openBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-modal-target');
        openModal(targetId, btn);
      });
    });

    closeBtns.forEach(btn => {
      btn.addEventListener('click', closeModal);
    });

    overlays.forEach(overlay => {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
      });
    });

    // إغلاق بمفتاح Escape وحصر التركيز داخل المودال (Focus trap)
    window.addEventListener('keydown', (e) => {
      if (!activeModal) return;

      if (e.key === 'Escape') {
        closeModal();
        return;
      }

      if (e.key === 'Tab') {
        const focusables = activeModal.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });
  }

  /**
   * 5) التفاعلات الدقيقة للنماذج: اهتزاز الخطأ وحالة النجاح والتحميل
   */
  function initFormInteractions() {
    const demoForm = document.getElementById('demo-motion-form');
    if (!demoForm) return;

    const emailInput = document.getElementById('demo-email');
    const emailField = emailInput ? emailInput.closest('.motion-field') : null;
    const submitBtn = demoForm.querySelector('button[type="submit"]');
    const resultNotice = document.getElementById('form-result-notice');

    demoForm.addEventListener('submit', (e) => {
      e.preventDefault();

      const val = emailInput ? emailInput.value.trim() : '';

      // التحقق البسيط لإظهار الاهتزاز عند الخطأ
      if (!val || !val.includes('@')) {
        if (emailField) {
          emailField.classList.add('has-error');
          emailField.classList.remove('is-shaking');
          // Force Reflow لتكرار الحركة في حال تم النقر مراراً
          void emailField.offsetWidth;
          emailField.classList.add('is-shaking');

          setTimeout(() => {
            emailField.classList.remove('is-shaking');
          }, 460);
        }
        return;
      }

      // إزالة علامات الخطأ
      if (emailField) {
        emailField.classList.remove('has-error', 'is-shaking');
      }

      // محاكاة الإرسال: زر يتحول إلى دوران (Spinner) ثم علامة نجاح خضراء
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <span class="motion-spinner" aria-hidden="true"></span>
        <span>جاري المعالجة...</span>
      `;

      setTimeout(() => {
        // حالة النجاح
        submitBtn.innerHTML = `
          <svg style="width:20px;height:20px;stroke:#fff;fill:none;" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
          </svg>
          <span>تم بنجاح!</span>
        `;
        submitBtn.style.backgroundColor = '#10b981';

        // إظهار إشعار النجاح بحركة انسيابية دون استخدام display: none
        if (resultNotice) {
          resultNotice.classList.add('is-visible');
        }

        setTimeout(() => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalText;
          submitBtn.style.backgroundColor = '';
          demoForm.reset();
          // إخفاء إشعار النجاح عند إعادة تعيين النموذج
          if (resultNotice) {
            resultNotice.classList.remove('is-visible');
          }
        }, 2500);
      }, 1200);
    });
  }

  /**
   * 6) زر تبديل تقليل الحركة لتجربة المطورين (Reduced Motion Sandbox)
   */
  function initReducedMotionTester() {
    const toggleBtn = document.getElementById('toggle-reduced-motion-btn');
    if (!toggleBtn) return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    // تحديث صنف تقليل الحركة على html وسمة aria والنص
    function setReducedMotionState(isReduced) {
      document.documentElement.classList.toggle('force-reduced-motion', isReduced);
      toggleBtn.setAttribute('aria-pressed', isReduced ? 'true' : 'false');
      toggleBtn.textContent = isReduced ? 'الحركة: معطّلة' : 'الحركة: مفعّلة';
    }

    // البدء بحالة النظام إن كانت مفعلة
    setReducedMotionState(mediaQuery.matches);

    // متابعة تغير تفضيل النظام تلقائياً
    mediaQuery.addEventListener('change', (e) => {
      setReducedMotionState(e.matches);
    });

    // تبديل الحالة عند نقر الزر
    toggleBtn.addEventListener('click', () => {
      const isCurrentlyReduced = document.documentElement.classList.contains('force-reduced-motion');
      setReducedMotionState(!isCurrentlyReduced);
    });
  }

  // التهيئة الشاملة عند اكتمال جاهزية الـ DOM
  function initMotionSystem() {
    initScrollReveal();
    initScrollEngine();
    initMobileMenu();
    initModal();
    initFormInteractions();
    initReducedMotionTester();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMotionSystem);
  } else {
    initMotionSystem();
  }

  // إتاحة المحرك في النطاق العام لإعادة الاستدعاء عند الحاجة (مثلاً بعد جلب AJAX/PJAX)
  window.MotionEngine = {
    refreshReveal: initScrollReveal,
    prefersReducedMotion: prefersReducedMotion
  };

})();

