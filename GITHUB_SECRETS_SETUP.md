# ⚙️ Configurazione GitHub Secrets - Supabase Keep Alive

## Problema Ricorrente
Il workflow **Supabase Keep Alive** fallisce regolarmente perché i GitHub Secrets non sono configurati o spariscono.

## Soluzione: Configurare i Secrets su GitHub

### Passo 1: Accedi a GitHub
1. Vai a: https://github.com/hobbyimprenditore/Analizzaste/settings/secrets/actions
2. Accedi al tuo account GitHub se richiesto

### Passo 2: Aggiungi il primo secret
1. Clicca il pulsante **"New repository secret"**
2. Compila i campi:
   - **Name**: `SUPABASE_URL`
   - **Secret**: `https://hvmnernovucnsksszsbe.supabase.co`
3. Clicca **"Add secret"**

### Passo 3: Aggiungi il secondo secret
1. Clicca il pulsante **"New repository secret"** di nuovo
2. Compila i campi:
   - **Name**: `SUPABASE_SERVICE_ROLE_KEY`
   - **Secret**: Copia il valore dalla tua dashboard Supabase
     - Accedi a: https://app.supabase.com/projects
     - Seleziona il progetto **analizzaste**
     - Vai a **Settings** → **API**
     - Copia il valore di **Service Role secret** (attenzione: non è la chiave pubblica!)
3. Clicca **"Add secret"**

### Passo 4: Verifica il Workflow
1. Vai alla sezione **Actions**: https://github.com/hobbyimprenditore/Analizzaste/actions
2. Seleziona **"Supabase Keep Alive"**
3. Clicca **"Run workflow"** per testare manualmente
4. Il workflow dovrebbe completarsi con ✅ e mostrare: `✅ Keep alive riuscito! Database attivo.`

---

## Perché questo è importante?

Il database Supabase nel piano free-tier viene **sospeso dopo 7 giorni di inattività**. Senza questo workflow:
- Il sito diventerebbe inaccessibile
- I dati sarebbero ancora presenti ma bloccati
- Avresti bisogno di contattare Supabase per ripristinare

Il workflow mantiene il database attivo facendo un semplice "ping" ogni 3 giorni.

---

## Troubleshooting

### Il workflow fallisce ancora dopo aver aggiunto i secrets?
1. **Verifica che i secrets siano visibili**: Vai su https://github.com/hobbyimprenditore/Analizzaste/settings/secrets/actions
   - Dovresti vedere sia `SUPABASE_URL` che `SUPABASE_SERVICE_ROLE_KEY` nella lista
   
2. **Controlla il valore di SUPABASE_SERVICE_ROLE_KEY**:
   - Deve essere il **Service Role secret**, non la chiave pubblica
   - Deve iniziare con `eyJ...` (JWT token)
   - Deve avere circa 350+ caratteri

3. **Leggi i log del workflow**:
   - Vai a Actions → "Supabase Keep Alive"
   - Clicca sull'ultimo run fallito
   - Espandi il job "Ping database Supabase"
   - Leggi l'output per capire l'errore esatto

### Il Secret è sparito da GitHub?
Può accadere se il repository è stato resettato o i secrets sono stati rimossi. Basta rifare i Passi 2-3 di sopra.

---

## Script di Verifica Locale

Se hai `gh` CLI configurato, puoi verificare i secrets direttamente (da fuori questa sessione):

```bash
cd /home/claude/analizzaste
gh secret list
```

Dovresti vedere:
```
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_URL
```

Se la lista è vuota, i secrets non sono configurati.

---

## Informazioni di Riferimento

| Parametro | Valore | Fonte |
|-----------|--------|-------|
| **SUPABASE_URL** | `https://hvmnernovucnsksszsbe.supabase.co` | Documentazione progetto |
| **SUPABASE_SERVICE_ROLE_KEY** | `eyJ...` | Supabase Dashboard → Settings → API → Service Role secret |
| **Workflow Schedule** | Ogni 3 giorni alle 08:00 UTC (10:00 Italia) | `.github/workflows/keepalive.yml` |
| **Endpoint Test** | `/rest/v1/reports?select=id&limit=1` | Keep Alive Workflow |

---

**Ultimo aggiornamento**: 13 ottobre 2026  
**Status**: ⏳ In attesa di configurazione manuale dei secrets
