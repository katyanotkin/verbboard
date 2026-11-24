// Visible, localized message + "Try again" when a sign-in attempt fails (issue #141).
//
// Before this, a closed or blocked desktop popup ended in a raw English alert(), and a
// failed redirect or a rejected sign-in from the practice gate only wrote a console line.
// auth.js maps every failure to a short code (the same codes #140 records) and calls
// show(code, retry). Strings live here, not in app/i18n, like pwa.js's update banner, so
// every page that loads auth.js has them without each route passing them in.
(function (root) {
  'use strict';

  var STRINGS = {
    en: {
      cancelled: 'Sign-in was cancelled. You can try again whenever you like.',
      blocked: 'Your browser blocked the Google sign-in window. Allow pop-ups for this site, then try again.',
      network: 'No connection to Google. Check your internet and try again.',
      unavailable: 'Sign-in could not load. Turn off content blockers or reload the page, then try again.',
      generic: 'Sign-in did not work. Please try again.',
      retry: 'Try again',
      close: 'Close'
    },
    ru: {
      cancelled: 'Вход отменён. Вы можете попробовать снова в любой момент.',
      blocked: 'Браузер заблокировал окно входа через Google. Разрешите всплывающие окна для этого сайта и повторите попытку.',
      network: 'Нет связи с Google. Проверьте подключение к интернету и повторите попытку.',
      unavailable: 'Не удалось загрузить сервис входа. Отключите блокировщики контента или перезагрузите страницу и повторите попытку.',
      generic: 'Войти не удалось. Пожалуйста, повторите попытку.',
      retry: 'Повторить',
      close: 'Закрыть'
    },
    es: {
      cancelled: 'Se canceló el inicio de sesión. Puede volver a intentarlo cuando quiera.',
      blocked: 'El navegador bloqueó la ventana de inicio de sesión de Google. Permita las ventanas emergentes para este sitio e inténtelo de nuevo.',
      network: 'No se puede conectar con Google. Revise su conexión a internet e inténtelo de nuevo.',
      unavailable: 'No se pudo cargar el inicio de sesión. Desactive los bloqueadores de contenido o recargue la página e inténtelo de nuevo.',
      generic: 'No se pudo iniciar sesión. Por favor, inténtelo de nuevo.',
      retry: 'Reintentar',
      close: 'Cerrar'
    },
    he: {
      cancelled: 'ההתחברות בוטלה. אפשר לנסות שוב בכל עת.',
      blocked: 'הדפדפן חסם את חלון ההתחברות של Google. אפשרו חלונות קופצים באתר זה ונסו שוב.',
      network: 'אין חיבור ל-Google. בדקו את החיבור לאינטרנט ונסו שוב.',
      unavailable: 'לא ניתן היה לטעון את שירות ההתחברות. כבו חוסמי תוכן או רעננו את הדף ונסו שוב.',
      generic: 'ההתחברות לא הצליחה. נסו שוב.',
      retry: 'נסו שוב',
      close: 'סגירה'
    }
  };

  var BANNER_ID = 'vb-signin-error';

  // Failure code (same vocabulary as /api/analytics/sign_in_failed) -> message key.
  function messageKey(code) {
    if (code === 'popup_closed') return 'cancelled';
    if (code === 'popup_blocked') return 'blocked';
    if (code === 'network') return 'network';
    if (code === 'sdk_unavailable') return 'unavailable';
    return 'generic';
  }

  function pickLanguage(uiLang, htmlLang) {
    var candidates = [uiLang, htmlLang];
    for (var i = 0; i < candidates.length; i++) {
      var code = String(candidates[i] || '').slice(0, 2).toLowerCase();
      if (STRINGS[code]) return code;
    }
    return 'en';
  }

  // Pure: what to show for a failure code in a UI language.
  function messageFor(code, uiLang, htmlLang) {
    var lang = pickLanguage(uiLang, htmlLang);
    var strings = STRINGS[lang];
    return { lang: lang, text: strings[messageKey(code)], retry: strings.retry, close: strings.close };
  }

  function dismiss() {
    var existing = root.document && root.document.getElementById(BANNER_ID);
    if (existing && existing.remove) existing.remove();
  }

  // Shows one message at a time (a second failure replaces the first). `onRetry` runs from a
  // click, so a popup opened by it still counts as a user gesture. Text goes in via
  // textContent only.
  function show(code, onRetry) {
    var doc = root.document;
    if (!doc || !doc.body) return null;
    var msg = messageFor(code, root.VB_UI_LANG, doc.documentElement && doc.documentElement.lang);
    dismiss();

    var banner = doc.createElement('div');
    banner.id = BANNER_ID;
    banner.className = 'vb-update-banner vb-signin-error';
    banner.setAttribute('role', 'alert');
    if (msg.lang === 'he') banner.setAttribute('dir', 'rtl');

    var text = doc.createElement('span');
    text.className = 'vb-update-text';
    text.textContent = msg.text;
    banner.appendChild(text);

    if (typeof onRetry === 'function') {
      var retry = doc.createElement('button');
      retry.type = 'button';
      retry.className = 'vb-update-btn';
      retry.textContent = msg.retry;
      retry.addEventListener('click', function () {
        dismiss();
        // A failed retry is already shown and tracked by signIn(); keep the console free of an unhandled rejection.
        Promise.resolve(onRetry()).catch(function () {});
      });
      banner.appendChild(retry);
    }

    var close = doc.createElement('button');
    close.type = 'button';
    close.className = 'vb-update-dismiss';
    close.setAttribute('aria-label', msg.close);
    close.textContent = '×';
    close.addEventListener('click', dismiss);
    banner.appendChild(close);

    doc.body.appendChild(banner);
    return banner;
  }

  var api = { show: show, dismiss: dismiss, messageFor: messageFor, messageKey: messageKey, STRINGS: STRINGS };
  root.VerbBoardSignInError = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
