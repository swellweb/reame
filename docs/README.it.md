<p align="center">
  <img src="figures/logo.svg" alt="Reame" width="300">
</p>

<p align="center">
  <a href="https://swellweb.github.io/reame/"><b>▶ Prova il demo</b></a> — gira su una macchina ARM Oracle gratuita, senza GPU.
</p>

# Reame

Reame è un server di inferenza per LLM che gira su CPU normali. L'ho
costruito perché volevo far girare modelli sui miei dati senza mandarli a
un'API esterna e senza comprare una GPU: il PC che ho già, o la macchina
gratuita di Oracle, dovevano bastare.

L'API è quella di OpenAI, quindi i client esistenti funzionano senza
toccare niente. Sotto ci sono due motori: llama.cpp per i modelli grandi,
e nucleo, un motore che ho scritto da zero per i piccoli (0.5B–3B). Sui
piccoli nucleo è più veloce di llama.cpp — sulla stessa macchina, +31% in
generazione — e parte occupando 99 MB di RAM, perché il modello viene
convertito una volta sola e poi mappato in memoria, invece di essere
riorganizzato a ogni avvio.

![Due motori](figures/due-motori.svg)

## Un esempio concreto

Sul sito di un'azienda di pavimenti in resina, un visitatore scrive:
"quanto mi viene a costare quel pavimento liscio per il salotto?". Nel
listino quella cosa si chiama "resina epossidica autolivellante per
interni civili" — il visitatore non lo sa e non deve saperlo. Reame
capisce che sta chiedendo quello, e risponde "35,00 € al metro quadro" in
un paio di secondi, da una macchina che costa zero.

Questo è il punto che un bot a regole non copre: un bot cerca parole
chiave, e alla prima domanda scritta con parole diverse dal listino muore,
o peggio risponde a caso. Qui sotto ci sono modelli di linguaggio veri —
uno piccolo che vive sulla macchina gratuita e uno grande per le domande
difficili — e nessuna regola da scrivere: dai in pasto i tuoi dati e le
domande arrivano come la gente le scrive davvero.

In più c'è una garanzia che un LLM da solo non ti dà: quando la risposta
è un dato tuo (un prezzo, un orario, un telefono), Reame non lo lascia
generare al modello — lo copia dai dati, tale e quale. Inventare un prezzo
non è improbabile: è impossibile. E se la risposta nei tuoi dati non c'è,
dice che non c'è.

Come regge i tempi su hardware così scarso:

- quando il visitatore apre la pagina, il widget avvisa il server, che
  legge il documento in anticipo. Quando arriva la domanda, la parte
  costosa è già fatta (misurato: da 59 secondi a 3,2).
- quello che il server ha già letto una volta finisce su disco e viene
  riusato, anche tra riavvii. Una domanda già vista risponde in mezzo
  secondo.
- per le domande dove è sicuro di aver capito, salta il modello e serve
  il dato direttamente: 20 millisecondi. È una scorciatoia, non il
  cervello — al primo dubbio la domanda va ai modelli.
- se il modello piccolo non sa rispondere, la richiesta passa da sola a
  quello grande, che nel frattempo è già caldo.

![La cascata del concierge](figures/concierge-cascata.svg)

![Warm-ahead](figures/warm-ahead.svg)

## Per cosa lo uso, per cosa no

Funziona bene per il lavoro ripetitivo sui propri dati: estrarre campi da
fatture e ticket, taggare un catalogo di notte, rispondere a domande su un
listino, autocompletamento di codice in locale. Casi dove la risposta sta
nel contesto che gli dai tu, e dove il costo per richiesta deve scendere
col tempo invece di crescere come una bolletta a token.

Non è un sostituto di ChatGPT: un modello piccolo su CPU non ha né la
conoscenza né il ragionamento di un modello frontier. Se vuoi provare
tanti modelli sul portatile, usa Ollama che è fatto apposta. Se hai delle
GPU, usa vLLM.

## Partire

```bash
brew tap swellweb/reame && brew install reame
reame run qwen2.5-1.5b            # scarica e chatta
reame run qwen2.5-1.5b --serve    # API su :8080
```

```bash
curl http://127.0.0.1:8080/v1/chat/completions -d '{
  "model": "reame",
  "messages": [{"role": "user", "content": "Ciao!"}]
}'
```

Per il resto (build da sorgente, file di config, la staffetta
`[escalation]` verso il modello grande, l'endpoint `/v1/warm`) c'è il
[README inglese](../README.md), che è quello di riferimento.

## I numeri

Sono tutti misurati, quasi tutti sulla macchina Oracle gratuita, e in
[BENCHMARKS.md](BENCHMARKS.md) c'è il metodo di ciascuno. Ci sono anche i
fallimenti: le idee che abbiamo costruito, misurato e buttato via, coi
numeri del perché. Su CPU sapere cosa NON funziona vale quanto sapere cosa
funziona.

| | |
|---|---|
| nucleo vs llama.cpp, stesso modello 0.5B | 35,4 contro 27,2 tok/s |
| RAM all'avvio | 99 MB |
| domanda su documento già scaldato | 3,2 s (era 59) |
| richiesta identica ripetuta | 0,5 s |

## Licenza

[MIT](../LICENSE). La parte dei modelli grandi poggia su
[llama.cpp](https://github.com/ggml-org/llama.cpp), che è un gran pezzo di
ingegneria. Nucleo è nostro, verificato token per token contro
un'implementazione di riferimento scritta apposta per non fidarci di noi
stessi.
