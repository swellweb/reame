"""The real bi-encoder behind IndiceParafrasi: multilingual-e5-small.

Mean pooling over the last hidden state (mask-aware), L2-normalised, exactly
as the model card prescribes. Kept apart from fusione.py so everything else
stays testable without torch.
"""
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

MODELLO = "intfloat/multilingual-e5-small"


def carica_encoder():
    tok = AutoTokenizer.from_pretrained(MODELLO)
    modello = AutoModel.from_pretrained(MODELLO)
    modello.eval()

    @torch.no_grad()
    def encode(testi, lotto=64):
        vettori = []
        for da in range(0, len(testi), lotto):
            pezzo = tok(testi[da:da + lotto], padding=True, truncation=True,
                        max_length=128, return_tensors="pt")
            uscita = modello(**pezzo).last_hidden_state
            maschera = pezzo["attention_mask"].unsqueeze(-1).float()
            media = (uscita * maschera).sum(1) / maschera.sum(1)
            vettori.append(torch.nn.functional.normalize(media, dim=-1).numpy())
        return np.vstack(vettori).astype(np.float32)

    return encode
