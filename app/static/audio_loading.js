(function () {
  var LOAD_ICON = "…";
  var PULSE_CLASS = "is-loading";

  function setLoading(btn, originalHTML) {
    btn.textContent = LOAD_ICON;
    btn.classList.add(PULSE_CLASS);
    btn.disabled = true;
  }

  function clearLoading(btn, originalHTML) {
    btn.innerHTML = originalHTML;
    btn.classList.remove(PULSE_CLASS);
    btn.disabled = false;
  }

  function wireAudio(audio) {
    // The play button is the immediate next sibling of the <audio> element.
    // The slow button (examples only) is the sibling after the play button.
    var playBtn = audio.nextElementSibling;
    if (!playBtn || !playBtn.classList.contains("btn")) return;
    var slowBtn =
      playBtn.nextElementSibling &&
      playBtn.nextElementSibling.classList.contains("slow-btn")
        ? playBtn.nextElementSibling
        : null;

    // Capture original markup before any mutations (slow-btn contains an <img>).
    var playOriginal = playBtn.innerHTML;
    var slowOriginal = slowBtn ? slowBtn.innerHTML : null;

    // Which button triggered the current load, so we only animate that one.
    var activeBtn = null;

    function originalFor(btn) {
      return btn === slowBtn ? slowOriginal : playOriginal;
    }

    function onLoadStart() {
      // readyState >= 2 (HAVE_CURRENT_DATA) means the browser already has
      // enough data to play without waiting -- skip the loading state.
      if (audio.readyState >= 2) return;
      if (activeBtn) setLoading(activeBtn, originalFor(activeBtn));
    }

    function onDone() {
      if (activeBtn) {
        clearLoading(activeBtn, originalFor(activeBtn));
        activeBtn = null;
      }
    }

    audio.addEventListener("waiting", onLoadStart);
    audio.addEventListener("playing", onDone);
    audio.addEventListener("canplaythrough", onDone);
    audio.addEventListener("error", onDone);

    // Intercept clicks on both buttons to record which one is active before
    // the onclick handler fires audio.play().
    playBtn.addEventListener("click", function () {
      activeBtn = playBtn;
      if (slowBtn) clearLoading(slowBtn, slowOriginal);
      if (audio.readyState < 2) setLoading(playBtn, playOriginal);
    }, true);

    if (slowBtn) {
      slowBtn.addEventListener("click", function () {
        activeBtn = slowBtn;
        clearLoading(playBtn, playOriginal);
        if (audio.readyState < 2) setLoading(slowBtn, slowOriginal);
      }, true);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("audio").forEach(wireAudio);
  });
})();
