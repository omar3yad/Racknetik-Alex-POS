(function () {
  let lastSubmit = 0;

  function init() {
    const scanInput = document.getElementById("scan-input");
    if (scanInput) {
      scanInput.focus();
      scanInput.value = "";

      scanInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.keyCode === 13) {
          e.preventDefault();
          const now = Date.now();
          if (now - lastSubmit > 100) {
            lastSubmit = now;
            const scanForm = document.getElementById("scan-form");
            if (scanForm) {
              scanForm.requestSubmit();
            }
          }
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
