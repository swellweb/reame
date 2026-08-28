<p align="center">
  <img src="figures/logo.svg" alt="Reame" width="300">
</p>

<p align="center">
  <a href="https://swellweb.github.io/reame/"><b>▶ Prova la demo</b></a> — gira su un'istanza ARM Oracle gratuita, senza GPU.
</p>

# Reame

Reame è un server di inferenza per LLM progettato per girare su CPU standard, costruito attorno ai modelli ternari — pesi che valgono solo −1, 0 o +1. Un modello da 8 miliardi di parametri occupa 2,2 GB, entrando comodamente nella RAM di un'istanza cloud gratuita. Il motore che lo esegue, nucleo, è stato scritto da zero ed è più veloce del runtime ufficiale fornito dagli stessi sviluppatori del modello.

Quest'ultima affermazione si basa su dati misurati, non su promesse di marketing. Eseguendo Bonsai-8B — il modello ternario di punta di PrismML — contro il fork ufficiale di llama.cpp di PrismML, sulla stessa macchina, con lo stesso prompt e in condizioni di test pulite:

|  | Generazione | Lettura del prompt |
|---|---|---|
| **2 core ARM** (Oracle Always Free) | **2,8 contro 2,46 tok/s (+14%)** | **4,3 contro 2,77 tok/s (+55%)** |
| **4 core ARM** | **5,7 contro 4,84 tok/s (+18%)** | **7,9 contro 5,5 tok/s (+44%)** |

I risultati sono replicati su esecuzioni consecutive — il protocollo esatto per riga è nella pagina benchmark. L'accuratezza è del 19/20 su un test di venti domande eseguito sul server in produzione — la singola risposta errata è dovuta a un limite di conoscenza che gli stessi pesi superano quando viene loro consentito di ragionare prima di rispondere. La metodologia completa, tutti i dati e anche i confronti in cui **perdiamo** sono disponibili in [BENCHMARKS.md](BENCHMARKS.md): una pagina di benchmark che mostra solo vittorie è pura pubblicità.

L'API utilizzata è quella standard di OpenAI, pertanto i client esistenti funzionano senza richiedere modifiche. Sotto il cofano operano due motori: nucleo per i modelli ternari e di piccole dimensioni, e llama.cpp per tutto il resto.

![Due motori](figures/due-motori.svg)

## Perché il ternario, e perché un motore nostro

In un modello ternario, ogni peso è limitato a uno di tre valori. Il prodotto matrice-vettore diventa così aritmetica intera, che le istruzioni vettoriali della CPU gestiscono in modo molto efficiente, riducendo drasticamente l'occupazione di memoria: 2,125 bit per peso, dall'inizio alla fine della rete. Vengono inclusi anche la testa e l'embedding; nessun tensore viene lasciato di nascosto a 6 bit.

nucleo converte il modello **una sola volta** nel suo formato interlacciato (`.nuc`) per poi mapparlo in memoria. Il loop di esecuzione critico accumula un intero blocco da 128 pesi in int32 esatto, toccando la virgola mobile una sola volta. L'attention viene eseguito in modalità vettoriale in fp16 sulla cache KV e si distribuisce tra i core man mano che il contesto cresce. L'intero progetto è stato sviluppato con un approccio test-first: 149 casi di test, 254.000 asserzioni, ogni kernel verificato rispetto a un oracolo indipendente. I percorsi per il singolo token e per i lotti producono output bit-identici per costruzione.

Nessuna parte di questo codice è derivata da llama.cpp — llama.cpp è semplicemente lo standard rispetto a cui ci misuriamo.

## Inizia col ternario

```bash
git clone https://github.com/swellweb/reame
cd reame && ./build.sh
```

```bash
# 1. scarica Bonsai-8B ternario (2,1 GB) dal repository ufficiale di PrismML
curl -LO https://huggingface.co/prism-ml/Ternary-Bonsai-8B-gguf/resolve/main/Ternary-Bonsai-8B-Q2_0.gguf

# 2. converti una volta (circa un minuto; produce un file .nuc da 2,2 GB)
./build/src/reame-converti Ternary-Bonsai-8B-Q2_0.gguf bonsai-8b.nuc

# 3. avvia il server
./build/src/reame run bonsai-8b.nuc --serve
```

```bash
curl http://127.0.0.1:8080/v1/chat/completions -d '{
  "model": "reame",
  "messages": [{"role": "user", "content": "Ciao!"}]
}'
```

La variante da 1.7B funziona allo stesso modo (`Ternary-Bonsai-1.7B-gguf`, 460 MB) e genera ~22 token al secondo sulla stessa macchina gratuita. I file GGUF convenzionali vengono instradati tramite il motore llama.cpp: il comando `reame run qwen2.5-1.5b` scarica e avvia il server in un'unica operazione.

## Un esempio concreto

Sul sito di un'azienda specializzata in pavimentazioni in resina, un visitatore scrive: *"Quanto mi costa quel pavimento liscio per il salotto?"*. Nel listino aziendale quel prodotto è registrato come "resina epossidica autolivellante per interni civili" — una terminologia tecnica che il visitatore non conosce e non dovrebbe dover conoscere. Reame comprende l'intento della domanda e risponde "35,00 € al metro quadro" in un paio di secondi, utilizzando un'infrastruttura a costo zero.

Inoltre, il sistema offre una garanzia che un LLM standard non può fornire: quando la risposta deve essere un dato specifico — un prezzo, un numero di telefono, un orario — Reame non lo genera, ma lo estrae e copia tale e quale dai dati originali. L'invenzione di un prezzo non è semplicemente improbabile, è strutturalmente impossibile. E se l'informazione non è presente nei dati, il sistema lo dichiara apertamente invece di tirare a indovinare.

## Come funziona, in parole povere

Quattro concetti fondamentali, tutti misurati; tutto il resto è pura implementazione.

1. **Converti una volta, mai più.** Il modello viene trasformato in un file `.nuc` e il server lo mappa in memoria: 99 MB di RAM all'avvio, pronto in pochi secondi.
2. **Non leggere mai due volte la stessa cosa.** Tutto ciò che il modello ha già processato viene salvato su disco (la *cache dei prefissi*) e riutilizzato tra richieste, riavvii e prompt che condividono un'iniziale comune: una richiesta identica costa mezzo secondo.
3. **Leggi in anticipo, mentre nessuno aspetta.** Non appena il visitatore apre la pagina, il widget notifica Reame (`/v1/warm`) e il modello inizia a leggere il documento mentre il visitatore sta ancora leggendo la pagina.
4. **Capisci con i modelli, rispondi con i dati.** La comprensione linguistica è gestita da veri LLM; i valori nelle risposte provengono dai tuoi dati, copiati fedelmente. Le richieste semplici e inequivocabili saltano i modelli del tutto (~20 ms); quelle più complesse vengono passate al modello più grande tramite il relè `[escalation]`.

## La parte onesta

Riteniamo che documentare i fallimenti sia metà del valore del progetto:

- La similarità semantica non è in grado di riconoscere l'assenza di un dato (per questo il sistema concierge *calcola* i rifiuti basandosi sull'evidenza, invece di predirli tramite punteggi).
- Tre diversi design dei kernel sono risultati inferiori ai loro predecessori durante i test, e ne forniamo la documentazione accanto alle soluzioni che hanno prevalso.
- Un numero inferiore di esperti MoE velocizza la lettura del prompt, ma compromette la generazione.
- La decodifica speculativa su vCPU condivise e sovrasottoscritte risulta controproducente; Reame lo rileva a runtime e la disabilita automaticamente.

E cosa **non** affermiamo: di essere il motore ternario più veloce in assoluto. Attualmente, il formato TQ2_0 di llama.cpp mainline è più rapido sul modello da 1.7B e su architetture Apple Silicon. La tabella completa, inclusi i test in cui risultiamo perdenti, è disponibile in [BENCHMARKS.md](BENCHMARKS.md), insieme alle strategie che stiamo adottando per colmare il divario.

## Quando usare altro

**Ollama** è lo strumento ideale se si desidera sperimentare vari modelli sul proprio portatile senza complicazioni: è la scelta giusta per la maggior parte degli utenti, e Reame non compete in quel segmento. Se si dispone di GPU, **vLLM** o **SGLang** rimangono le opzioni migliori. 

Reame è progettato per uno scenario diverso: un carico di lavoro ripetitivo su hardware CPU economico, dove il costo per richiesta *diminuisce* all'aumentare del tempo di attività del server — l'esatto opposto del modello di fatturazione a consumo delle API.

## Licenza

Rilasciato sotto licenza [MIT](../LICENSE). I modelli Bonsai sono sviluppati da [PrismML](https://huggingface.co/prism-ml) (fare riferimento alle rispettive licenze nelle loro repository); llama.cpp è distribuito sotto licenza MIT. Il motore nucleo è stato scritto da zero e verificato token per token tramite implementazioni di riferimento indipendenti.