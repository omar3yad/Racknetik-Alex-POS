(function () {
  let html5QrCode = null;
  let isScanning = false;
  let torchEnabled = false;

  function playBeep() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(1200, audioCtx.currentTime);
      gainNode.gain.setValueAtTime(0.15, audioCtx.currentTime);
      oscillator.start();
      setTimeout(() => {
        oscillator.stop();
        audioCtx.close();
      }, 150);
    } catch (err) {
      console.warn("AudioContext beep failed:", err);
    }
  }

  function startScanning() {
    const scannerWrapper = document.getElementById("scanner-wrapper");
    const loadingEl = document.getElementById("scanner-loading");
    const startBtn = document.getElementById("btn-start-camera");

    if (!scannerWrapper || isScanning) return;

    // Show scanner wrapper, hide start button
    scannerWrapper.classList.remove("hidden");
    if (startBtn) startBtn.classList.add("hidden");
    if (loadingEl) loadingEl.classList.remove("hidden");

    try {
      if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("qr-reader");
      }

      const config = {
        fps: 15,
        qrbox: (width, height) => {
          const boxWidth = Math.min(width * 0.85, 300);
          const boxHeight = Math.min(height * 0.4, 150);
          return { width: boxWidth, height: boxHeight };
        },
        aspectRatio: 1.333333, // 4:3 aspect ratio is standard and lightweight
        formatsToSupport: [
          Html5QrcodeSupportedFormats.CODE_128,
          Html5QrcodeSupportedFormats.CODE_39,
          Html5QrcodeSupportedFormats.QR_CODE,
          Html5QrcodeSupportedFormats.EAN_13,
          Html5QrcodeSupportedFormats.EAN_8
        ]
      };

      html5QrCode.start(
        { facingMode: "environment" },
        config,
        onScanSuccess,
        onScanFailure
      ).then(() => {
        isScanning = true;
        if (loadingEl) loadingEl.classList.add("hidden");
      }).catch(err => {
        console.error("Camera startup failed:", err);
        stopScanning();
      });
    } catch (e) {
      console.error("Html5Qrcode initialization failed:", e);
      stopScanning();
    }
  }

  function stopScanning() {
    const scannerWrapper = document.getElementById("scanner-wrapper");
    const startBtn = document.getElementById("btn-start-camera");
    const toggleTorchBtn = document.getElementById("btn-toggle-torch");

    isScanning = false;
    torchEnabled = false;

    if (toggleTorchBtn) {
      toggleTorchBtn.textContent = "تشغيل الكشاف";
    }

    if (scannerWrapper) scannerWrapper.classList.add("hidden");
    if (startBtn) startBtn.classList.remove("hidden");

    if (html5QrCode) {
      html5QrCode.stop().then(() => {
        console.log("Camera stopped.");
      }).catch(err => {
        console.warn("Failed to stop camera:", err);
      });
    }
  }

  function onScanSuccess(decodedText, decodedResult) {
    playBeep();
    const scanInput = document.getElementById("scan-input");
    if (scanInput) {
      scanInput.value = decodedText;
    }

    stopScanning();
    setTimeout(() => {
      const scanForm = document.getElementById("scan-form");
      if (scanForm) {
        scanForm.requestSubmit();
      }
    }, 100);
  }

  function onScanFailure(error) {
    // Normal failure during scanning, ignored to prevent console spamming
  }

  function init() {
    startScanning();

    // Bind control buttons
    const btnStop = document.getElementById("btn-stop-camera");
    if (btnStop) {
      btnStop.addEventListener("click", stopScanning);
    }

    const btnStart = document.getElementById("btn-start-camera");
    if (btnStart) {
      btnStart.addEventListener("click", startScanning);
    }

    const btnToggleTorch = document.getElementById("btn-toggle-torch");
    if (btnToggleTorch) {
      btnToggleTorch.addEventListener("click", () => {
        if (!html5QrCode || !isScanning) return;
        torchEnabled = !torchEnabled;
        html5QrCode.applyVideoConstraints({
          advanced: [{ torch: torchEnabled }]
        }).then(() => {
          btnToggleTorch.textContent = torchEnabled ? "إطفاء الكشاف" : "تشغيل الكشاف";
        }).catch(err => {
          console.warn("Torch control not supported:", err);
        });
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
