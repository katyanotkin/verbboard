// Reusable "tap to reveal" help-hint pattern.
// Markup contract (any page, any spot):
//   <span class="help-hint">
//     <button type="button" class="help-hint-trigger" aria-expanded="false" aria-label="...">?</button>
//     <span class="help-hint-panel" role="note" hidden>...explanation text...</span>
//   </span>
// No page-specific wiring needed -- include this script and the markup above,
// this file finds and drives every .help-hint-trigger on the page.
document.addEventListener("DOMContentLoaded", function () {
  function closeTrigger(trigger) {
    trigger.setAttribute("aria-expanded", "false");
    const wrap = trigger.closest(".help-hint");
    const panel = wrap && wrap.querySelector(".help-hint-panel");
    if (panel) panel.hidden = true;
  }

  document.addEventListener("click", function (event) {
    const trigger = event.target.closest(".help-hint-trigger");

    document.querySelectorAll('.help-hint-trigger[aria-expanded="true"]').forEach(function (openTrigger) {
      if (openTrigger !== trigger) closeTrigger(openTrigger);
    });

    if (!trigger) return;

    const wrap = trigger.closest(".help-hint");
    const panel = wrap && wrap.querySelector(".help-hint-panel");
    if (!panel) return;

    const isOpen = trigger.getAttribute("aria-expanded") === "true";
    trigger.setAttribute("aria-expanded", isOpen ? "false" : "true");
    panel.hidden = isOpen;
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document.querySelectorAll('.help-hint-trigger[aria-expanded="true"]').forEach(closeTrigger);
  });
});
