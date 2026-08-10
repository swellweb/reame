/* Reame Concierge — il widget che un sito incolla con uno script tag.
 *
 * <script>
 *   window.REAME_CONCIERGE = {
 *     server: "https://concierge.miosito.it",     // il server Reame
 *     factsheet: "/dati/concierge.txt",           // URL del factsheet
 *     titolo: "Chiedi a noi",
 *   };
 * </script>
 * <script src="reame-concierge.js" defer></script>
 *
 * Al caricamento della pagina il widget scarica il factsheet e avvisa il
 * server (/v1/warm) cosi' il documento viene letto in anticipo: quando il
 * visitatore fa la prima domanda, la parte costosa e' gia' pagata.
 * Niente dipendenze, niente cookie, nessun dato inviato a terzi: le
 * domande vanno solo al server indicato in `server`.
 */
(function () {
  "use strict";
  var cfg = window.REAME_CONCIERGE || {};
  var server = (cfg.server || "").replace(/\/$/, "");
  if (!server) { console.warn("[reame] REAME_CONCIERGE.server mancante"); return; }
  var titolo = cfg.titolo || "Chiedi a noi";
  var factsheet = "";

  // Niente esempio few-shot qui: aiuta i modelli base in completamento, ma
  // AVVELENA gli instruct in chat (misurato: il modello grande rispondeva
  // sull'argomento dell'esempio). Questo formato e' quello del 20/20.
  function messaggi(domanda) {
    return [{ role: "user", content:
      "Documento:\n" + factsheet +
      "\n\nRispondi alla domanda usando SOLO il documento, con il solo dato " +
      "richiesto, in una sola riga, senza spiegazioni. Se il documento non " +
      "contiene l'informazione rispondi esattamente: NON PRESENTE.\n" +
      "Domanda: " + domanda }];
  }

  // Warm-ahead: stesso identico prefisso che manderemo con la domanda,
  // meno la domanda — la prefix cache aggancia fino a dove i token combaciano.
  function scalda() {
    fetch(server + "/v1/warm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: messaggi("") }),
    }).catch(function () { /* il warm e' un regalo, mai un errore */ });
  }

  function chiedi(domanda, fatto) {
    fetch(server + "/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "reame", temperature: 0, max_tokens: 96,
        messages: messaggi(domanda),
      }),
    }).then(function (r) { return r.json(); })
      .then(function (j) {
        var testo = (j.choices && j.choices[0].message.content || "").trim();
        if (/NON PRESENTE/i.test(testo))
          testo = "Su questo non ho l'informazione qui — meglio chiedere " +
                  "direttamente ai contatti del sito.";
        fatto(testo);
      })
      .catch(function () {
        fatto("Il servizio non risponde in questo momento, riprova tra poco.");
      });
  }

  // ---- interfaccia -------------------------------------------------------
  // Ogni colore e' dichiarato ESPLICITO, testo compreso: il widget vive
  // dentro pagine altrui e non deve ereditare niente (il testo bianco di un
  // sito scuro su una bolla chiara era illeggibile — successo davvero).
  // Temi con contrasto verificato (WCAG AA): scuro di default, chiaro via
  // REAME_CONCIERGE.tema = "chiaro".
  var temi = {
    scuro: { pannello: "#1C1F26", bordo: "#3A3F4B", testa: "#0F1115",
             testaTesto: "#F2F1EC", corpoTesto: "#F2F1EC",
             io: "#2E6E62", ioTesto: "#FFFFFF",
             lui: "#2A2E37", luiTesto: "#F2F1EC",
             campo: "#F2F1EC", segnaposto: "#9AA0AC", invia: "#7FC4B4" },
    chiaro: { pannello: "#FBFAF6", bordo: "#D8D4C8", testa: "#20242E",
              testaTesto: "#FBFAF6", corpoTesto: "#20242E",
              io: "#DCEAE4", ioTesto: "#14261F",
              lui: "#F5E8D4", luiTesto: "#33240E",
              campo: "#20242E", segnaposto: "#6B7078", invia: "#20242E" },
  };
  var t = temi[cfg.tema === "chiaro" ? "chiaro" : "scuro"];
  var css = "#rc-bolla{position:fixed;right:18px;bottom:18px;width:54px;height:54px;" +
    "border-radius:27px;background:" + t.testa + ";color:" + t.testaTesto + ";border:1px solid " + t.bordo + ";" +
    "font-size:22px;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.35);z-index:9999}" +
    "#rc-box{position:fixed;right:18px;bottom:84px;width:320px;max-width:92vw;" +
    "height:420px;max-height:70vh;background:" + t.pannello + ";border:1px solid " + t.bordo + ";" +
    "border-radius:12px;display:none;flex-direction:column;overflow:hidden;" +
    "box-shadow:0 4px 24px rgba(0,0,0,.35);z-index:9999;font:14px/1.45 system-ui,sans-serif;" +
    "color:" + t.corpoTesto + "}" +
    "#rc-testa{background:" + t.testa + ";color:" + t.testaTesto + ";padding:10px 14px;font-weight:600}" +
    "#rc-corpo{flex:1;overflow-y:auto;padding:10px}" +
    ".rc-io,.rc-lui{margin:6px 0;padding:8px 10px;border-radius:10px;max-width:85%;" +
    "white-space:pre-wrap;word-wrap:break-word;font-weight:500}" +
    ".rc-io{background:" + t.io + ";color:" + t.ioTesto + ";margin-left:auto}" +
    ".rc-lui{background:" + t.lui + ";color:" + t.luiTesto + "}" +
    "#rc-riga{display:flex;border-top:1px solid " + t.bordo + "}" +
    "#rc-campo{flex:1;border:none;padding:10px;font:inherit;background:transparent;" +
    "outline:none;color:" + t.campo + "}" +
    "#rc-campo::placeholder{color:" + t.segnaposto + ";opacity:1}" +
    "#rc-invia{border:none;background:none;color:" + t.invia + ";font-weight:700;padding:0 14px;cursor:pointer}";

  function crea() {
    var stile = document.createElement("style");
    stile.textContent = css;
    document.head.appendChild(stile);

    var bolla = document.createElement("button");
    bolla.id = "rc-bolla";
    bolla.setAttribute("aria-label", titolo);
    bolla.textContent = "💬";
    var box = document.createElement("div");
    box.id = "rc-box";
    box.innerHTML =
      '<div id="rc-testa"></div><div id="rc-corpo"></div>' +
      '<form id="rc-riga"><input id="rc-campo" autocomplete="off" ' +
      'placeholder="Scrivi una domanda…"><button id="rc-invia" type="submit">Invia</button></form>';
    document.body.appendChild(bolla);
    document.body.appendChild(box);
    box.querySelector("#rc-testa").textContent = titolo;

    var corpo = box.querySelector("#rc-corpo");
    function riga(classe, testo) {
      var d = document.createElement("div");
      d.className = classe;
      d.textContent = testo;
      corpo.appendChild(d);
      corpo.scrollTop = corpo.scrollHeight;
      return d;
    }

    bolla.addEventListener("click", function () {
      box.style.display = box.style.display === "flex" ? "none" : "flex";
      if (box.style.display === "flex") box.querySelector("#rc-campo").focus();
    });

    box.querySelector("#rc-riga").addEventListener("submit", function (e) {
      e.preventDefault();
      var campo = box.querySelector("#rc-campo");
      var domanda = campo.value.trim();
      if (!domanda) return;
      campo.value = "";
      riga("rc-io", domanda);
      var attesa = riga("rc-lui", "…");
      chiedi(domanda, function (testo) { attesa.textContent = testo; });
    });
  }

  function via() {
    var sorgente = cfg.factsheet;
    if (!sorgente) { console.warn("[reame] REAME_CONCIERGE.factsheet mancante"); return; }
    fetch(sorgente).then(function (r) { return r.text(); }).then(function (t) {
      factsheet = t;
      crea();
      scalda();
    }).catch(function () { console.warn("[reame] factsheet non raggiungibile"); });
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", via);
  else via();
})();
