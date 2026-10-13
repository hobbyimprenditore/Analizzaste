#!/bin/bash

# 🔍 Script di verifica Supabase Keep Alive Setup
# Questo script verifica se tutto è configurato correttamente

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Verifica Setup Supabase Keep Alive"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════
# 1. Verifica file workflow
# ═══════════════════════════════════════════════════════════════
echo -e "${BLUE}1️⃣  Verifica file Workflow${NC}"
echo "─────────────────────────────────────────"

WORKFLOW_FILE=".github/workflows/keepalive.yml"

if [ -f "$WORKFLOW_FILE" ]; then
    echo -e "${GREEN}✅ File workflow trovato${NC}: $WORKFLOW_FILE"

    # Verifica se il file ha la struttura corretta
    if grep -q "secrets.SUPABASE_URL" "$WORKFLOW_FILE" && \
       grep -q "secrets.SUPABASE_SERVICE_ROLE_KEY" "$WORKFLOW_FILE"; then
        echo -e "${GREEN}✅ Workflow ha la struttura corretta${NC}"
    else
        echo -e "${RED}❌ Workflow non contiene i references ai secrets${NC}"
    fi
else
    echo -e "${RED}❌ File workflow NON trovato${NC}: $WORKFLOW_FILE"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 2. Verifica Supabase URL
# ═══════════════════════════════════════════════════════════════
echo -e "${BLUE}2️⃣  Verifica Supabase URL${NC}"
echo "─────────────────────────────────────────"

EXPECTED_URL="https://hvmnernovucnsksszsbe.supabase.co"
echo -e "URL atteso: ${YELLOW}$EXPECTED_URL${NC}"
echo ""

# Prova a fare una richiesta di test (senza auth)
echo "Tentativo di ping al server Supabase..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$EXPECTED_URL/rest/v1/")

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✅ Server Supabase raggiungibile${NC} (HTTP $HTTP_CODE - unauthorized, come atteso)"
elif [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Server Supabase raggiungibile${NC} (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}❌ Server Supabase NON raggiungibile${NC} (timeout o errore di connessione)"
else
    echo -e "${YELLOW}⚠️  Server Supabase ha risposto con HTTP $HTTP_CODE${NC}"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 3. Verifica GitHub CLI
# ═══════════════════════════════════════════════════════════════
echo -e "${BLUE}3️⃣  Verifica GitHub CLI${NC}"
echo "─────────────────────────────────────────"

if command -v gh &> /dev/null; then
    echo -e "${GREEN}✅ GitHub CLI (gh) installato${NC}"

    # Verifica se l'utente è autenticato
    if gh auth status &> /dev/null; then
        echo -e "${GREEN}✅ GitHub CLI autenticato${NC}"

        # Prova a listare i secrets (potrebbe fallire per proxy)
        echo ""
        echo "Tentativo di verificare i secrets su GitHub..."
        echo "(Questo potrebbe fallire se il proxy blocca l'API)"
        echo ""

        if gh secret list 2>&1 | grep -q "SUPABASE"; then
            echo -e "${GREEN}✅ I secrets sono configurati su GitHub${NC}"
            echo ""
            gh secret list
        else
            RESULT=$(gh secret list 2>&1)
            if echo "$RESULT" | grep -q "403\|Access to this"; then
                echo -e "${YELLOW}⚠️  Impossibile verificare via CLI (proxy blocca l'API)${NC}"
                echo "Verifica manualmente su: https://github.com/hobbyimprenditore/Analizzaste/settings/secrets/actions"
            else
                echo -e "${RED}❌ I secrets NON sono configurati su GitHub${NC}"
                echo ""
                echo "Azione richiesta:"
                echo "1. Vai a: https://github.com/hobbyimprenditore/Analizzaste/settings/secrets/actions"
                echo "2. Aggiungi SUPABASE_URL: $EXPECTED_URL"
                echo "3. Aggiungi SUPABASE_SERVICE_ROLE_KEY: (il tuo service role key di Supabase)"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  GitHub CLI NON autenticato${NC}"
        echo "Esegui: gh auth login"
    fi
else
    echo -e "${YELLOW}ℹ️  GitHub CLI (gh) NON installato${NC}"
    echo "Per verificare i secrets via CLI, installa: https://cli.github.com"
    echo "Oppure verifica manualmente su:"
    echo "https://github.com/hobbyimprenditore/Analizzaste/settings/secrets/actions"
fi
echo ""

# ═══════════════════════════════════════════════════════════════
# 4. Riepilogo e istruzioni
# ═══════════════════════════════════════════════════════════════
echo -e "${BLUE}4️⃣  Riepilogo${NC}"
echo "─────────────────────────────────────────"
echo ""
echo "Se vedi ❌ nelle sezioni sopra, segui:"
echo "📖 GITHUB_SECRETS_SETUP.md (nella root del progetto)"
echo ""
echo "Se vedi ✅ in tutte le sezioni, il setup è corretto."
echo ""
echo "Per testare il workflow manualmente:"
echo "👉 https://github.com/hobbyimprenditore/Analizzaste/actions"
echo "   → Supabase Keep Alive → Run workflow"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
