# 📊 Analizzaste.it

Piattaforma di analisi e monitoraggio dati.

---

## ⚡ Quick Start

### 1. Verifica GitHub Secrets (IMPORTANTE!)

Se il workflow "Supabase Keep Alive" continua a fallire:

```bash
./check-supabase-setup.sh
```

Questo script verifica se tutto è configurato correttamente.

**Se vedi ❌**: Segui le istruzioni in [`GITHUB_SECRETS_SETUP.md`](./GITHUB_SECRETS_SETUP.md)

### 2. Configurazione iniziale

```bash
# Clone e setup
git clone https://github.com/hobbyimprenditore/Analizzaste.git
cd Analizzaste

# Installa dipendenze (se applicabile)
npm install  # o pip install -r requirements.txt, ecc.
```

---

## 🔄 GitHub Actions Workflows

### Supabase Keep Alive

**Purpose**: Mantiene il database Supabase attivo (free-tier si sospende dopo 7 giorni di inattività)

**Schedule**: Ogni 3 giorni alle 08:00 UTC (10:00 Italia)

**Status**: ⏳ In attesa di configurazione secrets su GitHub

**Setup richiesto**:
1. Vai a: https://github.com/hobbyimprenditore/Analizzaste/settings/secrets/actions
2. Aggiungi 2 secrets:
   - `SUPABASE_URL`: `https://hvmnernovucnsksszsbe.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY`: (dal tuo Supabase Dashboard)

**Documentazione completa**: [`GITHUB_SECRETS_SETUP.md`](./GITHUB_SECRETS_SETUP.md)

---

## 📁 Struttura Progetto

```
Analizzaste/
├── .github/
│   └── workflows/
│       └── keepalive.yml          # Supabase Keep Alive workflow
├── GITHUB_SECRETS_SETUP.md         # 📖 Guida configurazione secrets
├── check-supabase-setup.sh         # 🔍 Script di verifica
├── SECRETS_SETUP_STATUS.md         # Status storico
└── README.md                        # Questo file
```

---

## 🐛 Troubleshooting

### Il workflow fallisce con errore "secrets not configured"

**Soluzione**: Vedi [`GITHUB_SECRETS_SETUP.md`](./GITHUB_SECRETS_SETUP.md), Passo 2-3

### Il database è sospeso

1. Configura i GitHub Secrets (vedi sopra)
2. Il workflow riattiva il database automaticamente
3. Se è già sospeso, contatta Supabase Support per ripristino manuale

### Come testare il workflow manualmente

1. Vai a: https://github.com/hobbyimprenditore/Analizzaste/actions
2. Clicca "Supabase Keep Alive"
3. Clicca "Run workflow" → "Run workflow"

---

## 📚 Documentazione Aggiuntiva

- **[GITHUB_SECRETS_SETUP.md](./GITHUB_SECRETS_SETUP.md)** - Guida completa configurazione secrets
- **[SECRETS_SETUP_STATUS.md](./SECRETS_SETUP_STATUS.md)** - Status storico problemi
- **[privacy-policy-analizzaste.md](./privacy-policy-analizzaste.md)** - Privacy policy GDPR

---

## 📧 Supporto

Se il problema persiste:
1. Leggi [`GITHUB_SECRETS_SETUP.md`](./GITHUB_SECRETS_SETUP.md) completamente
2. Esegui `./check-supabase-setup.sh` e condividi l'output
3. Controlla i log del workflow: https://github.com/hobbyimprenditore/Analizzaste/actions

---

**Ultimo aggiornamento**: 13 ottobre 2026  
**Versione**: 2.0
